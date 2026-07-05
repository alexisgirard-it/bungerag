# Journal de bord — BungeRAG

Tenu par l'IA, relu par Alexis. Fait / Appris / Surprise. Banque d'anecdotes pour le README et les entretiens.

---

## 2026-07-04 — Phase 0 : fondations

**Fait :** stack vérifié sur pages officielles (15 agents de recherche) ; corpus curé : 25 œuvres retenues, 3 exclusions motivées (2 collectifs, 1 doublon) ; repo créé, Python 3.12, premier commit sans un seul PDF ; manifest.csv en ASCII pur.

**Appris :** un plan de juin était déjà périmé en juillet (BGE-M3 battu par Qwen3, SDK Streamlit retiré de HF, Qdrant Cloud free = piège de suspension) — les stacks LLM se re-vérifient au moment du build, jamais de mémoire.

**Surprise :** deux « livres de Bunge » étaient en fait des collectifs écrits par d'autres — le piège de la voix polluée se joue dès la curation, pas dans le code.

## 2026-07-04 — Phase 1 : extraction

**Fait :** 25/25 œuvres → `extracted/*.jsonl` (1 ligne = 1 page avec {livre, titre, année, page}), ~8 200 pages, ~21,6 M caractères. Natifs via pymupdf4llm (markdown, césures recollées) + heuristique anti-mobilier par répétition (~35 000 lignes d'en-têtes/pieds retirées). 2 livres passés à l'OCR Apple Vision (0,7 s/page, local, gratuit).

**Appris :** avoir une couche texte ≠ avoir une BONNE couche texte. Political Philosophy avait du texte… découpé en morceaux (« thi », « ocial ») par une police mal encodée : 460 pages re-OCRisées en 5 min. La vérification s'échantillonne et se chiffre (alignement page↔PDF, taux de vrais mots), elle ne se fait pas « à l'œil ».

**Surprise :** le thermomètre aussi peut être faux — le dictionnaire macOS n'a pas les pluriels, ce qui faisait paniquer le contrôle sur TOUS les livres ; et les flèches de renvoi ↑ du Philosophical Dictionary étaient encodées comme des « i » collés (2 002 réparées par regex). Deux vraies anomalies, un faux positif : enquêter avant de corriger.

## 2026-07-05 — Phase 2 : chunking

**Fait :** 8 200 pages → 11 249 chunks de ~512 tokens (+ variante 5 707 × ~1024 pour l'éval), 5,3 M tokens. Pages recollées avant découpe (75 % des chunks chevauchent 2 pages — une frontière de page n'est pas une frontière d'idée), césures réparées, EPUB découpé par essai. Vérifié : traçabilité chunk→pages 100/100, 96 % des chunks finissent en fin de phrase.

**Appris :** le chunking est un compromis sans optimum absolu (petit = précis mais sans contexte, gros = l'inverse) — on garde DEUX tailles et l'éval de la Phase 6 tranchera aux chiffres.

**Surprise :** un chunk moyen de « 512 tokens » en fait 468 : le découpeur sacrifie du remplissage pour respecter les fins de phrases.

## 2026-07-05 — Phase 3 : embeddings + index

**Fait :** 11 249 chunks → vecteurs Qwen3-Embedding-0.6B (local, GPU M3, float16) → LanceDB + index BM25. 3 h de calcul unique, index final : 64 Mo. Vérifié : auto-retrouvage 20/20, requêtes-témoins 7/7 dont 3 posées EN FRANÇAIS sur le corpus anglais, latence de recherche 0,04 s.

**Appris :** l'asymétrie fondamentale du RAG — indexer coûte des heures (une fois), chercher coûte 40 millisecondes (à chaque fois). Et le cross-lingue marche : « Qu'est-ce que l'émergence ? » trouve la définition anglaise du Philosophical Dictionary sans traduction.

**Surprise :** float16 n'a rien accéléré (le goulot était la puissance GPU brute, pas la précision) ; et sur « systemism », BM25 bat le dense — il trouve la définition exacte dans le Treatise là où le dense remonte des réminiscences des mémoires. Chaque mode a ses victoires : d'où l'hybride.

## 2026-07-05 — Phase 4 : retrieval sérieux + première éval chiffrée

**Fait :** reranker Qwen3-0.6B (cross-encodeur) + retriever 2 étages (hybride k=40 → top-10) + jeu de 20 questions FR avec livres attendus. Résultat final : rerank 95 % hit@5, 100 % hit@10, rang moyen 2,1.

**Appris :** la boucle centrale du métier — mesurer → inspecter les échecs → corriger les DONNÉES → re-mesurer. Les premiers chiffres étaient médiocres (60-70 %) non pas à cause de l'algorithme mais parce que l'index était pollué par 835 chunks d'annexes (bibliographies, index, pages de garde, intro de l'éditeur de l'anthologie). La page « About the author » sortait 1re sur la question sur l'esprit. Deux passes de filtrage plus tard : +25 points.

**Surprise :** BM25 perd des points quand on nettoie — ses « bons » résultats d'avant étaient des pages de biblio des bons livres, des faux positifs. Et ses 5 échecs restants sont TOUS des questions au vocabulaire très français : il ne peut pas matcher « démocratie intégrale » sur un corpus anglais. La reformulation FR→EN de la phase 5 est déjà justifiée par les chiffres.

## 2026-07-06 — Phase 5 : génération citée + abstention

**Fait :** pipeline complet question → réponse française citée [n] ou « Absent du corpus ». generate() unique commutable par variable d'env (anti lock-in), Gemini 2.5 Flash temp 0, reformulation FR→EN (BM25 : 50 → 95 % hit@5 !), abstention à deux étages. Fidélité vérifiée en lecture : la définition citée de l'émergence est mot pour mot dans E&C p.25-26.

**Appris :** le seuil pré-génération sur le score du reranker ne suffit PAS pour l'abstention — le piège « recette préférée de Bunge » score 0,966 (les mémoires parlent de repas !) : le reranker mesure la proximité de SUJET, pas « ça répond vraiment ». C'est la règle stricte du prompt qui a refusé les 3 pièges. Deux filets valent mieux qu'un, et c'est le 2e qui travaille.

**Surprise :** les réponses tronquées à 3 lignes — les tokens de « réflexion » de Gemini 2.5 se décomptent silencieusement de max_output_tokens. thinking_budget=0 et tout est rentré dans l'ordre.
