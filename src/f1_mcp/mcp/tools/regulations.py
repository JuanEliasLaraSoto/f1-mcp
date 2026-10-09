"""Tool for searching the FIA Sporting Regulations (retrieval over a Chroma index)."""

import asyncio

from f1_mcp import regulations
from f1_mcp.mcp.server import mcp_server


@mcp_server.tool()
async def search_regulations(query: str, k: int = 5) -> str:
    """Searches the 2026 FIA F1 Sporting Regulations and returns the most relevant
    articles with their number (e.g. B5.13.2), so you can cite the rule behind an event:
    a penalty, a Safety Car, track limits, parc fermé, tyre rules, points...
    `query` must be in English (translate the user's question first); describe the
    situation or rule, e.g. 'driver overtakes under Safety Car'. `k` is how many
    articles to return (1-10). Similarity goes from 0 to 1: below ~0.3 the article is
    probably not relevant. Quote the article text; do not invent rules."""
    query = query.strip()
    if not query:
        return "Empty query: describe the rule or situation to search for."
    k = max(1, min(k, 10))
    try:
        hits = await asyncio.to_thread(regulations.search, query, k)
    except regulations.IndexNotBuiltError:
        return "The regulations index is not built on this server (run f1-mcp-build-index)."
    if not hits:
        return "The regulations index is empty."
    return "\n\n".join(f"[{h.ref}] {h.title} (similarity {h.similarity})\n{h.text}" for h in hits)
