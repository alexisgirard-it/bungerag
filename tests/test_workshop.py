from workshop import assess, formal_rights, open_question, step, choose_dossier


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


def test_unrelated_ai_question_does_not_open_the_curated_llm_dossier():
    assert (
        choose_dossier("Comment un modèle de langage pourrait-il comprendre ?") == "ia"
    )
    assert choose_dossier("Quelle GPU est utilisée pour entraîner Gemini 4 ?") is None
    assert not open_question("Zzzz", [])["steps"]
