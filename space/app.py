"""BungeRAG - demo publique (Hugging Face Space, CPU Basic gratuit).

Specificites demo vs pipeline local :
- index telecharge au demarrage depuis le dataset HF PRIVE (le texte des
  livres ne doit jamais etre public) via le secret HF_TOKEN ;
- reranking reduit (RAG_K_CANDIDATES=12) : 2 vCPU, pas un GPU M3 ;
- cache des reponses (une question deja posee ne consomme aucun quota) ;
- garde-fous quota : limite globale/jour et par visiteur, message clair
  quand le quota Gemini gratuit est atteint (il est PARTAGE entre tous).
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import gradio as gr

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("RAG_K_CANDIDATES", "12")
os.environ.setdefault("RAG_K_FINAL", "5")

INDEX = ROOT / "index" / "lancedb"
if not INDEX.exists():
    from huggingface_hub import snapshot_download
    print("telechargement de l'index depuis le dataset prive...")
    snapshot_download("alexisgirard/bungerag-index", repo_type="dataset",
                      local_dir=ROOT / "index", token=os.environ["HF_TOKEN"])

from rag import ask  # noqa: E402

POOL = ThreadPoolExecutor(max_workers=2)
CACHE = {}
USAGE = {"day": None, "total": 0, "ips": {}}
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "80"))
IP_LIMIT = int(os.environ.get("IP_LIMIT", "10"))

MSG_QUOTA = ("⏳ **Quota du jour atteint.** Cette démo tourne sur des API "
             "gratuites au quota limité, partagé entre tous les visiteurs. "
             "Reviens demain — ou pose une question déjà posée (servie depuis "
             "le cache, sans quota).")

def check_quota(ip):
    today = date.today().isoformat()
    if USAGE["day"] != today:
        USAGE.update(day=today, total=0, ips={})
    if USAGE["total"] >= DAILY_LIMIT:
        return "global"
    if USAGE["ips"].get(ip, 0) >= IP_LIMIT:
        return "ip"
    return None

def format_result(r, cached, elapsed):
    out = r["answer"]
    if r["sources"]:
        out += "\n\n---\n**Sources** (extraits courts — les ouvrages complets ne sont pas redistribués) :\n"
        for i, s in enumerate(r["sources"], 1):
            out += (f"\n**[{i}]** *{s['titre']}*, {s['pages']} — "
                    f"« {s['extrait'][:180]}… »\n")
    origin = "cache (zéro quota)" if cached else f"{elapsed:.0f} s"
    out += f"\n\n<sub>{origin} · réponses citées ou abstention · "
    out += "faithfulness 0,935 mesurée par harnais RAGAS indépendant</sub>"
    return out

def answer(question, request: gr.Request):
    """Generateur : Gradio affiche chaque yield -> retour visuel immediat,
    puis compteur de secondes en direct pendant le calcul."""
    q = " ".join((question or "").lower().split())
    if len(q) < 4:
        yield "Pose une vraie question sur la philosophie de Mario Bunge."
        return
    if q in CACHE:
        yield format_result(CACHE[q], cached=True, elapsed=0)
        return

    ip = getattr(getattr(request, "client", None), "host", "?")
    blocked = check_quota(ip)
    if blocked == "ip":
        yield ("🐢 **Limite par visiteur atteinte** (" + str(IP_LIMIT)
               + " questions/jour) — le quota gratuit est partagé, "
                 "chacun sa part. Reviens demain !")
        return
    if blocked == "global":
        yield MSG_QUOTA
        return

    fut = POOL.submit(ask, question)
    t0 = time.time()
    while not fut.done():
        yield (f"⏳ **{time.time()-t0:.0f} s** — recherche dans les 25 ouvrages, "
               "reranking des passages puis génération citée…\n\n"
               "*Serveur CPU gratuit : compte ~1 à 2 minutes. Les questions "
               "déjà posées par quelqu'un sont instantanées (cache).*")
        time.sleep(2)
    try:
        r = fut.result()
    except Exception:
        yield MSG_QUOTA  # quota LLM epuise en cours de route ou API down
        return
    USAGE["total"] += 1
    USAGE["ips"][ip] = USAGE["ips"].get(ip, 0) + 1
    CACHE[q] = r
    yield format_result(r, cached=False, elapsed=time.time() - t0)

DESCRIPTION = """# 🔎 BungeRAG
**Interroge l'œuvre de Mario Bunge (25 ouvrages) en français.**
Chaque affirmation est citée **[livre, page]** ; si la réponse n'est pas dans le corpus, le système répond « Absent du corpus » plutôt que d'inventer.

*Projet étudiant (RAG : retrieval hybride + reranking + génération contrainte). Fidélité mesurée : **93,5 %** (RAGAS, juge indépendant, [méthodo](https://github.com/alexisgirard-it/bungerag)). Le corpus n'est pas redistribué : seules de courtes citations sont affichées. Première réponse parfois lente (démarrage à froid + CPU gratuit : ~1-2 min).*
"""

EXAMPLES = [
    "Qu'est-ce que l'émergence pour Bunge ?",
    "Pourquoi Bunge considère-t-il la psychanalyse comme une pseudoscience ?",
    "Quelle différence entre causalité et déterminisme ?",
    "Que pense Bunge du dualisme corps-esprit ?",
    "Que dit Bunge à propos du Bitcoin ?",
]

with gr.Blocks(title="BungeRAG") as demo:
    gr.Markdown(DESCRIPTION)
    question = gr.Textbox(label="Ta question", placeholder="Qu'est-ce que le systémisme ?", lines=2)
    btn = gr.Button("Demander à Bunge 📚", variant="primary")
    output = gr.Markdown()
    gr.Examples(examples=EXAMPLES, inputs=question)
    btn.click(answer, inputs=question, outputs=output)
    question.submit(answer, inputs=question, outputs=output)

if __name__ == "__main__":
    demo.launch()
