"""Le pipeline BungeRAG complet : question -> reponse citee ou abstention.

Etapes :
 1. Reformulation EN de la question (repare la jambe BM25, aveugle au
    francais sur un corpus anglais - 5 echecs sur 20 a l'eval de phase 4)
 2. Retrieval 2 etages : hybride (dense=question FR, bm25=version EN),
    40 candidats -> reranker -> top 6
 3. ABSTENTION AVANT GENERATION : si le meilleur score du reranker est
    sous le seuil, on repond "Absent du corpus" sans appeler le LLM
    (pas de passage pertinent = rien a citer = on ne genere pas)
 4. Generation Gemini, temperature 0, prompt strict : francais, chaque
    affirmation citee [n], abstention si les extraits ne suffisent pas
    (2e filet de securite, au niveau du modele cette fois)

Usage : .venv/bin/python src/rag.py "ta question"
"""

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import generate  # noqa: E402
from retrieve import retrieve  # noqa: E402
from search import search  # noqa: E402

SEUIL_ABSTENTION = 0.10  # P(yes) max du reranker sous lequel on ne genere pas
K_FINAL = 6

SYSTEM = """Tu es BungeRAG, un assistant qui restitue fidelement la philosophie de Mario Bunge.

REGLES ABSOLUES :
1. Reponds en francais, de facon claire et structuree.
2. Tu ne peux utiliser QUE les extraits numerotes fournis. Jamais tes connaissances generales.
3. Apres CHAQUE affirmation, cite l'extrait qui la fonde : [1], [2]...
4. Si les extraits ne permettent pas de repondre a la question, reponds exactement : Absent du corpus.
5. Si les extraits ne repondent que partiellement, reponds a ce qui est couvert et signale explicitement ce qui ne l'est pas.
6. Ne romance pas, n'extrapole pas : restitue ce que disent les extraits."""

def reformulate_en(question):
    return generate(
        f"Translate this French question into concise academic English "
        f"(philosophy of science context). Reply with the translation only.\n\n{question}",
        max_tokens=200)

def format_pages(h):
    if h["page_start"] == h["page_end"]:
        return f"p. {h['page_start']}"
    return f"p. {h['page_start']}-{h['page_end']}"

def ask(question, verbose=False):
    t0 = time.time()
    question_en = reformulate_en(question)
    t_translate = time.time() - t0

    # hybride : jambe dense = FR (le cross-lingue marche), jambe BM25 = EN
    hits = search(question_en, "hybrid", 40)
    from retrieve import get_reranker
    scores = get_reranker().score(question, [h["text"] for h in hits])
    for h, s in zip(hits, scores):
        h["rerank_score"] = s
    hits.sort(key=lambda h: h["rerank_score"], reverse=True)
    hits = hits[:K_FINAL]
    t_retrieve = time.time() - t0 - t_translate

    if not hits or hits[0]["rerank_score"] < SEUIL_ABSTENTION:
        return {"answer": "Absent du corpus.", "sources": [], "abstained": "pre-generation",
                "question_en": question_en, "top_score": hits[0]["rerank_score"] if hits else 0,
                "timings": {"translate": t_translate, "retrieve": t_retrieve, "generate": 0}}

    extraits = "\n\n".join(
        f"[{i}] ({h['title']}, {format_pages(h)})\n{h['text']}"
        for i, h in enumerate(hits, 1))
    prompt = f"EXTRAITS DU CORPUS :\n\n{extraits}\n\nQUESTION : {question}"
    answer = generate(prompt, system=SYSTEM)
    t_generate = time.time() - t0 - t_translate - t_retrieve

    abstained = "llm" if answer.strip().lower().startswith("absent du corpus") else None
    return {
        "answer": answer,
        "sources": [{"titre": h["title"], "pages": format_pages(h),
                     "score": round(h["rerank_score"], 3),
                     "extrait": " ".join(h["text"].split())[:200]} for h in hits],
        "abstained": abstained,
        "question_en": question_en,
        "top_score": round(hits[0]["rerank_score"], 3),
        "timings": {k: round(v, 1) for k, v in
                    {"translate": t_translate, "retrieve": t_retrieve,
                     "generate": t_generate}.items()},
    }

if __name__ == "__main__":
    r = ask(sys.argv[1])
    print(r["answer"])
    if r["sources"]:
        print("\n--- SOURCES ---")
        for i, s in enumerate(r["sources"], 1):
            print(f"[{i}] {s['titre']}, {s['pages']} (score {s['score']})")
    print(f"\n(EN: {r['question_en']} | top score {r['top_score']} | {r['timings']})")
