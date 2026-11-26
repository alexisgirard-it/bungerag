"""Quatre cas de raisonnement, mêmes sources courtes, réponses anonymisées avant relecture."""

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from time import monotonic

from evidence import parse_object
from generate import generate_json
from workshop import DOSSIERS

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = {
    "bonheur": "Si je suspends le postulat 2.1, qu’advient-il du théorème sur le bonheur ? Distingue croyance et possibilité réelle.",
    "devoir": "Le seul fait qu’une action satisfasse mon besoin suffit-il à en faire un devoir pour autrui ?",
    "existence": "L’existence des constructions mathématiques contredit-elle le matérialisme ? Justifie la portée des deux textes.",
    "ia": "Bunge aurait-il dit que Llama 3.1 comprend ? Construis l’argument conditionnel et une objection.",
}
RUBRIC = {
    "bonheur": "Le lien indiqué par Bunge perd une prémisse. La suspension ne prouve pas le contraire. Distinguer possibilité réelle et croyance dans la définition.",
    "devoir": "Besoin, valeur, droit et devoir ont des statuts différents. La condition concernant autrui limite le passage normatif.",
    "existence": "Comparer les sens de réellement et conceptuellement sans attribuer une contradiction ou un changement historique sans preuve.",
    "ia": "Distinguer texte de Bunge, fait de 2024 et hypothèse de transposition. Aucune opinion posthume attribuée. Présenter un critère rival.",
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("models", nargs="+")
    p.add_argument("--out", default="arguments-v3")
    p.add_argument("--judge", default="gemini/gemini-3.1-flash-lite")
    args = p.parse_args()
    out = ROOT / "eval/cache" / args.out
    out.mkdir(parents=True, exist_ok=True)
    for case, question in QUESTIONS.items():
        steps = DOSSIERS[case]()["steps"]
        evidence = [
            {
                "identifiant": s["id"],
                "rôle": s["role"],
                "extraits": [r["excerpt"] for r in s["sources"]],
                "fait_externe": s.get("external", []),
            }
            for s in steps
            if s["sources"] or s.get("external")
        ]
        source_ids = {s["identifiant"] for s in evidence}
        for backend in args.models:
            path = out / (case + "-" + backend.replace("/", "_") + ".json")
            if path.exists():
                continue
            t = monotonic()
            rec = {"case": case, "model": backend, "date": str(date.today())}
            try:
                obj = parse_object(
                    generate_json(
                        json.dumps(
                            {"question": question, "sources": evidence},
                            ensure_ascii=False,
                        ),
                        'Rédige une réponse française à partir des données. Distingue texte, inférence et incertitude. Inclus une objection. Retourne {"texte":"...","appuis":["identifiant"]}.',
                        backend,
                        2000,
                    )
                )
                ids = obj.get("appuis", [])
                if (
                    not isinstance(obj.get("texte"), str)
                    or not isinstance(ids, list)
                    or not ids
                    or not all(isinstance(i, str) and i in source_ids for i in ids)
                ):
                    rec["error"] = "format ou référence"
                else:
                    rec["answer"] = obj
            except Exception as e:
                rec.update(error=type(e).__name__, code=getattr(e, "code", None))
            rec["seconds"] = round(monotonic() - t, 2)
            path.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
            print(
                case, backend, rec.get("error", "réponse"), rec["seconds"], flush=True
            )
        blind = []
        for candidate in out.glob(case + "-*.json"):
            obj = json.loads(candidate.read_text())
            if "answer" in obj:
                opaque = hashlib.sha256(
                    (case + str(obj["answer"])).encode()
                ).hexdigest()[:10]
                blind.append({"id": opaque, "texte": obj["answer"]})
        blind.sort(key=lambda x: x["id"])
        if not blind:
            continue
        path = out / (case + ".blind.json")
        path.write_text(
            json.dumps(
                {
                    "question": question,
                    "sources": evidence,
                    "critères": RUBRIC[case],
                    "copies": blind,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        judgement = out / (case + ".review.json")
        if judgement.exists():
            continue
        try:
            scores = parse_object(
                generate_json(
                    path.read_text(),
                    'Relis les copies anonymes à la lumière des sources et critères. Pour chacune donne {"copies":[{"id":"...","soutien":true,"attribution":true,"objection":true,"motif":"..."}]}. Signale toute attribution insuffisante.',
                    args.judge,
                    2200,
                )
            )
            judgement.write_text(json.dumps(scores, ensure_ascii=False, indent=2))
        except Exception as e:
            print(
                "relecture",
                case,
                type(e).__name__,
                getattr(e, "code", None),
                flush=True,
            )


if __name__ == "__main__":
    main()
