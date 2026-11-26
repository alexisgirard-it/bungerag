"""Contrôle les éditions des dossiers, les conditions de transposition et les objections."""

import json
from pathlib import Path

from audit_reader import verified
from formal_logic import FOL_VERIFIERS
from library import NODES
from workshop import (
    DOSSIERS,
    assess,
    formal_efficiency,
    formal_happiness,
    formal_rights,
    formal_systemism,
    formal_world,
)

ROOT = Path(__file__).resolve().parents[1]
TRANSPOSITION_HYPOTHESES = {
    "Hypothèse de transposition",
    "Hypothèse du lecteur",
    "Hypothèse de travail",
}
FORMALIZATIONS = (
    formal_rights,
    formal_happiness,
    formal_world,
    formal_systemism,
    formal_efficiency,
)


def verify_transposition_conditions(name, steps):
    """Vérifie que chaque conclusion conditionnelle repose sur un fait daté et une hypothèse nécessaire."""
    by_id = {step["id"]: step for step in steps}
    checked = 0
    for step in steps:
        if step["role"] != "Conclusion conditionnelle":
            continue
        if not step["supports"]:
            raise ValueError(f"Conclusion conditionnelle sans appui dans {name}/{step['id']}")
        for chain in step["supports"]:
            facts = [
                key
                for key in chain
                if by_id[key]["role"] == "Fait contemporain daté"
                and by_id[key].get("external")
            ]
            hypotheses = [
                key
                for key in chain
                if by_id[key]["role"] in TRANSPOSITION_HYPOTHESES
            ]
            if not facts or not hypotheses:
                raise ValueError(
                    f"Condition nécessaire absente dans la transposition {name}/{step['id']}"
                )
            for key in facts:
                for ext in by_id[key]["external"]:
                    if not ext.get("url", "").startswith("https://") or not ext.get("title"):
                        raise ValueError(f"Source contemporaine incomplète dans {name}/{key}")
            if any(by_id[key]["role"] == "Hypothèse de transposition" for key in hypotheses):
                if not any(by_id[key]["sources"] for key in chain):
                    raise ValueError(
                        f"Transposition sans appui textuel de Bunge dans {name}/{step['id']}"
                    )
            for necessary in (*facts, *hypotheses):
                state = assess(steps, {necessary: ""})
                if state[step["id"]] != "justification suspendue":
                    raise ValueError(
                        f"Condition {necessary} non nécessaire pour {name}/{step['id']}"
                    )
                checked += 1
    return checked


def verify_dossiers():
    dossiers = {name: build() for name, build in DOSSIERS.items()}
    checked_sources = 0
    checked_conditions = 0
    for name, content in dossiers.items():
        earlier = set()
        for step in content["steps"]:
            key = step["id"]
            if key in earlier:
                raise ValueError(f"Étape répétée dans le dossier {name} ({key})")
            for chain in step["supports"]:
                if not chain or not set(chain) <= earlier:
                    raise ValueError(f"Appui absent ou placé après l’étape {name}/{key}")
            earlier.add(key)
            for source in step["sources"]:
                if not verified(source):
                    raise ValueError(f"Extrait non retrouvé pour {name}/{key} ({source['pages']})")
                checked_sources += 1
        checked_conditions += verify_transposition_conditions(name, content["steps"])
    for check in FORMALIZATIONS:
        result = check()
        if not result.get("valid"):
            raise ValueError(f"Formalisation invalide : {result.get('formula')}")
    for key, check in FOL_VERIFIERS.items():
        result = check()
        if not result.get("valid"):
            raise ValueError(f"Preuve du premier ordre invalide ({key}) : {result.get('formula')}")
    return dossiers, checked_sources, checked_conditions


def main():
    fixture = json.loads((ROOT / "eval/recette-atelier.json").read_text())
    dossiers, checked_sources, checked_conditions = verify_dossiers()
    for case in fixture.get("cas_libres", []):
        missing = [key for key in case["appuis"] if key not in NODES]
        assert not missing, (case["id"], missing)
        assert case["critères"], case["id"]
    tested = 0
    for scenario in fixture["séquences"]:
        name = scenario["dossier"]
        steps = dossiers[name]["steps"]
        original = json.dumps(steps, sort_keys=True)
        changes = {}
        for index, event in enumerate(scenario["étapes"], 1):
            key, value = event["changer"], event["texte"]
            assert any(s["id"] == key for s in steps)
            if value is None:
                changes.pop(key, None)
            else:
                changes[key] = value
            state = assess(steps, changes)
            assert all(state[k] == v for k, v in event["attendu"].items()), (
                name,
                index,
                state,
            )
            assert json.dumps(steps, sort_keys=True) == original, (name, index)
            tested += 1
    print(
        f"{len(dossiers)} dossiers, {checked_sources} appuis, {checked_conditions} conditions de transposition, "
        f"{len(FORMALIZATIONS)} formalisations propositionnelles, {len(FOL_VERIFIERS)} preuves du premier ordre "
        f"et {tested} modifications contrôlées."
    )


if __name__ == "__main__":
    main()
