from dataclasses import replace

import pytest

from config import PUBLIC_V1, RESEARCH_40X6, get_config


ENV_KEYS = (
    "RAG_PROFILE",
    "LLM_BACKEND",
    "RAG_TRANSLATOR_BACKEND",
    "RAG_ROUTER_BACKEND",
    "RAG_K_CANDIDATES",
    "RAG_K_FINAL",
    "RAG_PANO_K",
    "RAG_PANO_PER_QUESTION",
    "RAG_PANO_FINAL",
    "RAG_ABSTENTION_THRESHOLD",
    "BUNGE_TABLE",
)


def clear_rag_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_profiles_are_explicit_and_distinct(monkeypatch):
    clear_rag_env(monkeypatch)
    assert get_config().name == "public_v2"
    assert get_config("research_40x6") == RESEARCH_40X6
    assert PUBLIC_V1.config_id != RESEARCH_40X6.config_id


def test_fingerprint_changes_with_behavior():
    changed = replace(PUBLIC_V1, k_final=4)
    assert changed.config_id != PUBLIC_V1.config_id
    assert "secret" not in PUBLIC_V1.public_dict()


def test_explicit_config_ignores_shell_overrides(monkeypatch):
    monkeypatch.setenv("RAG_K_FINAL", "1")
    assert get_config(PUBLIC_V1) is PUBLIC_V1


def test_ollama_makes_utility_calls_local_by_default(monkeypatch):
    clear_rag_env(monkeypatch)
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    config = get_config()
    assert config.generation_backend == "ollama"
    assert config.translator_backend == "ollama"
    assert config.router_backend == "ollama"


def test_unknown_profile_is_rejected(monkeypatch):
    clear_rag_env(monkeypatch)
    with pytest.raises(ValueError, match="profil RAG inconnu"):
        get_config("missing")


def _install_fake_genai(monkeypatch):
    import sys
    import types

    class FakeAPIError(Exception):
        def __init__(self, code, message=""):
            super().__init__(message)
            self.code = code

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    fake_errors = types.SimpleNamespace(APIError=FakeAPIError)
    fake_types = types.SimpleNamespace(
        HttpOptions=lambda **kw: kw,
        HttpRetryOptions=lambda **kw: kw,
    )
    fake_genai = types.SimpleNamespace(
        Client=FakeClient, errors=fake_errors, types=fake_types
    )
    fake_google = types.SimpleNamespace(genai=fake_genai)
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.errors", fake_errors)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    return FakeAPIError


def test_gemini_cascade_falls_back_on_transient_errors(monkeypatch):
    import generate

    generate._MODEL_COOLDOWN.clear()
    FakeAPIError = _install_fake_genai(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    tried = []

    def fake_call(client, model, prompt, system, max_tokens, *, structured):
        tried.append(model)
        if model == "gemini-4-hydrogen":
            raise FakeAPIError(503, "high demand")
        if model == "gemini-3.8-flash":
            return model, ""
        return "gemini-2.5-flash-001", '{"ok": true}'

    monkeypatch.setattr(generate, "_call_gemini_model", fake_call)
    cascade = "gemini/gemini-4-hydrogen,gemini-3.8-flash,gemini-2.5-flash"
    out = generate.generate_json("Q", "S", cascade, 512)
    assert out == '{"ok": true}'
    assert tried == ["gemini-4-hydrogen", "gemini-3.8-flash", "gemini-2.5-flash"]
    assert generate.GEMINI_LAST_MODEL == "gemini-2.5-flash-001"

    # Second call immediately skips models in cooldown (0 ms wasted on 503/empty).
    tried.clear()
    out2 = generate.generate_json("Q2", "S", cascade, 512)
    assert out2 == '{"ok": true}'
    assert tried == ["gemini-2.5-flash"]

    # After cooldown expires, best model is probed again automatically.
    generate._MODEL_COOLDOWN.clear()


def test_gemini_cascade_does_not_swallow_client_400(monkeypatch):
    import generate

    generate._MODEL_COOLDOWN.clear()
    FakeAPIError = _install_fake_genai(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake_call(client, model, prompt, system, max_tokens, *, structured):
        raise FakeAPIError(400, "bad request")

    monkeypatch.setattr(generate, "_call_gemini_model", fake_call)
    with pytest.raises(FakeAPIError):
        generate.generate_json(
            "Q",
            "S",
            "gemini/gemini-4-hydrogen,gemini-2.5-flash",
            512,
        )


def test_public_v3_uses_best_first_cascade():
    from config import PUBLIC_V3
    from generate import parse_gemini_models

    reasoning = parse_gemini_models(PUBLIC_V3.generation_backend)
    fast = parse_gemini_models(PUBLIC_V3.translator_backend)
    assert reasoning[:3] == ["gemini-4-hydrogen", "gemini-3.8-flash", "gemini-2.5-flash"]
    assert "gemini-3.1-flash-lite" in reasoning
    assert all("|" not in model for model in reasoning)
    assert fast[0] == "gemini-3.5-flash-lite"
    assert all("|" not in model for model in fast)
