# BungeRAG · évaluation et publication de la V2

Les comparaisons du 24 novembre 2026 ont été réalisées sur un Mac M3 de 16 Go. Le 25 novembre, la V2 a été publiée sur le [Space Hugging Face de BungeRAG](https://huggingface.co/spaces/alexisgirard/bungerag).

## Vérification du site public

À la question « Qu’est-ce qu’un psychon selon Bunge ? », le site a cité la définition de Bunge et distingué le postulat qui la suit. Les deux extraits anglais affichés et leurs renvois ont été contrôlés sur la version publique. Les deux extraits se trouvent à la page imprimée 70 de *Scientific Materialism* (1981), page 78 du PDF de l’édition indexée. La première réponse a pris 125 secondes sur le CPU public, chargement initial des modèles compris. [Version vérifiée](https://huggingface.co/spaces/alexisgirard/bungerag/commit/d384565ebae0fe7df6b7ddfacf084eec2bd5f6db)

À la question « Quels seront les six numéros gagnants du prochain tirage du Loto français ? », le site a répondu « Absent du corpus. » sans afficher de source. Cet essai a pris 134 secondes.

## Retrouver le bon passage

La définition du psychon dans *Scientific Materialism* est absente du top 5 de la V1. Elle arrive au rang 5 avec la recherche de définitions de la V2. La réponse française cite deux extraits localisés à la page 70 du livre, page 78 du PDF. Le test a pris 53,6 secondes hors cache et a ouvert avec succès les deux liens vers l’exemplaire local. La référence à l’entrée « Life » du dictionnaire couvre désormais les pages imprimées 163–164, PDF 165–166. Le dernier mot de la phrase se trouve sur la seconde page.

La concordance couvre 24 PDF et un EPUB. Sur 8 255 pages physiques, 7 887 ont un folio identifié par correspondance avec les marges, les étiquettes et les séquences de pagination. Pour les 368 restantes, la carte utilise la position PDF. Les pages numérisées utilisent une transcription Apple Vision. Deux cas de lecture défectueuse connus ont été vérifiés sur l’image et dans la V2, *Political Philosophy* (PDF 64) et *Philosophical Dictionary* (PDF 163). Le programme vérifie la présence du court extrait et conserve les coordonnées des lignes. L’exactitude du contenu philosophique reste tributaire de la lecture du modèle et de la qualité de l’extraction.

## Recherche et embeddings

| Essai | Résultat |
|---|---|
| Qwen3-Embedding-0.6B, recherche dense | 21/30 dans le top 5, rang réciproque moyen 0,368 |
| Harrier-OSS-v1-0.6B, recherche dense | 20/30 dans le top 5, rang réciproque moyen 0,311 |
| Index complet, recherche hybride et reclassement Qwen, V1 | 10/30 dans le top 5, rang réciproque moyen tronqué à 5 de 0,173 |
| Même index complet, V2 avec recherche de définitions | 10/30 dans le top 5, rang réciproque moyen tronqué à 5 de 0,173 |

La comparaison dense porte sur les mêmes 227 candidats, à partir des questions françaises, des passages cibles et de passages récupérés par l’ancienne évaluation. Chaque modèle utilise sa propre instruction de recherche. La composition de cet échantillon peut influer sur le classement. Le test de recherche hybride porte sur l’ensemble des 10 412 passages, avec des traductions anglaises figées, 12 candidats initiaux et 5 résultats finaux. Pour les définitions, la V2 peut ajouter jusqu’à quatre candidats lexicaux avant reclassement. Dans les deux essais, une question réussit dès qu’un passage attendu est présent dans les cinq premiers résultats. Un autre passage peut répondre correctement à la question tout en étant absent des références annotées.

Les 30 questions proviennent du jeu historique. Le psychon, l’hypothèse d’association de psychons et le portefeuille Bitcoin constituent trois contrôles supplémentaires. Le premier a servi à concevoir le correctif. Le résultat global sur les 30 questions reste identique. Qwen est conservé sur ce matériel. Ces essais ne classent pas tous les modèles disponibles.

## Rédaction et abstention

| Rédacteur | Cas de contenu | Question hors corpus | Conditions |
|---|---|---|---|
| Gemini 3.1 Flash-Lite | 5 réponses avec extraits localisés sur 5 | 1 abstention explicite sur 1 | Vérificateur Gemini 3.1 Flash-Lite, 20,6 s de médiane sur les six cas |
| Gemini 3.8 Flash | Aucun résultat exploitable | Aucun résultat exploitable | Même vérificateur et mêmes entrées. Quatre erreurs HTTP 503 et deux 504 |
| Qwen3.5 9B Q4 via Ollama | 2 réponses avec extraits localisés sur 2 | Réponse bloquée par le contrôle des citations | Rédaction et vérification locales. Respectivement 610, 248 et 173 s pour les trois cas, avec d’autres calculs en cours sur le Mac |

Les rédacteurs Gemini reçoivent exactement les mêmes passages pour chaque question. La récupération est neutralisée dans cet essai. Les questions couvrent définition, statut d’une hypothèse, sens et référence, philosophie politique, biosystèmes et hors-corpus. Gemini 3.1 distingue la conjecture sur l’association des psychons de la définition du psychon. La localisation de 17 extraits sur cinq réponses constitue un contrôle de traçabilité. Les six observations n’établissent pas un taux général de fidélité philosophique. Les erreurs du service 3.8 empêchent de comparer sa qualité rédactionnelle sur cet échantillon.

## Reproduire les essais

Depuis le dépôt, avec l’index et la concordance privés disponibles :

```sh
.venv/bin/python src/compare_embeddings.py
.venv/bin/python src/compare_retrieval.py
.venv/bin/python src/compare_generation.py --models gemini/gemini-3.8-flash gemini/gemini-3.1-flash-lite --judge gemini/gemini-3.1-flash-lite
.venv/bin/python src/compare_generation.py --models ollama --judge ollama --cases definition hypothese hors-corpus
```

Les cibles et le groupe de candidats sont figés dans `eval/passages-eval.json`. Les révisions des modèles, les résultats par question et les erreurs des fournisseurs sont archivés dans `eval/mesures-v2.json`. Les caches détaillés restent locaux. Les fiches des éditeurs décrivent les autres tâches de référence utilisées pour ces modèles. [Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) · [Microsoft Harrier](https://huggingface.co/microsoft/harrier-oss-v1-0.6b)
