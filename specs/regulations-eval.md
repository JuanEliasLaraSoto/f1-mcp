# Spec: regulations retrieval evaluation

## Goal
Measure how well `search_regulations` finds the right article, so retrieval changes are
compared with numbers instead of by eye, and the tool can say "no answer" when the
corpus does not cover a question.

## Eval set (`evals/regulations.jsonl`)
- One JSON object per line: `question` (English, phrased as a user would ask, not copied
  from the rule), `relevant` (accepted citations, e.g. `["B2.5.2", "B2.5.3"]`), `note`.
- 30 answerable questions covering procedures, penalties, Safety Car / VSC, tyres,
  parc fermé, power unit limits, weather, media; several with a vocabulary gap on purpose
  ("track limits" vs "leave the track", "movable rear wing" vs "Driver Adjustable Bodywork").
- 4 unanswerable questions (`relevant: []`): points, car weight, budget cap, calendar.
  They live in other FIA sections or nowhere.
- Every `relevant` citation is checked to exist in `data/regulations_chunks.json`.

## Metrics (`scripts/eval_regulations.py`)
- recall@1, @3, @5 and MRR over the answerable questions, per retrieval mode
  (vector, bm25, hybrid), counting one result per citation.
- Top-1 cosine similarity of answerable vs unanswerable questions, to choose the
  "no answer" threshold.

## Retrieval changes evaluated
- BM25 (Okapi, k1 = 1.5, b = 0.75) implemented in pure Python over the same chunks.
- Hybrid: vector and BM25 rankings fused with Reciprocal Rank Fusion (k = 60).
- One result per citation: parts of a long article no longer fill several slots.
- Threshold on the top-1 cosine similarity below which the tool answers "no article".

## Acceptance
- The script runs against the real index and prints the table; the numbers go in the
  README and journal 12.
- The tool uses the best mode by recall@5 (the tool returns 5 articles by default).
- The threshold rejects no answerable question of the set.
- Unit tests: tokenizer, BM25 ranking, RRF, every mode, one hit per citation, threshold,
  tool "no answer" message. No network, fake embeddings, as before.
