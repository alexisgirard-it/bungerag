import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "space") not in sys.path:
    sys.path.insert(0, str(ROOT / "space"))

from deductive_tree import TREE_BRANCHES, all_tree_node_ids, render_deductive_tree  # noqa: E402
from library import DATABASE, NODES, read_page_content  # noqa: E402
from presenter import render_answer_html  # noqa: E402
from wiki_concepts import (  # noqa: E402
    CONCEPTS,
    annotate_concepts,
    find_concept_for_query,
    render_concept_wiki,
)
from workshop import choose_dossier, order_argument_steps, step  # noqa: E402


def test_pedagogical_ordering_puts_definitions_before_postulates_theorems_and_conclusions():
    steps = [
        step("c1", "Conclusion", "Donc X.", "Conclusion", [["t1"]]),
        step("b1", "Biosystémisme", "Vie.", "Thèse"),
        step("t1", "Théorème 1", "Il suit que...", "Théorème", [["p1"]]),
        step("p1", "Postulat 1.5 · Émergence", "Émergence par assemblage.", "Postulat", [["d1"]]),
        step("d1", "Définition de l’émergence", "Une propriété nouvelle.", "Définition"),
    ]
    ordered = order_argument_steps(steps, "Qu'est-ce que l'émergence pour Bunge ?")
    ids = [s["id"] for s in ordered]
    assert ids[0] == "d1"
    assert ids.index("d1") < ids.index("p1") < ids.index("t1") < ids.index("c1")


def test_emergence_question_routes_to_systemism_dossier():
    assert choose_dossier("Qu'est-ce que l'émergence pour Bunge ?") == "systemisme"
    assert choose_dossier("Qu’est-ce que l’émergence ?") == "systemisme"


def test_concepts_catalog_is_complete_coherent_and_all_links_valid():
    assert len(CONCEPTS) >= 60
    for cid, c in CONCEPTS.items():
        assert c["status"] in ("bunge", "standard")
        assert c["definition"].strip() and c["bunge_view"].strip()
        for rel in c.get("related_concepts", ()):
            assert rel in CONCEPTS, f"{cid} -> missing related concept {rel}"
        for nid in c.get("nodes", ()):
            assert nid in NODES, f"{cid} -> missing node {nid}"


def test_deductive_tree_covers_100_percent_of_all_113_propositions_without_duplicates():
    flat = [nid for branches in TREE_BRANCHES.values() for _, ids in branches for nid in ids]
    assert len(flat) == len(set(flat)), "Duplicate node in TREE_BRANCHES"
    assert all_tree_node_ids() == set(NODES)
    assert len(flat) == 113


def test_annotate_concepts_underlines_philosophie_systemes_and_preserves_html():
    html_in = (
        "<p>Le systémisme est la philosophie qui sous-tend la théorie générale "
        "des systèmes, face au holisme. Voir <a href='#source-1'>[1]</a> et "
        "<code>systémisme</code>.</p>"
    )
    out = annotate_concepts(html_in)
    assert 'data-wiki-concept="systemisme"' in out
    assert 'data-wiki-concept="philosophie"' in out
    assert 'data-wiki-concept="systeme"' in out
    assert 'data-wiki-concept="holisme"' in out
    assert "<a href='#source-1'>[1]</a>" in out
    assert "<code>systémisme</code>" in out
    excluded = annotate_concepts("<p>Le systémisme est central.</p>", exclude_key="systemisme")
    assert 'data-wiki-concept="systemisme"' not in excluded
    assert find_concept_for_query("Qu'est-ce que l'émergence pour Bunge ?") == "emergence"


def test_render_answer_html_links_citations_and_concepts():
    out = render_answer_html(
        "Pour Bunge, l’**émergence** distingue un système d’un agrégat [1].",
        source_count=2,
    )
    assert 'href="#source-1"' in out
    assert 'class="cite-badge"' in out
    assert 'data-wiki-concept="emergence"' in out
    assert 'data-wiki-concept="systeme"' in out


def test_render_concept_and_proposition_pages_and_deductive_tree(monkeypatch):
    def fake_node_source(key):
        src = NODES[key]["source"]
        return {
            "id": 1,
            "book": src["book"],
            "page": str(src["page"]),
            "folio": src.get("folio", src["page"]),
            "chapter": "System",
            "year": 1979,
            "title": "Treatise 4",
            "authors": "Mario Bunge",
            "file": "treatise-4.pdf",
            "edition": src["edition"],
            "edition_label": "Reidel, 1979",
            "excerpt": src["quote"],
            "pages": f"p. {src.get('folio', src['page'])} du livre · PDF p. {src['page']}",
        }

    monkeypatch.setattr("wiki_concepts.node_source", fake_node_source)
    monkeypatch.setattr("deductive_tree.node_source", fake_node_source)
    monkeypatch.setattr("workshop.node_source", fake_node_source)
    monkeypatch.setattr("wiki_concepts.chapter_formal_markers", lambda *a, **k: [])

    # Page concept défini par Bunge
    sys_page = render_concept_wiki("systemisme")
    assert "Défini / thématisé par Mario Bunge" in sys_page
    assert 'data-wiki-concept="philosophie"' in sys_page
    assert "Définitions, postulats, thèses et théorèmes associés" in sys_page

    # Page concept standard cohérent avec Bunge
    phil_page = render_concept_wiki("philosophie")
    assert "Sens philosophique / scientifique usuel (cohérent avec Bunge)" in phil_page
    assert "Chez Mario Bunge" in phil_page

    # Page proposition formelle (postulat / théorème)
    prop_page = render_concept_wiki("postulat-emergence")
    assert 'class="wiki-article"' in prop_page
    assert 'class="wiki-infobox"' in prop_page

    # Arbre déductif complet + filtres
    full_tree = render_deductive_tree()
    assert "113 proposition(s) affichée(s)" in full_tree
    assert "Ontologie" in full_tree and "Éthique" in full_tree
    ont_postulates = render_deductive_tree("Ontologie", "postulat")
    assert "Postulat 1.5" in ont_postulates
    assert "Éthique" not in ont_postulates


@pytest.mark.skipif(not DATABASE.is_file(), reason="lecture.sqlite absente en CI")
def test_read_page_content_returns_full_page_and_chapter_navigation():
    data = read_page_content("treatise-4-ontology-2-world-of-systems-1979", "46")
    assert data is not None
    assert data["paragraphs"]
    assert data["prev_page"] == "45"
    assert data["next_page"] == "47"
    assert len(data["chapter_pages"]) >= 10
    assert data["chapter"] == "System"


def test_external_step_does_not_say_source_dans_bunge(monkeypatch):
    import importlib
    import types

    if "gradio" not in sys.modules:
        fake_gr = types.SimpleNamespace(
            Dropdown=lambda *a, **k: dict(args=a, kwargs=k),
            Tabs=lambda **k: k,
        )
        monkeypatch.setitem(sys.modules, "gradio", fake_gr)
    reader = sys.modules.get("reader") or importlib.import_module("reader")
    fake_src = {
        "book": "b",
        "page": "1",
        "title": "Treatise",
        "year": 1979,
        "authors": "Mario Bunge",
        "file": "",
        "pages": "p. 1",
        "excerpt": "Excerpt.",
    }
    monkeypatch.setattr(reader, "node_source", lambda _k: fake_src)

    ext_step = step("ext1", "Modèle Llama", "Fait daté", "Fait contemporain daté")
    ext_step["external"] = [{"title": "Llama 3.1", "url": "https://example.org/llama"}]
    html_out = reader.dossier_view(
        {"title": "Test", "steps": [ext_step], "objection": "Obj", "open": "Q?"},
        {},
        local=None,
    )
    assert "Voir la source externe datée" in html_out
    assert "Voir la source dans Bunge" not in html_out

    both_step = step("both1", "Fait hybride", "Texte", "Thèse")
    both_step["sources"] = [fake_src]
    both_step["external"] = [{"title": "Llama 3.1", "url": "https://example.org/llama"}]
    html_both = reader.dossier_view(
        {"title": "Test", "steps": [both_step], "objection": "Obj", "open": "Q?"},
        {},
        local=None,
    )
    assert "Voir les sources (Bunge et source externe datée)" in html_both


def test_free_form_debate_turn_without_dossier_and_with_external_source(monkeypatch):
    import json
    from workshop import debate_turn

    source = {
        "book": "treatise-4-ontology-2-world-of-systems-1979",
        "page": "46",
        "folio": "30",
        "title": "Treatise 4",
        "year": 1979,
        "authors": "Bunge",
        "file": "t4.pdf",
        "edition": "ed",
        "excerpt": "Every assembly process is accompanied by the emergence of some properties",
        "pages": "p. 30 du livre · PDF p. 46",
    }
    monkeypatch.setattr("workshop.suggested_nodes", lambda *a, **k: [])
    monkeypatch.setattr("workshop.on_page", lambda *a, **k: [])
    monkeypatch.setattr("workshop.core_context", lambda: "Cadre sourcé")
    monkeypatch.setattr("workshop.choose_dossier", lambda *a, **k: None)

    def fake_gen(prompt, system):
        payload = json.loads(prompt)
        assert "source_externe_datee_hors_bunge" in payload
        return json.dumps(
            {
                "reponse": "Selon Bunge, les propriétés émergentes apparaissent par assemblage.",
                "appuis": ["c1"],
                "impact_premisses": "La source externe reste distincte des textes de Bunge.",
                "question_suivante": "Quel mécanisme biologique ou technique invoquez-vous ?",
            }
        )

    ext = {"title": "Rapport externe", "url": "https://example.org/r", "text": "Fait récent"}
    hist, notice = debate_turn(
        None,
        {},
        [],
        "Est-ce que l’émergence explique tout ?",
        search_fn=lambda _q: [source],
        generate=fake_gen,
        external=ext,
    )
    assert not notice and len(hist) == 1
    assert hist[0]["mode"] == "verified-debate"
    assert hist[0]["external"] == ext
    assert len(hist[0]["sources"]) == 1
