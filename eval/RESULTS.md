# BungeRAG — Résultats finaux du harnais d'éval (31/07/2026)

Pipeline évalué (legacy pré-clôture) : chemin direct, recherche hybride utilisant la
reformulation EN pour les jambes dense **et** BM25, k=40 → reranker Qwen3-0.6B → top 6
→ Gemini Flash (rotation multi-modèles, température 0, prompt strict citations +
abstention). Il ne comportait ni le routeur panoramique ni les validateurs V1.

Juge : Cerebras gpt-oss-120b (distinct du générateur). RAGAS 0.4.3 épinglé.
Jeu : 30 questions de contenu en français + 10 pièges hors corpus. Les 30 références
ont été confrontées au corpus : 23 confirmées, 7 corrigées, puis les 7 corrections
[approuvées humainement](VALIDATION-HUMAINE.md) le 2026-07-31.

| Métrique | Score | Cible | Ce que ça mesure |
|---|---|---|---|
| **Faithfulness** | **0,935** | ≥ 0,75 ✅ | Les affirmations de la réponse sont-elles déductibles des extraits cités ? (anti-hallucination) |
| **Context precision** | **0,893** | — | Les extraits remontés sont-ils pertinents ? |
| **Context recall** | **0,848** | ≥ 0,80 ✅ | Les extraits couvrent-ils la réponse de référence ? |
| **Abstention (pièges)** | **8/10 strict** | ≥ 8/10 ✅ | Refus explicite « Absent du corpus » |

Les 2 pièges non refusés (ChatGPT, « recette préférée ») n'ont PAS halluciné : réponses
partielles explicitement cadrées sur ce que le corpus contient réellement (Bunge sur l'IA ;
la « recette du Bonheur » métaphorique) — pièges mal conçus plus que défaillance.

### Traçabilité de ces chiffres

Ces résultats proviennent du run finalisé avant l'introduction du harnais fingerprinté.
Ils ne décrivent ni `research_40x6` actuel, malgré les mêmes valeurs de k, ni `public_v1`.
À partir de la V1, chaque nouveau run archive le commit, les hashes du code, du prompt,
des questions, des dépendances et du manifeste d'index, les modèles de génération,
traduction, routage et jugement, le `config_id` et ses caches sous un `run_id` unique.

## Périmètre et limites

- La faithfulness mesure la fidélité aux extraits **récupérés**, pas la vérité ni
  l'exhaustivité du retrieval.
- Le context recall dépend du texte de référence. Sa valeur finale de 0,848 remplace
  l'ancien 0,903 calculé avant la correction des sept références.
- Pire cas identifié : q20 (biographie), où le retrieval manque une partie des pages
  d'enfance des mémoires (faithfulness 0,67 sur le bras Gemini de référence).
- La rotation de plusieurs modèles Gemini est imposée par les quotas du free tier : le
  bras « Gemini » n'est donc pas un modèle unique parfaitement homogène.
- Chaque réponse et métrique a été notée une fois par le même juge ; la variance du juge
  n'est pas mesurée et ses notes n'ont pas été calibrées sur un échantillon humain.
- Ces scores décrivent le pipeline legacy direct **k=40 → top 6**. Le Space utilise un
  autre pipeline et aucune de ses réponses individuelles n'hérite de ces scores.

## Trouvailles du build
1. +25 pts de hit@5 en nettoyant 837 chunks d'annexes (biblios, index, voix éditoriale de l'anthologie) — les points sont dans les données.
2. Le score du reranker mesure la proximité de sujet, PAS « ça répond » : piège « recette » à 0,966 → l'abstention doit vivre dans le prompt, pas dans un seuil.
3. Reformulation FR→EN : BM25 passe de 50 % à 95 % hit@5 sur corpus anglais interrogé en français.
4. Les tokens de « réflexion » (Gemini 2.5, gpt-oss-120b) se décomptent silencieusement des budgets de sortie : 2 bugs distincts, même cause.

## Comparatif génération locale vs API — résultats complets

Même pipeline legacy, même jeu de 40 questions et même juge. Les trois métriques RAGAS
disposent de **n=30** dans les deux bras. Seul le backend de réponse changeait via
`LLM_BACKEND`.

| Métrique | Gemini Flash (API) | Qwen 3.5 9B Q4 (réponse locale, M3 16 Go) |
|---|---|---|
| Faithfulness | **0,935** | 0,904 |
| Context precision | 0,893 | **0,903** |
| Context recall | 0,848 | **0,885** |
| Abstention pièges (strict) | 8/10 | **10/10** |
| Périmètre local | — | retrieval + génération de réponse |

Le bras Ollama n'est pas qualifié de « 100 % local » de bout en bout : dans l'état
évalué, la reformulation FR→EN est un appel utilitaire Cerebras lorsqu'il est disponible,
et l'évaluation elle-même utilise Cerebras comme juge. Le code prévoit une dégradation
gracieuse en conservant la question française si la reformulation externe échoue.

Depuis la fermeture technique V1, `LLM_BACKEND=ollama` commute aussi la traduction et
le routeur panoramique sur Ollama par défaut. Cette amélioration d'isolation est couverte
par les tests, mais les chiffres historiques ci-dessus n'ont pas été recalculés avec elle.

**Verdict nuancé** : le 9B local reste très fidèle, améliore le recall et refuse les
10 pièges, au prix d'une génération sensiblement plus lente sur le matériel évalué. Le
choix porte donc sur la confidentialité de la réponse, la latence et le comportement
d'abstention, pas sur un classement qualitatif absolu.

**Le prix de la fiabilité du gratuit, vécu pendant cette éval** : 3 processus tués (mémoire 16 Go saturée par le 9B + reranker → déchargement du modèle entre appels), congestion serveur Cerebras (retries + dégradation gracieuse : sans traducteur, la question FR continue seule), 2 épuisements du quota journalier (sonde de retour + reprise auto). Architecture finale : boucles auto-réparantes + caches par question/métrique + supervision.

## Sentence-window — bras expérimental séparé

Le bras sentence-window legacy conserve le retrieval sur des chunks de 512 tokens, puis
étend les passages retenus à leurs voisins uniquement pour la génération. La mesure
historique annonçait **n=30** pour chaque métrique :

| Métrique | Sentence-window expérimental |
|---|---:|
| Faithfulness | **0,969** |
| Context precision | **0,873** |
| Context recall | **0,922** |
| Abstention pièges (strict) | **9/10** |

Les caches bruts et métadonnées de ce run ne sont pas versionnés. Ces résultats restent
donc une trace historique, pas un benchmark reproductible du pipeline V1. Le code exact
est conservé au commit `aec4846` sur `experiment/sentence-window-v1.1` ; il n'appartient
pas à la V1 et n'est pas activé sur le Space.

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

## Décomposition des questions panoramiques (07/07/2026 — extension b)

Routeur (Cerebras, 1 appel : classe + décompose + traduit) → questions larges éclatées en
3-5 sous-questions → retrieval par sous-question → synthèse unique (toujours 1 seul appel
Gemini). A/B sur 8 questions panoramiques :

| Métrique (moyenne / 8 questions) | Pipeline direct | Décomposé |
|---|:---:|:---:|
| Livres distincts cités | 4,5 | **6,2** (+38 %) |
| Extraits mobilisés | 6 (fixe) | 9,6 |
| Citations [n] dans la réponse | 3,6 | **8,8** |

Cas emblématique : « Présente les grandes lignes de la philosophie de Bunge » — le pipeline
direct répondait **« Absent du corpus »** (6 extraits épars jugés insuffisants pour une
synthèse → abstention à tort) ; le décomposé répond par une synthèse en 5 sections,
8 livres, 11 citations. La décomposition ne corrige pas qu'une couverture faible : elle
corrige des refus injustifiés ET une discipline de citation qui s'effondrait sur les
questions larges (2 réponses baseline sur 8 sans aucun [n]).

Coût : +1 appel Cerebras par question (routeur) ; latence panoramique observée sur le
Space CPU gratuit : ~6 min. Le cache du Space est en mémoire et accélère une question
déjà posée tant que le processus n'a pas redémarré. Questions directes : pipeline de
réponse inchangé après routage.
