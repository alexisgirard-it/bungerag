"""Extension (b) - routeur + decomposition des questions panoramiques.

Le RAG simple excelle sur les questions precises et plafonne sur les
panoramiques (« resume la philosophie de Bunge ») : 6 extraits ne couvrent
pas une oeuvre. Remede : eclater la question en sous-questions, recuperer
pour chacune, synthetiser le tout.

UN SEUL appel LLM (Cerebras, pas le quota Gemini) fait les trois taches :
router (direct/panoramique), decomposer, traduire (la jambe BM25 veut de
l'anglais). Sortie JSON stricte.
"""

import json
import re

from generate import generate

PROMPT = """Tu prepares une question pour un systeme de recherche documentaire sur l'oeuvre du philosophe Mario Bunge.

Question : {question}

Etape 1 - CLASSIFIE :
- "direct" : la question porte sur UN concept/theme precis (une definition, une critique ciblee, un fait). La recherche documentaire directe suffira.
- "panoramique" : la question demande une vue d'ensemble, une synthese multi-themes, un parcours a travers l'oeuvre (resume general, "grandes lignes", comparaison de plusieurs domaines, evolution d'une pensee).

Etape 2 - si "panoramique", DECOMPOSE en 3 a 5 sous-questions PRECISES et complementaires qui, ensemble, couvrent la question (chacune doit etre trouvable dans des livres : concepts nommes, pas de meta-questions).

Reponds UNIQUEMENT avec ce JSON (rien d'autre) :
{{"mode": "direct"}}
ou
{{"mode": "panoramique", "sous_questions": [{{"fr": "...", "en": "..."}}, ...]}}"""

def analyse(question):
    raw = generate(PROMPT.format(question=question), max_tokens=1200,
                   backend="cerebras")
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        d = json.loads(m.group(0))
        assert d.get("mode") in ("direct", "panoramique")
        if d["mode"] == "panoramique":
            assert 2 <= len(d["sous_questions"]) <= 6
        return d
    except Exception:
        # degradation gracieuse : au moindre doute, pipeline direct
        return {"mode": "direct"}

if __name__ == "__main__":
    import sys
    print(json.dumps(analyse(sys.argv[1]), ensure_ascii=False, indent=2))
