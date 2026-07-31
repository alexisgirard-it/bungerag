import pytest

from output_guard import has_long_verbatim_overlap, short_excerpt


def words(count):
    return " ".join(f"mot{index}" for index in range(count))


def test_more_than_twenty_copied_words_are_rejected():
    context = "préfixe " + words(21) + " suffixe"
    answer = "Réponse : " + words(21) + " [1]"
    assert has_long_verbatim_overlap(answer, [context])


def test_twenty_words_or_paraphrase_are_allowed():
    context = words(21)
    assert not has_long_verbatim_overlap(words(20), [context])
    assert not has_long_verbatim_overlap("formulation entièrement différente", [context])


def test_public_excerpt_is_bounded_by_words():
    excerpt = short_excerpt(words(25))
    assert len(excerpt.removesuffix("…").split()) == 20
    assert excerpt.endswith("…")


def test_invalid_limit_is_rejected():
    with pytest.raises(ValueError):
        has_long_verbatim_overlap("texte", ["texte"], max_words=0)
