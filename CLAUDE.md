# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repo contains **two coexisting applications**:
1. **BuildSmart** — original Flask app (document vault for construction projects)
2. **BuildIQ** — FastAPI compliance advisor built on top, for Tamil Nadu building plan compliance (TNCDBR 2019 rules)

Do not modify Flask files unless explicitly asked. The FastAPI backend (`backend/`) is the active development target.

## Running the Applications

**FastAPI backend (BuildIQ):**
```bash
# From repo root (package-relative imports require this)
python -m uvicorn backend.main:app --reload --port 8000
```

**Flask app (BuildSmart, legacy):**
```bash
python app.py
```

**React frontend:**
```bash
cd frontend
npm start   # dev server on port 3000
npm run build
npm test
```

**Static HTML dashboard** (no build needed):
Open `frontend/public/buidq_dashboard.html` directly in a browser. It calls the FastAPI backend at `http://localhost:8000`.

## RAG Database Setup

The SQLite RAG database (`backend/db/buildiq.db`) must be initialized before the `/api/explain-rule` route works:
```bash
python -m backend.init_rag_db   # create tables
python -m backend.ingest        # ingest regulation markdown → 98 chunks
```

Always run backend scripts as modules (`python -m backend.X`) — never as `python backend/X.py` — due to package-relative imports.

## Architecture

### Two-Database Pattern
- `backend/db/buildiq.db` — SQLite used for: (1) user auth (`users` table via SQLAlchemy), (2) compliance audit log (`compliance_log`), (3) RAG chunks (`regulation_chunks`, `ingestion_log`)
- `database.db` / `buildiq.db` (root) — legacy Flask SQLite databases, ignore

### Compliance Pipeline
Request → `POST /api/check-compliance` → `ComplianceChecker.run_full_check()` → fuzzy logic scoring → optional Claude Haiku explanation (if `ANTHROPIC_API_KEY` set) → SQLite log

`backend/compliance.py` uses pure-Python fuzzy membership functions (no scikit-fuzzy). Rules are loaded from `backend/config/rules.json` at instantiation with hardcoded fallbacks. The four checks (setback, FAR, coverage, height) are weighted: `setback×0.35 + far×0.30 + coverage×0.20 + height×0.15`.

### RAG Pipeline
`backend/regulations/*.md` → `backend/ingest.py` (paragraph chunking, 150 words, 20 overlap) → `backend/db/buildiq.db:regulation_chunks` → `backend/rag.py` (BM25-inspired scoring + category keyword filter) → `backend/llm.py` (Claude Haiku with retrieved context) → response with citation objects

Each regulation file has YAML frontmatter (`rule_id`, `go_number`, `category`, `authority`, `confidence`). The 7 categories mapped to DOMAIN_KEYWORDS in `rag.py` are: `setback`, `far`, `height`, `coverage`, `documents`, `parking`, `jurisdiction`.

### Auth Flow
Both apps use the same `users` table schema. FastAPI auth (`backend/routers/auth.py`) uses PyJWT + httponly cookies (12h expiry). The `get_current_user` dependency is in `backend/core/security.py`. Rate limiting is via slowapi; the shared `Limiter` instance lives in `backend/core/limiter.py` to avoid circular imports.

### Config
All secrets flow through `backend/config.py` which reads from `.env`. Never use inline `os.environ.get()` in backend modules — import from `backend.config` instead.

## Key Constraints

- `zone_type` must be one of: `residential_R1`, `residential_R2`, `commercial_C1`
- `road_width_ft` must be one of: 10, 12, 15, 20, 24, 30, 40
- Height cap is 14m (non-highrise), per G.O.Ms.No.70, HUD, 11-03-2024
- The `/api/explain-rule` endpoint is rate-limited to 10/hour per IP

## Frontend Notes

The React app (`frontend/src/`) uses Tailwind v3 (not v4 — `package.json` lists `tailwindcss@^3`). The static dashboard (`frontend/public/buidq_dashboard.html`) is standalone and does not use React. All React API calls go through `frontend/src/api.js` (axios, base URL `http://localhost:8000`).
