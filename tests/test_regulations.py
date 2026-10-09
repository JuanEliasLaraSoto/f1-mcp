"""Regulations RAG: chunking on synthetic text, search and tool on an index built
with a fake embedding function (no model download, no network)."""

import hashlib

import numpy as np
import pytest
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from f1_mcp import config, regulations
from f1_mcp.mcp.tools.regulations import search_regulations

PDF_LINES = [
    "SECTION B: SPORTING REGULATIONS",
    "B55.7 Safety Car 42",  # table of contents entry, with page number
    "B1 2026 Formula 1: Sporting Regulations",  # page header
    "©2026 Fédération Internationale de l'Automobile",  # page footer
    "1 October 2026",
    "",
    "B55.7 Safety Car",
    "B55.7.1 When the Safety Car is deployed, no car may overtake another car",
    "on the track until the cars pass the Safety Car line.",
    "B55.7.2 Short.",
    "B48.1 Pit lane",
    "B48.1.1 The speed limit in the pit lane is 80 km/h during the whole Competition.",
]


class KeywordEmbedding(EmbeddingFunction[Documents]):
    """Deterministic bag-of-words hashing: texts sharing words get similar vectors."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        out = []
        for text in input:
            v = np.zeros(64, dtype=np.float32)
            for word in text.lower().split():
                v[int(hashlib.md5(word.strip(".,").encode()).hexdigest(), 16) % 64] += 1
            out.append(v / (np.linalg.norm(v) or 1))
        return out

    @staticmethod
    def name() -> str:
        return "keyword-test"

    def get_config(self) -> dict[str, str]:
        return {}

    @staticmethod
    def build_from_config(config: dict[str, str]) -> "KeywordEmbedding":
        return KeywordEmbedding()


def test_clean_lines_drops_headers_footers_and_blanks():
    lines = list(regulations.clean_lines(PDF_LINES))
    assert not any(line.startswith(("B1 2026", "©", "SECTION B")) for line in lines)
    assert "1 October 2026" not in lines
    assert "" not in lines


def test_chunk_articles_one_chunk_per_sub_article():
    chunks = regulations.chunk_articles(regulations.clean_lines(PDF_LINES))
    by_id = {c["id"]: c for c in chunks}
    # B55.7 and B48.1 are bare headings, B55.7.2 is too short: all dropped
    assert set(by_id) == {"B55.7.1", "B48.1.1"}
    sc = by_id["B55.7.1"]
    assert sc["article"] == "B55.7"
    assert sc["title"] == "Safety Car"  # page number from the TOC stripped
    assert sc["text"].endswith("pass the Safety Car line.")  # continuation line joined


@pytest.fixture
def index(tmp_path, monkeypatch):
    chunks = regulations.chunk_articles(regulations.clean_lines(PDF_LINES))
    db = tmp_path / "chroma"
    regulations.build_index(chunks, db, embedding_function=KeywordEmbedding())
    # Chroma reopens a collection with its default (downloaded) model unless told
    # otherwise, so the search must also get the fake embedding function.
    collection = regulations._client(db).get_collection(
        regulations.COLLECTION, embedding_function=KeywordEmbedding()
    )
    monkeypatch.setattr(regulations, "_collection", lambda: collection)
    return db


def test_build_index_is_rebuilt_from_scratch(index):
    chunks = regulations.chunk_articles(regulations.clean_lines(PDF_LINES))
    n = regulations.build_index(chunks[:1], index, embedding_function=KeywordEmbedding())
    assert n == 1


def test_search_ranks_the_relevant_article_first(index):
    hits = regulations.search("overtake under the Safety Car", k=2)
    assert [h.id for h in hits] == ["B55.7.1", "B48.1.1"]
    assert hits[0].similarity > hits[1].similarity
    assert hits[0].title == "Safety Car"


async def test_tool_returns_citable_articles(index):
    text = await search_regulations("pit lane speed limit", k=1)
    assert text.startswith("[B48.1.1] Pit lane (similarity")
    assert "80 km/h" in text


async def test_tool_clamps_k(index):
    text = await search_regulations("Safety Car", k=50)
    assert text.count("(similarity") == 2


async def test_tool_empty_query(index):
    assert "Empty query" in await search_regulations("   ")


async def test_tool_missing_index(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REGULATIONS_DB_PATH", tmp_path / "nothing")
    regulations._collection.cache_clear()
    assert "not built" in await search_regulations("Safety Car")


async def test_tool_missing_collection(tmp_path, monkeypatch):
    regulations._client(tmp_path)  # creates an empty database, no collection
    monkeypatch.setattr(config, "REGULATIONS_DB_PATH", tmp_path)
    regulations._collection.cache_clear()
    assert "not built" in await search_regulations("Safety Car")
    regulations._collection.cache_clear()
