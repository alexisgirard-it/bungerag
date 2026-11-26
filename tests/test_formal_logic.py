from formal_logic import (
    FOL_VERIFIERS,
    fol_factual_model,
    fol_semantic_synonymy,
    fol_world_uniqueness,
)


def test_fol_world_uniqueness_exhausts_finite_relations_and_finds_countermodel():
    proof = fol_world_uniqueness()
    assert proof["valid"] is True
    assert proof["counterexamples"] == 0
    assert proof["models_checked"] > 100
    cm = proof["countermodel"]
    assert cm is not None and cm["m1"] != cm["m2"]
    assert (cm["m1"], cm["m2"]) in cm["relation"]
    assert (cm["m2"], cm["m1"]) in cm["relation"]


def test_fol_semantic_synonymy_refutes_coreference_sufficiency():
    proof = fol_semantic_synonymy()
    assert proof["valid"] is True
    assert proof["counterexamples"] == 0
    cm = proof["countermodel"]
    assert cm["R"]["c₁"] == cm["R"]["c₂"]
    assert cm["S"]["c₁"] != cm["S"]["c₂"]
    assert cm["Syn(c₁, c₂)"] is False


def test_fol_factual_model_requires_domain_and_interpretation():
    proof = fol_factual_model()
    assert proof["valid"] is True
    assert proof["counterexamples"] == 0
    cm = proof["countermodel"]
    assert cm["Form(m)"] is True and cm["MF(m)"] is False
    assert set(FOL_VERIFIERS) == {"unique", "non-synonymie", "formalisation-insuffisante"}
