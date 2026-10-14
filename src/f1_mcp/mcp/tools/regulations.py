"""Tool for searching the FIA Sporting Regulations (hybrid retrieval over a Chroma index)."""

import asyncio

from f1_mcp import regulations
from f1_mcp.mcp.server import mcp_server

# Calibrated on evals/regulations.jsonl: every answerable question has a top-1 cosine
# similarity of at least 0.48, so 0.45 only rejects queries the corpus cannot answer.
MIN_SIMILARITY = 0.45


@mcp_server.tool()
async def search_regulations(query: str, k: int = 5) -> str:
    """Searches the 2026 FIA F1 Sporting Regulations (Section B: race weekend format,
    procedures, Safety Car, penalties, tyres, parc fermé, power unit limits...) and returns
    the most relevant articles with their number (e.g. B5.13.2), so you can cite the rule
    behind an event. It does NOT cover championship points, technical specs (car weight,
    dimensions) or financial rules (budget cap): say so instead of guessing.
    `query` must be in English (translate the user's question first); describe the
    situation or rule, e.g. 'driver overtakes under Safety Car'. `k` is how many
    articles to return (1-10). Similarity goes from 0 to 1; below ~0.55 the match is
    uncertain, so check that the article really answers the question. Quote the article
    text; do not invent rules."""
    query = query.strip()
    if not query:
        return "Empty query: describe the rule or situation to search for."
    k = max(1, min(k, 10))
    try:
        hits = await asyncio.to_thread(regulations.search, query, k, "hybrid", MIN_SIMILARITY)
    except regulations.IndexNotBuiltError:
        return "The regulations index is not built on this server (run f1-mcp-build-index)."
    if not hits:
        return (
            "No article of the Sporting Regulations (Section B) matches this query. "
            "It may be covered by another section of the FIA regulations that is not "
            "indexed here; do not answer from memory as if it were a rule."
        )
    return "\n\n".join(f"[{h.ref}] {h.title} (similarity {h.similarity})\n{h.text}" for h in hits)
