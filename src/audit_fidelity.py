"""Vérifie la fidélité face aux formulations orientées et aux conversations longues multi-tours."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evidence import editorial_attribution
from library import CATALOG, NODES, question_scope
from workshop import DOSSIERS, assess, choose_dossier

ROOT = Path(__file__).resolve().parents[1]

LONG_CONVERSATIONS = [
    {
        "id": "conv-longue-ia-12-tours",
        "dossier": "ia",
        "turns": [
            ("critere-neural", "", {"inference-ia": "justification suspendue", "condition-fonctionnelle": "disponible"}),
            ("critere-fonctionnel", "Un score de benchmark suffit à prouver la compréhension.", {"critere-fonctionnel": "remplacée", "condition-fonctionnelle": "justification suspendue"}),
            ("emergence-esprit", "", {"inference-ia": "justification suspendue"}),
            ("autoregressif", "", {"inference-ia": "justification suspendue", "condition-fonctionnelle": "justification suspendue"}),
            ("autoregressif", None, {"inference-ia": "justification suspendue", "condition-fonctionnelle": "justification suspendue"}),
            ("critere-fonctionnel", None, {"condition-fonctionnelle": "disponible", "inference-ia": "justification suspendue"}),
            ("emergence-esprit", None, {"inference-ia": "justification suspendue"}),
            ("critere-neural", None, {"inference-ia": "disponible", "condition-fonctionnelle": "disponible"}),
            ("analogie", "Le cerveau est un ordinateur numérique.", {"analogie": "remplacée", "inference-ia": "justification suspendue", "condition-fonctionnelle": "disponible"}),
            ("analogie", None, {"inference-ia": "disponible"}),
            ("cerveau", "", {"inference-ia": "justification suspendue", "condition-fonctionnelle": "disponible"}),
            ("cerveau", None, {"inference-ia": "disponible", "condition-fonctionnelle": "disponible"}),
        ],
    },
    {
        "id": "conv-longue-monde-10-tours",
        "dossier": "monde",
        "turns": [
            ("supremum", "", {"unique": "disponible"}),
            ("unicite-sup", "", {"unique": "disponible"}),
            ("autre-preuve", "", {"unique": "justification suspendue"}),
            ("supremum", None, {"unique": "justification suspendue"}),
            ("unicite-sup", None, {"unique": "disponible"}),
            ("monde", "Le monde est un agrégat disjoint.", {"monde": "remplacée", "unique": "justification suspendue"}),
            ("autre-preuve", None, {"unique": "disponible"}),
            ("monde", None, {"unique": "disponible"}),
            ("autre-preuve", "", {"unique": "disponible"}),
            ("autre-preuve", None, {"unique": "disponible"}),
        ],
    },
]


def _catalog_digest() -> str:
    return hashlib.sha256(
        json.dumps(CATALOG, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def verify_fidelity() -> dict:
    before_digest = _catalog_digest()
    cases = [
        json.loads(line)
        for line in (ROOT / "eval/fidelite-orientee.jsonl").read_text().splitlines()
        if line.strip()
    ]
    checked_oriented = 0
    for case in cases:
        q = case["question"]
        kind = case["kind"]
        if kind == "posthumous" or kind == "edition":
            disposition, _ = question_scope(q)
            if disposition != case["expected_disposition"]:
                raise ValueError(
                    f"Fidélité rompue sur {case['id']} : attendu {case['expected_disposition']}, obtenu {disposition}"
                )
        elif kind == "attribution":
            attributed = editorial_attribution(q, "bunge_512")
            if attributed is None or case["expected_voice"] not in attributed[0]:
                raise ValueError(f"Attribution erronée sur {case['id']}")
            if choose_dossier(q) != case["expected_dossier"]:
                raise ValueError(f"Dossier inattendu sur {case['id']}")
        elif kind == "oriented_dossier":
            chosen = choose_dossier(q)
            if chosen != case["expected_dossier"]:
                raise ValueError(
                    f"Orientation incorrecte sur {case['id']} : attendu {case['expected_dossier']}, obtenu {chosen}"
                )
            steps = DOSSIERS[chosen]()["steps"]
            if case["must_include_node"] not in {s["id"] for s in steps}:
                raise ValueError(
                    f"Appui manquant {case['must_include_node']} dans {chosen}"
                )
        checked_oriented += 1

    checked_turns = 0
    for conv in LONG_CONVERSATIONS:
        dossier_name = conv["dossier"]
        fresh_before = json.dumps(DOSSIERS[dossier_name](), sort_keys=True)
        steps = DOSSIERS[dossier_name]()["steps"]
        changes = {}
        for turn_idx, (key, value, expected) in enumerate(conv["turns"], 1):
            if value is None:
                changes.pop(key, None)
            else:
                changes[key] = value
            state = assess(steps, changes)
            for target_step, target_state in expected.items():
                if state[target_step] != target_state:
                    raise ValueError(
                        f"Conversation {conv['id']} tour {turn_idx} : {target_step}={state[target_step]} != {target_state}"
                    )
            checked_turns += 1
        # Vérifier l’isolation : les hypothèses de conversation ne mutent jamais le dossier source.
        if json.dumps(DOSSIERS[dossier_name](), sort_keys=True) != fresh_before:
            raise ValueError(f"Mutation du dossier source détectée après {conv['id']}")
        if changes:
            raise ValueError(f"État final non rétabli dans {conv['id']} : {changes}")

    if _catalog_digest() != before_digest:
        raise ValueError("Le référentiel en mémoire a été muté pendant les tests de fidélité")

    return {
        "oriented_cases": checked_oriented,
        "long_conversations": len(LONG_CONVERSATIONS),
        "conversation_turns": checked_turns,
        "catalog_version": CATALOG["version"],
        "nodes_count": len(NODES),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    summary = verify_fidelity()
    print(
        f"{summary['oriented_cases']} formulations orientées, "
        f"{summary['long_conversations']} conversations longues ({summary['conversation_turns']} tours) "
        f"contrôlées sans mutation du référentiel {summary['catalog_version']}."
    )


if __name__ == "__main__":
    main()
