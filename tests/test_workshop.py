from workshop import (
    assess,
    formal_happiness,
    formal_rights,
    open_question,
    step,
    choose_dossier,
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
