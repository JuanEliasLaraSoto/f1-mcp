"""Retrieval evaluation for search_regulations on a hand-labelled question set.

Usage: uv run python scripts/eval_regulations.py [evals/regulations.jsonl]

For the answerable questions it reports, per retrieval mode:
- recall@k: share of questions with a correct article among the top k results;
- MRR: mean of 1 / rank of the first correct article (0 if not in the top 10).
For the unanswerable ones (no relevant article in Section B) it compares the top-1
cosine similarity with the answerable ones, to pick the "no answer" threshold.
"""

import json
import sys
from pathlib import Path
from typing import get_args

from f1_mcp import regulations

KS = (1, 3, 5)
DEPTH = 10


def first_correct_rank(refs: list[str], relevant: set[str]) -> int | None:
    return next((rank for rank, ref in enumerate(refs, start=1) if ref in relevant), None)


def main(path: Path) -> None:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    answerable = [r for r in rows if r["relevant"]]
    unanswerable = [r for r in rows if not r["relevant"]]
    print(f"{len(answerable)} answerable + {len(unanswerable)} unanswerable questions\n")

    print(f"{'mode':<8}" + "".join(f"  R@{k:<4}" for k in KS) + "  MRR")
    misses: dict[str, list[str]] = {}
    for mode in get_args(regulations.Mode):
        ranks = []
        for row in answerable:
            refs = [h.ref for h in regulations.search(row["question"], DEPTH, mode)]
            rank = first_correct_rank(refs, set(row["relevant"]))
            ranks.append(rank)
            if rank is None or rank > 5:
                misses.setdefault(mode, []).append(f"{row['question']} (rank {rank or '>10'})")
        recall = [sum(1 for r in ranks if r and r <= k) / len(ranks) for k in KS]
        mrr = sum(1 / r for r in ranks if r) / len(ranks)
        print(f"{mode:<8}" + "".join(f"  {x:<6.2f}" for x in recall) + f"  {mrr:.2f}")

    for mode, items in misses.items():
        print(f"\nMissed in top 5 ({mode}):")
        for item in items:
            print(f"  - {item}")

    def top1(question: str) -> float:
        return regulations.search(question, 1, "vector")[0].similarity

    ok = sorted(top1(r["question"]) for r in answerable)
    no = sorted(top1(r["question"]) for r in unanswerable)
    print("\nTop-1 cosine similarity")
    print(f"  answerable:   min {ok[0]:.3f}  median {ok[len(ok) // 2]:.3f}  max {ok[-1]:.3f}")
    print(f"  unanswerable: min {no[0]:.3f}  max {no[-1]:.3f}  values {no}")
    below = sum(1 for s in ok if s <= no[-1])
    print(f"  answerable questions at or below the highest unanswerable score: {below}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "evals/regulations.jsonl"))
