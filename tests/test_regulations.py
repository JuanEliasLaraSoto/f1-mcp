"""Regulations RAG: chunking on synthetic text, search and tool on an index built
with a fake embedding function (no model download, no network)."""

import hashlib

import numpy as np
import pytest
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from f1_mcp import config, regulations
from f1_mcp.mcp.tools import regulations as tool_module
from f1_mcp.mcp.tools.regulations import search_regulations

HEADER = [  # page header block exactly as PyMuPDF extracts it (Section B, Issue 09)
    "SECTION B: SPORTING REGULATIONS ",
    " ",
    "0  B ",
    "B46 ",
    "2026 Formula 1 Regulations - Section B [Sporting] ",
    "©2026 Fédération Internationale de l’Automobile ",
    "01 October 2026",
    "Issue 09",
]
PDF_LINES = [
    *HEADER,
    # table of contents: numbers, headings and page numbers on separate lines
    "ARTICLE B1: ORGANISATION OF A COMPETITION ",
    "4 ",
    "B1.8 ",
    "Driving ",
    "12 ",
    "APPENDIX B3: INFORMATION REQUIRED 90 DAYS BEFORE A COMPETITION ",
    "90 ",
    *HEADER,
    # body
    "ARTICLE B1: ORGANISATION OF A COMPETITION ",
    "Advisory Committee: SAC  ",
    "Governance: F1 Commission / WMSC ",
    "B1.8 ",
    "Driving ",
    "B1.8.1 ",
    "The driver must drive the F1 Car alone and unaided. ",
    "ARTICLE B5: TOTAL TIME CLASSIFIED SESSIONS (TTCS) ",
    "B5.13 ",
    "Safety Car (SC) ",
    "The Safety Car will be used only if Competitors or officials are in immediate physical ",
    "danger on or near the track. ",
    "B5.13.2 ",
    "During a SC Deployment ",
    "No driver may overtake another F1 Car on the track, including the Safety Car, unless ",
    *HEADER,  # page break in the middle of a sentence
    "signalled to do so. The exceptions are listed in Articles B5.10.6, B5.10.8 and ",
    "B5.15.3 shall remain unchanged. ",  # wrapped cross-reference, not a new article
    "B5.13.5 ",
    "Duration of SC Period ",
    "a. ",
    "Except under Article B5.13.4c, the Safety Car shall be used at least until the leader is ",
    "behind it. ",
    "ARTICLE B6: TYRE LIMITATIONS ",
    "B6.1 ",
    "Supply Of Tyres ",
    "B6.1.1 ",
    "The pit lane speed limit is 80 km/h during the whole Competition. ",
    "APPENDIX B1: DEFINITIONS ",
    "“Fast Lane”: The Pit Lane will be divided into two lanes, the lane closest to the pit wall ",
    "will be designated the Fast Lane. ",
    "“Inner Lane”: The lane closest to the garages will be designated the Inner lane. ",
    "APPENDIX B2: PARC FERME REQUIRED & PERMITTED WORKS ",
    "1. BRAKES ",
    " 1.1 Brake friction material may be removed, measured, de-glazed and refitted ",
    "APPENDIX B3: INFORMATION REQUIRED 90 DAYS BEFORE A COMPETITION ",
    "1. ",
    "NAME AND ADDRESS OF THE NATIONAL SPORTING AUTHORITY (ASN). ",
    "APPENDIX B5: APPROVED CHANGES TO SECTION B FOR SUBSEQUENT YEARS ",
    "B2.5.2 ",
    "Race Session Distance ",
    "The distance of the Race shall exceed 305km. ",
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


def chunks() -> list[regulations.Chunk]:
    return regulations.chunk_regulations(PDF_LINES)


def by_ref() -> dict[str, list[regulations.Chunk]]:
    out: dict[str, list[regulations.Chunk]] = {}
    for c in chunks():
        out.setdefault(c["ref"], []).append(c)
    return out


def test_clean_lines_drops_page_headers_and_boilerplate():
    lines = list(regulations.clean_lines(HEADER + ["Governance: F1 Commission / WMSC", "a. "]))
    assert lines == ["a."]


def test_table_of_contents_and_later_appendices_are_skipped():
    refs = set(by_ref())
    assert refs == {
        "B1.8.1",
        "B5.13",
        "B5.13.2",
        "B5.13.5",
        "B6.1.1",
        "Appendix B1",
        "Appendix B2.1",
    }
    # Appendix B5 (2027 changes) reuses 2026 numbers: it must not leak in
    assert not any("305km" in c["text"] for c in chunks())


def test_titles_carry_the_heading_path():
    refs = by_ref()
    assert refs["B1.8.1"][0]["title"] == "Driving"
    assert refs["B5.13"][0]["title"] == "Safety Car (SC)"
    assert refs["B5.13.5"][0]["title"] == "Safety Car (SC) > Duration of SC Period"
    assert refs["Appendix B1"][0]["title"] == "Definitions > Fast Lane"
    assert refs["Appendix B2.1"][0]["title"] == "Parc Fermé Required & Permitted Works > Brakes"


def test_page_breaks_and_cross_references_stay_in_the_text():
    text = by_ref()["B5.13.2"][0]["text"]
    assert "unless signalled to do so." in text  # page header removed mid-sentence
    assert text.endswith("B5.15.3 shall remain unchanged.")
    assert "B5.15.3" not in by_ref()


def test_list_markers_are_text_not_headings():
    assert by_ref()["B5.13.5"][0]["text"].startswith("a. Except under Article B5.13.4c")


def test_repeated_refs_get_unique_ids():
    ids = [c["id"] for c in chunks()]
    assert len(ids) == len(set(ids))
    assert [c["id"] for c in by_ref()["Appendix B1"]] == ["Appendix B1", "Appendix B1~2"]


def test_long_text_is_split_by_sentence():
    text = " ".join(f"Sentence number {i} is here." for i in range(100))
    parts = regulations.split_text(text, max_chars=200)
    assert all(len(p) <= 200 for p in parts)
    assert " ".join(parts) == text


def test_long_articles_get_numbered_part_ids():
    long_body = [f"Sentence number {i} about the Safety Car. " for i in range(60)]
    lines = ["ARTICLE B1: X", "B1.1 ", "Driving ", "B1.1.1 ", *long_body]
    parts = regulations.chunk_regulations(lines)
    assert len(parts) > 1
    assert parts[0]["id"] == "B1.1.1#1" and parts[1]["id"] == "B1.1.1#2"
    assert {p["ref"] for p in parts} == {"B1.1.1"}


def test_is_heading():
    assert regulations.is_heading("Order of Cars Behind the SC")
    assert regulations.is_heading("Safety Car (SC)")
    assert not regulations.is_heading("The driver must drive the F1 Car alone and unaided.")
    assert not regulations.is_heading("a.")
    assert not regulations.is_heading("danger on or near the track")


@pytest.fixture
def index(tmp_path, monkeypatch):
    db = tmp_path / "chroma"
    regulations.build_index(chunks(), db, embedding_function=KeywordEmbedding())
    # Chroma reopens a collection with its default (downloaded) model unless told
    # otherwise, so the search must also get the fake embedding function.
    collection = regulations._client(db).get_collection(
        regulations.COLLECTION, embedding_function=KeywordEmbedding()
    )
    monkeypatch.setattr(regulations, "_collection", lambda: collection)
    # The fake embeddings give lower similarities than the real model: no threshold
    # in the tool tests, except where the threshold itself is tested.
    monkeypatch.setattr(tool_module, "MIN_SIMILARITY", 0.0)
    regulations._index.cache_clear()
    yield db
    regulations._index.cache_clear()


def test_build_index_is_rebuilt_from_scratch(index):
    n = regulations.build_index(chunks()[:1], index, embedding_function=KeywordEmbedding())
    assert n == 1


def test_tokenize_drops_accents_case_and_stopwords():
    assert regulations.tokenize("What is the Parc Fermé rule?") == ["parc", "ferme", "rule"]


def test_bm25_prefers_rare_matching_terms():
    bm25 = regulations.BM25(
        ["the car on the track", "the car in parc ferme", "the car in the pits"]
    )
    scores = bm25.scores("car parc ferme")
    assert scores.index(max(scores)) == 1
    # "car" is in every document (all of equal length): same small score everywhere
    assert scores[0] == scores[2] > 0
    assert bm25.scores("monaco") == [0.0, 0.0, 0.0]


def test_rrf_rewards_items_ranked_well_by_both_lists():
    fused = regulations.rrf([["a", "b", "c"], ["d", "b", "e"]])
    assert fused[0] == "b"  # 2nd in both lists beats 1st in only one
    assert set(fused) == {"a", "b", "c", "d", "e"}


def test_search_ranks_the_relevant_article_first(index):
    hits = regulations.search("speed limit in the pit lane", k=3)
    assert hits[0].ref == "B6.1.1"
    assert hits[0].title == "Supply Of Tyres"
    assert hits[0].text.startswith("The pit lane speed limit")  # title not repeated


@pytest.mark.parametrize("mode", ["vector", "bm25", "hybrid"])
def test_every_mode_finds_an_exact_match(index, mode):
    assert regulations.search("brake friction material", k=1, mode=mode)[0].ref == "Appendix B2.1"


def test_search_returns_one_hit_per_article(index):
    refs = [h.ref for h in regulations.search("lane closest designated", k=10)]
    assert refs.count("Appendix B1") == 1  # two definitions share the citation
    assert len(refs) == len(set(refs))


def test_search_below_min_similarity_returns_nothing(index):
    assert regulations.search("Safety Car", k=3, min_similarity=1.01) == []


async def test_tool_returns_citable_articles(index):
    text = await search_regulations("pit lane speed limit", k=1)
    assert text.startswith("[B6.1.1] Supply Of Tyres (similarity")
    assert "80 km/h" in text


async def test_tool_clamps_k(index):
    text = await search_regulations("Safety Car", k=50)
    n_refs = len({c["ref"] for c in chunks()})  # fewer than 10 in this index
    assert text.count("(similarity") == n_refs


async def test_tool_says_when_nothing_matches(index, monkeypatch):
    monkeypatch.setattr(tool_module, "MIN_SIMILARITY", 1.01)
    text = await search_regulations("How many points does the winner score?")
    assert text.startswith("No article of the Sporting Regulations")


async def test_tool_empty_query(index):
    assert "Empty query" in await search_regulations("   ")


async def test_tool_missing_index(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REGULATIONS_DB_PATH", tmp_path / "nothing")
    regulations._collection.cache_clear()
    regulations._index.cache_clear()
    assert "not built" in await search_regulations("Safety Car")


async def test_tool_missing_collection(tmp_path, monkeypatch):
    regulations._client(tmp_path)  # creates an empty database, no collection
    monkeypatch.setattr(config, "REGULATIONS_DB_PATH", tmp_path)
    regulations._collection.cache_clear()
    regulations._index.cache_clear()
    assert "not built" in await search_regulations("Safety Car")
    regulations._collection.cache_clear()
