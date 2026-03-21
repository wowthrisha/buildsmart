import anthropic
from backend.config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def explain_compliance_result(results: list, language: str = "en") -> str:
    """Takes compliance check results and generates plain language explanation"""

    results_text = "\n".join([
        f"- {r['rule_name']}: {r['status']} | Provided: {r['provided_value']} | Required: {r['required_value']} | {r['fix_suggestion']}"
        for r in results
    ])

    system_prompt = """You are BuildIQ, a building plan compliance advisor
    for Tamil Nadu, India. You help building owners understand why their
    plans fail TNCDBR 2019 rules in plain simple language.
    Be concise, practical, and cite the specific rule.
    If language is 'ta', respond entirely in Tamil.
    Never say the plan will definitely pass - always recommend
    consulting a licensed architect."""

    user_prompt = f"""These are compliance check results for a building plan in Coimbatore:

{results_text}

Give a plain language summary of:
1. What the main problems are
2. The most important fix the owner should make first
3. Approximate cost impact if they fix it

Language: {language}
Keep response under 150 words."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    return message.content[0].text


def answer_rule_question(question: str, jurisdiction: str,
                          language: str = "en") -> dict:
    """Answers a plain language question about TNCDBR rules using RAG retrieval."""
    from backend.rag import get_rag
    rag = get_rag()
    rag_result = rag.query(question, jurisdiction)

    context = rag_result.get("context", "No specific rule found.")

    system_prompt = """You are BuildIQ, a building regulations advisor
    for Tamil Nadu India. Answer ONLY using the provided context.
    If context does not answer the question say exactly:
    'This requires verification with the relevant authority.'
    Never guess. Always be concise. Under 120 words.
    If language is 'ta' respond entirely in Tamil."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": f"Context from TNCDBR 2019:\n{context}\n\nQuestion: {question}\nJurisdiction: {jurisdiction}\nLanguage: {language}"
        }]
    )

    citations = rag_result.get("citations", [])
    sources = [
        {
            "text": c["text"][:300] + ("..." if len(c["text"]) > 300 else ""),
            "source": c["source_file"],
            "page_number": c["page_number"] if c.get("chunk_type") == "pdf" else None,
            "chunk_type": c.get("chunk_type", "md"),
        }
        for c in citations
    ]

    return {
        "answer": message.content[0].text,
        "citations": citations,
        "sources": sources,
        "confidence": rag_result.get("confidence", "MEDIUM"),
        "verified_date": "2026-03-20",
        "rag_found": rag_result.get("found", False),
        "disclaimer": "AI guidance based on TNCDBR 2019. Verify with licensed architect."
    }
