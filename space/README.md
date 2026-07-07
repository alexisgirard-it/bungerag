---
title: BungeRAG
emoji: 🔎
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 6.19.0
app_file: app.py
pinned: false
license: mit
short_description: L'œuvre de Mario Bunge en Q&R, cité page à page
---

# BungeRAG

RAG sur 25 ouvrages de Mario Bunge : réponses en français, citées (livre + page),
abstention (« Absent du corpus ») plutôt qu'hallucination.
Fidélité mesurée : 0,935 (RAGAS 0.4.3, juge indépendant Cerebras).

Stack : Qwen3-Embedding-0.6B + LanceDB hybride (dense+BM25) + Qwen3-Reranker +
Gemini Flash (rotation multi-modèles, température 0).

Le corpus (sous droits) vit dans un dataset privé : cette démo n'affiche que de
courtes citations sourcées.

Code source complet : https://github.com/alexisgirard-it/bungerag
