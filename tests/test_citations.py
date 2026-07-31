import pytest

from citations import validate_citations


def test_valid_indices_are_structurally_accepted():
    result = validate_citations("Une idee [1]. Une autre [2].", 2)
    assert result == {
        "valid": True,
        "indices": [1, 2],
        "invalid_indices": [],
        "reason": None,
    }
    assert "confidence" not in result


@pytest.mark.parametrize("answer, invalid", [
    ("Texte [0]", [0]),
    ("Texte [-1]", [-1]),
    ("Texte [3]", [3]),
])
def test_out_of_range_indices_are_rejected(answer, invalid):
    result = validate_citations(answer, 2)
    assert result["valid"] is False
    assert result["invalid_indices"] == invalid
    assert result["reason"] == "invalid-indices"


def test_grounded_answer_requires_at_least_one_citation():
    result = validate_citations("Texte sans source", 2)
    assert result["valid"] is False
    assert result["reason"] == "missing-citation"


def test_abstention_does_not_require_a_citation():
    result = validate_citations("Absent du corpus.", 0, abstained=True)
    assert result["valid"] is True
    assert result["reason"] == "abstained"


def test_negative_source_count_is_rejected():
    with pytest.raises(ValueError):
        validate_citations("Texte [1]", -1)
