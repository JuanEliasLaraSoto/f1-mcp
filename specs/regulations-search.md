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
1. `scripts/extract_regulations.py`: extract text from the PDF with PyMuPDF; drop repeated page headers and footers.
2. Chunk by article number (`B33.3`, `B33.3.1`...), not by fixed size: each chunk is one
   sub-article, carrying its parent article id and title as metadata. Table-of-contents
   lines and fragments shorter than 40 characters are discarded.
3. `f1-mcp-build-index`: embed `"{title}. {text}"` with Chroma's default model (all-MiniLM-L6-v2, ONNX, CPU)
   and store in a persistent Chroma collection `regulations` (cosine distance).
   The collection is rebuilt from scratch on each run, so issues never mix.

## Tool
`search_regulations(query: str, k: int = 5) -> str`
- `query`: the question or topic **in English** (the corpus and the embedding model are
  English); the docstring tells the model to translate first.
- `k`: number of articles, 1–10.
- Output: one block per article: `[B55.7] Safety Car (similarity 0.71)` + article text,
  ordered by similarity. Readable text, like every other tool.

## Edge cases
- Index missing or empty → readable message ("regulations index not built"), no traceback.
- `k` outside 1–10 → clamped.
- Empty query → readable message, no search.
- Nothing relevant → still returns top-k; the similarity score lets the model judge.

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
- Unit tests for chunking with a synthetic text of known articles (ids, titles, TOC lines
  dropped, header/footer noise removed).
- Tool test against an in-memory Chroma collection with a fake embedding function
  (no model download, no network in CI).
- Missing-index test returns the readable message.
- Manual: `try_client.py search_regulations '{"query": "safety car deployment"}'` returns
  the Safety Car article first.
- Coverage stays >= 80%, ruff and strict mypy pass.
