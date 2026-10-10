# 12 - Retrieval evaluation: hybrid search and a "no answer" threshold

## Context
Two spot checks failed: "track limits" did not find B1.8.6, and "points in the sprint"
returned confident-looking articles although points are not in Section B. Without a
labelled set there was no way to tell whether a change helped or hurt.

## Method
34 hand-labelled questions (`evals/regulations.jsonl`): 30 with the accepted citations
and 4 the corpus cannot answer. Questions are phrased like a user, not copied from the
rules. `scripts/eval_regulations.py` reports recall@k and MRR per retrieval mode.

## Results

| Mode | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| Vector (all-MiniLM-L6-v2) | 0.50 | 0.77 | 0.80 | 0.66 |
| BM25 | 0.30 | 0.53 | 0.53 | 0.45 |
| Hybrid (RRF) | 0.47 | 0.80 | **0.90** | 0.63 |

- BM25 alone is weak: users rarely use the rulebook's words.
- Hybrid recovers questions the embeddings rank 6th-10th ("How long is a Grand Prix
  race?", "How many engines can a driver use?") and trades a little precision at rank 1.
  The tool returns 5 articles, so recall@5 is the metric that matters: hybrid is the default.
- Still missed: "track limits" (the rule says "leave the track"; no shared word, and the
  embeddings do not link them), "refuel the car during a pit stop" and the parc fermé
  start time (rank 9).
- A tokenizer bug surfaced on the way: "fermé" was split into "ferm", so BM25 never
  matched "parc ferme". Accents are now stripped before tokenizing.

## "No answer" threshold
Top-1 cosine similarity: answerable 0.48-0.77, unanswerable 0.33-0.57. The ranges overlap:
9 of the 30 answerable questions score at or below the best unanswerable one, so no
threshold separates them. The tool uses 0.45, which rejects only scores no answerable
question reached (it catches the budget cap question), and its description now says
explicitly what Section B does not cover (points, car specs, finances) so the model
declines those instead of trusting a 0.5 match.

## Consequences
- Every retrieval change now gets a before/after table.
- The eval set is small and labelled by the author, and the threshold was chosen on the
  same set: the numbers are indicative, not a benchmark.
- Next candidates, to be measured the same way: query rewriting by the client model
  (fixes vocabulary gaps such as "track limits"), a stemmer for BM25 ("refuel" vs
  "refuelling"), and indexing Section A for championship points.
