"""Retrieval over the FIA F1 Sporting Regulations.

Two halves:
- Chunking (pure, no I/O): turns the text lines of the PDF into one chunk per
  sub-article, so each chunk carries its own citation (e.g. B55.7.2).
- Vector search (Chroma): builds a persistent collection from the chunks and
  queries it by semantic similarity.
"""

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.api.types import Embeddable, EmbeddingFunction
from chromadb.config import Settings
from chromadb.errors import NotFoundError

from f1_mcp import config

COLLECTION = "regulations"
DOCUMENT = "FIA 2026 F1 Sporting Regulations"
MIN_CHARS = 40  # shorter fragments are stray titles or table-of-contents lines
BATCH_SIZE = 200

# Headers and footers repeated on every page of the PDF
_NOISE = [
    re.compile(r"^B\d+\s+2026 Formula 1"),
    re.compile(r"^©\d{4} F[ée]d[ée]ration"),
    re.compile(r"^\d{1,2} \w+ 2026$"),
    re.compile(r"^SECTION B"),
]
# A line starting with an article number: B1.2, B1.2.1, B33.3.4...
_ARTICLE = re.compile(r"^(B\d+(?:\.\d+)+)\s*(.*)$")
_TRAILING_PAGE = re.compile(r"\s+\d+$")


class Chunk(TypedDict):
    id: str  # sub-article number, e.g. "B55.7.2"
    article: str  # parent article, e.g. "B55.7"
    title: str  # parent article title, e.g. "Safety Car"
    text: str


@dataclass(frozen=True)
class Hit:
    id: str
    title: str
    similarity: float
    text: str


class IndexNotBuiltError(Exception):
    """The Chroma collection does not exist yet (run f1-mcp-build-index)."""


# --- Chunking -----------------------------------------------------------------


def clean_lines(lines: Iterable[str]) -> Iterator[str]:
    """Strips whitespace and drops empty lines and page headers/footers."""
    for line in lines:
        line = line.strip()
        if line and not any(p.match(line) for p in _NOISE):
            yield line


def chunk_articles(lines: Iterable[str]) -> list[Chunk]:
    """Splits the regulation text into one chunk per numbered (sub-)article.

    An article id can appear twice: once in the table of contents and once in the
    body. Both are collected and the longest wins, which is always the body.
    """
    titles: dict[str, str] = {}
    parts: dict[str, list[list[str]]] = {}
    current: str | None = None
    for line in lines:
        match = _ARTICLE.match(line)
        if match:
            art_id, rest = match.groups()
            if art_id.count(".") == 1:
                # Article heading; the TOC version ends with a page number
                titles.setdefault(art_id, _TRAILING_PAGE.sub("", rest))
            current = art_id
            parts.setdefault(art_id, []).append([rest])
        elif current:
            parts[current][-1].append(line)

    chunks: list[Chunk] = []
    for art_id, versions in parts.items():
        text = max((" ".join(v).strip() for v in versions), key=len)
        if len(text) < MIN_CHARS:
            continue
        article = ".".join(art_id.split(".")[:2])
        chunks.append(
            {"id": art_id, "article": article, "title": titles.get(article, ""), "text": text}
        )
    return chunks


# --- Vector store -------------------------------------------------------------


def _client(path: Path) -> ClientAPI:
    return chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))


def build_index(
    chunks: list[Chunk],
    db_path: Path,
    embedding_function: EmbeddingFunction[Embeddable] | None = None,
) -> int:
    """(Re)creates the collection from scratch so regulation issues never mix.
    The title is embedded with the text: short sub-articles need that context.
    Returns the number of chunks stored."""
    client = _client(db_path)
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    collection = client.create_collection(
        COLLECTION,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"},
    )
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        collection.add(
            ids=[c["id"] for c in batch],
            documents=[f"{c['title']}. {c['text']}" for c in batch],
            metadatas=[{"article": c["article"], "title": c["title"]} for c in batch],
        )
    count: int = collection.count()
    return count


@lru_cache(maxsize=1)
def _collection() -> Collection:
    path = config.REGULATIONS_DB_PATH
    if not path.exists():
        raise IndexNotBuiltError(f"no index at {path}")
    try:
        collection: Collection = _client(path).get_collection(COLLECTION)
        return collection
    except NotFoundError as exc:
        raise IndexNotBuiltError(f"no '{COLLECTION}' collection in {path}") from exc


def search(query: str, k: int = 5) -> list[Hit]:
    """Top-k chunks by cosine similarity, most similar first."""
    collection = _collection()
    k = min(k, collection.count())
    if k == 0:
        return []
    res = collection.query(query_texts=[query], n_results=k)
    ids = res["ids"][0]
    docs = (res["documents"] or [[]])[0]
    metas = (res["metadatas"] or [[]])[0]
    dists = (res["distances"] or [[]])[0]
    return [
        Hit(id=i, title=str(m["title"]), similarity=round(1 - d, 3), text=doc)
        for i, doc, m, d in zip(ids, docs, metas, dists, strict=True)
    ]


def build_main() -> None:
    """Entry point `f1-mcp-build-index`: JSON chunks -> Chroma collection."""
    chunks: list[Chunk] = json.loads(config.REGULATIONS_CHUNKS_PATH.read_text())
    n = build_index(chunks, config.REGULATIONS_DB_PATH)
    print(f"Indexed {n} chunks into {config.REGULATIONS_DB_PATH}")
