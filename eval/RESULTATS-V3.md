# BungeRAG · essais de la V3

Mesures du 25 et du 26 novembre 2026. Le point de départ et les conventions de pagination sont décrits dans le [bilan V2](RESULTATS-V2.md). Les résultats par question, les révisions et les délais bruts sont dans [mesures-v3.json](mesures-v3.json).

## Rechercher et reclasser

Sur les 30 questions historiques, la V2 retrouvait 10 références annotées dans les cinq premiers résultats. Parmi les 20 restantes, 14 avaient disparu avant le reclassement et 6 à cette étape. Le profil de rédaction V3 avec Horizon Labs et 24 candidats retrouve **13 références sur 30** sur les mêmes questions et traductions. La comparaison à 12, 24 et 40 candidats donne respectivement 12, 13 et 12 résultats retrouvés. [Diagnostic V2](diagnostic-recherche-v2.json)

| Embedding | Top 5 sur 227 passages | Rang réciproque moyen | Top 5 dense sur index complet |
|---|---:|---:|---:|
| Qwen3-Embedding-0.6B | 21/30 | 0,368 | 9/30 |
| IBM Granite 311M Multilingual R2 | 21/30 | 0,380 | 9/30 |
| EmbeddingGemma 2, texte | 17/30 | 0,303 | 6/30 |
| Microsoft Harrier 0.6B | 20/30 | 0,311 | |

Qwen est conservé. Granite obtient un rang moyen un peu meilleur sur le petit groupe. Les deux retrouvent autant de références à cinq passages sur l’index complet. Le comparateur de classement mesure 13/30 en encodant la question anglaise et 11/30 dans les deux variantes hybrides avant reclassement. Le français reste utilisable pour la recherche vectorielle et le reclassement reçoit la question originale. [Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) · [Granite](https://huggingface.co/ibm-granite/granite-embedding-311m-multilingual-r2) · [Horizon Labs](https://huggingface.co/Horizon-Labs/multilingual-reranker-small)

Sur les questions réservées, la recherche dense seule interroge les **10 412 passages** avec le texte original de chaque question. Les deux index ont un encodage des documents propre à leur modèle. Les éditions du jeu et de la bibliothèque ont été comparées avant de compter les pages.

| Embedding | Rang 1 | Top 5 | Rang réciproque moyen | Citation / souvenir / définition / symbole / argument au top 5 |
|---|---:|---:|---:|---|
| Qwen3-Embedding-0.6B | 8/25 | 18/25 | 0,466 | 3/5 · 2/5 · 5/5 · 5/5 · 3/5 |
| EmbeddingGemma 2, texte (270 M) | 10/25 | 16/25 | 0,508 | 2/5 · 2/5 · 3/5 · 5/5 · 4/5 |
| IBM Granite 311M Multilingual R2 | 9/25 | 12/25 | 0,410 | 1/5 · 1/5 · 3/5 · 3/5 · 4/5 |

Qwen récupère huit pages cibles qui manquaient aux cinq premiers résultats de Granite (contre deux pour Granite) et quatre pages cibles qui manquaient à EmbeddingGemma 2 (`citation-4`, `souvenir-4`, `définition-1`, `définition-4`, contre deux pour Gemma : `souvenir-2`, `argument-2`), tout en le devançant aussi sur les 30 questions historiques (9/30 contre 6/30). Malgré un bon rang 1 d’EmbeddingGemma 2 (10/25, MRR 0,508), le meilleur rappel top 5 de Qwen sur les deux jeux confirme définitivement **`Qwen3-Embedding-0.6B`** comme étage dense du profil public. Les temps mesurés sur le Mac pendant d’autres calculs servent à reproduire l’essai. [Protocole](../src/benchmark_encoders.py) · [Mesures par question](mesures-v3.json)

## Recette réservée

La série a été figée avant le choix des options. Elle contient 25 questions avec pages cibles et cinq demandes de clarification ou sans source disponible.

| Parcours sur les questions documentées | Première réponse au rang 1 | Au moins une cible dans le top 5 | Ensemble des prémisses |
|---|---:|---:|---:|
| V2, sélection des blocs destinés à la rédaction | 16/25 | 21/25 | 3/5 |
| V3, sélection des blocs destinés à la rédaction | 15/25 | 23/25 | 3/5 |
| V3, recherche directe de pages | 14/25 | 24/25 | 1/5 |

Le reclassement V3 gagne deux références au total par rapport à la V2. La recherche par page donne la réponse d’orientation attendue dans les cinq cas sans cible unique. Son seul échec de localisation concerne une question de notation. Le contrôle des ancrages retrouve 125 extraits sur leurs pages. Les délais de recherche avec traduction ont été mesurés sur le Mac pendant plusieurs calculs et ne servent pas de référence pour le CPU du Space. [Questions réservées](lecture-reservee.jsonl)

## Rédaction et disponibilité

Les six cas à passages identiques ont donné cinq réponses documentées et une abstention avec Gemini 3.1 Flash-Lite lors des essais V2. Dans la nouvelle série, Gemini 4 Hydrogen et 3.8 Flash ont renvoyé cinq erreurs 503 et une erreur 429 chacun. Gemini 3.5 Flash-Lite a renvoyé quatre erreurs 503, une abstention et une réponse retirée au contrôle des citations. Une deuxième recette de raisonnement a reçu des erreurs 400. Une requête minimale a confirmé le refus de région depuis l’environnement de test. Les deux modèles Cerebras accessibles en métadonnées ont répondu 402 à la requête de génération. Ces résultats justifient le maintien de Flash-Lite comme profil de rédaction déjà vérifié sur le Space et la disponibilité indépendante de la recherche et des dossiers édités. Ils ne classent pas la qualité argumentative des candidats. [Bilan V2](RESULTATS-V2.md) · [Palier Gemini](https://aistudio.google.com/docs/pricing) · [Tarifs Cerebras](https://www.cerebras.ai/pricing)

La relecture des deux réponses de Qwen3.5 9B via Ollama a trouvé deux problèmes d’interprétation. Sur le bonheur, le modèle repère la perte d’une justification, mais passe sous silence la croyance dans la définition. Sur Llama 3.1, il assimile les neurones biologiques et artificiels avant de changer le critère de compréhension. Le dossier édité présente les deux hypothèses et le rôle des prémisses explicites. L’option Ollama reste accessible sur le Mac.

## Référentiel et interface

Le répertoire contient 25 ouvrages et 54 chapitres du *Traité* repérés. Le référentiel éditorial comptait 37 fiches et 25 relations lors de la première recette. Les 125 extraits affichés ont été retrouvés dans leur page de concordance. Les repères formels et renvois transcrits automatiquement sont signalés comme tels. La lecture d’un extrait, le passage vers l’Atlas et le retour au texte ont été testés au clavier avec la définition de psychon, p. 70 du livre et PDF p. 78. Les deux dossiers d’éthique permettent d’identifier les enseignements directs des sources et les étapes de reconstruction. [Référentiel](../src/referentiel.json)

Pour les cinq questions à plusieurs références, la lecture des dossiers et des relations a fait passer la couverture complète des références de 1/5 à 3/5 sur le premier audit. Deux questions restent partielles. Les 54 ouvertures de chapitre ont été contrôlées contre la concordance.

Sur ordinateur, l’argument sur le bonheur s’est ouvert depuis une question de recherche. La suspension puis le rétablissement du postulat ont modifié l’état de sa justification. Sur mobile, le dossier sur l’IA s’ouvre depuis une navigation dédiée. Ces parcours ont également été rejoués à partir du bundle de 23 fichiers destiné au Space. Le résultat du psychon y affiche les deux numéros de page.


## Recette sur le Space

Le 26 novembre, le Space CPU a servi le profil V3. La recette sur le navigateur a confirmé la recherche paginée, la navigation jusqu’à une page de chapitre, l’Atlas au clavier et retour à la recherche, puis la suspension d’un postulat et l’ouverture du dossier IA sur mobile. La première révision publique a rédigé une réponse sur le psychon en 91 secondes. Ses quatre extraits ont été contrôlés dans les PDF, aux pages physiques 78, 76 et 54 de leurs éditions respectives. La révision suivante utilise le rendu côté navigateur. [Space](https://huggingface.co/spaces/alexisgirard/bungerag) · [Révision testée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/7cab50878e3ddb62bbe07398537589f0580b03bf)

Le référentiel public étendu contient 77 fiches et 65 liens. Sur les cinq demandes à plusieurs références, il permet de retrouver toutes les pages annotées pour quatre demandes après ouverture de l’argument. Ces cas sont les mêmes que ceux du premier audit. Le résultat documente une vérification de la couverture sur ces questions connues. [Inventaire des chapitres](COUVERTURE-TRAITE.md)

La révision suivante retrouve aussi la notation ℳ = ⟨D, F, I⟩ en saisie directe. Le test navigateur a affiché la page 82 du livre, PDF p. 93, puis le lexique des symboles dans l’Atlas. [Révision testée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/8df36386f741039ec1f999034d64a7d77d22ece3)


## Éditions, attribution et vérification des dossiers

Les 25 exemplaires sont identifiés dans le référentiel par leur SHA-256 et les indications relevées dans le livre ou l’EPUB. Le PDF de *Causality and Modern Science* correspond à l’édition revue de Dover (1979, ISBN 978-0-486-23728-2). La phrase citée est attribuée à Emerson, la discussion d’une objection distincte à H. van Rensselaer Wilson. La recette publique a vérifié l’attribution, la navigation et l’effet de deux contestations successives. Un dossier avec une donnée contemporaine fournie par le lecteur conserve la source et la date avec le statut « à vérifier ». [Révision éditions et attribution](https://huggingface.co/spaces/alexisgirard/bungerag/commit/58328b02fd300a2280a8c5a9bb068c7ec2987776)

Les six recherches chronométrées sur le CPU du Space ont affiché leur page attendue. Les cinq recherches par citation ou notation ont pris entre 0,36 et 0,86 seconde dans ce scénario, et la recherche par souvenir français a pris 15,93 secondes. L’échantillon est trop petit pour estimer un p95 de production. L’appel de rédaction lancé en parallèle a rencontré un verrou à l’import de PyTorch sur cette révision. Cette panne de chargement a motivé la sérialisation des importations et des initialisations des modèles.

Sur la révision suivante, les deux parcours lancés ensemble ont réussi. Le souvenir français a retrouvé la réfraction au bout de 23,08 secondes, PDF p. 32. La rédaction obtenue en 45,42 secondes attribue la citation à Emerson, p. 101 du livre et PDF p. 135. Elle omet toutefois d’expliquer la critique par Bunge demandée dans la seconde partie. La recette suivante retient cette omission comme échec de couverture. [Révision de la recette concurrente](https://huggingface.co/spaces/alexisgirard/bungerag/commit/e7a4643d723f59421963661790d22a93d9e063fb)

Une deuxième rédaction, en 53,09 secondes, ajoute la distinction entre fatalisme et déterminisme causal. Elle laisse de nouveau implicite la réaction de Bunge à Emerson. La réponse éditée ajoute cette réaction avec son propre extrait. Le contrôle local accepte les deux ancrages p. 101 du livre, PDF p. 135, et laisse au parcours de recherche les variantes dont la citation ou la demande diffèrent. Le contrôle avant publication valide 25 éditions, 87 citations de fiches et 75 relations. Sur l’EPUB, la recette accepte un extrait de sa section et rejette une autre section, un autre exemplaire et un texte inventé. [Deuxième révision testée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/ae7686f8eef03fe9f87a074f550ebb185865e693)

Le nouvel appel public affiche les deux appuis en 1,82 seconde, tandis que la recherche simultanée sur la réfraction retrouve PDF p. 32 en 21,18 secondes. Les deux extraits anglais de la réponse ont été contrôlés dans le PDF de l’édition 1979. Ce temps concerne une réponse éditée à une citation reconnue. [Révision vérifiée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/6f664c14d867b419bf4cc9817599c287df96962f)

Dans l’Atlas, la comparaison entre le tome I du *Traité* et *Scientific Materialism* présente la portée des deux énoncés sur l’existence. L’annotation de lecture indique sous quelle interprétation ils sont compatibles. La quatrième séquence de l’Atelier essaie deux suspensions, trois rétablissements et un changement de sens. L’interface affiche les appuis à rétablir pour chaque justification. Le contrôle local passe sur huit dossiers, 29 citations et 21 modifications dans quatre séquences. [Séquences de l’Atelier](recette-atelier.json)

Le contrôle navigateur confirme sur le Space l’affichage d’une seule comparaison pour la paire d’ouvrages, puis la suspension d’une des deux preuves de l’unicité du monde et le retour à l’état initial. L’essai sur une question libre relative à la prévision produit deux branches en 36,93 secondes. Leur suspension indépendante fonctionne. La relecture relève deux glissements. La reproduction de données est qualifiée de prédiction valide et l’exactitude future devient le seul test d’une explication. La recette demande désormais de vérifier la distinction entre ajustement, validation indépendante et mise à l’épreuve d’un mécanisme. [Révision testée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/aae58b0404310163a892cf1ebe0805f1c56452c7) · [Critères de relecture](recette-atelier.json)

Sur le même CPU du Space, après chargement des modèles, les 20 recherches directes de la série réservée retrouvent une page cible. Le premier résultat arrive en **1,465 seconde de médiane et 1,99 seconde au 95e percentile empirique**, file et transport inclus. Les cinq souvenirs en français prennent de 1,46 à 2,68 secondes. Les cinq demandes sans cible obtiennent toutes l’orientation attendue. L’échantillon mesure des recherches de passages à chaud, sur cette série et cette révision. [Protocole](../src/measure_reader_http.py) · [Mesures](mesures-v3.json)

Dans *Scientific Realism*, les 37 sections associées au sommaire affichent désormais le titre de l’essai ou de la partie. Les 38 identifiants de section et les textes extraits correspondent à l’index existant. Une recherche dans le premier essai affiche son titre complet, avec la section ch05. Un renvoi produit par la rédaction conserve en plus la position du caractère. [Notice et intitulés](../src/referentiel.json)

La reprise sur le Space retrouve la section EPUB en 0,35 seconde. Sur le cas libre, la rédaction soumet deux branches en 49,72 secondes. La seconde présente la précision comme un indice sous contrôle, et la première décrit une subsomption au lieu de déclarer une prédiction validée. L’étape reliant un modèle au mécanisme réel mérite encore un contrôle explicite. Le comportement des deux branches après suspension est confirmé. [Révision vérifiée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/f9862f78d7cdd86e2d1f20e16c4d92bea46dec66)

La recette locale vérifie 91 citations et 81 relations. Les appuis supplémentaires relient l’émergentisme du tome IV, la place de la psychologie au tome VII et la définition du psychon. En éthique, le tome VIII fournit un repère pour distinguer bonheur et bien-être. Les contrôles des formules préservent les opérateurs, les variables et la portée des parenthèses. Une notation concise sans appui exact donne une absence de passage. [Couverture du Traité](COUVERTURE-TRAITE.md)

La recette publique retrouve la formule compacte ℳ=⟨D,F,I⟩ au PDF p. 93 et distingue une variable différente. Dans l’Atlas, le passage du tome VII (PDF p. 14) conduit au passage du tome IV (PDF p. 200). Dans l’Atelier mobile, suspendre la thèse sur l’émergence des propriétés mentales suspend la justification neurobiologique et laisse accessible l’hypothèse fonctionnelle. Le contrôle local couvre 31 appuis et 23 modifications sur huit dossiers. [Révision vérifiée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/dd658e2c4c43a9235614530f54275232e3e25597)

### Renvois du graphe à budget fixe

L’essai à budget fixe de six fiches compare les racines seules, l’expansion sans plafond de racines (`graphe_parent`) et le plafond à 3, 2 ou 1 racine sur les cinq cas historiques à plusieurs prémisses ([questions réservées](lecture-reservee.jsonl)) et sur six nouvelles formulations indépendantes ([recette de liaisons](liaisons-reservees.jsonl)).

| Variante (budget de 6 fiches) | Série historique (5 cas) | Nouvelles formulations (6 cas) | Total complet (11 cas) |
|---|---:|---:|---:|
| Pages seules | 1/5 | 1/6 | 2/11 |
| Fiches sans liens | 3/5 | 3/6 | 6/11 |
| Graphe sans plafond de racines | 3/5 | 5/6 | 8/11 |
| Graphe plafonné à 3 racines (`seed_limit=3`) | 4/5 | 5/6 | 9/11 |
| Graphe plafonné à 2 racines (`seed_limit=2`) | 5/5 | 4/6 | 9/11 |
| Graphe plafonné à 1 racine (`seed_limit=1`) | 5/5 | 4/6 | 9/11 |

Plafonner l’expansion initiale à 3 racines (`seed_limit=3`) gagne un cas complet sur la série historique (4/5 contre 3/5) tout en préservant 5/6 cas complets sur les nouvelles formulations (alors que 2 ou 1 racine perdent le troisième appui de `plasticite-esprit`) et en améliorant les rangs des appuis sur `existence-et-matiere` et `action-destin`. Ce réglage est retenu dans l’Atelier (`open_question`) et l’enrichissement par graphe de la rédaction (`add_linked_passages`). [Protocole](../src/compare_graph_evidence.py) · [Mesures](mesures-v3.json)

### Extension des chaînes d’arguments et contrôle des transpositions

Le référentiel `2026-11-26.17` passe à **103 fiches et 96 liens vérifiés** sur les 25 éditions indexées. Trois nouveaux dossiers d’Atelier ouvrent des chapitres qui n’avaient pas encore de chaîne argumentée publiée : **Systémisme et émergence** (T4 `System`, avec formalisation `S → L, ¬L ⊨ ¬S`), **Efficacité, vérité et rectitude** (T6 `Producing Evidence`, T7/II `Technology` et T8 `Action`, avec formalisation `E ⊭ V · E ⊭ J`) et **Sens, référence et synonymie** (T1 `Intension` et T2 `Meaning`), complétés par la chaîne Postulat 4.9 → Théorème 4.1 dans T4 `Mind`. La couverture de l’Atelier passe de 7 à **13 chapitres du *Traité* reliés** sur 54.

Le script `src/audit_workshop.py` (appelé aussi avant toute publication par `src/push_space.py`) contrôle désormais les **conditions nécessaires des transpositions** : chaque conclusion conditionnelle doit dépendre à la fois d’un fait contemporain daté avec source HTTPS, d’une hypothèse explicite de transposition (et d’un appui textuel de Bunge pour les transpositions issues du système), et la suspension de chacune de ces conditions doit effectivement suspendre la conclusion. La recette locale valide **11 dossiers, 45 appuis, 6 conditions de transposition, 5 formalisations booléennes et 41 modifications** réparties sur huit séquences, ainsi que les deux cas libres documentés. La publication sur le Space confirme 11 dossiers d’Atelier, 103 notions dans l’Atlas et l’affichage en direct des trois nouvelles chaînes avec leurs pages PDF et leurs fragments formels (`S → L, ¬L ⊨ ¬S` et `E ⊭ V`). [Couverture du Traité](COUVERTURE-TRAITE.md) · [Séquences](recette-atelier.json) · [Révision vérifiée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/6a7070c306b5e6317a9137c22c12f113484d5828)

### Comparatif du reclasseur Horizon Labs (`small` vs `base`)

Sur les mêmes pools de 24 candidats hybrides (30 questions historiques et 25 questions réservées documentées), `Horizon-Labs/multilingual-reranker-base` (308 M, 1,23 Go) est comparé à `Horizon-Labs/multilingual-reranker-small` (141 M) :

| Reclasseur (24 candidats → 5) | Historique Hit@1 / Hit@5 / MRR | Réservée Hit@1 / Hit@5 / MRR / Args | Médiane CPU (5 q. sous charge Mac) |
|---|---|---|---|
| `Horizon-Labs/multilingual-reranker-small` | **4/30 · 13/30 · 0,230** | 15/25 · **23/25** · 0,727 · **3/5** | **35,4 s** |
| `Horizon-Labs/multilingual-reranker-base` | 3/30 · 10/30 · 0,188 | **18/25** · **23/25** · **0,810** · **3/5** | 52,8 s (+49 %) |

`base` améliore le rang 1 sur la série réservée (18/25 contre 15/25) sans augmenter le rappel au top 5 (23/25 pour les deux, 3/5 arguments complets), mais régresse de trois cas sur le jeu historique (10/30 contre 13/30 : perte des questions 4, 12, 22 et 24 pour un seul gain sur la 14) tout en doublant l’empreinte mémoire et en alourdissant la latence CPU de 49 %. **`Horizon-Labs/multilingual-reranker-small` est donc conservé.** [Protocole](../src/compare_rerankers.py) · [Mesures](mesures-v3.json)

### Cascade LLM gratuite et budget de réflexion

Dans `src/generate.py` et `src/config.py`, `PUBLIC_V3` remplace le modèle unique `gemini-3.1-flash-lite` par deux cascades avec bascule automatique sur erreurs transitoires (`429`, `500`, `503`, `504`) ou réponse vide :

- **Rédaction, vérification et Atelier :** `gemini-4-hydrogen` → `gemini-3.8-flash` → `gemini-2.5-flash` → `gemini-3.1-flash-lite` → `gemini-3.5-flash-lite`, avec `thinking_budget=512` ajouté à `max_output_tokens` sur les modèles pensants et un **coupe-circuit temporaire par modèle** (5 min sur `500`/`503`/`504` ou réponse vide, 30 min sur `429`, délai court de 15 s avant bascule). Dès qu’un modèle de tête est saturé, il est écarté en 0 ms sur les appels suivants (y compris la passe de vérification) puis retenté automatiquement après la pause.
- **Traduction et routage :** `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemini-2.5-flash` (sans `thinking_config` sur les variantes `flash-lite`).

Un premier essai plaçant `gemini-4-hydrogen` et `gemini-3.8-flash` en tête sans `thinking_budget` borné a montré des `503`/`504` fréquents (+30 à +45 s d’attente) et une troncature JSON sur `gemini-2.5-flash`. Avec `gemini-2.5-flash` en tête et le budget de réflexion borné, sur les deux cas libres de l’Atelier (`prévision-explication` et `algorithme-efficace-et-norme`) :

| Profil | `prévision-explication` | `algorithme-efficace-et-norme` | Suspension de prémisse |
|---|---|---|---|
| `gemini-3.1-flash-lite` seul | 15,10 s · 2 branches (principale + rivale) | 14,05 s · 1 branche | OK |
| Cascade `PUBLIC_V3` (`gemini-2.5-flash` en tête) | **13,60 s** · 2 branches (principale + rivale) | **12,97 s** · **2 branches (principale + rivale)** | OK |

La cascade améliore simultanément la rapidité, la couverture des interprétations rivales et la résilience aux quotas journaliers par modèle gratuit. La révision publiée sur le Space confirme la réponse sourcée sur la distinction vérité/efficacité en 40,79 s (chargement à froid compris, 2 sources vérifiées, aucune abstention) et l’ouverture du dossier d’Atelier correspondant en 0,35 s. [Mesures](mesures-v3.json) · [Révision vérifiée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/aed5f4c9ba5c13b72799878a1aaf8cf32f5fda76)

### Comparatif qualitatif contrôlé des LLM sur passages identiques

Sur quatre questions exigeantes fournies avec les mêmes passages vérifiés (`attribution-emerson`, `ethique-bonheur`, `biais-holisme`, `efficacite-verite` via [compare_llm_blind.py](../src/compare_llm_blind.py)) :

- **`gemini-4-hydrogen`** produit nettement les réponses les plus complètes et fidèles lorsqu’il dispose de quota : **7 sources vérifiées** sur Emerson (distinction exacte de la voix d’Emerson, critique de Bunge, incompatibilité fatalisme/déterminisme causal), **6 sources vérifiées** sur le bonheur et le bien-être, **3 sources** sur l’anti-holisme, et abstention honnête lorsqu’une citation soumise est absente du passage. Il atteint vite son quota gratuit (`429`).
- **`gemini-2.5-flash`** (avec `thinking_budget=512`) produit 2 branches validées (principale + rivale) sur les deux cas libres de l’Atelier en 13,0–13,6 s, mais partage un quota gratuit journalier serré (`429`).
- **`gemini-3.1-flash-lite`** reste disponible en continu (4/4 réponses sans erreur, 1,9–7,1 s), mais avec des réponses plus courtes (1 à 2 sources) qui omettent parfois une sous-question (ex. la réponse de Bunge à Emerson ou la distinction bonheur/bien-être).

Ce contraste confirme l’architecture retenue : **meilleur en premier (`gemini-4-hydrogen` → `3.8-flash` → `2.5-flash` → `3.1-flash-lite` → `3.5-flash-lite`) avec coupe-circuit par modèle** (5 min sur `503`/`504`, 30 min sur `429`).

### Couverture des 9/9 tomes, logique du premier ordre et fidélité orientée

Le référentiel `2026-11-26.18` atteint **109 fiches et 105 liens vérifiés** sur les 25 éditions. Deux nouveaux dossiers ouvrent les deux derniers tomes qui n’avaient pas encore de chaîne d’Atelier publiée : **Conjecture, inférence et théorie** (T5 `Inferring`, `Conjecturing`, `Systematizing` + T6 `Producing Evidence`) et **Modèle factuel et physique** (T7/I `Formal Science` et `Physical Science`), portant la couverture à **9/9 tomes/parties du *Traité*** (**18/54 chapitres reliés**, **13 dossiers d’Atelier**, 55 appuis, 49 modifications contrôlées sur 10 séquences). [Couverture du Traité](COUVERTURE-TRAITE.md)

Le module [formal_logic.py](../src/formal_logic.py) ajoute **trois preuves vérifiées en logique du premier ordre** sur structures finies (distinction explicite entre formalisation éditoriale, preuve vérifiée et démonstration reproduite de l’auteur) :
- **Unicité du monde (`monde`) :** énumération exhaustive des relations binaires `⊑` sur domaines finis de taille 1 à 3 (`∀x∀y ((x ⊑ y ∧ y ⊑ x) → x = y), ∀x (x ⊑ m₁), ∀x (x ⊑ m₂) ⊨ m₁ = m₂`, 0 contre-exemple sous les axiomes complets, et construction d’un contre-modèle fini explicite sans antisymétrie).
- **Synonymie sémantique (`signification`) :** réfutation de la suffisance de la coréférence `R(c₁) = R(c₂)` par contre-modèle fini explicite (`S(c₁) ≠ S(c₂)`).
- **Modèle factuel `ℳ = ⟨D, F, I⟩` (`modele_factuel`) :** preuve que le seul formalisme `F` ne suffit pas à constituer un modèle factuel sans domaine concret `D` et interprétation `I`.

La suite de fidélité ([audit_fidelity.py](../src/audit_fidelity.py), bloquante avant toute publication dans `push_space.py`) contrôle **8 formulations orientées** (dont fausses attributions à Bunge sur une citation d’Emerson, demandes d’avis posthume sur GPT-4/Gemini 4, demandes d’édition française et présuppositions biaisées sur holisme/empirisme/formalisme) et **2 conversations longues multi-tours (22 tours)** sans aucune mutation du référentiel ni des dossiers sources. La révision publiée sur le Space confirme en direct les 13 dossiers d’Atelier, les 109 notions de l’Atlas, les dossiers T5 (`conjecture`) et T7/I (`modele_factuel`) ainsi que les blocs de preuve du premier ordre (`∀x∀y`). [Révision vérifiée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/cfab09ddf404289cdfc52d77c0811b110495c19b)

### Pages voisines à budget strictement égal (5 pages)

Sur les 25 questions réservées documentées et les 6 nouvelles formulations de liaisons ([compare_neighbors_equal_budget.py](../src/compare_neighbors_equal_budget.py)), remplacer les rangs 4–5 par les pages physiques voisines à budget strictement égal de 5 pages donne :

| Variante (budget strict de 5 pages) | Réservée : Hit@1 / Au moins 1 cible / Arguments complets | Nouvelles liaisons (6 cas) : Au moins 1 / Arguments complets |
|---|---|---|
| **5 premières pages classées (`top5`)** | 14/25 · **24/25** · 1/5 | **4/6** · 1/6 |
| Top 3 + 2 pages voisines (`top3_voisines_5`) | 14/25 · 20/25 (-4) · 3/5 | 4/6 · 2/6 |
| Top 2 + 3 pages voisines (`top2_voisines_5`) | 14/25 · 17/25 (-7) · 3/5 | 4/6 · 2/6 |

À budget de pages égal, insérer les pages voisines fait perdre **4 à 7 questions** sur le jeu réservé (24/25 → 20/25 ou 17/25), alors que l’expansion par graphe de l’Atlas (`seed_limit=3`) atteint déjà **9/11 arguments complets** sans dégrader les 5 premières pages. Le classement de recherche conserve donc strictement les **5 premières pages (`top5`)**.

## Titres et pages voisines

Essai exploratoire après correction de la notation sur les 25 questions documentées de la première recette. Les traductions anglaises sont les mêmes dans les trois variantes BM25. Les pages sont dédupliquées avant de calculer les rangs.

| Pondération des titres dans BM25 | Au rang 1 | Dans les 5 premières pages | Rang réciproque moyen |
|---:|---:|---:|---:|
| 0 | 10/25 | 18/25 | 0,526 |
| 0,2 | 11/25 | 19/25 | 0,568 |
| 1,5 | 12/25 | 19/25 | 0,585 |

Le parcours de recherche complet, avec la correction de notation, retrouve une cible pour 25/25 questions sur ce réemploi de la série. Il retrouve toutes les prémisses de 1/5 arguments dans les cinq premières pages. Ajouter les pages physiques adjacentes aux trois premières complète deux autres arguments, soit 3/5 avec davantage de pages. Le classement public conserve son poids de 0,2 et ses cinq premiers résultats. Les deux variantes n’ont pas encore été départagées sur de nouvelles questions et à budget de pages égal. [Mesures et traductions](mesures-v3.json) · [Script](../src/compare_page_context.py)

## Extension V4 : carte mentale SVG, débat multi-tours, 54/54 chapitres et secours multi-fournisseurs

- **Couverture intégrale du *Traité* (54/54 chapitres reliés) :** ajout de 8 nouveaux dossiers curatés multi-chapitres (`semantique_verite`, `ontologie_choses`, `niveaux_systemes`, `cognition_enquete`, `evolution_savoir`, `sciences_vie_societe`, `ethique_normes`, `metaethique_survie`), portant l’Atelier à **21 dossiers, 94 appuis vérifiés contre `provenance-512.sqlite` et 55 modifications contrôlées** sur 13 séquences (`src/audit_workshop.py`). Plus aucun chapitre des 9 tomes/parties du *Traité* n’est marqué « à établir ». [Couverture du Traité](COUVERTURE-TRAITE.md)
- **Carte mentale graphique interactive & lexique des symboles :** [atlas_graph.py](../space/atlas_graph.py) rend une carte mentale SVG interactive embarquée dans Gradio (zéro CDN externe : zoom/pan, filtrage des 6 domaines, inspection au clic des nœuds et des arêtes avec citations sourcées) et un **lexique filtrable de 16 notations formelles** (`2026-11-26.20` : `⟨C, E, S, M⟩`, `M(c) = ⟨S(c), R(c)⟩`, `v(p)`, `ℳ = ⟨D, F, I⟩`, `⊑`, `x ∘ y`, `R(x)`, etc.).
- **Débat philosophique multi-tours dans l’Atelier :** `workshop.debate_turn` conserve à chaque tour la liste des prémisses suspendues ou remplacées, relance une recherche de passages pertinents dans la bibliothèque sur chaque objection, applique `question_scope` (refus des avis posthumes), vérifie chaque identifiant de citation et bascule proprement en mode passages sourcés hors quota API sans jamais muter le référentiel.
- **Secours LLM multi-fournisseurs & pré-remplissage SSRF des faits contemporains :** [generate.py](../src/generate.py) accepte les cascades `gemini/...|groq/...|mistral/...` (ignorant silencieusement tout fournisseur sans clé API configurée et basculant automatiquement sur `429`/`500`/`503`/`504`) et [contemporary.py](../src/contemporary.py) permet de pré-remplir une source datée (URL HTTPS publique validée contre les IP privées/locales et sans redirection, ou API REST Wikipédia FR/EN). Suite unitaire étendue à **108 tests** (`tests/test_v4_features.py`).
