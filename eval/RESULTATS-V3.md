# BungeRAG · essais de la V3

Mesures du 25 et du 26 novembre 2026. Le point de départ et les conventions de pagination sont décrits dans le [bilan V2](RESULTATS-V2.md). Les résultats par question, les révisions et les délais bruts sont dans [mesures-v3.json](mesures-v3.json).

## Rechercher et reclasser

Sur les 30 questions historiques, la V2 retrouvait 10 références annotées dans les cinq premiers résultats. Parmi les 20 restantes, 14 avaient disparu avant le reclassement et 6 à cette étape. Le profil de rédaction V3 avec Horizon Labs et 24 candidats retrouve **13 références sur 30** sur les mêmes questions et traductions. La comparaison à 12, 24 et 40 candidats donne respectivement 12, 13 et 12 résultats retrouvés. [Diagnostic V2](diagnostic-recherche-v2.json)

| Embedding | Top 5 sur 227 passages | Rang réciproque moyen | Top 5 dense sur index complet |
|---|---:|---:|---:|
| Qwen3-Embedding-0.6B | 21/30 | 0,368 | 9/30 |
| IBM Granite 311M Multilingual R2 | 21/30 | 0,380 | 9/30 |
| EmbeddingGemma 2, texte | 17/30 | 0,303 | |
| Microsoft Harrier 0.6B | 20/30 | 0,311 | |

Qwen est conservé. Granite obtient un rang moyen un peu meilleur sur le petit groupe. Les deux retrouvent autant de références à cinq passages sur l’index complet. Le comparateur de classement mesure 13/30 en encodant la question anglaise et 11/30 dans les deux variantes hybrides avant reclassement. Le français reste utilisable pour la recherche vectorielle et le reclassement reçoit la question originale. [Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) · [Granite](https://huggingface.co/ibm-granite/granite-embedding-311m-multilingual-r2) · [Horizon Labs](https://huggingface.co/Horizon-Labs/multilingual-reranker-small)

## Recette réservée

La série a été figée avant le choix des options. Elle contient 25 questions avec pages cibles et cinq demandes de clarification ou sans source disponible. Le profil de rédaction V3 retrouve au moins une page annotée pour **23/25** et toutes les prémisses pour **3/5** questions argumentatives. La recherche paginée retrouve au moins une page pour **24/25** et donne la réponse d’orientation attendue dans les cinq cas restants. Le seul échec de localisation porte sur la formulation d’une question de notation. Les deux chemins ont des objectifs de classement distincts. La comparaison complète à la V2 et le contrôle extrait par extrait sont en cours. [Questions réservées](lecture-reservee.jsonl)

## Rédaction et disponibilité

Les six cas à passages identiques ont donné cinq réponses documentées et une abstention avec Gemini 3.1 Flash-Lite lors des essais V2. Dans la nouvelle série, Gemini 4 Hydrogen et 3.8 Flash ont renvoyé cinq erreurs 503 et une erreur 429 chacun. Gemini 3.5 Flash-Lite a renvoyé quatre erreurs 503, une abstention et une réponse retirée au contrôle des citations. Une deuxième recette de raisonnement a reçu des erreurs 400. Une requête minimale a confirmé le refus de région depuis l’environnement de test. Les deux modèles Cerebras accessibles en métadonnées ont répondu 402 à la requête de génération. Ces résultats justifient le maintien de Flash-Lite comme profil de rédaction déjà vérifié sur le Space et la disponibilité indépendante de la recherche et des dossiers édités. Ils ne classent pas la qualité argumentative des candidats. [Bilan V2](RESULTATS-V2.md) · [Palier Gemini](https://aistudio.google.com/docs/pricing) · [Tarifs Cerebras](https://www.cerebras.ai/pricing)

## Référentiel et interface

Le répertoire contient 25 ouvrages et 54 chapitres du *Traité* repérés. Le référentiel éditorial actuel compte 37 fiches et 25 relations documentées. Les 125 extraits affichés sur la recette réservée ont été retrouvés dans leur page de concordance. Les repères formels et renvois transcrits automatiquement sont signalés comme tels. La lecture d’un extrait, le passage vers l’Atlas et le retour au texte ont été testés au clavier avec la définition de psychon, p. 70 du livre et PDF p. 78. Les deux dossiers d’éthique permettent d’identifier les enseignements directs des sources et les étapes de reconstruction. [Référentiel](../src/referentiel.json)

Pour les cinq questions à plusieurs références, la lecture des dossiers et des relations a fait passer la couverture complète des références de 1/5 à 3/5 sur le premier audit. Deux questions restent partielles. Le graphe fournit des appuis supplémentaires selon la question et ne mesure pas à lui seul la validité d’un argument.
