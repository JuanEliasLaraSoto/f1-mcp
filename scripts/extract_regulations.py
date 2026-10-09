"""PDF -> JSON chunks for the regulations index (dev-only: needs pymupdf).

Usage: uv run python scripts/extract_regulations.py data/sporting.pdf
Writes data/regulations_chunks.json (committed), then build the index with
`uv run f1-mcp-build-index`.
"""

import json
import sys
from pathlib import Path

import pymupdf

from f1_mcp import config
from f1_mcp.regulations import chunk_regulations


def pdf_lines(pdf: Path) -> list[str]:
    with pymupdf.open(pdf) as doc:
        return [line for page in doc for line in page.get_text().splitlines()]


if __name__ == "__main__":
    chunks = chunk_regulations(pdf_lines(Path(sys.argv[1])))
    out = config.REGULATIONS_CHUNKS_PATH
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(chunks, ensure_ascii=False, indent=2) + "\n")

    sizes = sorted(len(c["text"]) for c in chunks)
    print(f"{len(chunks)} chunks -> {out}")
    print(f"length: min {sizes[0]}, median {sizes[len(sizes) // 2]}, max {sizes[-1]}")
    for c in chunks[:2] + chunks[len(chunks) // 2 : len(chunks) // 2 + 1]:
        print(f"\n[{c['id']}] {c['title']}\n{c['text'][:300]}...")
