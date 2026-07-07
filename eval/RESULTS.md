# BungeRAG — Résultats du harnais d'éval (06/07/2026)

Pipeline évalué : hybride (dense FR + BM25 sur reformulation EN) k=40 → reranker Qwen3-0.6B → top 6 → Gemini Flash (rotation multi-modèles, temp 0, prompt strict citations+abstention).
Juge : Cerebras gpt-oss-120b (≠ générateur, pas de biais d'auto-préférence). RAGAS 0.4.3 épinglé.
Jeu : 30 questions de contenu en français (références = brouillon IA, à valider) + 10 pièges hors corpus.

| Métrique | Score | Cible | Ce que ça mesure |
|---|---|---|---|
| **Faithfulness** | **0,935** | ≥ 0,75 ✅ | Les affirmations de la réponse sont-elles déductibles des extraits cités ? (anti-hallucination) |
| **Context precision** | **0,893** | — | Les extraits remontés sont-ils pertinents ? |
| **Context recall** | **0,903** | ≥ 0,80 ✅ | Les extraits couvrent-ils la réponse de référence ? |
| **Abstention (pièges)** | **8/10 strict** | ≥ 8/10 ✅ | Refus explicite « Absent du corpus » |

Les 2 pièges non refusés (ChatGPT, « recette préférée ») n'ont PAS halluciné : réponses
partielles explicitement cadrées sur ce que le corpus contient réellement (Bunge sur l'IA ;
la « recette du Bonheur » métaphorique) — pièges mal conçus plus que défaillance.

## Limites assumées
- Faithfulness mesure la fidélité aux extraits RÉCUPÉRÉS, pas la vérité, ni si les meilleurs extraits ont été trouvés.
- Context recall dépend de la qualité des références (brouillons IA — cas q28 : recall 0,00 avec une réponse correcte = référence mal formulée, pas pipeline défaillant).
- Pire cas identifié : q20 (biographie) — le retrieval rate les pages d'enfance des mémoires (faithfulness 0,67).
- Générateur hétérogène (rotation de 5 modèles Gemini imposée par le quota réel : ~20 req/jour/modèle).
- Notation en une passe par un seul juge ; non re-testé en re-run (variance du juge non mesurée).

## Trouvailles du build
1. +25 pts de hit@5 en nettoyant 837 chunks d'annexes (biblios, index, voix éditoriale de l'anthologie) — les points sont dans les données.
2. Le score du reranker mesure la proximité de sujet, PAS « ça répond » : piège « recette » à 0,966 → l'abstention doit vivre dans le prompt, pas dans un seuil.
3. Reformulation FR→EN : BM25 passe de 50 % à 95 % hit@5 sur corpus anglais interrogé en français.
4. Les tokens de « réflexion » (Gemini 2.5, gpt-oss-120b) se décomptent silencieusement des budgets de sortie : 2 bugs distincts, même cause.

## Comparatif local vs API (07/07/2026 — phase 8)

Même pipeline, même jeu de 40 questions, même juge (Cerebras). Seul le générateur change (`LLM_BACKEND`).

| Métrique | Gemini Flash (API) | Qwen 3.5 9B Q4 (100 % local, M3 16 Go) |
|---|---|---|
| Faithfulness | **0,935** | 0,912 *(n=25)* |
| Context precision | 0,893 | **0,902** *(n=24)* |
| Context recall | 0,903 | **0,928** |
| Abstention pièges (strict) | 8/10 | **10/10** |
| Réponses avec citations [n] | **28/30** | 26/30 |
| Génération médiane | **~15 s** | 146 s |
| Confidentialité | question envoyée à Google | **rien ne quitte la machine** |

*(n<30 : 11 notes juge perdues sur épuisement du quota journalier Cerebras, complétées dès son retour — les moyennes sont stables entre n=13, 25 et 30.)*

**Verdict nuancé** : le 9B local est étonnamment fidèle (0,91 vs 0,94 — l'écart est faible), plus strict sur l'abstention, comparable sur le retrieval (normal : le retrieval est identique). Il paie en discipline de citation (13 % de réponses sans [n]) et surtout en latence (10×). Le choix local vs API n'est donc PAS qualitatif d'abord : c'est un arbitrage confidentialité/latence/coût — et il est désormais chiffré.

**Le prix de la fiabilité du gratuit, vécu pendant cette éval** : 3 processus tués (mémoire 16 Go saturée par le 9B + reranker → déchargement du modèle entre appels), congestion serveur Cerebras (retries + dégradation gracieuse : sans traducteur, la question FR continue seule), 2 épuisements du quota journalier (sonde de retour + reprise auto). Architecture finale : boucles auto-réparantes + caches par question/métrique + supervision.

## Chunks 512 vs 1024 tokens (07/07/2026 — extension a)

Mêmes 20 questions, mêmes conditions (re-passe fraîche des deux index, filtrage annexes identique).

| Config | 512 : hit@5 / @10 | 1024 : hit@5 / @10 |
|---|:---:|:---:|
| BM25 seul | 50 % / 75 % | 60 % / 70 % |
| Dense seul | 85 % / 100 % | 90 % / 95 % |
| Hybride | 85 % / 95 % | 85 % / 95 % |
| **Hybride + reranker** | **100 % / 100 %** | **100 % / 100 %** |

**Verdict : égalité au niveau qui compte** (config complète : plafond des deux côtés — le
test au niveau livre sur 20 questions ne peut plus les séparer). **On reste en 512**, pour
trois raisons pratiques : citations plus précises (plage de pages ~2× plus étroite), prompts
de génération ~2× plus courts à nombre d'extraits égal (quota Gemini ménagé), et index déjà
en production. Limite honnête : un jeu plus grand et une vérité-terrain au niveau page
pourraient les départager — au niveau livre, la différence est indétectable.

*(Note : le 512 affiche ici 100 % contre 95 % en phase 4 — entre-temps, la vérité-terrain a
été élargie sur justification bibliographique et l'index a reçu la passe de filtrage v3.
Les chiffres d'une éval vivent avec leur jeu d'éval.)*
