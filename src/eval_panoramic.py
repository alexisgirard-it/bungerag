"""Extension (b) - mesure avant/apres de la decomposition sur questions panoramiques.

Metriques sans juge (le quota Cerebras sert deja au trickle) :
  - couverture : nb de LIVRES distincts dans les sources (une synthese d'oeuvre
    doit puiser large - proxy direct de la faiblesse panoramique)
  - nb d'extraits distincts, nb de citations [n] dans la reponse
  - latence
+ un document cote a cote (eval/PANORAMIQUES.md) pour lecture humaine.

Usage : .venv/bin/python src/eval_panoramic.py
"""

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from rag import ask, ask_smart  # noqa: E402

QUESTIONS = [
    "Présente les grandes lignes de la philosophie de Mario Bunge.",
    "Quelles sont les thèses principales du matérialisme de Bunge à travers son œuvre ?",
    "Comment le systémisme de Bunge s'applique-t-il de la physique à la société ?",
    "Résume la critique bungéenne des pseudosciences et ses critères de démarcation.",
    "Quelle est la place de l'éthique dans le système philosophique de Bunge ?",
    "Comment Bunge conçoit-il les rapports entre science, technologie et philosophie ?",
    "Quel est le parcours intellectuel de Bunge et comment a-t-il façonné son œuvre ?",
    "En quoi le Treatise on Basic Philosophy forme-t-il un système unifié ?",
]

CACHE = ROOT / "eval" / "cache" / "panoramic.json"

def stats(r, elapsed):
    return {"livres": len({s["titre"] for s in r["sources"]}),
            "extraits": len(r["sources"]),
            "citations": len(set(re.findall(r"\[(\d+)\]", r["answer"]))),
            "mode": r.get("mode", "direct"), "secondes": round(elapsed),
            "answer": r["answer"], "sources": r["sources"],
            "sous_questions": r.get("sous_questions")}

def main():
    data = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    for i, q in enumerate(QUESTIONS, 1):
        key = str(i)
        data.setdefault(key, {"question": q})
        for variant, fn in (("baseline", ask), ("decompose", ask_smart)):
            if variant in data[key]:
                continue
            t0 = time.time()
            r = fn(q)
            data[key][variant] = stats(r, time.time() - t0)
            CACHE.write_text(json.dumps(data, ensure_ascii=False))
            print(f"  q{i} {variant:10} {data[key][variant]['livres']} livres, "
                  f"{data[key][variant]['extraits']} extraits "
                  f"({data[key][variant]['secondes']}s)", flush=True)

    # tableau + document de lecture
    print(f"\n{'':4} {'livres cités':>22} {'extraits':>16} {'citations [n]':>16}")
    print(f"{'q':4} {'base':>10} {'décomp':>11} {'base':>7} {'déc':>8} {'base':>7} {'déc':>8}")
    tb = td = 0
    L = ["# Questions panoramiques — avant / après décomposition", ""]
    for i in range(1, len(QUESTIONS) + 1):
        d = data[str(i)]
        b, c = d["baseline"], d["decompose"]
        tb += b["livres"]; td += c["livres"]
        print(f"q{i:<3} {b['livres']:>10} {c['livres']:>11} {b['extraits']:>7} "
              f"{c['extraits']:>8} {b['citations']:>7} {c['citations']:>8}")
        L += [f"## q{i} — {d['question']}", "",
              f"**Baseline** ({b['livres']} livres, {b['secondes']}s) :", "",
              b["answer"], "", "---", "",
              f"**Décomposé** ({c['livres']} livres, {c['secondes']}s ; "
              f"sous-questions : {'; '.join(c.get('sous_questions') or [])}) :", "",
              c["answer"], "", "===", ""]
    print(f"\nmoyenne livres cités : baseline {tb/8:.1f} vs décomposé {td/8:.1f}")
    (ROOT / "eval" / "PANORAMIQUES.md").write_text("\n".join(L))
    print("lecture côte à côte -> eval/PANORAMIQUES.md")

if __name__ == "__main__":
    main()
