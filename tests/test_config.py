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
    assert get_config().name == "public_v1"
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
