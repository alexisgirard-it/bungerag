---
title: BungeRAG
emoji: 🔎
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 6.19.0
app_file: app.py
pinned: false
license: mit
short_description: Interroger l'œuvre de Mario Bunge et vérifier les sources
---

# BungeRAG — édition numérique expérimentale

Interrogez en français un corpus privé de 25 ouvrages de Mario Bunge. Les
réponses sont construites à partir de passages retrouvés, accompagnées de
renvois vers l'ouvrage et la page du fichier PDF (ou la section EPUB), ou
remplacées par une abstention explicite.

Les indices `[n]` sont vérifiés structurellement avant exposition : cela
garantit qu'ils pointent vers une source affichée, pas que toute interprétation
philosophique soit vraie ni exhaustive.

Le benchmark legacy pré-clôture, chemin direct `40 candidats → 6 extraits`,
obtient `0,935` de faithfulness, `0,893` de context precision et `0,848` de
context recall sur le jeu documenté. Il utilisait une requête anglaise commune
aux jambes dense et BM25, sans les validateurs actuels. La V1 sépare dense FR
et BM25 EN : son chemin direct emploie `12 → 5`, tandis que le panoramique prend
8 candidats par sous-question et conserve au plus 12 sources. Aucun score
legacy n'est présenté comme la confiance de cette démo ou d'une réponse.

Le corpus sous droits reste dans un dataset privé épinglé à une révision ;
les extraits publics sont bornés à 20 mots et toute réponse recopiant plus de
20 mots consécutifs d'un contexte est retirée avant exposition.

Code, protocole et limites : https://github.com/alexisgirard-it/bungerag
