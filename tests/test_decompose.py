import pytest

import decompose


def test_valid_direct_route(monkeypatch):
    monkeypatch.setattr(decompose, "generate", lambda *a, **k: '{"mode":"direct"}')
    assert decompose.analyse("Question", backend="ollama") == {"mode": "direct"}


def test_valid_panoramic_route_is_normalized(monkeypatch):
    raw = (
        '{"mode":"panoramique","sous_questions":['
        '{"fr":" A ","en":" A en "},{"fr":"B","en":"B en"}]}'
    )
    monkeypatch.setattr(decompose, "generate", lambda *a, **k: raw)
    assert decompose.analyse("Question", backend="ollama") == {
        "mode": "panoramique",
        "sous_questions": [
            {"fr": "A", "en": "A en"},
            {"fr": "B", "en": "B en"},
        ],
    }


@pytest.mark.parametrize("raw", [
    "pas de json",
    '{"mode":"inconnu"}',
    '{"mode":"panoramique","sous_questions":[]}',
    '{"mode":"panoramique","sous_questions":[{"fr":"A"},{"fr":"B","en":"B"}]}',
    '{"mode":"panoramique","sous_questions":["A","B"]}',
])
def test_invalid_router_output_falls_back_to_direct(monkeypatch, raw):
    monkeypatch.setattr(decompose, "generate", lambda *a, **k: raw)
    assert decompose.analyse("Question", backend="ollama") == {"mode": "direct"}


def test_provider_failure_is_inside_fallback(monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError("provider down")

    monkeypatch.setattr(decompose, "generate", fail)
    assert decompose.analyse("Question", backend="ollama") == {"mode": "direct"}


def test_configured_backend_is_forwarded(monkeypatch):
    seen = {}

    def fake_generate(*args, **kwargs):
        seen["backend"] = kwargs["backend"]
        return '{"mode":"direct"}'

    monkeypatch.setattr(decompose, "generate", fake_generate)
    decompose.analyse("Question", backend="ollama")
    assert seen["backend"] == "ollama"
