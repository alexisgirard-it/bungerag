"""Carte mentale SVG interactive de l’Atlas et lexique consultable des symboles."""

from __future__ import annotations

import html
import json
import math

from library import CATALOG, NODES, fold

esc = html.escape

DOMAIN_ORDER = (
    "Ontologie",
    "Sémantique",
    "Épistémologie",
    "Philosophie de l’esprit",
    "Philosophie des sciences",
    "Éthique",
)
DOMAIN_COLORS = {
    "Ontologie": "#2b5b84",
    "Sémantique": "#5d4a8a",
    "Épistémologie": "#2e6f5e",
    "Philosophie de l’esprit": "#9b4d3a",
    "Philosophie des sciences": "#9e6718",
    "Éthique": "#8a3b5c",
}

MINDMAP_CSS = """
.atlas-mindmap { border: 1px solid #d6d1c7; border-radius: 10px; background: #faf8f4; padding: 12px; margin: 10px 0 14px; }
.atlas-mindmap-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.atlas-mindmap-controls { display: flex; gap: 6px; align-items: center; }
.atlas-mindmap-controls button, .atlas-domain-pill {
  border: 1px solid #c7c0b4; background: #fff; color: #26231f; border-radius: 6px;
  padding: 4px 9px; font-size: 12px; cursor: pointer;
}
.atlas-domain-pill.is-active { background: #26231f; color: #fff; border-color: #26231f; }
.atlas-mindmap-legend { display: flex; flex-wrap: wrap; gap: 6px; }
.atlas-mindmap-canvas { width: 100%; height: 460px; border: 1px solid #e5e0d7; border-radius: 8px; background: #fffdfa; cursor: grab; touch-action: none; display: block; }
.atlas-mindmap-canvas:active { cursor: grabbing; }
.atlas-mindmap-node { cursor: pointer; transition: opacity 0.15s ease; }
.atlas-mindmap-edge { cursor: pointer; transition: opacity 0.15s ease, stroke-width 0.15s ease; }
.atlas-mindmap-inspector { margin-top: 10px; padding: 10px 12px; border-left: 3px solid #2b5b84; background: #fff; border-radius: 0 6px 6px 0; font-size: 13.5px; line-height: 1.45; }
.atlas-mindmap-inspector blockquote { margin: 6px 0 0; padding-left: 10px; border-left: 2px solid #d6d1c7; color: #3a352f; font-style: italic; }
.symbol-lexicon { display: grid; gap: 10px; margin-top: 8px; }
.symbol-entry { border: 1px solid #ded8ce; border-radius: 8px; padding: 10px 12px; background: #fffdfa; }
.symbol-entry .formula { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 15px; font-weight: 600; margin: 4px 0; color: #1d1a16; }
"""

MINDMAP_JS = """
const root = element.querySelector('.atlas-mindmap');
if (!root || root.dataset.bound === '1') return;
root.dataset.bound = '1';
const svg = root.querySelector('svg.atlas-mindmap-canvas');
const inspector = root.querySelector('.atlas-mindmap-inspector');
const payloadEl = root.querySelector('.atlas-mindmap-data');
if (!svg || !inspector || !payloadEl) return;

let data = { nodes: {}, edges: [] };
try { data = JSON.parse(payloadEl.textContent || '{}'); } catch (_) { return; }

let vb = { x: 0, y: 0, w: 960, h: 620 };
const applyViewBox = () => svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);

const zoom = (factor, cx = vb.x + vb.w / 2, cy = vb.y + vb.h / 2) => {
  const nw = Math.max(220, Math.min(1800, vb.w * factor));
  const nh = Math.max(142, Math.min(1162, vb.h * factor));
  vb.x = cx - ((cx - vb.x) / vb.w) * nw;
  vb.y = cy - ((cy - vb.y) / vb.h) * nh;
  vb.w = nw;
  vb.h = nh;
  applyViewBox();
};

root.querySelector('[data-action="zoom-in"]')?.addEventListener('click', () => zoom(0.8));
root.querySelector('[data-action="zoom-out"]')?.addEventListener('click', () => zoom(1.25));
root.querySelector('[data-action="zoom-reset"]')?.addEventListener('click', () => {
  vb = { x: 0, y: 0, w: 960, h: 620 };
  applyViewBox();
});

let dragging = false, startX = 0, startY = 0;
svg.addEventListener('pointerdown', (e) => {
  if (e.target.closest('.atlas-mindmap-node, .atlas-mindmap-edge')) return;
  dragging = true; startX = e.clientX; startY = e.clientY;
  svg.setPointerCapture(e.pointerId);
});
svg.addEventListener('pointermove', (e) => {
  if (!dragging) return;
  const rect = svg.getBoundingClientRect();
  const dx = (e.clientX - startX) * (vb.w / rect.width);
  const dy = (e.clientY - startY) * (vb.h / rect.height);
  vb.x -= dx; vb.y -= dy; startX = e.clientX; startY = e.clientY;
  applyViewBox();
});
svg.addEventListener('pointerup', () => { dragging = false; });
svg.addEventListener('wheel', (e) => {
  e.preventDefault();
  zoom(e.deltaY > 0 ? 1.12 : 0.89);
}, { passive: false });

const escHtml = (s) => String(s || '').replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[c]));

const highlightNode = (key) => {
  const node = data.nodes[key];
  if (!node) return;
  const neighbors = new Set([key]);
  const incident = [];
  for (const edge of data.edges) {
    if (edge.origin === key || edge.target === key) {
      neighbors.add(edge.origin); neighbors.add(edge.target);
      incident.push(edge);
    }
  }
  svg.querySelectorAll('.atlas-mindmap-node').forEach((el) => {
    const k = el.dataset.key;
    el.style.opacity = neighbors.has(k) ? '1' : '0.25';
    const circle = el.querySelector('circle');
    if (circle) circle.setAttribute('stroke-width', k === key ? '3.5' : '1.4');
  });
  svg.querySelectorAll('.atlas-mindmap-edge').forEach((el) => {
    const active = el.dataset.origin === key || el.dataset.target === key;
    el.style.opacity = active ? '0.95' : '0.12';
    el.setAttribute('stroke-width', active ? '2.2' : '0.9');
  });
  const rels = incident.slice(0, 6).map((e) => {
    const other = e.origin === key ? e.target : e.origin;
    const oTitle = data.nodes[other]?.title || other;
    return `<li>${escHtml(data.nodes[e.origin]?.title || e.origin)} → <em>${escHtml(e.verb)}</em> → ${escHtml(data.nodes[e.target]?.title || e.target)} (${escHtml(e.kind)})</li>`;
  }).join('');
  const notation = node.formula ? `<p><strong>Notation :</strong> <code>${escHtml(node.formula)}</code></p>` : '';
  const voice = node.voice ? ` · Auteur cité : ${escHtml(node.voice)}` : '';
  inspector.style.borderLeftColor = node.color || '#2b5b84';
  inspector.innerHTML = `<strong>${escHtml(node.title)}</strong> <small>(${escHtml(node.domain)} · ${escHtml(node.kind)}${voice})</small>`
    + `<p style="margin:6px 0 4px;">${escHtml(node.text)}</p>${notation}`
    + `<small>${escHtml(node.book)} · p. ${escHtml(node.folio || node.page)} (PDF p. ${escHtml(node.page)})</small>`
    + `<blockquote lang="en">« ${escHtml(node.quote)} »</blockquote>`
    + (rels ? `<ul style="margin:6px 0 0 18px;">${rels}</ul>` : '');
};

const highlightEdge = (id) => {
  const edge = data.edges.find((e) => e.id === id);
  if (!edge) return;
  const o = data.nodes[edge.origin], t = data.nodes[edge.target], w = data.nodes[edge.witness];
  inspector.style.borderLeftColor = o?.color || '#2b5b84';
  inspector.innerHTML = `<strong>${escHtml(o?.title || edge.origin)} → ${escHtml(edge.verb)} → ${escHtml(t?.title || edge.target)}</strong>`
    + `<br><small>${escHtml(edge.kind)} · Témoin : ${escHtml(w?.title || edge.witness)} (PDF p. ${escHtml(w?.page || '')})</small>`
    + (edge.comparison ? `<p style="margin:6px 0 0;"><strong>Lecture éditoriale :</strong> ${escHtml(edge.comparison)}</p>` : '')
    + (w?.quote ? `<blockquote lang="en">« ${escHtml(w.quote)} »</blockquote>` : '');
};

svg.querySelectorAll('.atlas-mindmap-node').forEach((el) => {
  el.addEventListener('click', () => highlightNode(el.dataset.key));
});
svg.querySelectorAll('.atlas-mindmap-edge').forEach((el) => {
  el.addEventListener('click', () => highlightEdge(el.dataset.id));
});
root.querySelectorAll('.atlas-domain-pill').forEach((btn) => {
  btn.addEventListener('click', () => {
    const dom = btn.dataset.domain;
    root.querySelectorAll('.atlas-domain-pill').forEach((b) => b.classList.toggle('is-active', b === btn));
    svg.querySelectorAll('.atlas-mindmap-node').forEach((el) => {
      const match = dom === 'ALL' || el.dataset.domain === dom;
      el.style.opacity = match ? '1' : '0.14';
    });
    svg.querySelectorAll('.atlas-mindmap-edge').forEach((el) => {
      const oDom = data.nodes[el.dataset.origin]?.domain;
      const tDom = data.nodes[el.dataset.target]?.domain;
      const match = dom === 'ALL' || oDom === dom || tDom === dom;
      el.style.opacity = match ? '0.6' : '0.06';
    });
  });
});
"""


def compute_layout(nodes: dict) -> dict[str, tuple[float, float]]:
    """Positionnement déterministe en 6 grappes de domaines autour du centre."""
    cx, cy = 480.0, 310.0
    cluster_radius_x, cluster_radius_y = 295.0, 185.0
    grouped: dict[str, list[str]] = {d: [] for d in DOMAIN_ORDER}
    for key, node in nodes.items():
        grouped.setdefault(node["domain"], []).append(key)

    core = set(CATALOG["core"])
    positions: dict[str, tuple[float, float]] = {}
    domains = list(grouped.keys())
    for idx, dom in enumerate(domains):
        angle = -math.pi / 2 + (2 * math.pi * idx) / max(1, len(domains))
        hx = cx + cluster_radius_x * math.cos(angle)
        hy = cy + cluster_radius_y * math.sin(angle)
        keys = sorted(grouped[dom], key=lambda k: (k not in core, fold(nodes[k]["title"])))
        for pos_i, key in enumerate(keys):
            if pos_i == 0:
                positions[key] = (round(hx, 1), round(hy, 1))
                continue
            ring = 1 if pos_i <= 7 else (2 if pos_i <= 19 else 3)
            ring_start = 1 if ring == 1 else (8 if ring == 2 else 20)
            ring_cap = 7 if ring == 1 else (12 if ring == 2 else max(1, len(keys) - 20))
            step = (pos_i - ring_start) / ring_cap
            r = 46.0 * ring
            a = angle + 2 * math.pi * step + (0.35 * ring)
            px = max(36.0, min(924.0, hx + r * math.cos(a)))
            py = max(34.0, min(586.0, hy + r * 0.78 * math.sin(a)))
            positions[key] = (round(px, 1), round(py, 1))
    return positions


def render_mindmap(selected_key: str = "systemisme", active_domain: str = "Tous les domaines") -> str:
    """Construit la carte mentale SVG interactive des 6 domaines, 113+ notions et 113+ liens."""
    positions = compute_layout(NODES)
    relations = CATALOG["relations"]
    core = set(CATALOG["core"])
    neighbors = {selected_key}
    for rel in relations:
        if selected_key in (rel["origin"], rel["target"]):
            neighbors.add(rel["origin"])
            neighbors.add(rel["target"])

    edge_svg = []
    edges_payload = []
    for rel in relations:
        o, t = rel["origin"], rel["target"]
        x1, y1 = positions[o]
        x2, y2 = positions[t]
        incident = selected_key in (o, t)
        dom_match = active_domain == "Tous les domaines" or NODES[o]["domain"] == active_domain or NODES[t]["domain"] == active_domain
        opacity = "0.88" if incident else ("0.24" if dom_match else "0.07")
        width = "2.1" if incident else "0.95"
        stroke = DOMAIN_COLORS.get(NODES[o]["domain"], "#666") if incident else "#9b9488"
        edge_svg.append(
            f'<line class="atlas-mindmap-edge" data-id="{esc(rel["id"])}" '
            f'data-origin="{esc(o)}" data-target="{esc(t)}" '
            f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}">'
            f'<title>{esc(NODES[o]["title"])} → {esc(rel["verb"])} → {esc(NODES[t]["title"])}</title></line>'
        )
        edges_payload.append(
            {
                "id": rel["id"],
                "origin": o,
                "target": t,
                "witness": rel["witness"],
                "verb": rel["verb"],
                "kind": rel["kind"],
                "comparison": rel.get("comparison", ""),
            }
        )

    node_svg = []
    nodes_payload = {}
    for key, node in NODES.items():
        x, y = positions[key]
        dom = node["domain"]
        color = DOMAIN_COLORS.get(dom, "#4a4a4a")
        is_selected = key == selected_key
        is_core = key in core
        radius = 9.5 if is_selected else (7.0 if is_core else 5.0)
        dom_match = active_domain == "Tous les domaines" or dom == active_domain
        opacity = "1" if (key in neighbors or (active_domain != "Tous les domaines" and dom_match)) else ("0.78" if dom_match else "0.18")
        stroke = "#111" if is_selected else ("#fff" if is_core else "#faf8f4")
        stroke_w = "3.2" if is_selected else "1.4"
        short_label = node["title"][:26] + ("…" if len(node["title"]) > 26 else "")
        show_label = is_selected or is_core or key in neighbors
        label_el = (
            f'<text x="{x + radius + 3}" y="{y + 3.5}" font-size="{11 if is_selected else 9.5}" '
            f'font-weight="{700 if is_selected else 500}" fill="#1f1c18">{esc(short_label)}</text>'
            if show_label
            else ""
        )
        node_svg.append(
            f'<g class="atlas-mindmap-node" data-key="{esc(key)}" data-domain="{esc(dom)}" opacity="{opacity}">'
            f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}" stroke="{stroke}" stroke-width="{stroke_w}"/>'
            f"{label_el}<title>{esc(node['title'])} ({esc(dom)})</title></g>"
        )
        src = node["source"]
        nodes_payload[key] = {
            "title": node["title"],
            "domain": dom,
            "kind": node["kind"],
            "text": node["text"],
            "quote": src["quote"],
            "book": src["book"],
            "page": str(src["page"]),
            "folio": str(src.get("folio") or src["page"]),
            "voice": src.get("voice") if src.get("voice") not in (None, "Bunge") else "",
            "formula": (node.get("notation") or {}).get("formula", ""),
            "color": color,
        }

    # Domain cluster headings
    domain_labels = []
    for idx, dom in enumerate(DOMAIN_ORDER):
        angle = -math.pi / 2 + (2 * math.pi * idx) / len(DOMAIN_ORDER)
        lx = round(480.0 + 365.0 * math.cos(angle), 1)
        ly = round(310.0 + 265.0 * math.sin(angle), 1)
        lx = max(75.0, min(885.0, lx))
        ly = max(20.0, min(605.0, ly))
        domain_labels.append(
            f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="11.5" font-weight="700" '
            f'fill="{DOMAIN_COLORS[dom]}" opacity="0.9">{esc(dom.upper())}</text>'
        )

    pills = [
        f'<button type="button" class="atlas-domain-pill{" is-active" if active_domain == "Tous les domaines" else ""}" data-domain="ALL">Tous ({len(NODES)})</button>'
    ]
    for dom in DOMAIN_ORDER:
        cnt = sum(1 for n in NODES.values() if n["domain"] == dom)
        active_cls = " is-active" if active_domain == dom else ""
        pills.append(
            f'<button type="button" class="atlas-domain-pill{active_cls}" data-domain="{esc(dom)}" '
            f'style="border-left:4px solid {DOMAIN_COLORS[dom]};">{esc(dom)} ({cnt})</button>'
        )

    sel = nodes_payload.get(selected_key) or next(iter(nodes_payload.values()))
    initial_inspector = (
        f"<strong>{esc(sel['title'])}</strong> "
        f"<small>({esc(sel['domain'])} · {esc(sel['kind'])})</small>"
        f"<p style='margin:6px 0 4px;'>{esc(sel['text'])}</p>"
        f"<small>Cliquez sur n’importe quel nœud ou lien du graphe pour inspecter sa citation sourcée · Molette pour zoomer · Glisser pour déplacer.</small>"
        f"<blockquote lang='en'>« {esc(sel['quote'])} »</blockquote>"
    )
    payload_json = json.dumps({"nodes": nodes_payload, "edges": edges_payload}, ensure_ascii=False).replace("</", "<\\/")

    return (
        '<section class="atlas-mindmap" aria-label="Carte mentale interactive du système de Mario Bunge">'
        '<div class="atlas-mindmap-bar">'
        '<div class="atlas-mindmap-legend">' + "".join(pills) + "</div>"
        '<div class="atlas-mindmap-controls">'
        '<button type="button" data-action="zoom-in" title="Zoomer">Zoom +</button>'
        '<button type="button" data-action="zoom-out" title="Dézoomer">Zoom −</button>'
        '<button type="button" data-action="zoom-reset" title="Réinitialiser la vue">Réinitialiser</button>'
        "</div></div>"
        '<svg class="atlas-mindmap-canvas" viewBox="0 0 960 620" role="img" aria-label="Graphe des concepts de Bunge">'
        + "".join(edge_svg)
        + "".join(node_svg)
        + "".join(domain_labels)
        + "</svg>"
        f'<div class="atlas-mindmap-inspector" style="border-left-color:{sel["color"]};">{initial_inspector}</div>'
        f'<script type="application/json" class="atlas-mindmap-data">{payload_json}</script>'
        "</section>"
    )


def render_symbol_lexicon(query: str = "") -> str:
    """Rend le lexique filtrable des symboles et notations collationnés du Traité."""
    needle = fold(query.strip())
    entries = [
        (key, node)
        for key, node in sorted(NODES.items(), key=lambda item: fold(item[1]["title"]))
        if node.get("notation")
    ]
    if needle:
        entries = [
            (key, node)
            for key, node in entries
            if needle
            in fold(
                f"{node['title']} {node['domain']} {node['notation']['formula']} {node['notation']['gloss']} {' '.join(node.get('tags', ()))}"
            )
            or query.strip() in node["notation"]["formula"]
        ]
    if not entries:
        return "<p>Aucune notation ne correspond à ce filtre dans le lexique.</p>"
    cards = []
    for _, node in entries:
        not_ = node["notation"]
        src = node["source"]
        cards.append(
            f'<article class="symbol-entry">'
            f'<header><strong>{esc(node["title"])}</strong> · <small>{esc(node["domain"])} · PDF p. {esc(str(src["page"]))}</small></header>'
            f'<p class="formula">{esc(not_["formula"])}</p>'
            f'<p>{esc(not_["gloss"])}</p>'
            f'<small>{esc(not_["status"])}</small>'
            f"</article>"
        )
    return f'<div class="symbol-lexicon"><p><small>{len(entries)} notation(s) collationnée(s).</small></p>' + "".join(cards) + "</div>"
