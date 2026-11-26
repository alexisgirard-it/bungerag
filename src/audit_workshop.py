"""Contrôle les éditions des dossiers et les effets d’objections successives."""

import json
from pathlib import Path

from audit_reader import verified
from workshop import DOSSIERS, assess

ROOT = Path(__file__).resolve().parents[1]


def main():
    fixture = json.loads((ROOT / "eval/recette-atelier.json").read_text())
    dossiers = {name: build() for name, build in DOSSIERS.items()}
    checked_sources = 0
    for name, content in dossiers.items():
        for step in content["steps"]:
            for source in step["sources"]:
                assert verified(source), (name, step["id"], source["pages"])
                checked_sources += 1
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
