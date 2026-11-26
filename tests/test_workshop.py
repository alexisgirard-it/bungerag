import json

import pytest

from workshop import (
    CATALOG,
    assess,
    formal_happiness,
    formal_rights,
    open_question,
    step,
    choose_dossier,
    contemporary_claim,
)


def test_replacing_a_premise_preserves_independent_justifications():
    steps = [
        step("a", "Postulat", "A", "Postulat"),
        step("b", "Autre appui", "B", "Définition"),
        step("c", "Deux voies", "C", "Théorème", [["a"], ["b"]]),
        step("d", "Une voie", "D", "Conclusion", [["a"]]),
        step("e", "Conséquence", "E", "Conclusion", [["d"]]),
    ]
    states = assess(steps, {"a": "Nouvelle hypothèse"})
    assert states["a"] == "remplacée"
    assert states["c"] == "disponible"
    assert states["d"] == states["e"] == "justification suspendue"
    assert set(assess(steps, {}).values()) == {"disponible"}


def test_formal_example_checks_every_boolean_valuation():
    result = formal_rights()
    assert result["formula"] == "R → ¬H, H ⊨ ¬R"
    assert result["valid"] and len(result["rows"]) == 4
    happiness = formal_happiness()
    assert happiness["valid"]
    assert [row for row in happiness["rows"] if row[3]] == [(True, False, False, True)]


def test_unrelated_ai_question_does_not_open_the_curated_llm_dossier():
    assert (
        choose_dossier("Comment un modèle de langage pourrait-il comprendre ?") == "ia"
    )
    assert choose_dossier("Quelle GPU est utilisée pour entraîner Gemini 4 ?") is None
    assert not open_question("Zzzz", [])["steps"]


def test_a_proposed_argument_requires_real_appuis_and_a_second_read(monkeypatch):
    monkeypatch.setitem(CATALOG, "core", [])
    monkeypatch.setattr("workshop.core_context", lambda: "Cadre sourcé")
    monkeypatch.setattr("workshop.suggested_nodes", lambda *_: [])
    source = {
        "book": "book",
        "page": "19",
        "title": "Source",
        "excerpt": "A short passage",
    }
    proposed = '{"premisses":["p1"],"hypothese":"Si H","conclusion":"Alors C","objection":"Si non H ?", "question_ouverte":"Quel test ?"}'
    for confirmation in ('{"valide":false}', '{"valide":true}'):
        responses = iter((proposed, confirmation))
        result = open_question(
            "Sujet expérimental", [source], generate=lambda *_: next(responses)
        )
        fields = [row["id"] for row in result["steps"]]
        if confirmation == '{"valide":true}':
            assert fields == ["p1", "hypothese", "conclusion"]
            assert (
                assess(result["steps"], {"hypothese": ""})["conclusion"]
                == "justification suspendue"
            )
        else:
            assert fields == ["p1"]
    impossible = proposed.replace('"p1"', '"passage inexistant"')
    called = iter((impossible,))
    assert (
        len(
            open_question(
                "Sujet expérimental", [source], generate=lambda *_: next(called)
            )["steps"]
        )
        == 1
    )


def test_contemporary_claim_without_bunge_evidence_stays_an_open_case():
    fact = contemporary_claim(
        "Le système produit du texte.", "https://example.org/report", "2026-11-26"
    )
    dossier = open_question(
        "Question inédite",
        [],
        external=fact,
        generate=lambda *_: pytest.fail("aucun appui textuel"),
    )
    assert dossier["steps"][0]["external"] == [fact]
    assert dossier["steps"][0]["role"] == "Donnée contemporaine à vérifier"
    with pytest.raises(ValueError, match="HTTPS"):
        contemporary_claim("Un fait", "javascript:alert(1)", "2026-11-26")


def test_verified_rivals_keep_their_own_dependencies(monkeypatch):
    monkeypatch.setattr("workshop.core_context", lambda: "Cadre sourcé")
    monkeypatch.setattr("workshop.suggested_nodes", lambda *_: [])
    source = {"book": "book", "page": "19", "title": "Source", "excerpt": "An excerpt"}
    monkeypatch.setitem(CATALOG, "core", ["noyau"])
    monkeypatch.setattr(
        "workshop.proposition",
        lambda key: step(key, "Cadre", "Principe", "Thèse", sources=[source]),
    )
    fact = contemporary_claim("Résultat rapporté", "https://example.org/report", "2026-11-26")
    proposal = {
        "premisses": ["p1", "fait-propose"],
        "hypothese": "Si le mécanisme est nécessaire.",
        "conclusion": "La performance est compatible avec une simple prédiction.",
        "objection": "Quel critère permet de distinguer les deux cas ?",
        "question_ouverte": "Dispose-t-on d’une description du processus ?",
        "alternative": {
            "premisses": ["noyau", "p1", "fait-propose"],
            "hypothese": "Si une prédiction suffit.",
            "conclusion": "La performance est un indice selon ce critère.",
        },
    }

    def generate(prompt, system):
        message = json.loads(prompt)
        if "proposition" in message:
            assert message["question"] == "Quel critère faut-il appliquer ?"
            assert set(message["appuis"]) == {"p1", "fait-propose"}
            if "alternative" in message:
                assert set(message["appuis_alternatifs"]) == {"noyau", "p1", "fait-propose"}
            return '{"valide":true,"alternative_valide":true}'
        assert "noyau" in message["preuves"]
        return json.dumps(proposal)

    dossier = open_question("Quel critère faut-il appliquer ?", [source], generate=generate, external=fact)
    state = assess(dossier["steps"], {"hypothese": ""})
    assert state["conclusion"] == "justification suspendue"
    assert state["conclusion-rivale"] == "disponible"
    assert assess(dossier["steps"], {"noyau": ""})["conclusion-rivale"] == "justification suspendue"
    state = assess(dossier["steps"], {"fait-propose": ""})
    assert state["conclusion"] == state["conclusion-rivale"] == "justification suspendue"

    proposal["alternative"]["premisses"] = ["p1"]
    dossier = open_question("Quel critère faut-il appliquer ?", [source], generate=generate, external=fact)
    assert "conclusion-rivale" not in assess(dossier["steps"], {})

    proposal["premisses"] = ["noyau", "fait-propose"]
    dossier = open_question("Quel critère faut-il appliquer ?", [source], generate=generate, external=fact)
    assert "conclusion" not in assess(dossier["steps"], {})
