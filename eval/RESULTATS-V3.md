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

Le répertoire contient 25 ouvrages et 54 chapitres du *Traité* repérés. Le référentiel éditorial actuel compte 37 fiches et 25 relations documentées. Les 125 extraits affichés sur la recette réservée ont été retrouvés dans leur page de concordance. Les repères formels et renvois transcrits automatiquement sont signalés comme tels. La lecture d’un extrait, le passage vers l’Atlas et le retour au texte ont été testés au clavier avec la définition de psychon, p. 70 du livre et PDF p. 78. Les deux dossiers d’éthique permettent d’identifier les enseignements directs des sources et les étapes de reconstruction. [Référentiel](../src/referentiel.json)

Pour les cinq questions à plusieurs références, la lecture des dossiers et des relations a fait passer la couverture complète des références de 1/5 à 3/5 sur le premier audit. Deux questions restent partielles. Les 54 ouvertures de chapitre ont été contrôlées contre la concordance.

Sur ordinateur, l’argument sur le bonheur s’est ouvert depuis une question de recherche. La suspension puis le rétablissement du postulat ont modifié l’état de sa justification. Sur mobile, le dossier sur l’IA s’ouvre depuis une navigation dédiée. Ces parcours ont également été rejoués à partir du bundle de 23 fichiers destiné au Space. Le résultat du psychon y affiche les deux numéros de page.


## Recette sur le Space

Le 26 novembre, le Space CPU a servi le profil V3. La recette sur le navigateur a confirmé la recherche paginée, la navigation jusqu’à une page de chapitre, l’Atlas au clavier et retour à la recherche, puis la suspension d’un postulat et l’ouverture du dossier IA sur mobile. La première révision publique a rédigé une réponse sur le psychon en 91 secondes. Ses quatre extraits ont été contrôlés dans les PDF, aux pages physiques 78, 76 et 54 de leurs éditions respectives. La révision suivante utilise le rendu côté navigateur. [Space](https://huggingface.co/spaces/alexisgirard/bungerag) · [Révision testée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/7cab50878e3ddb62bbe07398537589f0580b03bf)

Le référentiel public étendu contient 77 fiches et 65 liens. Sur les cinq demandes à plusieurs références, il permet de retrouver toutes les pages annotées pour quatre demandes après ouverture de l’argument. Ces cas sont les mêmes que ceux du premier audit. Le résultat documente une vérification de la couverture sur ces questions connues. [Inventaire des chapitres](COUVERTURE-TRAITE.md)

La révision suivante retrouve aussi la notation ℳ = ⟨D, F, I⟩ en saisie directe. Le test navigateur a affiché la page 82 du livre, PDF p. 93, puis le lexique des symboles dans l’Atlas. [Révision testée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/8df36386f741039ec1f999034d64a7d77d22ece3)
