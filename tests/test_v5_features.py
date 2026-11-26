import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "space") not in sys.path:
    sys.path.insert(0, str(ROOT / "space"))

from library import DATABASE, NODES, read_page_content  # noqa: E402
from presenter import render_answer_html  # noqa: E402
from wiki_concepts import CONCEPT_ALIASES, annotate_concepts, render_concept_wiki  # noqa: E402
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


def test_annotate_concepts_adds_blue_wiki_links_and_preserves_html_and_tags():
    assert all(k in NODES for k in CONCEPT_ALIASES)
    html_in = (
        "<p>Pour Bunge, le matérialisme émergentiste s’oppose au holisme "
        "et repose sur le systémisme. Voir <a href='#source-1'>[1]</a> et "
        "<code>systémisme</code>.</p>"
    )
    out = annotate_concepts(html_in)
    assert 'class="wiki-link"' in out
    assert 'data-wiki-concept="cadre-emergentiste"' in out
    assert 'data-wiki-concept="ni-holisme-ni-atomisme"' in out
    assert 'data-wiki-concept="systemisme"' in out
    # Ne pas casser les liens existants ni les blocs <code>
    assert "<a href='#source-1'>[1]</a>" in out
    assert "<code>systémisme</code>" in out
    # Exclure la notion courante sur sa propre page Wikipédia
    excluded = annotate_concepts("<p>Le systémisme est central.</p>", exclude_key="systemisme")
    assert 'data-wiki-concept="systemisme"' not in excluded


def test_render_answer_html_links_citations_and_concepts():
    out = render_answer_html(
        "Pour Bunge, l’**émergence** distingue un système d’un agrégat [1].",
        source_count=2,
    )
    assert 'href="#source-1"' in out
    assert 'class="cite-badge"' in out
    assert 'class="wiki-link"' in out
    assert 'data-wiki-concept="postulat-emergence"' in out


def test_render_concept_wiki_builds_infobox_and_structured_relations(monkeypatch):
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
    monkeypatch.setattr("workshop.node_source", fake_node_source)
    monkeypatch.setattr("wiki_concepts.chapter_formal_markers", lambda *a, **k: [])
    wiki = render_concept_wiki("systemisme")
    assert 'class="wiki-article"' in wiki
    assert 'class="wiki-infobox"' in wiki
    assert "Lire dans le livre" in wiki
    assert 'class="wiki-link"' in wiki
    assert "Dossiers d’Atelier associés" in wiki


@pytest.mark.skipif(not DATABASE.is_file(), reason="lecture.sqlite absente en CI")
def test_read_page_content_returns_full_page_and_chapter_navigation():
    data = read_page_content("treatise-4-ontology-2-world-of-systems-1979", "46")
    assert data is not None
    assert data["paragraphs"]
    assert data["prev_page"] == "45"
    assert data["next_page"] == "47"
    assert len(data["chapter_pages"]) >= 10
    assert data["chapter"] == "System"
