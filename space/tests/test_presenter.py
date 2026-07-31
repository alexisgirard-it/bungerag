from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SPACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SPACE_DIR))

from presenter import link_citations, present_result, render_sources  # noqa: E402


class PresenterTests(unittest.TestCase):
    def test_legacy_result_is_whitelisted_and_contexts_never_leak(self):
        raw = {
            "answer": "Le système est composé [1].",
            "sources": [
                {
                    "titre": "Treatise",
                    "pages": "p. 42",
                    "extrait": "A system is a complex object.",
                    "score": 0.98,
                }
            ],
            "contexts": ["FULL COPYRIGHTED CONTEXT"],
            "question_en": "private translation",
            "mode": "direct",
        }
        view = present_result(raw, elapsed_seconds=12.4)
        payload = view.public_payload()
        serialized = json.dumps(payload)
        self.assertNotIn("contexts", serialized)
        self.assertNotIn("FULL COPYRIGHTED CONTEXT", serialized)
        self.assertNotIn("question_en", serialized)
        self.assertNotIn("score", serialized)
        self.assertEqual(payload["meta"]["citation_validation"], "valid")

    def test_future_nested_contract_is_accepted(self):
        raw = {
            "output": {
                "response": "Une réponse partielle [1].",
                "evidence": [
                    {"book": "Scientific Realism", "page_label": "pp. 12–13", "snippet": "Evidence."}
                ],
                "status": "partial",
            },
            "metadata": {"mode": "panoramique", "elapsed_seconds": 8.2},
        }
        view = present_result(raw, elapsed_seconds=99)
        self.assertTrue(view.partial)
        self.assertEqual(view.mode, "panoramique")
        self.assertEqual(view.elapsed_seconds, 8.2)
        self.assertEqual(view.sources[0].title, "Scientific Realism")

    def test_invalid_citation_is_reported_without_blocking_answer(self):
        view = present_result(
            {
                "answer": "Affirmation [2].",
                "sources": [{"titre": "Livre", "pages": "p. 1", "extrait": "Texte"}],
            },
            elapsed_seconds=1,
        )
        self.assertEqual(view.citation_status, "warning")
        self.assertIn("[2]", view.citation_message)

    def test_raw_html_is_escaped_in_answer_and_sources(self):
        view = present_result(
            {
                "answer": "<script>alert(1)</script> [1]",
                "sources": [
                    {"titre": "<b>Livre</b>", "pages": "p. 1", "extrait": "<img src=x>"}
                ],
            },
            elapsed_seconds=1,
        )
        self.assertNotIn("<script>", view.answer_markdown)
        rendered = render_sources(view)
        self.assertNotIn("<b>Livre</b>", rendered)
        self.assertNotIn("<img src=x>", rendered)

    def test_only_valid_citations_become_links(self):
        linked = link_citations("Valide [1], invalide [3].", source_count=2)
        self.assertIn("[1](#source-1)", linked)
        self.assertIn("invalide [3]", linked)

    def test_public_source_excerpt_is_limited_to_twenty_words(self):
        excerpt = " ".join(f"word{i}" for i in range(30))
        view = present_result(
            {
                "answer": "Réponse [1]",
                "sources": [{"titre": "Livre", "pages": "p. 1", "extrait": excerpt}],
            },
            elapsed_seconds=1,
        )
        public_excerpt = view.sources[0].excerpt
        self.assertEqual(len(public_excerpt.removesuffix("…").split()), 20)
        self.assertTrue(public_excerpt.endswith("…"))

    def test_abstention_does_not_require_citation(self):
        view = present_result(
            {"answer": "Absent du corpus.", "sources": [], "abstained": "pre-generation"},
            elapsed_seconds=2,
        )
        self.assertTrue(view.abstained)
        self.assertEqual(view.citation_status, "not_applicable")

    def test_citation_validation_failure_is_not_corpus_abstention(self):
        view = present_result(
            {
                "answer": "Impossible de produire une réponse correctement sourcée.",
                "sources": [{"titre": "Livre", "pages": "p. 1", "extrait": "Texte"}],
                "abstained": "citation-validation",
            },
            elapsed_seconds=2,
        )
        self.assertFalse(view.abstained)
        self.assertEqual(view.citation_status, "warning")


if __name__ == "__main__":
    unittest.main()
