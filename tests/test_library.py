import sqlite3

from library import formal_hits, lexical_match


def test_literal_matching_checks_words_after_stemming():
    assert lexical_match("It is called a psychon.", "called a psychon")
    assert not lexical_match("It is calling a psychon.", "called a psychon")
    assert lexical_match("‘The book of Nature’", "the book of nature")


def test_numbered_lemma_lookup_uses_full_number_and_the_kind():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE labels(page_id,kind,number,excerpt);
        CREATE TABLE pages(id,book,chapter);
        CREATE TABLE books(book,title);
        INSERT INTO books VALUES ('ethics','Ethics');
        INSERT INTO pages VALUES (56,'ethics','Values');
        INSERT INTO labels VALUES
          (56,'postulate','2.1','The full realization'),
          (56,'theorem','2.1','Nobody can be'),
          (56,'postulate','2.10','Something else');
    """)
    assert [row["text"] for row in formal_hits(db, "Où est le postulat 2.1 ?")] == [
        "The full realization"
    ]


def test_attribution_uses_the_quote_and_edition():
    from library import NODES, quotation_voice

    loc = NODES["emerson-fatum"]["source"]
    assert (
        quotation_voice(loc["book"], loc["page"], loc["edition"], loc["quote"])
        == "Emerson"
    )
    assert not quotation_voice(loc["book"], loc["page"], "autre édition", loc["quote"])
    assert not quotation_voice(
        loc["book"],
        loc["page"],
        loc["edition"],
        "an unknowable and inescapable Destiny",
    )
