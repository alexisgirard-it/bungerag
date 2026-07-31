from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "space" / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "space" / "styles.css").read_text(encoding="utf-8")
SPACE_README = (ROOT / "space" / "README.md").read_text(encoding="utf-8")


def test_public_page_is_a_consultation_interface_not_a_project_report() -> None:
    required = (
        "Questionner les textes.",
        "Une question · une réponse · ses sources",
        'elem_id="chat-shell"',
        "Envoyer la question",
        "Sources citées",
        "ÉTUDE DE CAS",
    )
    forbidden = (
        "Fidélité historique",
        "Couverture du contexte",
        "BENCHMARK LEGACY",
        "Du texte à l'affirmation",
        "Recherche bilingue",
        "Fusion hybride",
        "Reranking",
        "0,935",
        "0,848",
        "40→6",
    )

    assert all(text in APP for text in required)
    assert all(text not in APP for text in forbidden)


def test_styles_only_target_the_minimal_consultation_layout() -> None:
    assert "#chat-shell" in CSS
    assert "#evidence-grid" not in CSS
    assert "#method-section" not in CSS
    assert "#lab-heading" not in CSS


def test_space_readme_routes_technical_detail_away_from_the_demo() -> None:
    assert "centrée sur la consultation" in SPACE_README
    assert "Étude de cas complète" in SPACE_README
    assert "Code, méthode et résultats" in SPACE_README
    assert "0,935" not in SPACE_README
    assert "12 → 5" not in SPACE_README
