# BungeRAG

RAG sur le corpus de Mario Bunge (25 ouvrages) : réponses en français, citées (livre + page), qui s'abstiennent (« absent du corpus ») plutôt que d'halluciner. Cœur du projet : un harnais d'évaluation qui mesure la fidélité.

> 🚧 En construction — Phase 0 (fondations) faite. Prochaine étape : Phase 1 (extraction).

## Pourquoi

Projet d'apprentissage RAG/LLMOps de bout en bout : ingestion → chunking → retrieval hybride + reranking → génération citée → **évaluation chiffrée** (RAGAS). Les métriques seront affichées ici, y compris ce qui ne marche pas.

## Légal

Le corpus (livres sous droit d'auteur) n'est **pas** dans ce dépôt et ne le sera jamais — voir `.gitignore`. Le code permet de reconstruire l'index à partir de ses propres exemplaires. La démo publique n'affiche que de courtes citations sourcées.

## Structure

```
corpus/     les 25 œuvres (non versionné)     manifest.csv  la liste curée + exclusions motivées
extracted/  markdown extrait (non versionné)  src/          le pipeline
index/      base LanceDB (non versionné)      eval/         jeu de questions + harnais
```
