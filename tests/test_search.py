import search


class FakeQuery:
    def __init__(self):
        self.vector_value = None
        self.text_value = None
        self.reranker = None
        self.limit_value = None

    def vector(self, value):
        self.vector_value = value
        return self

    def text(self, value):
        self.text_value = value
        return self

    def rerank(self, value):
        self.reranker = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def to_list(self):
        return [{"ok": True}]


class FakeTable:
    def __init__(self):
        self.calls = []
        self.last_query = None

    def search(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        self.last_query = FakeQuery()
        return self.last_query


def test_hybrid_uses_french_dense_and_english_text(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(search, "_open_table", lambda name: table)
    monkeypatch.setattr(search, "embed_query", lambda value: f"vector:{value}")
    marker = object()
    monkeypatch.setattr(search, "_rrf_reranker", lambda: marker)

    result = search.search(
        mode="hybrid",
        k=7,
        table="bunge_512",
        dense_query="question francaise",
        text_query="english question",
    )

    assert result == [{"ok": True}]
    assert table.last_query.vector_value == "vector:question francaise"
    assert table.last_query.text_value == "english question"
    assert table.last_query.reranker is marker
    assert table.last_query.limit_value == 7


def test_legacy_single_query_call_remains_supported(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(search, "_open_table", lambda name: table)
    monkeypatch.setattr(search, "embed_query", lambda value: f"vector:{value}")
    monkeypatch.setattr(search, "_rrf_reranker", object)

    search.search("same query", "hybrid", 5, "bunge_512")
    assert table.last_query.vector_value == "vector:same query"
    assert table.last_query.text_value == "same query"
