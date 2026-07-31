import decompose
import rag
from citations import CITATION_FAILURE_ANSWER
from config import PUBLIC_V1, get_config
from schemas import RESULT_KEYS


class FakeReranker:
    def __init__(self, scores=None):
        self.scores = scores

    def score(self, query, docs):
        if self.scores is not None:
            return self.scores[:len(docs)]
        return [0.9] * len(docs)


def hit(chunk_id="book:00001", text="Passage utile"):
    return {
        "chunk_id": chunk_id,
        "book": chunk_id.split(":")[0],
        "title": "Livre",
        "page_start": "10",
        "page_end": "11",
        "text": text,
    }


def patch_direct_dependencies(monkeypatch, *, hits, answer="Reponse [1]"):
    seen = {}

    monkeypatch.setattr(
        rag, "reformulate_en", lambda question, config=None, backend=None: "English"
    )

    def fake_search(*args, **kwargs):
        seen["search"] = kwargs
        return [item.copy() for item in hits]

    monkeypatch.setattr(rag, "search", fake_search)
    monkeypatch.setattr(rag, "get_reranker", lambda: FakeReranker())

    def fake_generate(*args, **kwargs):
        seen["generation_backend"] = kwargs["backend"]
        return answer

    monkeypatch.setattr(rag, "generate", fake_generate)
    return seen


def assert_contract(result):
    assert set(result) == RESULT_KEYS
    assert set(result["timings"]) == {"translate", "retrieve", "generate"}


def test_direct_path_separates_query_languages_and_has_full_contract(monkeypatch):
    seen = patch_direct_dependencies(monkeypatch, hits=[hit()])
    result = rag.ask("Question francaise", config=PUBLIC_V1)

    assert_contract(result)
    assert seen["search"]["dense_query"] == "Question francaise"
    assert seen["search"]["text_query"] == "English"
    assert seen["generation_backend"] == "gemini"
    assert result["mode"] == "direct"
    assert result["abstained"] is None
    assert result["citation_validation"]["valid"] is True
    assert result["config_id"] == PUBLIC_V1.config_id


def test_pre_generation_abstention_keeps_full_contract(monkeypatch):
    patch_direct_dependencies(monkeypatch, hits=[])
    monkeypatch.setattr(
        rag,
        "get_reranker",
        lambda: (_ for _ in ()).throw(AssertionError("reranker should not load")),
    )
    result = rag.ask("Question", config=PUBLIC_V1)

    assert_contract(result)
    assert result["abstained"] == "pre-generation"
    assert result["contexts"] == []
    assert result["sources"] == []
    assert result["citation_validation"]["valid"] is True


def test_invalid_citation_fails_safely_without_confidence(monkeypatch):
    patch_direct_dependencies(monkeypatch, hits=[hit()], answer="Reponse [2]")
    result = rag.ask("Question", config=PUBLIC_V1)

    assert_contract(result)
    assert result["answer"] == CITATION_FAILURE_ANSWER
    assert result["abstained"] == "citation-validation"
    assert result["citation_validation"]["valid"] is False
    assert "confidence" not in result["citation_validation"]


def test_long_verbatim_copy_is_removed_before_publication(monkeypatch):
    copied = " ".join(f"mot{index}" for index in range(21))
    patch_direct_dependencies(
        monkeypatch,
        hits=[hit(text=f"préface {copied} conclusion")],
        answer=f"{copied} [1]",
    )
    result = rag.ask("Question", config=PUBLIC_V1)

    assert result["answer"] == rag.OUTPUT_FAILURE_ANSWER
    assert result["abstained"] == "output-validation"
    assert result["citation_validation"]["reason"] == "verbatim-overlap"
    assert len(result["sources"][0]["extrait"].removesuffix("…").split()) == 20


def test_panoramic_path_separates_each_language_and_detects_llm_abstention(monkeypatch):
    seen = []

    def fake_search(*args, **kwargs):
        seen.append((kwargs["dense_query"], kwargs["text_query"]))
        index = len(seen)
        return [hit(f"book{index}:00001", f"Passage {index}")]

    monkeypatch.setattr(rag, "search", fake_search)
    monkeypatch.setattr(rag, "get_reranker", lambda: FakeReranker())
    monkeypatch.setattr(rag, "generate", lambda *a, **k: "Absent du corpus.")
    questions = [
        {"fr": "Aspect A", "en": "Aspect A EN"},
        {"fr": "Aspect B", "en": "Aspect B EN"},
    ]

    result = rag.ask_decomposed("Vue generale", questions, config=PUBLIC_V1)

    assert_contract(result)
    assert seen == [("Aspect A", "Aspect A EN"), ("Aspect B", "Aspect B EN")]
    assert result["mode"] == "panoramique"
    assert result["abstained"] == "llm"
    assert result["question_en"] is None
    assert result["sous_questions"] == ["Aspect A", "Aspect B"]


def test_panoramic_pre_generation_abstention_has_same_contract(monkeypatch):
    monkeypatch.setattr(rag, "search", lambda *a, **k: [])
    monkeypatch.setattr(rag, "get_reranker", lambda: FakeReranker())
    result = rag.ask_decomposed(
        "Vue generale",
        [{"fr": "A", "en": "A EN"}, {"fr": "B", "en": "B EN"}],
        config=PUBLIC_V1,
    )
    assert_contract(result)
    assert result["abstained"] == "pre-generation"
    assert result["contexts"] == []


def test_ollama_profile_is_used_for_translation_and_router(monkeypatch):
    for key in ("RAG_PROFILE", "RAG_TRANSLATOR_BACKEND", "RAG_ROUTER_BACKEND"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    seen = {}

    def fake_generate(*args, **kwargs):
        seen["translator"] = kwargs["backend"]
        return "English"

    monkeypatch.setattr(rag, "generate", fake_generate)
    config = get_config()
    assert rag.reformulate_en("Question", config=config) == "English"

    def fake_analyse(question, backend=None):
        seen["router"] = backend
        return {"mode": "direct"}

    monkeypatch.setattr(decompose, "analyse", fake_analyse)
    monkeypatch.setattr(rag, "ask", lambda question, config=None: config)
    routed_config = rag.ask_smart("Question")

    assert seen == {"translator": "ollama", "router": "ollama"}
    assert routed_config.generation_backend == "ollama"
