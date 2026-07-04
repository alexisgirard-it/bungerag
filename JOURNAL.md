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
