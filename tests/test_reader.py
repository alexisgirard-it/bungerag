import importlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "space") not in sys.path:
    sys.path.insert(0, str(ROOT / "space"))

from library import CATALOG, NODES  # noqa: E402
from workshop import DOSSIERS  # noqa: E402


def _load_reader(monkeypatch):
    if "gradio" not in sys.modules:
        try:
            importlib.import_module("gradio")
        except ImportError:
            fake_gr = types.SimpleNamespace(
                Dropdown=lambda *args, **kwargs: dict(args=args, **kwargs),
                Tabs=lambda **kwargs: kwargs,
            )
            monkeypatch.setitem(sys.modules, "gradio", fake_gr)
    if "reader" in sys.modules:
        return sys.modules["reader"]
    return importlib.import_module("reader")


def _fake_source(key="systemisme"):
    node = NODES[key]
    src = node["source"]
    return {
        "id": 1,
        "book": src["book"],
        "page": str(src["page"]),
        "folio": src["folio"],
        "chapter": "System",
        "year": 1979,
        "title": "Treatise 4",
        "authors": "Mario Bunge",
        "file": "treatise-4.pdf",
        "edition": src["edition"],
        "edition_label": "Reidel, 1979",
        "excerpt": src["quote"],
        "pages": f"p. {src['folio']} du livre · PDF p. {src['page']}",
        **({"voice": src["voice"]} if src.get("voice") not in (None, "Bunge") else {}),
    }


def test_card_escapes_html_and_displays_cited_voice(monkeypatch):
    reader = _load_reader(monkeypatch)
    src = _fake_source("emerson-fatum")
    src["excerpt"] = "<script>alert(1)</script> quote"
    rendered = reader.card(src, local=None)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "Auteur cité · Emerson" in rendered
    assert "Reidel, 1979" in rendered


def test_atlas_view_renders_notation_links_and_comparison(monkeypatch):
    reader = _load_reader(monkeypatch)
    monkeypatch.setattr(reader, "node_source", _fake_source)
    monkeypatch.setattr(reader, "read_marker", lambda _k: None)
    html_out, dropdown, compare = reader.atlas_view("couple-signification", local=None)
    assert "ℳ(c) = ⟨𝒮(c), ℛ(c)⟩" in html_out
    assert 'class="concept-map"' in html_out
    assert dropdown["interactive"] is True
    assert "Lecture éditoriale" in compare

    missing_html, missing_dd, _ = reader.atlas_view("inexistant", local=None)
    assert "Choisissez une notion" in missing_html
    assert missing_dd["choices"] == []


def test_dossier_view_renders_suspension_propositional_and_fol_proofs(monkeypatch):
    reader = _load_reader(monkeypatch)
    monkeypatch.setattr("workshop.node_source", _fake_source)
    monkeypatch.setattr(reader, "node_source", _fake_source)
    dossier = DOSSIERS["monde"]()
    html_initial = reader.dossier_view(dossier, {}, local=None)
    assert "Vérifier le fragment formel (propositionnel)" in html_initial
    assert "Vérifier la preuve du premier ordre" in html_initial
    assert "∀x∀y" in html_initial
    assert "Contre-modèle sans" in html_initial
    assert "Cadre philosophique de cette lecture" in html_initial

    html_suspended = reader.dossier_view(
        dossier, {"supremum": "", "autre-preuve": ""}, local=None
    )
    assert "justification suspendue" in html_suspended
    assert "à rétablir" in html_suspended


def test_every_atlas_node_has_at_least_one_relation():
    connected = {
        k
        for link in CATALOG["relations"]
        for k in (link["origin"], link["target"])
    }
    assert set(NODES) == connected
