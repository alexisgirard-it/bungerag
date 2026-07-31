# Journal de bord — BungeRAG

Journal de bord du build, en binôme humain-IA. Trois entrées par session : Fait / Appris / Surprise.

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

## 2026-07-06 — Phase 6 : LE harnais d'éval

**Fait :** 40 questions (30 contenu avec références + 10 pièges), réponses par le pipeline complet, notation RAGAS par Cerebras gpt-oss-120b. La première passe donnait **faithfulness 0,935 · precision 0,893 · recall 0,903 · abstention 8/10 strict**. Après correction et re-notation des références, les valeurs finales du même bras sont **0,935 · 0,893 · 0,848 · 8/10**. Toutes les cibles restent dépassées ; `eval/RESULTS.md` porte désormais uniquement les résultats finaux.

**Appris :** le quota Gemini réel = ~20 req/JOUR par modèle (pas ~1500) → rotation multi-modèles implémentée en plein vol. Un score d'éval anormal se DÉBOGUE : q05 basse → une PRÉFACE d'éditeur avait survécu au filtre (v3) ; q28 recall 0,00 avec une bonne réponse → référence mal écrite, pas pipeline cassé. L'éval juge aussi le jeu d'éval.

**Surprise :** les 2 pièges « ratés » ont donné les réponses les plus intelligentes du lot — dont la découverte de la « recette du gâteau du Bonheur » que Bunge utilise ironiquement. Un piège bien conçu doit être vraiment absent du corpus, pas juste improbable.

## 2026-07-06 — Phase 7 (1/2) : la démo est construite

**Fait :** app Gradio (space/app.py) : cache des réponses, quotas global + par visiteur avec messages clairs, extraits courts seulement (légal), bandeau avec la faithfulness mesurée. Pipeline rendu portable (device auto MPS→CPU, float32 sur CPU, k réglables par env). Script de publication (push_space.py) : dataset privé pour l'index, Space public en liste blanche stricte, secrets configurés par API. Testé localement en config Space exacte : 35 s/réponse à k=12, cache et rate-limit vérifiés.

**Appris :** une démo publique gratuite, c'est 20 % de pipeline et 80 % de garde-fous — le quota est partagé entre tous les visiteurs, donc cache + limites + message honnête quand c'est épuisé.

**Surprise :** mon propre script de publication copiait « tout le dossier » — un .env qui y aurait traîné serait parti sur un Space public. Liste blanche stricte désormais : en sécurité, on énumère ce qui part, jamais ce qui reste.

## 2026-07-06 — Phase 7 (2/2) : EN LIGNE

**Fait :** https://huggingface.co/spaces/alexisgirard/bungerag — déployé, testé en visiteur réel : 96 s à froid, ~70 s à chaud pour une question inédite (2 vCPU gratuits), 0,7 s depuis le cache. Index dans le dataset privé alexisgirard/bungerag-index. Secrets configurés par API.

**Appris :** un déploiement se teste depuis l'extérieur (gradio_client), pas en se croyant sur parole ; et la latence du gratuit s'assume en l'affichant (« ~1-2 min ») plutôt qu'en la cachant.

**Surprise :** le validateur HF refuse une description de 62 caractères (max 60) — les plateformes valident tout, et c'est tant mieux.

## 2026-07-07 — Phase 8 : la génération locale et son vrai prix

**Fait :** Ollama/Qwen3.5-9B branché derrière `generate()` (une variable d'environnement, zéro autre changement — l'abstraction de la phase 5 paie). Harnais complet rejoué avec ce backend de réponse. Résultats finaux n=30 : **faithfulness 0,904 · precision 0,903 · recall 0,885 · abstention 10/10**, contre **0,935 · 0,893 · 0,848 · 8/10** pour Gemini.

**Appris :** la fiabilité est le vrai sujet du gratuit. Cette éval a survécu à : 3 kills mémoire (→ keep_alive=0, le 9B se décharge entre les appels), la congestion Cerebras (→ retries + dégradation gracieuse), 2 épuisements de quota journalier (→ sonde + reprise auto). Boucles auto-réparantes + cache = rien ne se perd jamais.

**Surprise :** le petit modèle local est PLUS strict sur l'abstention que le grand modèle cloud (10/10 vs 8/10) — mais moins nuancé : il refuse aussi ce qui méritait une réponse partielle. La rigueur et l'intelligence de la nuance ne sont pas la même chose. « Local » désigne ici le retrieval et la génération de réponse : la reformulation FR→EN utilise encore Cerebras lorsqu'il est disponible, et le juge d'évaluation est externe.

## 2026-07-07 — Phase 9 : publication

**Fait :** README professionnel (chiffres en tête, schéma mermaid, 3 tableaux de résultats, mode « bring your own corpus », leçons de terrain, limites assumées), LICENSE MIT, keep-alive GitHub Actions quotidien pour la démo, repo public https://github.com/alexisgirard-it/bungerag (audit de sécurité de l'historique : zéro clé, zéro corpus), carte projet ajoutée au portfolio avec métriques et liens.

**Appris :** publier, c'est d'abord auditer — on vérifie ce que contient l'historique git AVANT de le rendre public, pas après. Et un README pro se structure pour deux lecteurs à la fois : le recruteur qui scanne 10 secondes (chiffres en haut) et l'ingénieur qui lit 3 minutes (architecture, ablations, limites).

**Fin du build initial.** 9 phases, ~4 jours, 0 €. Le projet vit : démo en ligne, code public, chiffres défendables.

## 2026-07-07 — Vérification des références + comparatif 512/1024

**Fait :** 30 agents vérificateurs ont confronté chaque référence du jeu d'éval au corpus (preuves livre+page) : 23 confirmées, 7 corrigées — dont un terme que j'avais inventé (« psychonisme ») et une confusion sur la sémantique technique sens/signification. À cette date, `REVUE-REFERENCES.md` préparait encore la validation humaine. Puis : index 1024 construit (2h24), filtré, et comparé au 512 sur les 4 configs — égalité parfaite en config complète (100 %/100 % des deux côtés) → on reste en 512 (citations plus précises, prompts plus courts).

**Appris :** l'outil qui mesure doit être vérifié aussi durement que l'outil mesuré — l'éval a ses propres hallucinations. Et un test peut saturer : au niveau livre sur 20 questions, 512 et 1024 sont indiscernables ; conclure « pareil » serait abusif, la bonne conclusion est « indétectable à cette granularité ».

**Surprise :** le crash machine de la veille venait de MOI (embedding + 30 agents + juge en parallèle sur 16 Go). Règle adoptée : une seule charge lourde à la fois. La fiabilité, ça vaut aussi pour l'orchestrateur.

## 2026-07-07 — Extension (b) : décomposition des panoramiques

**Fait :** routeur + décomposition (1 appel Cerebras : classer, éclater en sous-questions, traduire) → retrieval par sous-question → synthèse unique. A/B sur 8 panoramiques : 4,5 → 6,2 livres cités, citations [n] 3,6 → 8,8. Déployé sur la démo (questions directes inchangées), testé en visiteur réel.

**Appris :** la faiblesse panoramique était pire que « couverture faible » — le pipeline refusait carrément (« Absent du corpus ») la question la plus naturelle du monde : l'abstention, vertu sur les pièges, devient un défaut quand le retrieval sous-alimente la synthèse. Corriger le retrieval a corrigé l'abstention abusive ET la discipline de citation, sans toucher au prompt.

**Surprise :** le chemin décomposé conserve un seul appel Gemini de génération, mais ajoute un appel Cerebras pour router, décomposer et traduire. Le surcoût n'est donc pas entièrement local, même s'il n'ajoute pas d'appel au générateur principal.

## 2026-07-31 — Clôture de l'évaluation V1

**Fait :** les sept références corrigées (q05, q12, q13, q16, q17, q20, q30) ont été relues et approuvées humainement sans nouvelle modification ; la décision canonique est consignée dans `eval/VALIDATION-HUMAINE.md` et les sept statuts ne sont plus provisoires. Les caches re-notés après correction sont complets (n=30 par métrique). Résultats finaux : Gemini **0,935 / 0,893 / 0,848, 8/10** ; Ollama **0,904 / 0,903 / 0,885, 10/10**. Le sentence-window reste un bras expérimental séparé : **0,969 / 0,873 / 0,922, 9/10**.

**Appris :** corriger la vérité-terrain peut faire baisser un score — ici le context recall passe de 0,903 à 0,848 — sans que le pipeline ait régressé. Un chiffre plus bas mais calculé contre des références validées vaut davantage qu'un meilleur chiffre fondé sur des brouillons erronés.

**Surprise :** l'écart était plus profond qu'un simple k différent. Le benchmark legacy
passait la reformulation anglaise à la recherche hybride entière, donc aux jambes dense et
BM25, alors que l'architecture annoncée visait dense FR + BM25 EN. Il utilisait aussi le
chemin direct sans le routeur panoramique. Les résultats ci-dessus restent une trace utile
du pipeline historique 40 → 6, mais ne sont attribués ni aux profils V1 actuels ni au Space.

## 2026-07-31 — Fermeture technique V1

**Fait :** le sentence-window a été gelé sur la branche séparée
`experiment/sentence-window-v1.1`. La branche stable reçoit deux profils explicites
(`public_v1` 12 → 5 et `research_40x6` 40 → 6), un schéma de résultat commun aux chemins
direct et panoramique, la validation structurelle des citations, des caches d'évaluation
fingerprintés et une CI sans corpus ni API. La démo Gradio a été reconstruite comme une
édition critique sobre inspirée de Bunge, avec cache borné, quotas atomiques, surface API
réduite et exposition minimale des sources. Le prompt interdit la restitution du corpus ;
un garde-fou retire en plus toute réponse recopiant plus de 20 mots consécutifs d'un
contexte, et les extraits publics sont bornés à 20 mots. Le déploiement sépare désormais
le jeton d'écriture local du jeton de lecture limité au dataset privé et supprime les
anciens fichiers distants hors liste blanche.

**Appris :** une page de citation ne se déduit pas d'un préfixe de chunk. Le nouveau
mapping recherche le texte intégral dans le texte recollé et échoue explicitement si
l'alignement est impossible. Sur 11 249 chunks, textes et identifiants sont restés
strictement identiques ; seules 38 plages de pages ont changé. Parmi elles, 37 existaient
dans l'index 512 filtré, la dernière appartenant aux chunks exclus. Une migration de
métadonnées vérifiée suffit donc : aucun embedding n'a été recalculé.

**Surprise :** l'interface était lisible en thème clair mais perdait son contraste lorsque
Gradio héritait du mode sombre du navigateur. Le test visuel réel, puis mobile à 390 px,
a permis de corriger ce défaut que les tests Python ne pouvaient pas voir. Autres limites
rendues explicites : la « traçabilité 100/100 » initiale était un échantillon qui n'avait
pas détecté ces 38 erreurs de plage ; et les scores publiés restent ceux du pipeline
legacy 40 → 6. Le sentence-window (commit `aec4846`) est lui aussi une mesure historique
dont les caches bruts ne sont pas versionnés, pas un résultat du commit de durcissement.
