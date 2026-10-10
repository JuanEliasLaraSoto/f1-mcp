# Spec: regulations search (RAG)

## Goal
Let the model answer "why" questions about a session by citing the FIA rule behind it.
OpenF1 says *what* happened (a penalty, a Safety Car, a pit-lane infringement); the
regulations say *which rule* applies. A new tool retrieves the relevant articles of the
2026 FIA F1 Sporting Regulations so the model can quote them instead of guessing.

## Scope
- Corpus: Section B [Sporting], Issue 09 (2026-10-01). Technical/Financial later.
- Retrieval only: the tool returns articles; the MCP client's model writes the answer.
  No LLM call inside the server.

## Pipeline (offline)
1. `scripts/extract_regulations.py`: extract text lines from the PDF with PyMuPDF.
2. Clean: drop the page header block (section name, page number `B47`, issue, date) and
   governance boilerplate. Skip the table of contents (the body starts at the second
   `ARTICLE B1:`) and everything from Appendix B3 on (admin forms, and Appendix B5 with
   the 2027 changes, which reuses 2026 article numbers with different text).
3. Chunk by article number, not by fixed size. Numbers sit alone on their line
   (`B5.13.4`), optionally followed by a Title Case heading (`Order of Cars Behind the SC`);
   a line that starts with a number followed by text is a wrapped cross-reference and stays
   in the body. Each chunk keeps its citation (`ref`) and the heading path as title
   (`Safety Car (SC) > Order of Cars Behind the SC`). Appendix B1 gives one chunk per
   definition, Appendix B2 one per parc fermé group.
4. Split chunks longer than 1,000 characters on sentence boundaries (ids `B5.13.2#1`,
   `#2`...): all-MiniLM-L6-v2 only reads ~256 word pieces and ignores the rest.
5. `f1-mcp-build-index`: embed `"{title}\n{text}"` with Chroma's default model
   (all-MiniLM-L6-v2, ONNX, CPU) and store in a persistent Chroma collection `regulations`
   (cosine distance). The collection is rebuilt from scratch on each run.

## Tool
`search_regulations(query: str, k: int = 5) -> str`
- `query`: the question or topic **in English** (the corpus and the embedding model are
  English); the docstring tells the model to translate first.
- `k`: number of articles, 1–10.
- Output: one block per chunk: `[B5.13.2] Safety Car (SC) > During a SC Deployment
  (similarity 0.71)` + text,
  ordered by similarity. Readable text, like every other tool.

## Edge cases
- Index missing or empty → readable message ("regulations index not built"), no traceback.
- `k` outside 1–10 → clamped.
- Empty query → readable message, no search.
- Nothing relevant → below the calibrated similarity threshold the tool says no article
  matches (see `specs/regulations-eval.md`).
- The FIA PDF repeats a number (two `B1.5.11` in Issue 09) → unique ids (`B1.5.11~2`),
  same citation.

## Decisions to defend
- Chroma over a plain NumPy array: a real vector store with persistence and metadata,
  enough for a few hundred chunks; the trade-off is a heavier dependency
  (onnxruntime and friends, a few hundred MB in the image).
- Article-level chunking: the regulations are already split into self-contained,
  numbered units, and that number is the citation.
- Local embeddings: no API key, no per-query cost, works offline on the VPS.
- Retrieval-only tool: the client model already writes the answer; generating inside the
  server would add an API key, cost and a second model.

## Deployment
The chunks are committed as `data/regulations_chunks.json` (small, diffable when the FIA
publishes a new issue). `docker build` runs `f1-mcp-build-index`, which creates the
Chroma index and bakes the embedding model into the image. Rejected: downloading the PDF
during the build (deploys depend on fia.com) and committing the binary `data/chroma/`.

## Acceptance
- Unit tests for chunking on lines copied from the real PDF layout (header block, TOC,
  page break mid-sentence, wrapped cross-reference, appendices, 2027 changes dropped).
- Tool test against an in-memory Chroma collection with a fake embedding function
  (no model download, no network in CI).
- Missing-index test returns the readable message.
- Manual: `try_client.py search_regulations '{"query": "safety car deployment"}'` returns
  the Safety Car article first.
- Coverage stays >= 80%, ruff and strict mypy pass.
