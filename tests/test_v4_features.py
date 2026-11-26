import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "space") not in sys.path:
    sys.path.insert(0, str(ROOT / "space"))

from atlas_graph import DOMAIN_ORDER, render_mindmap, render_symbol_lexicon  # noqa: E402
from contemporary import fetch_contemporary_fact, validate_public_https_url  # noqa: E402
from library import CATALOG, NODES  # noqa: E402
from workshop import DOSSIERS, debate_turn, step  # noqa: E402


def test_mindmap_renders_all_domains_nodes_and_edges():
    svg_html = render_mindmap("systemisme")
    assert 'class="atlas-mindmap"' in svg_html
    assert 'class="atlas-mindmap-canvas"' in svg_html
    assert 'data-action="zoom-in"' in svg_html
    for dom in DOMAIN_ORDER:
        assert dom in svg_html
    assert svg_html.count('class="atlas-mindmap-node"') == len(NODES)
    assert svg_html.count('class="atlas-mindmap-edge"') == len(CATALOG["relations"])


def test_symbol_lexicon_lists_16_notations_and_filters():
    full = render_symbol_lexicon()
    assert "16 notation(s)" in full
    assert "ℳ = ⟨D, F, I⟩" in full
    assert "σ(x) = ⟨C(x), E(x), S(x)⟩" in full
    filtered = render_symbol_lexicon("psychon")
    assert "C_t(a, b)" in filtered
    assert "Aucune notation" in render_symbol_lexicon("zzzz_inexistant")


def test_contemporary_fact_ssrf_hardening_and_fetch():
    for bad in (
        "http://example.org",
        "javascript:alert(1)",
        "https://localhost/admin",
        "https://127.0.0.1/secret",
        "https://169.254.169.254/latest/meta-data/",
        "https://10.0.0.1/internal",
    ):
        with pytest.raises(ValueError):
            validate_public_https_url(bad, resolve_dns=False)

    class FakeResp:
        def __init__(self, status_code, text="", payload=None):
            self.status_code = status_code
            self.text = text
            self._payload = payload

        def json(self):
            return self._payload

    html_doc = (
        '<html><head><title>Rapport IA 2026</title>'
        '<meta name="description" content="Description vérifiée du modèle.">'
        '<meta property="article:published_time" content="2026-11-12T10:00:00Z"></head></html>'
    )
    res_url = fetch_contemporary_fact(
        "https://example.org/rapport",
        http_get=lambda *a, **k: FakeResp(200, text=html_doc),
        resolve_dns=False,
    )
    assert res_url["published"] == "2026-11-12"
    assert res_url["url"] == "https://example.org/rapport"
    assert "Description vérifiée" in res_url["text"]

    wiki_payload = {
        "title": "Large language model",
        "extract": "A large language model is a statistical model of text.",
        "timestamp": "2026-11-20T08:00:00Z",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Large_language_model"}},
    }
    res_topic = fetch_contemporary_fact(
        "Large language model",
        http_get=lambda *a, **k: FakeResp(200, payload=wiki_payload),
    )
    assert res_topic["published"] == "2026-11-20"
    assert res_topic["url"].startswith("https://en.wikipedia.org/")


def test_multi_provider_cascade_fails_over_to_groq_and_skips_missing_keys(monkeypatch):
    import generate

    generate._MODEL_COOLDOWN.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("GROQ_API_KEY", "q-key")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    class Boom(Exception):
        code = 429

    monkeypatch.setattr(generate, "named_gemini", lambda *a, **k: (_ for _ in ()).throw(Boom("quota")))
    calls = []

    def fake_compat(provider, model, prompt, system, max_tokens, *, structured):
        calls.append((provider, model, structured))
        return '{"ok": true}'

    monkeypatch.setattr(generate, "_call_openai_compat", fake_compat)
    out = generate.generate_json(
        "Q",
        "S",
        "gemini/gemini-4-hydrogen|groq/llama-3.3-70b-versatile|mistral/mistral-small-latest",
        512,
    )
    assert out == '{"ok": true}'
    assert calls == [("groq", "llama-3.3-70b-versatile", True)]
    assert generate.GEMINI_LAST_MODEL == "groq/llama-3.3-70b-versatile"


def test_debate_turn_preserves_suspended_premises_retrieves_and_guards_scope(monkeypatch):
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
    dossier = {
        "title": "Dossier test",
        "steps": [
            step("p1", "Prémisse 1", "Texte 1", "Postulat", sources=[source]),
            step("c1", "Conclusion", "Conséquence", "Conclusion", [["p1"]]),
        ],
        "open": "Question ouverte ?",
    }
    changes = {"p1": ""}

    # Tour 1 : réponse LLM vérifiée citant c1 (nouveau passage retrouvé) + état suspendu conservé.
    def fake_gen(prompt, system):
        payload = json.loads(prompt)
        assert any("suspendue" in x for x in payload["premisses_modifiees_par_lecteur"])
        return json.dumps(
            {
                "reponse": "Avec la prémisse 1 suspendue, la conclusion ne suit plus directement, mais le passage retrouvé rappelle l’assemblage.",
                "appuis": ["c1", "inexistant"],
                "impact_premisses": "Prémisse 1 reste suspendue.",
                "question_suivante": "Quel autre postulat proposez-vous ?",
            }
        )

    hist, notice = debate_turn(
        dossier, changes, [], "Et si j’écarte ce postulat d’assemblage ?",
        search_fn=lambda _q: [source], generate=fake_gen,
    )
    assert not notice and len(hist) == 1
    assert hist[0]["mode"] == "verified-debate"
    assert len(hist[0]["sources"]) == 1
    assert hist[0]["active_changes"] == {"p1": ""}

    # Tour 2 : demande d’avis posthume -> refusée même en plein débat multi-tours !
    hist2, notice2 = debate_turn(
        dossier, changes, hist, "Quel est l’avis personnel que Bunge a publié sur Gemini 4 ?",
        search_fn=lambda _q: [source], generate=fake_gen,
    )
    assert not notice2 and len(hist2) == 2
    assert hist2[1]["mode"] == "scope-guard"

    # Tour 3 : mode sans génération (quota épuisé) -> reste utile avec les passages retrouvés.
    hist3, notice3 = debate_turn(
        dossier, changes, hist2, "Montre un autre passage sur l’émergence.",
        search_fn=lambda _q: [source], generate=None,
    )
    assert not notice3 and len(hist3) == 3
    assert hist3[2]["mode"] == "retrieval-only"
    assert len(hist3[2]["sources"]) == 1
    assert len(DOSSIERS) == 21
