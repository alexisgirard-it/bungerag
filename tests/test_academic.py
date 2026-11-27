"""Tests unitaires hors ligne pour la recherche académique externe (OpenAlex / Europe PMC)."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "space"))

from academic import (  # noqa: E402
    build_academic_query,
    search_academic_papers,
    should_search_academic,
)
from workshop import debate_turn  # noqa: E402


def test_should_search_academic_smart_trigger():
    # Pure exégèse sur Bunge -> NON déclenché
    assert should_search_academic("Que dit Bunge sur le bonheur ?")[0] is False
    assert should_search_academic("Quelle est la définition du systémisme ?")[0] is False
    assert should_search_academic("La causalité entraîne-t-elle le fatalisme ?")[0] is False

    # Sujet contemporain / empirique -> OUI déclenché
    assert should_search_academic("Un modèle de langage peut-il comprendre ?")[0] is True
    assert should_search_academic("La psychanalyse aide pourtant certains patients en clinique")[0] is True
    assert should_search_academic("Quelles études récentes portent sur les neurosciences ?")[0] is True

    # Mode explicite off / force
    assert should_search_academic("Un LLM peut-il comprendre ?", mode="off")[0] is False
    assert should_search_academic("Que dit Bunge sur le bonheur ?", mode="force")[0] is True

    # Relance multi-tour sur un sujet contemporain
    turns = [{"turn": 1, "user": "Un modèle de langage peut-il comprendre ?", "answer": "..."}]
    assert should_search_academic("ok mais matériellement c'est moins complexe que le cerveau ?", turns)[0] is True


def test_build_academic_query_strips_bunge_and_keeps_science():
    q = build_academic_query(
        "Selon Mario Bunge, un modèle de langage peut-il comprendre comme un cerveau ?",
        translator=lambda s: "Can a language model understand like a brain?",
    )
    assert "bunge" not in q.lower()
    assert "large language model" in q.lower()
    assert "brain" in q.lower()


def test_search_academic_papers_merges_openalex_and_europe_pmc():
    class FakeResp:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code
            self.text = json.dumps(payload)

        def json(self):
            return self._payload

    def fake_get(url, **_kwargs):
        if "api.openalex.org" in url:
            return FakeResp(
                {
                    "results": [
                        {
                            "title": "Speech language models lack brain-relevant semantics",
                            "publication_year": 2024,
                            "doi": "https://doi.org/10.18653/v1/2024.acl-long.462",
                            "cited_by_count": 44,
                            "authorships": [
                                {"author": {"display_name": "A. Researcher"}},
                                {"author": {"display_name": "B. Neuro"}},
                            ],
                            "primary_location": {"source": {"display_name": "ACL 2024"}},
                            "abstract_inverted_index": {
                                "Neural": [0],
                                "semantics": [1],
                                "differ": [2],
                                "from": [3],
                                "LLMs.": [4],
                            },
                        }
                    ]
                }
            )
        if "europepmc" in url:
            return FakeResp(
                {
                    "resultList": {
                        "result": [
                            {
                                "title": "<b>Neurobiology</b> of semantic processing.",
                                "pubYear": "2025",
                                "doi": "10.1000/neuro.2025",
                                "authorString": "C. Biologist",
                                "journalTitle": "Nature Neuroscience",
                                "citedByCount": 12,
                                "abstractText": "Biological <i>plasticity</i> enables meaning.",
                            }
                        ]
                    }
                }
            )
        return FakeResp({}, status_code=404)

    papers = search_academic_papers(
        "Un LLM peut-il comprendre comme un cerveau ?",
        limit=3,
        http_get=fake_get,
        translator=lambda s: "Can an LLM understand like a brain?",
    )
    assert len(papers) == 2
    assert papers[0]["id"] == "ext1"
    assert papers[0]["provider"] == "OpenAlex"
    assert papers[0]["abstract"] == "Neural semantics differ from LLMs."
    assert papers[1]["id"] == "ext2"
    assert papers[1]["provider"] == "Europe PMC"
    assert "<i>" not in papers[1]["abstract"]
    assert papers[1]["url"] == "https://doi.org/10.1000/neuro.2025"


def test_debate_turn_segregates_academic_papers_and_renders_them(monkeypatch):
    source = {
        "book": "mind-body-problem-1980",
        "page": "26",
        "title": "The Mind-Body Problem",
        "year": 1980,
        "authors": "Mario Bunge",
        "file": "mbp.pdf",
        "edition": "ed",
        "excerpt": "The disanalogies between brains and computers are obvious.",
        "pages": "p. 14 du livre · PDF p. 26",
    }
    paper = {
        "id": "ext1",
        "title": "Speech language models lack brain-relevant semantics",
        "authors": "A. Researcher",
        "year": 2024,
        "venue": "ACL 2024",
        "url": "https://doi.org/10.18653/v1/2024.acl-long.462",
        "doi": "10.18653/v1/2024.acl-long.462",
        "cited_by": 44,
        "abstract": "Neural semantics differ from LLMs.",
        "provider": "OpenAlex",
    }
    monkeypatch.setattr("workshop.suggested_nodes", lambda *a, **k: [])
    monkeypatch.setattr("workshop.on_page", lambda *a, **k: [])
    monkeypatch.setattr("workshop.core_context", lambda: "Cadre sourcé")
    monkeypatch.setattr("workshop.choose_dossier", lambda *a, **k: None)

    def fake_gen(prompt, system):
        payload = json.loads(prompt)
        assert "etudes_scientifiques_externes_hors_bunge" in payload
        assert "ext1" not in payload["preuves"]
        return json.dumps(
            {
                "reponse": "Bunge distingue cerveau et ordinateur (c1), et une étude externe de 2024 (ext1) va dans ce sens.",
                "appuis": ["c1", "ext1"],
                "impact_premisses": "Les données externes restent distinctes de Bunge.",
                "question_suivante": "Quel critère retenez-vous ?",
            }
        )

    hist, notice = debate_turn(
        None,
        {},
        [],
        "Un modèle de langage peut-il comprendre comme un cerveau ?",
        search_fn=lambda _q: [source],
        generate=fake_gen,
        academic_mode="auto",
        academic_search_fn=lambda _q, _t: [paper],
    )
    assert not notice and len(hist) == 1
    # Les appuis vérifiés restent strictement issus de Bunge (ext1 filtré de `sources`)
    assert len(hist[0]["sources"]) == 1
    assert hist[0]["academic_sources"] == [paper]
    # Les identifiants techniques (c1) et (ext1) sont nettoyés de la prose
    assert "(c1)" not in hist[0]["answer"]
    assert "(ext1)" not in hist[0]["answer"]

    # Vérifier le rendu HTML distinct dans reader.render_debate sans polluer le cache gradio
    import importlib

    had_gradio = "gradio" in sys.modules
    had_reader = "reader" in sys.modules
    if not had_gradio:
        fake_gr = types.SimpleNamespace(
            Dropdown=lambda *a, **k: dict(choices=a[0] if a else k.get("choices"), **k),
            Tabs=lambda **k: k,
        )
        monkeypatch.setitem(sys.modules, "gradio", fake_gr)
    reader = sys.modules.get("reader") or importlib.import_module("reader")
    try:
        html_out = reader.render_debate(hist, local=None)
    finally:
        if not had_reader and not had_gradio:
            sys.modules.pop("reader", None)
    assert "Études scientifiques externes · hors Bunge (1)" in html_out
    assert "Passages de Bunge cités (1)" in html_out
    assert "https://doi.org/10.18653/v1/2024.acl-long.462" in html_out
