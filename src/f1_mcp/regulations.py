"""Retrieval over the FIA F1 Sporting Regulations.

Two halves:
- Chunking (pure, no I/O): turns the text lines of the PDF into chunks that each
  carry their own citation (e.g. B5.13.2) and the headings above them.
- Vector search (Chroma): builds a persistent collection from the chunks and
  queries it by semantic similarity.

Layout of the PDF text (Section B, Issue 09), as extracted by PyMuPDF:
- Every page starts with a header block (section name, page number "B47", issue...).
- Pages 1-3 are the table of contents; the body starts at the second "ARTICLE B1:".
- Numbers and headings sit on their own lines: "B5.13" / "Safety Car", then
  "B5.13.4" / "Order of Cars Behind the SC" / text... A third-level number is followed
  either by a heading or directly by text.
- Appendices B1 (definitions) and B2 (parc fermé works) are useful; B3 and B4 are
  admin forms and B5 holds the approved changes for 2027, which reuse 2026 article
  numbers with different text, so everything from Appendix B3 on is dropped.
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
# all-MiniLM-L6-v2 reads ~256 word pieces (~1,000 characters of this text) and
# ignores the rest, so longer articles are split into parts of at most this size.
MAX_CHARS = 1000
BATCH_SIZE = 200

# Page header lines and governance boilerplate
_NOISE = [
    re.compile(r"^SECTION B: SPORTING REGULATIONS$"),
    re.compile(r"^0\s+B$"),
    re.compile(r"^B\d+$"),  # page number
    re.compile(r"^\d{4} Formula 1 Regulations - Section B"),
    re.compile(r"^©\d{4} F[ée]d[ée]ration"),
    re.compile(r"^\d{1,2} \w+ \d{4}$"),
    re.compile(r"^Issue \d+$"),
    re.compile(r"^(Advisory Committee|Governance):"),
    re.compile(r"^(\.\./\.\.|…/…)$"),
]
# Article numbers always sit alone on their line; a line that starts with a number
# followed by text is a wrapped cross-reference ("...Articles B5.14.4, B5.15.1 and" /
# "B5.15.2 shall remain...") and belongs to the body.
_NUMBER = re.compile(r"^B\d+(?:\.\d+)+$")
_ARTICLE = re.compile(r"^ARTICLE (B\d+): (.+)$")
_APPENDIX = re.compile(r"^APPENDIX (B\d+): (.+)$")
_ITEM = re.compile(r"^(?:[a-z]|[ivx]+)\.$")  # list markers "a." / "iv." on their own line
_PARC_FERME_HEADING = re.compile(r"^(\d+)\. ([A-Z][A-Z &/-]+)$")
_SMALL_WORDS = {"a", "an", "and", "at", "by", "during", "for", "from", "in", "of", "on", "or"}
_SMALL_WORDS |= {"the", "to", "with", "&", "-", "–"}


class Chunk(TypedDict):
    id: str  # unique: the citation plus "#n" when an article is split in parts
    ref: str  # citation, e.g. "B5.13.2" or "Appendix B1"
    title: str  # headings above the text, e.g. "Safety Car > Order of Cars Behind the SC"
    text: str


@dataclass(frozen=True)
class Hit:
    ref: str
    title: str
    similarity: float
    text: str


class IndexNotBuiltError(Exception):
    """The Chroma collection does not exist yet (run f1-mcp-build-index)."""


# --- Chunking -----------------------------------------------------------------


def clean_lines(lines: Iterable[str]) -> Iterator[str]:
    """Strips whitespace and drops empty lines and page headers."""
    for line in lines:
        line = line.strip()
        if line and not any(p.match(line) for p in _NOISE):
            yield line


def is_heading(line: str) -> bool:
    """A heading is short Title Case text without final punctuation, e.g.
    'Order of Cars Behind the SC'. Body text starts with a full sentence."""
    if len(line) > 90 or line[-1] in ".:;," or _ITEM.match(line):
        return False
    words = [w.strip("()\"“”'") for w in line.split()]
    words = [w for w in words if w and w.lower() not in _SMALL_WORDS]
    return bool(words) and sum(w[0].isupper() or w[0].isdigit() for w in words) / len(words) > 0.7


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Packs whole sentences into parts of at most max_chars (a single longer
    sentence becomes its own part)."""
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.;:])\s+", text):
        if current and len(current) + 1 + len(sentence) > max_chars:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def _body(lines: list[str]) -> tuple[list[str], list[str]]:
    """(articles, appendices B1-B2): skips the table of contents, cuts at Appendix B3."""
    starts = [i for i, line in enumerate(lines) if line.startswith("ARTICLE B1:")]
    start = starts[1] if len(starts) > 1 else (starts[0] if starts else 0)
    body = lines[start:]
    end = next((i for i, line in enumerate(body) if line.startswith("APPENDIX B3:")), len(body))
    body = body[:end]
    appx = next((i for i, line in enumerate(body) if line.startswith("APPENDIX B1:")), len(body))
    return body[:appx], body[appx:]


def _article_chunks(lines: list[str]) -> list[tuple[str, str, str]]:
    """(ref, title, text) per numbered unit of the articles."""
    titles: dict[str, str] = {}  # "B5" -> "Total Time Classified Sessions (TTCS)", "B5.13" -> ...
    units: list[tuple[str, list[str]]] = []
    headings: list[str] = []  # own heading of each unit (numbers can repeat: B1.5.11)
    expect_heading_for: str | None = None
    for line in lines:
        if m := _ARTICLE.match(line):
            titles[m[1]] = m[2].title()
            expect_heading_for = None
            continue
        if _NUMBER.match(line):
            units.append((line, []))
            headings.append("")
            expect_heading_for = line
            continue
        if expect_heading_for and is_heading(line):
            titles[expect_heading_for] = line
            headings[-1] = line
            expect_heading_for = None
            continue
        expect_heading_for = None
        if units:
            units[-1][1].append(line)

    out = []
    for (number, body), heading in zip(units, headings, strict=True):
        text = " ".join(body).strip()
        if not text:
            continue  # a bare heading: its text lives in the sub-articles
        levels = number.split(".")
        parents = [".".join(levels[:n]) for n in range(2, len(levels))]
        title = " > ".join([titles[p] for p in parents if p in titles] + [heading] * bool(heading))
        out.append((number, title, text))
    return out


def _appendix_chunks(lines: list[str]) -> list[tuple[str, str, str]]:
    """Appendix B1: one chunk per definition. Appendix B2: one per parc fermé group."""
    out: list[tuple[str, str, str]] = []
    appendix = ""
    for line in lines:
        if m := _APPENDIX.match(line):
            appendix = m[1]
            continue
        if appendix == "B1":
            if line.startswith("“") or not out:
                term = line[1 : line.find("”")] if line.startswith("“") else "Definitions"
                out.append(("Appendix B1", f"Definitions > {term}", line))
            else:
                ref, title, text = out[-1]
                out[-1] = (ref, title, f"{text} {line}")
        elif appendix == "B2":
            if m := _PARC_FERME_HEADING.match(line):
                title = f"Parc Fermé Required & Permitted Works > {m[2].title()}"
                out.append((f"Appendix B2.{m[1]}", title, ""))
            elif out and out[-1][0].startswith("Appendix B2"):
                ref, title, text = out[-1]
                out[-1] = (ref, title, f"{text} {line}".strip())
    return [c for c in out if c[2]]


def chunk_regulations(lines: Iterable[str]) -> list[Chunk]:
    """Splits the regulation text into citable chunks of at most MAX_CHARS."""
    articles, appendices = _body(list(clean_lines(lines)))
    chunks: list[Chunk] = []
    seen: dict[str, int] = {}  # Appendix B1 has one ref for many definitions
    for ref, title, text in _article_chunks(articles) + _appendix_chunks(appendices):
        seen[ref] = seen.get(ref, 0) + 1
        base = ref if seen[ref] == 1 else f"{ref}~{seen[ref]}"
        parts = split_text(text)
        for n, part in enumerate(parts, start=1):
            chunk_id = base if len(parts) == 1 else f"{base}#{n}"
            chunks.append({"id": chunk_id, "ref": ref, "title": title, "text": part})
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
    The headings are embedded with the text: many sub-articles only make sense with
    them (e.g. "Safety Car > Duration of SC Period").
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
            documents=[f"{c['title']}\n{c['text']}" for c in batch],
            metadatas=[{"ref": c["ref"], "title": c["title"]} for c in batch],
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
    docs = (res["documents"] or [[]])[0]
    metas = (res["metadatas"] or [[]])[0]
    dists = (res["distances"] or [[]])[0]
    return [
        Hit(
            ref=str(m["ref"]),
            title=str(m["title"]),
            similarity=round(1 - d, 3),
            text=doc.split("\n", 1)[-1],  # the stored document is "title\ntext"
        )
        for doc, m, d in zip(docs, metas, dists, strict=True)
    ]


def build_main() -> None:
    """Entry point `f1-mcp-build-index`: JSON chunks -> Chroma collection."""
    chunks: list[Chunk] = json.loads(config.REGULATIONS_CHUNKS_PATH.read_text())
    n = build_index(chunks, config.REGULATIONS_DB_PATH)
    print(f"Indexed {n} chunks into {config.REGULATIONS_DB_PATH}")
