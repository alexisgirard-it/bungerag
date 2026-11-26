# Organisation de `src/`

`src/` regroupe deux familles de modules clairement séparées par la liste blanche de déploiement ([push_space.py](push_space.py)) :

## 1. Runtime public (16 modules déployés sur le Space Hugging Face)
Ces modules sont les seuls copiés dans le bundle public du Space (aucun corpus, cache ni script d’évaluation n’est publié) :

- **Bibliothèque & référentiel :** `library.py`, `referentiel.json`, `formal_logic.py`, `workshop.py`
- **Recherche hybride & reclassement :** `search.py`, `retrieve.py`, `rerank.py`, `definitions.py`
- **Génération, preuves & garde-fous :** `rag.py`, `evidence.py`, `generate.py`, `decompose.py`, `citations.py`, `output_guard.py`, `config.py`, `schemas.py`

## 2. Pipeline hors-ligne (ingestion, audits, benchmarks & déploiement)
Scripts exécutés uniquement en local sur le corpus privé (jamais déployés sur le Space) :

- **Ingestion & indexation :** `extract.py`, `ocr_scan.py`, `chunk.py`, `filter_backmatter.py`, `embed_index.py`, `build_index.py`, `page_map.py`, `update_page_metadata.py`, `build_provenance.py`, `build_library.py`
- **Audits bloquants pré-publication :** `audit_reader.py`, `audit_workshop.py`, `audit_fidelity.py`, `push_space.py`
- **Benchmarks & évaluations reproductibles :** `benchmark_encoders.py`, `benchmark_ranking.py`, `compare_rerankers.py`, `compare_graph_evidence.py`, `compare_neighbors_equal_budget.py`, `compare_page_context.py`, `compare_llm_blind.py`, `compare_retrieval.py`, `compare_embeddings.py`, `compare_generation.py`, `compare_arguments.py`, `evaluate_reader.py`, `measure_reader_http.py`, `audit_retrieval.py`, `eval_run.py`, `eval_ragas.py`, `eval_retrieval.py`, `eval_panoramic.py`
