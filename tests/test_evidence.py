import gzip
import json
import sqlite3

import pytest

from citations import validate_citations
from config import PUBLIC_V2
from definitions import candidates
from evidence import Passage, locate, resolve_quote
from rag import ranked_hits


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "test.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE pages(book,page,folio,lines)")
        for n, label, text in [
            ("165", "163", "Those remote ancestors were"),
            ("166", "164", "abiotic. Life can change."),
        ]:
            db.execute(
                "INSERT INTO pages VALUES(?,?,?,?)",
                (
                    "book",
                    n,
                    label,
                    gzip.compress(json.dumps([[[0, 0, 100, 20], text]]).encode()),
                ),
            )
    return path


def passage(page, raw, start=0):
    return Passage(
        "book", "Book", "2003", page, start, raw, 0.9, "book.pdf", "book:007"
    )


def test_quote_is_copied_from_printed_page(database):
    one = passage("165", "Those remote ancestors were")
    s = locate(one, "those remote ancestors", database)
    assert s["extrait"] == "Those remote ancestors"
    assert s["pages"] == "p. 163 du livre · PDF p. 165"
    assert s["locator"]["boxes"] == [[0, 0, 100, 20]]
    assert locate(one, "nothing remotely plausible", database) is None
    assert (
        locate(
            passage("165", "An invented assertion."), "An invented assertion", database
        )
        is None
    )


def test_cross_page_quote_keeps_both_folios(database):
    shared = {
        "P1": passage("165", "Those remote ancestors were"),
        "P2": passage("166", "###### Life 164\n\nabiotic. Life can change."),
    }
    s = resolve_quote(
        {"id": "P1", "end_id": "P2", "quote": "remote ancestors were abiotic"},
        shared,
        database,
    )
    assert s["pages"] == "p. 163–164 du livre · PDF p. 165–166"
    assert s["extrait"] == "remote ancestors were abiotic"
    assert (
        resolve_quote(
            {"id": "P1", "end_id": "P2", "quote": "remote ancestors Life can change"},
            shared,
            database,
        )
        is None
    )


def test_epub_has_section_offset(database):
    s = locate(
        passage("ch10", "An exact short quote.", 40), "exact short quote", database
    )
    assert s["locator"]["start"] == 43
    assert "caractère 44" in s["pages"]


def test_grouped_citations_do_not_hide_invalid_indices():
    assert validate_citations("A [2, 5].", 5)["indices"] == [2, 5]
    assert validate_citations("A [1, 90].", 2)["invalid_indices"] == [90]


def test_definition_adds_candidate_even_when_initial_pool_misses_it(monkeypatch):
    base = {"chunk_id": "other:1", "text": "A passing reference.", "book": "other"}
    valid = {
        "chunk_id": "book:2",
        "text": "Any plastic neural system is called a psychon.",
        "book": "book",
    }

    def lookup(*args, **kwargs):
        return [valid] if kwargs.get("mode") == "bm25" else [base]

    class Reranker:
        def score(self, q, docs):
            return [0.8, 0.7][: len(docs)]

    monkeypatch.setattr("rag.search", lookup)
    monkeypatch.setattr("rag.get_reranker", lambda: Reranker())
    assert (
        len(
            ranked_hits(
                "Qu'est-ce qu'un psychon ?", "What is a psychon?", PUBLIC_V2, 12, 5
            )
        )
        == 2
    )
    assert candidates("Pourquoi ?", "Why?", [base], lookup, "t") == ([base], [])


def test_verifier_rejects_unsupported_claim_and_publishes_only_selected_quote(monkeypatch):
    import evidence
    source = passage('ch01','One precise example shows the mechanism.')
    monkeypatch.setattr(evidence, 'passages_for', lambda hits, db: {'P1':source})
    def generator(prompt, system, backend, max_tokens):
        if system == evidence.CHECK:
            return '{"accepted":[1]}'
        return json.dumps({'claims':[
            {'text':'Bunge donne un exemple.','evidence':[{'id':'P1','quote':'One precise example'}]},
            {'text':'Bunge prouve cette proposition.','evidence':[{'id':'P1','quote':'shows the mechanism'}]},
            {'text':'Une affirmation inventée.','evidence':[{'id':'P1','quote':'the original proof'}]}]})
    text, sources, reason = evidence.answer_with_evidence('Q', [{'text':source.raw}], PUBLIC_V2, generator)
    assert reason is None
    assert text == 'Bunge donne un exemple. [1]'
    assert [s['extrait'] for s in sources] == ['One precise example']
