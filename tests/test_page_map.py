import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from page_map import ChunkLocationError, locate_chunks, overlap_length


def test_repeated_prefix_is_not_mistaken_for_previous_passage():
    prefix = "Une même amorce conceptuelle " * 4
    first = prefix + "se termine sur la première page."
    second = prefix + "se termine sur la seconde page."
    text = first + "\n\nTransition.\n\n" + second

    offsets = locate_chunks(text, [first, second])

    assert offsets[0] == (0, len(first))
    assert offsets[1][0] == text.index(second)


def test_overlap_reconstructs_expected_start():
    first = "alpha beta gamma delta"
    second = "gamma delta epsilon zeta"
    text = "alpha beta gamma delta epsilon zeta"

    assert overlap_length(first, second) == len("gamma delta")
    assert locate_chunks(text, [first, second]) == [
        (0, len(first)),
        (len("alpha beta "), len(text)),
    ]


def test_identical_chunks_use_distinct_occurrences():
    chunk = "bloc répété à localiser"
    text = f"{chunk}\n---\n{chunk}"

    offsets = locate_chunks(text, [chunk, chunk])

    assert offsets[0][0] == 0
    assert offsets[1][0] == text.rindex(chunk)


def test_missing_chunk_fails_instead_of_inventing_a_page():
    try:
        locate_chunks("texte disponible", ["passage absent"])
    except ChunkLocationError as exc:
        assert "introuvable" in str(exc)
    else:
        raise AssertionError("un chunk absent doit arrêter le build")
