"""Arbre déductif hiérarchique complet des 113 propositions vérifiées de Mario Bunge."""

from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path

from atlas_graph import DOMAIN_COLORS, DOMAIN_ORDER
from library import CATALOG, NODES, fold, node_source

esc = html.escape

# Taxonomie complète par domaine et sous-catégorie couvrant 100 % des 113 propositions.
TREE_BRANCHES: dict[str, list[tuple[str, list[str]]]] = {
    "Ontologie": [
        (
            "Substance, ordre des parties et unicité du monde",
            ["ordre-partiel", "supremum", "monde", "unicite-sup", "autre-preuve", "unique"],
        ),
        (
            "Matérialisme, choses, propriétés, changement et espace-temps",
            ["materialisme", "changement", "proprietes", "chose", "possible", "flux", "espace"],
        ),
        (
            "Systèmes, agrégats, émergence et niveaux de réalité",
            [
                "agregat-et-systeme",
                "postulat-emergence",
                "systemisme",
                "eau",
                "ni-holisme-ni-atomisme",
                "chimie",
                "biosystemisme",
                "cadre-emergentiste",
                "dynamique",
            ],
        ),
        (
            "Causalité, déterminisme et critique du fatalisme",
            [
                "determinisme-causal",
                "fatalisme",
                "emerson-fatum",
                "critique-emerson",
                "wilson-fatum",
                "distinction-fatum",
            ],
        ),
    ],
    "Sémantique": [
        (
            "Existence conceptuelle, référence et représentation",
            [
                "existence-conceptuelle",
                "existence-dictionnaire",
                "reference",
                "representation",
                "purport",
                "extension",
            ],
        ),
        (
            "Sens, signification, interprétation et synonymie",
            [
                "signification",
                "interpretation",
                "intension",
                "frege-sens",
                "mill-connotation",
                "couple-signification",
                "sens-reference-distincts",
                "synonymie",
            ],
        ),
        (
            "Vérité de raison, vérité partielle et disciplines voisines",
            ["raison", "verite", "voisins"],
        ),
    ],
    "Épistémologie": [
        (
            "Réalisme scientifique, cognition, perception et concepts",
            [
                "realisme",
                "connaissance",
                "perception",
                "perception-concepts",
                "concept",
                "communication",
                "probleme",
            ],
        ),
        (
            "Inférence, conjecture, hypothèse profonde et théorie",
            [
                "inference",
                "inference-saut",
                "conjecture",
                "hypothese-profonde",
                "coherence",
                "theorie-systeme",
            ],
        ),
        (
            "Explication par mécanisme, compréhension et mise à l’épreuve",
            [
                "niveaux-comprehension",
                "snell",
                "mecanisme",
                "superiorite-mecanisme",
                "controle",
                "verite-efficacite",
                "husserl-essences",
                "critique-evidence-intuitive",
                "testabilite-reelle",
            ],
        ),
        (
            "Évaluation, évolution et typologie des savoirs",
            ["evaluation", "changement-savoir", "types-savoirs", "etude-savoir"],
        ),
    ],
    "Philosophie de l’esprit": [
        (
            "Cerveau, plasticité neuronale et psychon",
            ["plasticite", "psychon", "acquisition", "cerveau"],
        ),
        (
            "Émergence mentale, identité psychoneurale et contrôle du comportement",
            [
                "emergence-esprit",
                "identite",
                "analogie",
                "postulat-comportement",
                "theoreme-comportement",
            ],
        ),
    ],
    "Philosophie des sciences": [
        (
            "Sciences formelles, modèle factuel et physique",
            [
                "math-neutre",
                "modele",
                "interpretation-modele",
                "physique",
                "choses-physiques-autonomes",
            ],
        ),
        (
            "Psychologie, sciences sociales et technologie",
            [
                "psychologie",
                "renvoi-psychologie-esprit",
                "societe",
                "societe-nouveaute",
                "technique",
                "regle-technologique",
            ],
        ),
    ],
    "Éthique": [
        (
            "Besoins, valeurs, bien-être et théorème du bonheur complet",
            [
                "deficit",
                "besoin",
                "valeur",
                "bien-etre",
                "bonheur",
                "bonheur-et-bien-etre",
                "incompatibilite",
                "theoreme-bonheur",
            ],
        ),
        (
            "Droits moraux, devoirs exigibles et norme de réciprocité",
            ["droit", "devoir", "restriction", "axiologie", "changement-moral", "cas-moraux"],
        ),
        (
            "Doctrines éthiques, métaéthique, action et philosophie sociale",
            [
                "types-ethique",
                "ethique-action",
                "metaethique",
                "etre-devoir",
                "agir",
                "action-valeurs",
                "philo-sociale",
                "survie",
            ],
        ),
    ],
}

ROLE_CATEGORIES = (
    ("Toutes les natures", "ALL"),
    ("Définitions", "definition"),
    ("Postulats & Axiomes", "postulat"),
    ("Thèses & Principes", "these"),
    ("Théorèmes, Corollaires & Normes", "theoreme"),
    ("Exemples & Critiques", "exemple"),
)


def role_category(kind: str) -> str:
    k = fold(kind)
    if any(w in k for w in ("definition", "distinction")):
        return "definition"
    if any(w in k for w in ("postulat", "axiome", "programme", "cadre")):
        return "postulat"
    if any(w in k for w in ("theoreme", "corollaire", "norme", "preuve", "consequence", "argument")):
        return "theoreme"
    if any(w in k for w in ("exemple", "critique", "objection", "position", "reponse", "cite")):
        return "exemple"
    return "these"


def role_rank(kind: str) -> int:
    return {
        "definition": 0,
        "postulat": 1,
        "these": 2,
        "theoreme": 3,
        "exemple": 4,
    }[role_category(kind)]


def all_tree_node_ids() -> set[str]:
    return {
        nid
        for branches in TREE_BRANCHES.values()
        for _, ids in branches
        for nid in ids
    }


def _build_branch_graph(branch_ids: list[str]) -> tuple[list[str], dict[str, list[tuple[str, str]]], dict[str, list[tuple[str, str]]]]:
    """Construit la hiérarchie parent -> enfants à l’intérieur d’une sous-catégorie."""
    id_set = set(branch_ids)
    children: dict[str, list[tuple[str, str]]] = defaultdict(list)
    parents: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for rel in CATALOG["relations"]:
        o, t = rel["origin"], rel["target"]
        if o in id_set and t in id_set and o != t:
            # Orienter autant que possible des fondations (Définitions/Postulats) vers les conséquences.
            ro, rt = role_rank(NODES[o]["kind"]), role_rank(NODES[t]["kind"])
            if ro <= rt:
                children[o].append((t, rel["verb"]))
                parents[t].append((o, rel["verb"]))
            else:
                children[t].append((o, rel["verb"]))
                parents[o].append((t, rel["verb"]))

    # Racines : nœuds sans parent dans la branche, triés de Définition -> Postulat -> Thèse -> Théorème.
    roots = [nid for nid in branch_ids if not parents.get(nid)]
    roots.sort(key=lambda nid: (role_rank(NODES[nid]["kind"]), branch_ids.index(nid)))
    # Si un cycle local empêchait une racine, prendre le nœud de rang le plus fondamental.
    covered: set[str] = set()

    def _walk(u: str) -> None:
        if u in covered:
            return
        covered.add(u)
        for v, _ in children.get(u, ()):
            _walk(v)

    for r in roots:
        _walk(r)
    for nid in sorted(branch_ids, key=lambda x: (role_rank(NODES[x]["kind"]), branch_ids.index(x))):
        if nid not in covered:
            roots.append(nid)
            _walk(nid)
    return roots, children, parents


def _render_node_subtree(
    nid: str,
    children: dict[str, list[tuple[str, str]]],
    parents: dict[str, list[tuple[str, str]]],
    visited: set[str],
    *,
    via_verb: str = "",
    depth: int = 0,
    local: Path | None = None,
    annotate_fn=None,
) -> str:
    node = NODES[nid]
    cat = role_category(node["kind"])
    src = node_source(nid)
    notation = node.get("notation")
    body_text = annotate_fn(esc(node["text"]), exclude_key=nid) if annotate_fn else esc(node["text"])

    via_html = f'<span class="dtree-via">↳ {esc(via_verb)}</span>' if via_verb else ""
    formula_html = (
        f'<div class="dtree-formula"><code>{esc(notation["formula"])}</code> — {esc(notation["gloss"])}</div>'
        if notation
        else ""
    )

    # Autres relations hors branche (pour ne rien perdre des liens transverses entre tomes)
    cross_links = []
    branch_neighbors = {c for c, _ in children.get(nid, ())} | {p for p, _ in parents.get(nid, ())}
    for rel in CATALOG["relations"]:
        if nid in (rel["origin"], rel["target"]):
            other = rel["target"] if rel["origin"] == nid else rel["origin"]
            if other not in branch_neighbors and other in NODES:
                cross_links.append(
                    f'<a href="#wiki-{esc(other)}" class="wiki-link" data-wiki-concept="{esc(other)}">'
                    f'{esc(NODES[other]["title"])}</a> <small>({esc(NODES[other]["kind"])})</small>'
                )
    cross_html = (
        f'<p class="dtree-cross"><strong>Liens transverses :</strong> {" · ".join(cross_links[:5])}</p>'
        if cross_links
        else ""
    )

    child_items = []
    next_visited = visited | {nid}
    for cid, verb in sorted(
        children.get(nid, ()),
        key=lambda item: (role_rank(NODES[item[0]]["kind"]), fold(NODES[item[0]]["title"])),
    ):
        if cid in next_visited or depth >= 4:
            continue
        child_items.append(
            _render_node_subtree(
                cid,
                children,
                parents,
                next_visited,
                via_verb=verb,
                depth=depth + 1,
                local=local,
                annotate_fn=annotate_fn,
            )
        )
    sub_count = len(child_items)
    sub_badge = (
        f'<span class="dtree-children-count">{sub_count} suite{"s" if sub_count > 1 else ""}</span>'
        if sub_count
        else ""
    )
    children_html = (
        f'<div class="dtree-children">{"".join(child_items)}</div>' if child_items else ""
    )

    open_attr = " open" if depth == 0 and sub_count > 0 else ""
    return (
        f'<details class="dtree-node dtree-depth-{min(depth, 3)}"{open_attr}>'
        f'<summary class="dtree-summary">'
        f'<span class="dtree-role dtree-role-{cat}">{esc(node["kind"])}</span>'
        f'<span class="dtree-title">{esc(node["title"])}</span>'
        f'{sub_badge}'
        f'<span class="dtree-ref">{esc(src["title"])} · {esc(src["pages"])}</span>'
        f"</summary>"
        f'<div class="dtree-body">'
        f"{via_html}"
        f'<p class="dtree-text">{body_text}</p>'
        f"{formula_html}"
        f'<blockquote class="dtree-quote" lang="en">« {esc(src["excerpt"])} »</blockquote>'
        f'<div class="dtree-actions">'
        f'<button type="button" class="open-reader-btn open-reader-sm" '
        f'data-read-book="{esc(src["book"])}" data-read-page="{esc(str(src["page"]))}" '
        f'data-read-excerpt="{esc(src["excerpt"][:100])}">Lire dans le livre →</button>'
        f'<a href="#wiki-{esc(nid)}" class="wiki-link dtree-fiche-link" data-wiki-concept="{esc(nid)}">Voir la fiche complète</a>'
        f"</div>"
        f"{cross_html}"
        f"{children_html}"
        f"</div></details>"
    )


def render_deductive_tree(
    domain_filter: str = "Tous les domaines",
    role_filter: str = "ALL",
    query: str = "",
    local: Path | None = None,
) -> str:
    """Rend l’arbre déductif complet des 113 propositions (Définitions → Postulats → Thèses → Théorèmes/Corollaires)."""
    from wiki_concepts import annotate_concepts

    needle = fold((query or "").strip())
    domain_sections = []
    total_shown = 0

    for dom in DOMAIN_ORDER:
        if domain_filter != "Tous les domaines" and dom != domain_filter:
            continue
        color = DOMAIN_COLORS.get(dom, "#2563eb")
        branch_blocks = []
        dom_count = 0

        for branch_title, raw_ids in TREE_BRANCHES.get(dom, ()):
            branch_ids = [nid for nid in raw_ids if nid in NODES]
            if role_filter != "ALL" or needle:
                filtered_ids = [
                    nid
                    for nid in branch_ids
                    if (role_filter == "ALL" or role_category(NODES[nid]["kind"]) == role_filter)
                    and (
                        not needle
                        or needle
                        in fold(
                            f"{NODES[nid]['title']} {NODES[nid]['kind']} {NODES[nid]['text']} {NODES[nid]['source']['quote']}"
                        )
                    )
                ]
            else:
                filtered_ids = branch_ids

            if not filtered_ids:
                continue

            dom_count += len(filtered_ids)
            total_shown += len(filtered_ids)
            roots, children, parents = _build_branch_graph(filtered_ids)
            rendered_nodes = []
            seen_global: set[str] = set()
            for r in roots:
                if r in seen_global:
                    continue
                rendered_nodes.append(
                    _render_node_subtree(
                        r,
                        children,
                        parents,
                        set(),
                        depth=0,
                        local=local,
                        annotate_fn=annotate_concepts,
                    )
                )
                # Marquer comme rendus tous les nœuds atteignables depuis cette racine.
                stack = [r]
                while stack:
                    cur = stack.pop()
                    if cur in seen_global:
                        continue
                    seen_global.add(cur)
                    stack.extend(c for c, _ in children.get(cur, ()))

            branch_blocks.append(
                f'<section class="dtree-branch">'
                f'<h4 class="dtree-branch-title">{esc(branch_title)} <small>({len(filtered_ids)})</small></h4>'
                f'<div class="dtree-list">{"".join(rendered_nodes)}</div></section>'
            )

        if branch_blocks:
            domain_sections.append(
                f'<section class="dtree-domain">'
                f'<header class="dtree-domain-head" style="border-left-color:{color};">'
                f'<span class="wiki-dot" style="background:{color};"></span>'
                f'<h3>{esc(dom)}</h3><small>{dom_count} proposition(s)</small></header>'
                f'{"".join(branch_blocks)}</section>'
            )

    if not domain_sections:
        return "<p>Aucune proposition ne correspond à ces filtres dans l’arbre déductif.</p>"

    legend = (
        '<div class="dtree-legend">'
        '<span class="dtree-role dtree-role-definition">Définition</span>'
        '<span class="dtree-role dtree-role-postulat">Postulat / Axiome</span>'
        '<span class="dtree-role dtree-role-these">Thèse</span>'
        '<span class="dtree-role dtree-role-theoreme">Théorème / Corollaire / Norme</span>'
        '<span class="dtree-role dtree-role-exemple">Exemple / Critique</span>'
        f'<span class="dtree-total">{total_shown} proposition(s) affichée(s)</span>'
        "</div>"
    )
    return f'<div class="dtree-root">{legend}{"".join(domain_sections)}</div>'
