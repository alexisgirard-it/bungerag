import json
from pathlib import Path

import pytest

from audit_fidelity import LONG_CONVERSATIONS, verify_fidelity
from library import CATALOG, DATABASE, NODES, question_scope
from workshop import DOSSIERS, assess, choose_dossier

ROOT = Path(__file__).resolve().parents[1]


def test_oriented_formulations_pure_routing_and_scope():
    """Toujours exécuté en CI (sans base SQLite locale)."""
    cases = [
        json.loads(line)
        for line in (ROOT / "eval/fidelite-orientee.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(cases) >= 8
    for case in cases:
        if case["kind"] in ("posthumous", "edition"):
            disposition, _ = question_scope(case["question"])
            assert disposition == case["expected_disposition"], case["id"]
        elif case["kind"] in ("attribution", "oriented_dossier"):
            assert choose_dossier(case["question"]) == case["expected_dossier"], case["id"]


def test_long_conversations_keep_catalog_immutable_without_sqlite(monkeypatch):
    """Vérifie l’isolation multi-tours (22 tours) sans dépendre de index/lecture.sqlite."""
    fake_source = {
        "book": "book",
        "page": "1",
        "folio": "1",
        "chapter": "Ch",
        "year": 1980,
        "title": "Book",
        "authors": "Mario Bunge",
        "file": "book.pdf",
        "edition": "ed",
        "edition_label": "Ed",
        "excerpt": "Excerpt",
        "pages": "PDF p. 1",
    }
    monkeypatch.setattr("workshop.node_source", lambda _key: dict(fake_source))
    before = json.dumps(CATALOG, sort_keys=True)
    turns = 0
    for conv in LONG_CONVERSATIONS:
        steps = DOSSIERS[conv["dossier"]]()["steps"]
        changes = {}
        for key, value, expected in conv["turns"]:
            if value is None:
                changes.pop(key, None)
            else:
                changes[key] = value
            state = assess(steps, changes)
            for target_step, target_state in expected.items():
                assert state[target_step] == target_state
            turns += 1
        assert not changes
    assert turns >= 22
    assert json.dumps(CATALOG, sort_keys=True) == before
    assert len(NODES) >= 109


@pytest.mark.skipif(not DATABASE.is_file(), reason="index/lecture.sqlite absent en CI")
def test_oriented_formulations_and_long_conversations_preserve_catalog():
    summary = verify_fidelity()
    assert summary["oriented_cases"] >= 8
    assert summary["long_conversations"] >= 2
    assert summary["conversation_turns"] >= 22
