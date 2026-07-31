# Validation humaine des références corrigées

Date de validation : **2026-07-31**

Décision : **approuvées sans modification**

Périmètre : les sept références corrigées après la revue contradictoire du corpus.

## Méthode et portée

Les corrections proposées dans [`REVUE-REFERENCES.md`](REVUE-REFERENCES.md) ont été
relues avec leurs preuves livre + page. La décision humaine porte sur la conformité des
sept **réponses de référence** au corpus ; elle ne constitue pas une validation humaine
de chaque réponse produite par le RAG ni des notes attribuées par le juge RAGAS.

Les sept textes corrigés ont été approuvés tels quels. Comme aucun texte de référence n'a
été modifié lors de cette validation finale, il n'a pas été nécessaire de recalculer le
`context_recall` : les scores finaux avaient déjà été recalculés sur ces corrections.

## Décisions

| Question | Verdict de la revue | Décision humaine | Justification principale |
|---|---|---|---|
| q05 | Douteuse | Approuvée | Retrait du terme forgé « psychonisme » et distinction entre doctrine et « psychon ». |
| q12 | Douteuse | Approuvée | Restitution de la conception synthétique de la vérité et de la vérité partielle. |
| q13 | Fausse | Approuvée | Distinction corrigée entre sens, référence et signification. |
| q16 | Douteuse | Approuvée | Dimensions de la démocratie intégrale et socialisme coopératif corrigés. |
| q17 | Douteuse | Approuvée | Retrait de la reproduction comme propriété nécessaire du biosystème. |
| q20 | Fausse | Approuvée | Chronologie corrigée : la philosophie a conduit Bunge vers la physique. |
| q30 | Douteuse | Approuvée | Définition du scientisme et distinctions avec exclusivisme, dogmatisme et réductionnisme. |

Chaque entrée correspond à la section homonyme de
[`REVUE-REFERENCES.md`](REVUE-REFERENCES.md), où figurent le texte initial, la correction
appliquée et les citations justificatives. Les entrées q05, q12, q13, q16, q17, q20 et
q30 de [`questions-eval.jsonl`](questions-eval.jsonl) portent désormais le statut
`validee-humain` et renvoient vers le présent registre.

## État du jeu d'évaluation

- 23 références confirmées directement contre le corpus lors de la revue initiale ;
- 7 références corrigées, puis approuvées humainement le 2026-07-31 ;
- 30 références sur 30 ne portent plus de statut provisoire.
