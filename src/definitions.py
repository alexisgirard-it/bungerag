"""Complément lexical pour les demandes de définition."""

import re

INTENT = re.compile(
    r"qu['’]est[- ]ce qu|qu['’]appelle|que (?:désigne|signifie|veut dire)|qu['’]entend|défini[rt]|définition|what is|define\b",
    re.I,
)
STOP = set(
    "a an and are as at according bunge by call called concept conception define defined definition describe do does for in is mario meaning means of on or term the to understand what which how his philosophical philosophy".split()
)


def terms_for(question, english):
    if not INTENT.search(question):
        return []
    return list(
        dict.fromkeys(
            w
            for w in re.findall(r"[a-z]+", english.lower())
            if w not in STOP and len(w) > 2
        )
    )[:6]


def strength(row, terms):
    """Une relation définitoire doit porter sur les mots recherchés."""
    s = re.sub(r"[*_#]+", "", row["text"].lower())
    term_expression = r"\b" + r"\s+".join(re.escape(t) for t in terms) + r"s?\b"
    exact = rf"(?:called (?:a |an )?|(?:we )?define (?:a |an )?){term_expression}|{term_expression} (?:is defined as|denotes|means)"
    if re.search(exact, s):
        return 3
    for sentence in re.split(r"(?<=[.!?])\s+|\n\n", s):
        words = set(re.findall(r"[a-z]+", sentence))
        if not all(t in words or t + "s" in words for t in terms):
            continue
        if re.search(
            r"\b(?:is (?:called|defined|a|an|the)|we (?:call|define)|by definition|is any|means)\b",
            sentence,
        ):
            return 2
        if "dictionary" in row["book"]:
            return 1
    return 0


def candidates(question, english, hits, lookup, table):
    terms = terms_for(question, english)
    if not terms:
        return hits, []
    extra = lookup("definition " + " ".join(terms), mode="bm25", k=8, table=table)
    ranked = sorted(
        ((strength(row, terms), i, row) for i, row in enumerate(extra)),
        key=lambda item: (-item[0], item[1]),
    )
    chosen = [(score, row) for score, _, row in ranked if score][:4]
    merged = {row["chunk_id"]: row for row in hits}
    for _, row in chosen:
        merged.setdefault(row["chunk_id"], row)
    return list(merged.values()), [
        row["chunk_id"] for score, row in chosen if score >= 2
    ]
