import base64
import io
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic as _anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.compliance import ComplianceChecker
from backend.config import ANTHROPIC_API_KEY
from backend.package_generator import generate_submission_package
from backend.core.limiter import limiter
from backend.database import Base, engine
from backend.dependencies import require_auth
from backend.llm import explain_compliance_result, answer_rule_question
from backend.models.user import User
from backend.routers import auth

load_dotenv()

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BuildIQ API",
    description="Tamil Nadu building plan compliance advisor",
    version="1.0.0",
)

# ── Rate limiting ─────────────────────────────────────────────────────────────

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────

_origins = [
    "http://localhost:3000",
    "http://localhost:5001",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5001",
    os.getenv("FRONTEND_URL", "https://buildiq.vercel.app"),
    os.getenv("FRONTEND_URL_2", ""),
]
# Drop empty strings that come from unset env vars
_origins = [o for o in _origins if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── SQLite log DB path ────────────────────────────────────────────────────────

_DB_DIR = os.path.join(os.path.dirname(__file__), "db")
_LOG_DB = os.path.join(_DB_DIR, "buildiq.db")


def _get_log_conn():
    os.makedirs(_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_LOG_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS compliance_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT,
            timestamp     TEXT,
            road_width_ft INTEGER,
            overall_status TEXT,
            results_json  TEXT
        )
        """
    )
    conn.commit()
    return conn


def get_db():
    """Return a sqlite3 connection to the main DB with Row factory."""
    os.makedirs(_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_LOG_DB)
    conn.row_factory = sqlite3.Row
    return conn


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router)

# ── Request models ────────────────────────────────────────────────────────────

class ComplianceRequest(BaseModel):
    road_width_ft: int
    provided_front_m: float
    provided_rear_m: float
    provided_side_m: float
    plot_area_sqm: float
    proposed_builtup_sqm: float
    footprint_sqm: float
    proposed_height_m: float
    floors: int
    zone_type: str
    building_type: str
    proposed_spaces: int = 0
    num_units: int = 1
    session_id: Optional[str] = None
    language: str = "en"


class JurisdictionRequest(BaseModel):
    in_city_limits: bool
    plot_area_acres: float
    floors: int
    building_type: str


class FeeRequest(BaseModel):
    authority: str
    building_type: str
    builtup_area_sqm: float


class ExplainRuleRequest(BaseModel):
    question: str
    jurisdiction: str = "CCMC"
    language: str = "en"


# ── Route 1: Health ───────────────────────────────────────────────────────────

def get_chunk_count() -> int:
    try:
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM regulation_chunks").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "rag_chunks": get_chunk_count(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Route 2: Jurisdiction ─────────────────────────────────────────────────────

@app.post("/api/jurisdiction", tags=["compliance"])
@limiter.limit("100/hour")
def jurisdiction(request: Request, body: JurisdictionRequest,
                 user: User = Depends(require_auth)):
    if body.in_city_limits and body.plot_area_acres < 2.47 and body.floors <= 5:
        authority = "CCMC"
        note = "Submit to Coimbatore City Municipal Corporation"
        helpline = "0422-2390261"
        approval_time = "3-7 days"
    elif body.plot_area_acres >= 2.47:
        authority = "DTCP"
        note = "Layout above 2.47 acres requires DTCP approval"
        helpline = "044-29585247"
        approval_time = "4-6 months"
    else:
        authority = "LPA"
        note = "Plot in Local Planning Area - check with DTCP regional office"
        helpline = "044-29585247"
        approval_time = "4-6 months"

    return {
        "authority": authority,
        "note": note,
        "helpline": helpline,
        "approval_time": approval_time,
        "next_step": "Proceed to compliance check",
    }


# ── Route 3: Compliance check ─────────────────────────────────────────────────

@app.post("/api/check-compliance", tags=["compliance"])
@limiter.limit("30/hour")
def check_compliance(request: Request, body: ComplianceRequest,
                     user: User = Depends(require_auth)):
    checker = ComplianceChecker()
    result = checker.run_full_check(body.model_dump())

    # AI explanation — only if API key is configured and check succeeded
    ai_explanation = None
    if ANTHROPIC_API_KEY and not result.get("error") and result.get("results"):
        try:
            ai_explanation = explain_compliance_result(
                result["results"], language=body.language
            )
        except Exception as ai_err:
            print(f"WARNING: AI explanation failed: {ai_err}")
    result["ai_explanation"] = ai_explanation

    session_id = body.session_id or str(uuid.uuid4())
    try:
        conn = _get_log_conn()
        conn.execute(
            """
            INSERT INTO compliance_log
                (session_id, timestamp, road_width_ft, overall_status, results_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                datetime.utcnow().isoformat(),
                body.road_width_ft,
                result.get("overall_status", "ERROR"),
                json.dumps(result.get("results", [])),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as log_err:
        print(f"WARNING: compliance log write failed: {log_err}")

    return result


# ── Route 4: Fee estimate ─────────────────────────────────────────────────────

@app.post("/api/fee-estimate", tags=["compliance"])
@limiter.limit("100/hour")
def fee_estimate(request: Request, body: FeeRequest,
                 user: User = Depends(require_auth)):
    area = body.builtup_area_sqm

    if area <= 150:
        scrutiny_fee = 750
    elif area <= 300:
        scrutiny_fee = 1500
    else:
        scrutiny_fee = 3000

    permit_fee = area * 45
    development_charges = area * 120
    total_govt_fee = scrutiny_fee + permit_fee + development_charges

    return {
        "authority": body.authority,
        "builtup_area_sqm": area,
        "government_fees": {
            "scrutiny_fee_rs": scrutiny_fee,
            "permit_fee_rs": permit_fee,
            "development_charges_rs": development_charges,
            "total_rs": total_govt_fee,
        },
        "agency_fee_benchmark": {
            "min_rs": 15000,
            "max_rs": 40000,
            "note": (
                "Market rate for Coimbatore approval agencies. "
                "Above ₹50,000 for a standard residential plot — seek second opinion."
            ),
        },
        "disclaimer": (
            "Fee estimates are approximate. "
            "Verify current rates with CCMC/DTCP before proceeding."
        ),
    }


# ── Route 5: Explain rule (LLM Q&A) ──────────────────────────────────────────

@app.post("/api/explain-rule", tags=["ai"])
@limiter.limit("50/hour")
def explain_rule(request: Request, body: ExplainRuleRequest,
                 user: User = Depends(require_auth)):
    if not ANTHROPIC_API_KEY:
        return {
            "answer": "AI rule explanation is not configured. Please add a valid ANTHROPIC_API_KEY to .env.",
            "citations": [],
            "confidence": "LOW",
            "rag_found": False,
            "disclaimer": "Configure ANTHROPIC_API_KEY to enable AI-powered rule answers.",
        }
    try:
        result = answer_rule_question(
            question=body.question,
            jurisdiction=body.jurisdiction,
            language=body.language,
        )
        return result
    except Exception as e:
        return {
            "answer": "AI service temporarily unavailable. Please check your API key and try again.",
            "citations": [],
            "confidence": "LOW",
            "rag_found": False,
            "disclaimer": str(e)[:200],
        }


# ── Route 6: Citation lookup ──────────────────────────────────────────────────

@app.get("/api/citation/{chunk_id}", tags=["ai"])
@limiter.limit("100/hour")
def get_citation(request: Request, chunk_id: str,
                 user: User = Depends(require_auth)):
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent / "db" / "buildiq.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM regulation_chunks WHERE chunk_id = ?",
        (chunk_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {"error": "Citation not found"}
    return {
        "chunk_id": chunk_id,
        "text": row["text"],
        "rule_id": row["rule_id"],
        "go_number": row["go_number"],
        "page_number": row["page_number"],
        "source_file": row["source_file"],
        "verified_date": row["verified_date"],
    }


# ── Route 7: Generate submission package ─────────────────────────────────────

class PackageRequest(BaseModel):
    road_width_ft: int
    provided_front_m: float
    provided_rear_m: float
    provided_side_m: float
    plot_area_sqm: float
    proposed_builtup_sqm: float
    footprint_sqm: float
    proposed_height_m: float
    floors: int
    zone_type: str
    building_type: str
    proposed_spaces: int = 1
    num_units: int = 1
    authority: str = "CCMC"
    plot_width_ft: float = 30
    plot_depth_ft: float = 40
    owner_name: str = "Owner"


@app.post("/api/generate-package", tags=["package"])
@limiter.limit("10/hour")
async def generate_package(request: Request, body: PackageRequest,
                           user: User = Depends(require_auth)):
    checker = ComplianceChecker()
    params = body.model_dump()

    compliance_result = checker.run_full_check(params)

    zip_bytes = generate_submission_package(
        compliance_result=compliance_result,
        params=params,
        owner_name=body.owner_name,
    )

    filename = f"BuildIQ_Package_{body.zone_type}_{body.plot_width_ft:.0f}x{body.plot_depth_ft:.0f}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── PDF helpers ───────────────────────────────────────────────────────────────

_REGS_DIR = Path(__file__).parent / "regulations"


def _safe_pdf_path(filename: str) -> Path:
    """Resolve and validate that the path stays inside backend/regulations/."""
    # Reject path traversal attempts
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = (_REGS_DIR / filename).resolve()
    if not path.is_relative_to(_REGS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"PDF not found: {filename}")
    if path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    return path


# ── Route 8: Serve raw PDF file ───────────────────────────────────────────────

@app.get("/api/pdf/{filename}", tags=["pdf"])
@limiter.limit("100/hour")
async def serve_pdf(request: Request, filename: str,
                    user: User = Depends(require_auth)):
    pdf_path = _safe_pdf_path(filename)
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ── Route 9: PDF text highlight ───────────────────────────────────────────────

@app.get("/api/pdf-highlight", tags=["pdf"])
@limiter.limit("100/hour")
def pdf_highlight(
    request: Request,
    filename: str = Query(..., description="PDF filename inside backend/regulations/"),
    page: int = Query(..., ge=1, description="1-based page number"),
    query: str = Query(..., min_length=1, description="Term to search for"),
    user: User = Depends(require_auth),
):
    import pdfplumber

    pdf_path = _safe_pdf_path(filename)

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        if page > total_pages:
            raise HTTPException(
                status_code=404,
                detail=f"Page {page} does not exist — PDF has {total_pages} pages",
            )
        page_text = pdf.pages[page - 1].extract_text() or ""

    # Count case-insensitive matches
    matches = len(re.findall(re.escape(query), page_text, flags=re.IGNORECASE))

    return {
        "filename": filename,
        "page": page,
        "page_text": page_text,
        "total_pages": total_pages,
        "highlight_term": query,
        "matches": matches,
    }


# ── Route 10: PDF page as base64 PNG ─────────────────────────────────────────

@app.get("/api/pdf-page/{filename}/{page}", tags=["pdf"])
@limiter.limit("100/hour")
def pdf_page_image(request: Request, filename: str, page: int,
                   user: User = Depends(require_auth)):
    import pdfplumber

    if page < 1:
        raise HTTPException(status_code=400, detail="Page number must be >= 1")

    pdf_path = _safe_pdf_path(filename)

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        if page > total_pages:
            raise HTTPException(
                status_code=404,
                detail=f"Page {page} does not exist — PDF has {total_pages} pages",
            )
        img = pdf.pages[page - 1].to_image(resolution=150)
        buf = io.BytesIO()
        img.original.save(buf, format="PNG")
        buf.seek(0)
        image_b64 = base64.b64encode(buf.read()).decode("utf-8")

    return {
        "filename": filename,
        "page": page,
        "total_pages": total_pages,
        "image_base64": image_b64,
    }


# ── Route 11: Marketplace — list architects ───────────────────────────────────

class SubmissionRequest(BaseModel):
    owner_name: str
    owner_phone: str
    architect_id: int
    compliance_status: str = "UNKNOWN"
    plot_details: dict = {}


def send_whatsapp_notification(to: str, message: str):
    wati_token = os.getenv("WATI_API_TOKEN")
    wati_url = os.getenv("WATI_API_URL")
    if not wati_token or not wati_url:
        return
    import httpx
    httpx.post(
        f"{wati_url}/api/v1/sendSessionMessage/{to.replace('+', '')}",
        headers={"Authorization": f"Bearer {wati_token}"},
        json={"messageText": message},
    )


@app.get("/api/architects", tags=["marketplace"])
async def get_architects(req: Request):
    conn = get_db()
    architects = conn.execute(
        "SELECT * FROM architects WHERE active=1 ORDER BY rating DESC"
    ).fetchall()
    conn.close()
    return [dict(a) for a in architects]


@app.post("/api/request-submission", tags=["marketplace"])
@limiter.limit("5/hour")
async def request_submission(
    request: Request,
    body: SubmissionRequest,
    user: User = Depends(require_auth),
):
    conn = get_db()

    architect = conn.execute(
        "SELECT * FROM architects WHERE id=?", (body.architect_id,)
    ).fetchone()

    if not architect:
        conn.close()
        raise HTTPException(status_code=404, detail="Architect not found")

    conn.execute(
        """
        INSERT INTO submissions
            (owner_name, owner_phone, architect_name, architect_phone,
             compliance_status, plot_details, status)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            body.owner_name, body.owner_phone,
            architect["name"], architect["phone"],
            body.compliance_status,
            json.dumps(body.plot_details),
            "pending",
        ),
    )
    conn.commit()
    submission_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    try:
        send_whatsapp_notification(
            to=architect["phone"],
            message=(
                f"New BuildIQ submission request!\n\n"
                f"Owner: {body.owner_name}\n"
                f"Phone: {body.owner_phone}\n"
                f"Compliance: {body.compliance_status}\n"
                f"Submission ID: #{submission_id}\n\n"
                f"Please contact within {architect['response_hours']} hours."
            ),
        )
    except Exception:
        pass

    return {
        "submission_id": submission_id,
        "architect_name": architect["name"],
        "architect_phone": architect["phone"],
        "response_hours": architect["response_hours"],
        "message": (
            f"Request sent to {architect['name']}. "
            f"They will contact you within {architect['response_hours']} hours."
        ),
    }


# ── Route 12: OCR sketch → form values ───────────────────────────────────────

@app.post("/api/ocr-sketch", tags=["ai"])
@limiter.limit("20/hour")
async def ocr_sketch(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_auth),
):
    contents = await file.read()
    base64_image = base64.b64encode(contents).decode("utf-8")

    client = _anthropic.Anthropic()

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file.content_type,
                        "data": base64_image,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "You are analyzing a building plot sketch or floor plan.\n"
                        "Extract these measurements and return ONLY a JSON object with no explanation:\n"
                        "{\n"
                        '  "road_width_ft": <number or null>,\n'
                        '  "plot_width_ft": <number or null>,\n'
                        '  "plot_depth_ft": <number or null>,\n'
                        '  "plot_area_sqm": <number or null>,\n'
                        '  "proposed_builtup_sqm": <number or null>,\n'
                        '  "proposed_height_m": <number or null>,\n'
                        '  "floors": <integer or null>,\n'
                        '  "provided_front_m": <number or null>,\n'
                        '  "provided_rear_m": <number or null>,\n'
                        '  "provided_side_m": <number or null>,\n'
                        '  "confidence": <0.0 to 1.0>,\n'
                        '  "notes": "<what you could and could not read>"\n'
                        "}\n"
                        "If a value is not visible or unclear, use null.\n"
                        "Convert feet to metres where needed (1ft = 0.3048m).\n"
                        "Return only the JSON, nothing else."
                    ),
                },
            ],
        }],
    )

    text = message.content[0].text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    extracted = json.loads(text)
    return extracted


# ── Route 13: Demo OCR — no auth, for Owner portal ───────────────────────────

@app.post("/api/demo-ocr", tags=["ai"])
@limiter.limit("30/hour")
async def demo_ocr(request: Request, file: UploadFile = File(...)):
    """Extract building dimensions from a sketch image. No auth required."""
    from backend.ocr_extractor import extract_dimensions_from_image, generate_smart_questions

    contents = await file.read()
    media_type = file.content_type or "image/jpeg"

    extracted = extract_dimensions_from_image(contents, media_type)

    # Compute plot_area_sqm from width × depth if not already set
    w = extracted.get("plot_width_ft")
    d = extracted.get("plot_depth_ft")
    if w and d and not extracted.get("plot_area_sqm"):
        extracted["plot_area_sqm"] = round(w * d * 0.0929, 1)

    # Rename proposed_floors → floors key expected by compliance payload
    if "proposed_floors" in extracted and "floors" not in extracted:
        extracted["floors"] = extracted["proposed_floors"]

    smart_questions = generate_smart_questions(extracted)

    # Count non-null values (excluding metadata fields)
    meta_keys = {"confidence", "missing_fields", "notes", "error"}
    auto_filled_count = sum(
        1 for k, v in extracted.items()
        if k not in meta_keys and v is not None
    )

    return {
        "extracted": extracted,
        "smart_questions": smart_questions,
        "auto_filled_count": auto_filled_count,
    }


# ── Route 14: Demo compliance check — no auth, for Owner portal ──────────────

@app.post("/api/demo-check", tags=["compliance"])
@limiter.limit("30/hour")
def demo_check(request: Request, body: ComplianceRequest):
    """Run compliance check without auth. For Owner portal demo flow."""
    checker = ComplianceChecker()
    result = checker.run_full_check(body.model_dump())
    return result


if __name__ == "__main__":
    import uvicorn
    from backend.config import DEBUG
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=DEBUG)
