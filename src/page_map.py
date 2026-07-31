"""Localisation déterministe des chunks dans le texte source.

Le premier prototype cherchait seulement les 60 premiers caractères de
chaque chunk. Deux passages commençant de la même façon pouvaient donc être
rattachés à la mauvaise page. Ce module cherche le chunk complet et utilise
le chevauchement avec le chunk précédent pour choisir la bonne occurrence.

Il ne dépend d'aucune bibliothèque du pipeline afin de rester testable en CI.
"""

from __future__ import annotations


class ChunkLocationError(ValueError):
    """Le texte exact d'un chunk est introuvable dans le document recollé."""


def overlap_length(left: str, right: str) -> int:
    """Longueur du plus grand suffixe de ``left`` préfixant ``right``.

    Un chevauchement égal à la totalité des deux chaînes est ignoré : deux
    chunks identiques successifs doivent être localisés sur deux occurrences,
    et non sur la même position.
    """

    maximum = min(len(left), len(right))
    if left == right:
        maximum -= 1
    for size in range(maximum, 0, -1):
        if left[-size:] == right[:size]:
            return size
    return 0


def _occurrences(text: str, needle: str, start: int) -> list[int]:
    positions: list[int] = []
    cursor = max(0, start)
    while True:
        cursor = text.find(needle, cursor)
        if cursor < 0:
            return positions
        positions.append(cursor)
        cursor += 1


def locate_chunks(text: str, chunks: list[str]) -> list[tuple[int, int]]:
    """Renvoie les offsets ``[début, fin)`` exacts de chunks ordonnés.

    Le résultat est monotone par position de début. Une absence de
    correspondance exacte est une erreur explicite : produire une page
    plausible mais fausse serait plus dangereux que stopper le build.
    """

    offsets: list[tuple[int, int]] = []
    previous = ""
    previous_start = -1
    previous_end = 0

    for index, chunk in enumerate(chunks):
        if not chunk:
            raise ChunkLocationError(f"chunk {index} vide")

        overlap = overlap_length(previous, chunk) if previous else 0
        expected = max(0, previous_end - overlap)

        if text.startswith(chunk, expected) and expected > previous_start:
            start = expected
        else:
            candidates = [
                pos for pos in _occurrences(text, chunk, max(0, expected - 4096))
                if pos > previous_start
            ]
            if not candidates:
                # Dernier filet pour les très grands chevauchements. On garde
                # la contrainte de monotonie afin de ne jamais revenir vers une
                # occurrence antérieure partageant le même préfixe.
                candidates = [
                    pos for pos in _occurrences(text, chunk, 0)
                    if pos > previous_start
                ]
            if not candidates:
                preview = " ".join(chunk[:80].split())
                raise ChunkLocationError(
                    f"chunk {index} introuvable après l'offset "
                    f"{previous_start}: {preview!r}"
                )
            start = min(candidates, key=lambda pos: (abs(pos - expected), pos))

        end = start + len(chunk)
        if text[start:end] != chunk:
            raise ChunkLocationError(f"chunk {index} localisé sans égalité exacte")
        offsets.append((start, end))
        previous, previous_start, previous_end = chunk, start, end

    return offsets
