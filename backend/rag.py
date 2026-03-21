import sqlite3
import re
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "db" / "buildiq.db"


class RegulatoryRAG:

    DOMAIN_KEYWORDS = {
        "setback": ["setback", "front", "rear", "side", "boundary", "open space"],
        "far": ["far", "fsi", "floor space", "floor area ratio", "built-up"],
        "height": ["height", "floors", "storey", "high-rise", "14m", "14 metre"],
        "coverage": ["coverage", "footprint", "ground floor", "percentage"],
        "documents": ["document", "patta", "ec", "fmb", "sale deed", "chitta",
                      "encumbrance", "architect certificate"],
        "parking": ["parking", "car park", "vehicle", "space"],
        "jurisdiction": ["ccmc", "dtcp", "lpa", "authority", "corporation"],
    }

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def _detect_category(self, query: str) -> Optional[str]:
        query_lower = query.lower()
        best_cat = None
        best_score = 0
        for cat, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > best_score:
                best_score = score
                best_cat = cat
        return best_cat if best_score > 0 else None

    def _bm25_score(self, query: str, text: str) -> float:
        """BM25-inspired keyword scoring."""
        query_terms = re.findall(r'\b\w+\b', query.lower())
        text_lower = text.lower()
        text_words = re.findall(r'\b\w+\b', text_lower)
        text_len = len(text_words)
        avg_len = 100  # approximate average chunk length

        k1 = 1.5
        b = 0.75
        score = 0.0

        for term in set(query_terms):
            tf = text_words.count(term)
            if tf == 0:
                continue
            idf = 1.0  # simplified — all docs treated equally
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * text_len / avg_len))
            score += idf * tf_norm

        # Exact phrase bonus
        if query.lower() in text_lower:
            score *= 2.0

        # Number match bonus (road widths, dimensions)
        query_nums = re.findall(r'\d+\.?\d*', query)
        text_nums = re.findall(r'\d+\.?\d*', text)
        matching_nums = set(query_nums) & set(text_nums)
        score += len(matching_nums) * 0.5

        return round(score, 4)

    def retrieve(self, query: str, top_k: int = 3,
                 category_filter: Optional[str] = None) -> list:

        detected_cat = category_filter or self._detect_category(query)

        rows = []
        if detected_cat:
            rows = self.conn.execute(
                "SELECT * FROM regulation_chunks WHERE category = ?",
                (detected_cat,)
            ).fetchall()

        # Fall back to full scan if category filter yields nothing
        if not rows:
            rows = self.conn.execute("SELECT * FROM regulation_chunks").fetchall()

        scored = []
        for row in rows:
            score = self._bm25_score(query, row["text"])
            if score > 0:
                scored.append({
                    "chunk_id": row["chunk_id"],
                    "text": row["text"],
                    "source_file": row["source_file"],
                    "rule_id": row["rule_id"],
                    "go_number": row["go_number"],
                    "verified_date": row["verified_date"],
                    "authority": row["authority"],
                    "category": row["category"],
                    "page_number": row["page_number"],
                    "char_start": row["char_start"],
                    "char_end": row["char_end"],
                    "confidence": row["confidence"],
                    "relevance_score": score,
                })

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_k]

    def query(self, question: str, jurisdiction: str = "CCMC") -> dict:
        results = self.retrieve(question, top_k=3)

        if not results:
            return {
                "found": False,
                "context": "",
                "citations": [],
                "confidence": "LOW",
                "message": f"No specific rule found. Verify with {jurisdiction}.",
            }

        context = "\n\n".join([r["text"] for r in results])

        citations = [
            {
                "chunk_id": r["chunk_id"],
                "rule_id": r["rule_id"],
                "go_number": r["go_number"],
                "verified_date": r["verified_date"],
                "page_number": r["page_number"],
                "source_file": r["source_file"],
                "relevance_score": r["relevance_score"],
                "preview": r["text"][:120] + "..." if len(r["text"]) > 120 else r["text"],
                "highlight_text": r["text"][:80],
                "text": r["text"],
                "chunk_type": "pdf" if r["source_file"].lower().endswith(".pdf") else "md",
            }
            for r in results
        ]

        top_score = results[0]["relevance_score"]
        top_conf = results[0]["confidence"]

        if top_score >= 2.0 and top_conf == "HIGH":
            confidence = "HIGH"
        elif top_score >= 0.5:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return {
            "found": True,
            "context": context,
            "citations": citations,
            "confidence": confidence,
            "top_relevance": top_score,
        }


_rag = None


def get_rag() -> RegulatoryRAG:
    global _rag
    if _rag is None:
        _rag = RegulatoryRAG()
    return _rag
