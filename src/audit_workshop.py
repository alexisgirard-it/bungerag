"""Contrôle les éditions des dossiers et les effets d’objections successives."""

import json
from pathlib import Path

from audit_reader import verified
from workshop import DOSSIERS, assess

ROOT = Path(__file__).resolve().parents[1]


def verify_dossiers():
    dossiers = {name: build() for name, build in DOSSIERS.items()}
    checked_sources = 0
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
    return dossiers, checked_sources


def main():
    fixture = json.loads((ROOT / "eval/recette-atelier.json").read_text())
    dossiers, checked_sources = verify_dossiers()
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
        f"{len(dossiers)} dossiers, {checked_sources} appuis, {tested} modifications contrôlées."
    )


if __name__ == "__main__":
    main()
