# Regulations RAG

**Date:** 2026-10-09

## Context
OpenF1 says what happened in a session (a penalty, a Safety Car), but not which rule
applies. Without the regulations the model answers "why" questions from memory, which
is exactly the invented-data failure this project tries to avoid.

## Decision
- New tool `search_regulations(query, k)`: retrieval only, over the 2026 FIA Sporting
  Regulations (Section B, Issue 09). The client model writes the answer and cites the
  article number; the server makes no LLM call.
- Chunking by article number (`B5.13.2`), not fixed size: the regulations are already
  split into self-contained units and that number is the citation. Table-of-contents
  duplicates are resolved by keeping the longest version (the body).
- Chroma as the vector store, persisted to disk, cosine distance. A NumPy array would
  have been enough for a few hundred chunks; Chroma was chosen to work with a real vector
  store (persistence, metadata, rebuilds). Cost: a heavy dependency tree (onnxruntime).
- Local embeddings with Chroma's default model (all-MiniLM-L6-v2, ONNX, CPU): no API key,
  no per-query cost. It is English-only, so the tool asks the model for English queries.
- Deployment: the JSON chunks are committed (small, readable diff when the FIA publishes
  a new issue) and the Docker build creates the index from them, which also bakes the
  embedding model into the image. Rejected: downloading the PDF in the build (deploys
  would depend on fia.com) and committing the binary Chroma directory.
- Tests use a fake bag-of-words embedding function, so CI never downloads the model.
  Gotcha: Chroma reopens a persisted collection with its default model unless an
  embedding function is passed again, so the test fixture passes it on reopen too.

## Consequences
- Bigger image and more RAM on the VPS (onnxruntime + model).
- No evaluation at this point; it came later, with a labelled question set, recall@k and
  a comparison against hybrid search (entry 12).
