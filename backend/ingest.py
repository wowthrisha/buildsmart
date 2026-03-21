import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "db" / "buildiq.db"
REGS_DIR = Path(__file__).parent / "regulations"


def parse_frontmatter(content: str) -> tuple:
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = parts[2].strip()
    return meta, body


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def generate_chunk_id(source: str, index: int) -> str:
    raw = f"{source}_{index}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def extract_pdf_chunks(pdf_path: Path) -> list:
    """
    Opens a PDF with pdfplumber and returns a list of chunk dicts,
    one per page (skipping pages with < 50 chars of text).

    Each dict:
        content     — extracted page text
        source      — filename (e.g. TNCDBR_2019_base.pdf)
        page_number — 1-based page number
        chunk_type  — "pdf"
        chunk_name  — stem + "_page_" + page_number
    """
    import pdfplumber

    chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if len(text) < 50:
                continue  # skip blank/image-only pages
            chunks.append({
                "content": text,
                "source": pdf_path.name,
                "page_number": page_num,
                "chunk_type": "pdf",
                "chunk_name": f"{pdf_path.stem}_page_{page_num}",
            })
    return chunks


def ingest_markdown_files(conn):
    c = conn.cursor()
    total_chunks = 0

    for md_file in sorted(REGS_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)

        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

        chunk_index = 0
        char_pos = 0

        for para in paragraphs:
            sub_chunks = chunk_text(para, chunk_size=150, overlap=20)

            for sub_chunk in sub_chunks:
                chunk_id = generate_chunk_id(md_file.stem, chunk_index)

                # Simulate page number from chunk position
                # (Real PDF ingestion has actual page numbers)
                estimated_page = (chunk_index // 8) + 1

                c.execute("""
                INSERT OR REPLACE INTO regulation_chunks
                (chunk_id, source_file, rule_id, go_number, verified_date,
                 authority, category, page_number, chunk_index, text,
                 char_start, char_end, word_count, confidence)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    chunk_id,
                    md_file.name,
                    meta.get("rule_id", "TNCDBR-2019"),
                    meta.get("go_number", "G.O.Ms.No.18"),
                    meta.get("verified_date", "2026-03-20"),
                    meta.get("authority", "CCMC"),
                    meta.get("category", "general"),
                    estimated_page,
                    chunk_index,
                    sub_chunk,
                    char_pos,
                    char_pos + len(sub_chunk),
                    len(sub_chunk.split()),
                    meta.get("confidence", "HIGH"),
                ))

                char_pos += len(sub_chunk) + 1
                chunk_index += 1
                total_chunks += 1

        print(f"  [md]  {md_file.name}: {chunk_index} chunks")

    return total_chunks


def ingest_pdf_files(conn):
    c = conn.cursor()
    total_chunks = 0

    for pdf_file in sorted(REGS_DIR.glob("*.pdf")):
        chunks = extract_pdf_chunks(pdf_file)
        file_chunks = 0

        for i, ch in enumerate(chunks):
            chunk_id = generate_chunk_id(ch["chunk_name"], i)

            c.execute("""
            INSERT OR REPLACE INTO regulation_chunks
            (chunk_id, source_file, rule_id, go_number, verified_date,
             authority, category, page_number, chunk_index, text,
             char_start, char_end, word_count, confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                chunk_id,
                ch["source"],
                "TNCDBR-2019",
                "G.O.Ms.No.18",
                datetime.now().strftime("%Y-%m-%d"),
                "CCMC",
                "general",
                ch["page_number"],
                i,
                ch["content"],
                0,
                len(ch["content"]),
                len(ch["content"].split()),
                "HIGH",
            ))

            file_chunks += 1
            total_chunks += 1

        print(f"  [pdf] {pdf_file.name}: {file_chunks} chunks")

    return total_chunks


def ingest_all():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Clear existing chunks for a clean re-ingest
    c.execute("DELETE FROM regulation_chunks")
    conn.commit()

    print("── Markdown files ──────────────────────")
    md_total = ingest_markdown_files(conn)

    print("── PDF files ───────────────────────────")
    pdf_total = ingest_pdf_files(conn)

    grand_total = md_total + pdf_total

    # Log ingestion
    c.execute("""
    INSERT INTO ingestion_log (source_file, chunks_created, ingested_at, status)
    VALUES (?,?,?,?)
    """, ("all_regulations", grand_total, datetime.now().isoformat(), "success"))

    conn.commit()
    conn.close()

    print("────────────────────────────────────────")
    print(f"  Markdown chunks : {md_total}")
    print(f"  PDF chunks      : {pdf_total}")
    print(f"  Total chunks    : {grand_total}")
    return grand_total


if __name__ == "__main__":
    from backend.init_rag_db import init_rag_tables
    init_rag_tables()
    ingest_all()
