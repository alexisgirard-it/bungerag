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
    "Ontologie": "#2563eb",
    "Sémantique": "#7c3aed",
    "Épistémologie": "#0f766e",
    "Philosophie de l’esprit": "#c2410c",
    "Philosophie des sciences": "#b45309",
    "Éthique": "#be185d",
}

MINDMAP_CSS = """
.atlas-mindmap {
  background: rgba(255, 255, 255, 0.62);
  backdrop-filter: blur(22px) saturate(165%);
  -webkit-backdrop-filter: blur(22px) saturate(165%);
  border: 1px solid rgba(255, 255, 255, 0.88);
  border-radius: 20px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92), 0 16px 40px -16px rgba(15, 23, 42, 0.11), 0 0 0 1px rgba(15, 23, 42, 0.05);
  padding: 14px 16px 16px;
  margin: 4px 0 12px;
}
.atlas-mindmap-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 10px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.atlas-mindmap-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.atlas-mindmap-controls {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  background: rgba(255, 255, 255, 0.66);
  border: 1px solid rgba(15, 23, 42, 0.09);
  border-radius: 999px;
  padding: 3px;
}
.atlas-mindmap-controls button {
  background: transparent;
  border: 0;
  border-radius: 999px;
  color: #334155;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 10px;
  transition: background-color 140ms ease, color 140ms ease;
}
.atlas-mindmap-controls button:hover {
  background: rgba(37, 99, 235, 0.10);
  color: #1d4ed8;
}
.atlas-domain-pill {
  align-items: center;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(15, 23, 42, 0.09);
  border-radius: 999px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
  color: #334155;
  cursor: pointer;
  display: inline-flex;
  font-size: 11px;
  font-weight: 560;
  gap: 5px;
  padding: 4px 9px;
  white-space: nowrap;
  transition: all 150ms ease;
}
.atlas-domain-pill:hover {
  background: rgba(255, 255, 255, 0.96);
  border-color: rgba(37, 99, 235, 0.28);
  color: #0f172a;
}
.atlas-domain-pill.is-active {
  background: #0f172a;
  border-color: #0f172a;
  box-shadow: 0 6px 16px -6px rgba(15, 23, 42, 0.45);
  color: #ffffff;
}
.atlas-pill-dot {
  border-radius: 50%;
  display: inline-block;
  height: 7px;
  width: 7px;
  flex-shrink: 0;
}
.atlas-mindmap-stage {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background:
    radial-gradient(circle at 24% 20%, rgba(37, 99, 235, 0.06), transparent 46%),
    radial-gradient(circle at 78% 76%, rgba(124, 58, 237, 0.05), transparent 46%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.94) 0%, rgba(248, 250, 252, 0.96) 100%);
}
.atlas-mindmap-canvas {
  width: 100%;
  height: 500px;
  cursor: grab;
  touch-action: none;
  display: block;
}
.atlas-mindmap-canvas:active { cursor: grabbing; }
.atlas-mindmap-node { cursor: pointer; transition: opacity 180ms ease; }
.atlas-mindmap-node circle { transition: r 150ms ease, stroke-width 150ms ease; }
.atlas-mindmap-node:hover .atlas-node-label { opacity: 1 !important; }
.atlas-node-label {
  pointer-events: none;
  paint-order: stroke;
  stroke: rgba(255, 255, 255, 0.95);
  stroke-width: 4.5px;
  stroke-linejoin: round;
  transition: opacity 160ms ease;
}
.atlas-mindmap-edge { cursor: pointer; fill: none; transition: opacity 180ms ease, stroke-width 180ms ease; }
.atlas-mindmap-edge:hover { opacity: 0.95 !important; }
.atlas-mindmap-tip {
  color: #64748b;
  font-size: 11.5px;
  margin: 8px 4px 0;
  text-align: right;
}
.atlas-mindmap-inspector {
  margin-top: 12px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-left: 4px solid #2563eb;
  border-radius: 14px;
  font-size: 13.5px;
  line-height: 1.5;
  color: #0f172a;
}
.atlas-mindmap-inspector blockquote {
  margin: 8px 0 0;
  padding: 8px 12px;
  background: rgba(241, 245, 249, 0.65);
  border-left: 2px solid rgba(37, 99, 235, 0.5);
  border-radius: 0 8px 8px 0;
  color: #334155;
  font-family: "Iowan Old Style", Georgia, serif;
  font-style: italic;
}
"""

MINDMAP_JS = """
const bindMindmap = () => {
  const root = element.querySelector('.atlas-mindmap');
  if (!root || root.dataset.bound === '1') return;
  root.dataset.bound = '1';
  const svg = root.querySelector('svg.atlas-mindmap-canvas');
  const inspector = root.querySelector('.atlas-mindmap-inspector');
  const payloadEl = root.querySelector('.atlas-mindmap-data');
  if (!svg || !inspector || !payloadEl) return;

  let data = { nodes: {}, edges: [], selected: 'systemisme' };
  try { data = JSON.parse(payloadEl.textContent || '{}'); } catch (_) { return; }

  const DEFAULT_VB = { x: 0, y: 0, w: 1120, h: 680 };
  let vb = { ...DEFAULT_VB };
  const applyViewBox = () => svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);

  const zoom = (factor, cx = vb.x + vb.w / 2, cy = vb.y + vb.h / 2) => {
    const nw = Math.max(260, Math.min(1900, vb.w * factor));
    const nh = Math.max(158, Math.min(1154, vb.h * factor));
    vb.x = cx - ((cx - vb.x) / vb.w) * nw;
    vb.y = cy - ((cy - vb.y) / vb.h) * nh;
    vb.w = nw;
    vb.h = nh;
    applyViewBox();
  };

  const escHtml = (s) => String(s || '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const separateLabels = (keys) => {
    const placed = [];
    for (const k of keys) {
      const el = svg.querySelector(`.atlas-mindmap-node[data-key="${CSS.escape(k)}"]`);
      const lbl = el?.querySelector('.atlas-node-label');
      if (!lbl) continue;
      const baseX = parseFloat(lbl.dataset.bx || lbl.getAttribute('x') || '0');
      const baseY = parseFloat(lbl.dataset.by || lbl.getAttribute('y') || '0');
      const w = (lbl.textContent || '').length * 6.4 + 10;
      const anchor = lbl.getAttribute('text-anchor') || 'start';
      const x0 = anchor === 'end' ? baseX - w : baseX;
      let y = baseY;
      for (let tries = 0; tries < 10; tries++) {
        const hit = placed.some((b) => !(x0 + w < b.x0 || x0 > b.x1 || y - 14 > b.y1 || y + 3 < b.y0));
        if (!hit) break;
        y += (tries % 2 === 0 ? 1 : -1) * (16 * Math.ceil((tries + 1) / 2));
      }
      lbl.setAttribute('y', String(Math.round(y * 10) / 10));
      placed.push({ x0, x1: x0 + w, y0: y - 14, y1: y + 3 });
    }
  };

  const highlightNode = (key) => {
    const node = data.nodes[key];
    if (!node) return;
    const neighborsOrdered = [key];
    const incident = [];
    for (const edge of data.edges) {
      if (edge.origin === key || edge.target === key) {
        const other = edge.origin === key ? edge.target : edge.origin;
        if (!neighborsOrdered.includes(other)) neighborsOrdered.push(other);
        incident.push(edge);
      }
    }
    const neighbors = new Set(neighborsOrdered);
    const labeled = new Set(neighborsOrdered.slice(0, 6));
    svg.querySelectorAll('.atlas-mindmap-node').forEach((el) => {
      const k = el.dataset.key;
      el.style.opacity = neighbors.has(k) ? '1' : '0.22';
      const circle = el.querySelector('circle.atlas-dot');
      if (circle) {
        circle.setAttribute('stroke', k === key ? '#0f172a' : '#ffffff');
        circle.setAttribute('stroke-width', k === key ? '3.4' : '1.6');
      }
      const lbl = el.querySelector('.atlas-node-label');
      if (lbl) lbl.style.opacity = labeled.has(k) ? '1' : '0';
    });
    separateLabels(neighborsOrdered.slice(0, 6));
    svg.querySelectorAll('.atlas-mindmap-edge').forEach((el) => {
      const active = el.dataset.origin === key || el.dataset.target === key;
      el.style.opacity = active ? '0.92' : '0.09';
      el.setAttribute('stroke-width', active ? '2.2' : '0.9');
    });
    const rels = incident.slice(0, 6).map((e) => {
      return `<li>${escHtml(data.nodes[e.origin]?.title || e.origin)} → <em>${escHtml(e.verb)}</em> → ${escHtml(data.nodes[e.target]?.title || e.target)} <small>(${escHtml(e.kind)})</small></li>`;
    }).join('');
    const notation = node.formula ? `<p style="margin:6px 0;"><strong>Notation :</strong> <code>${escHtml(node.formula)}</code></p>` : '';
    const voice = node.voice ? ` · Auteur cité : ${escHtml(node.voice)}` : '';
    inspector.style.borderLeftColor = node.color || '#2563eb';
    inspector.innerHTML = `<strong style="font-size:15px;">${escHtml(node.title)}</strong> <small style="color:#64748b;">(${escHtml(node.domain)} · ${escHtml(node.kind)}${voice})</small>`
      + `<p style="margin:6px 0 4px;">${escHtml(node.text)}</p>${notation}`
      + `<small style="color:#64748b;">${escHtml(node.book)} · p. ${escHtml(node.folio || node.page)} (PDF p. ${escHtml(node.page)})</small>`
      + `<blockquote lang="en">« ${escHtml(node.quote)} »</blockquote>`
      + (rels ? `<ul style="margin:8px 0 0 18px;padding:0;font-size:12.5px;">${rels}</ul>` : '');
  };

  const highlightEdge = (id) => {
    const edge = data.edges.find((e) => e.id === id);
    if (!edge) return;
    const o = data.nodes[edge.origin], t = data.nodes[edge.target], w = data.nodes[edge.witness];
    inspector.style.borderLeftColor = o?.color || '#2563eb';
    inspector.innerHTML = `<strong style="font-size:14.5px;">${escHtml(o?.title || edge.origin)} → ${escHtml(edge.verb)} → ${escHtml(t?.title || edge.target)}</strong>`
      + `<br><small style="color:#64748b;">${escHtml(edge.kind)} · Témoin : ${escHtml(w?.title || edge.witness)} (PDF p. ${escHtml(w?.page || '')})</small>`
      + (edge.comparison ? `<p style="margin:6px 0 0;"><strong>Lecture éditoriale :</strong> ${escHtml(edge.comparison)}</p>` : '')
      + (w?.quote ? `<blockquote lang="en">« ${escHtml(w.quote)} »</blockquote>` : '');
  };

  const resetAll = () => {
    vb = { ...DEFAULT_VB };
    applyViewBox();
    root.querySelectorAll('.atlas-domain-pill').forEach((b) => {
      b.classList.toggle('is-active', b.dataset.domain === 'ALL');
    });
    highlightNode(data.selected || 'systemisme');
  };

  root.querySelector('[data-action="zoom-in"]')?.addEventListener('click', () => zoom(0.8));
  root.querySelector('[data-action="zoom-out"]')?.addEventListener('click', () => zoom(1.25));
  root.querySelector('[data-action="zoom-reset"]')?.addEventListener('click', resetAll);

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

  svg.addEventListener('click', (e) => {
    const nodeEl = e.target.closest('.atlas-mindmap-node');
    if (nodeEl) { highlightNode(nodeEl.dataset.key); return; }
    const edgeEl = e.target.closest('.atlas-mindmap-edge');
    if (edgeEl) { highlightEdge(edgeEl.dataset.id); }
  });

  root.querySelectorAll('.atlas-domain-pill').forEach((btn) => {
    btn.addEventListener('click', () => {
      const dom = btn.dataset.domain;
      root.querySelectorAll('.atlas-domain-pill').forEach((b) => b.classList.toggle('is-active', b === btn));
      if (dom === 'ALL') { resetAll(); return; }
      const shownKeys = [];
      svg.querySelectorAll('.atlas-mindmap-node').forEach((el) => {
        const match = el.dataset.domain === dom;
        el.style.opacity = match ? '1' : '0.12';
        const lbl = el.querySelector('.atlas-node-label');
        if (lbl) {
          const show = match && shownKeys.length < 6;
          lbl.style.opacity = show ? '1' : '0';
          if (show) shownKeys.push(el.dataset.key);
        }
      });
      separateLabels(shownKeys);
      svg.querySelectorAll('.atlas-mindmap-edge').forEach((el) => {
        const oDom = data.nodes[el.dataset.origin]?.domain;
        const tDom = data.nodes[el.dataset.target]?.domain;
        const match = oDom === dom || tDom === dom;
        el.style.opacity = match ? '0.62' : '0.05';
        el.setAttribute('stroke-width', match ? '1.3' : '0.8');
      });
    });
  });
};

bindMindmap();
const obs = new MutationObserver(() => bindMindmap());
obs.observe(element, { childList: true, subtree: true });
"""

CLUSTER_CENTERS = {
    "Ontologie": (560.0, 148.0),
    "Sémantique": (895.0, 222.0),
    "Épistémologie": (895.0, 472.0),
    "Philosophie de l’esprit": (560.0, 536.0),
    "Philosophie des sciences": (225.0, 472.0),
    "Éthique": (225.0, 222.0),
}

DOMAIN_HEADER_POS = {
    "Ontologie": (560.0, 32.0),
    "Sémantique": (960.0, 74.0),
    "Épistémologie": (960.0, 648.0),
    "Philosophie de l’esprit": (560.0, 656.0),
    "Philosophie des sciences": (160.0, 648.0),
    "Éthique": (160.0, 74.0),
}


def compute_layout(nodes: dict) -> dict[str, tuple[float, float]]:
    """Positionnement déterministe en 6 grappes aérées sans collision avec les titres."""
    grouped: dict[str, list[str]] = {d: [] for d in DOMAIN_ORDER}
    for key, node in nodes.items():
        grouped.setdefault(node["domain"], []).append(key)

    core = set(CATALOG["core"])
    positions: dict[str, tuple[float, float]] = {}
    for dom, keys_raw in grouped.items():
        hx, hy = CLUSTER_CENTERS.get(dom, (560.0, 340.0))
        keys = sorted(keys_raw, key=lambda k: (k not in core, fold(nodes[k]["title"])))
        for pos_i, key in enumerate(keys):
            if pos_i == 0:
                positions[key] = (round(hx, 1), round(hy, 1))
                continue
            ring = 1 if pos_i <= 6 else (2 if pos_i <= 16 else 3)
            ring_start = 1 if ring == 1 else (7 if ring == 2 else 17)
            ring_cap = 6 if ring == 1 else (10 if ring == 2 else max(1, len(keys) - 17))
            step = (pos_i - ring_start) / ring_cap
            rx = 46.0 * ring
            ry = 36.0 * ring
            a = -math.pi / 2 + 2 * math.pi * step + (0.42 * ring)
            px = max(56.0, min(1064.0, hx + rx * math.cos(a)))
            py = max(62.0, min(614.0, hy + ry * math.sin(a)))
            positions[key] = (round(px, 1), round(py, 1))
    return positions


def render_mindmap(selected_key: str = "systemisme", active_domain: str = "Tous les domaines") -> str:
    """Construit la carte mentale SVG interactive des 6 domaines, 113+ notions et 113+ liens."""
    positions = compute_layout(NODES)
    relations = CATALOG["relations"]
    core = set(CATALOG["core"])
    neighbors_ordered = [selected_key]
    for rel in relations:
        if selected_key in (rel["origin"], rel["target"]):
            other = rel["target"] if rel["origin"] == selected_key else rel["origin"]
            if other not in neighbors_ordered:
                neighbors_ordered.append(other)
    neighbors = set(neighbors_ordered)
    # Limiter les libellés permanents au nœud actif + ses 5 premiers voisins, séparés sans collision.
    initially_labeled_order = neighbors_ordered[:6]
    initially_labeled = set(initially_labeled_order)
    label_coords: dict[str, tuple[float, float, str]] = {}
    placed_boxes: list[tuple[float, float, float, float]] = []
    for k in initially_labeled_order:
        nx, ny = positions[k]
        dom_k = NODES[k]["domain"]
        ccx, _ = CLUSTER_CENTERS.get(dom_k, (560.0, 340.0))
        rad = 10.5 if k == selected_key else (7.2 if k in core else 5.2)
        anchor = "end" if (nx < ccx - 6 or nx > 800) else "start"
        tx = round(nx - rad - 6, 1) if anchor == "end" else round(nx + rad + 6, 1)
        title_k = NODES[k]["title"][:26] + ("…" if len(NODES[k]["title"]) > 26 else "")
        w = len(title_k) * 6.5 + 12
        x0 = tx - w if anchor == "end" else tx
        ty = ny + 4.0
        for tries in range(12):
            hit = any(not (x0 + w < bx0 or x0 > bx1 or ty - 14 > by1 or ty + 4 < by0) for bx0, bx1, by0, by1 in placed_boxes)
            if not hit:
                break
            step_dir = 1 if tries % 2 == 0 else -1
            ty = ny + 4.0 + step_dir * 18.0 * ((tries // 2) + 1)
        ty = round(max(52.0, min(626.0, ty)), 1)
        placed_boxes.append((x0, x0 + w, ty - 14.0, ty + 4.0))
        label_coords[k] = (tx, ty, anchor)

    edge_svg = []
    edges_payload = []
    for rel in relations:
        o, t = rel["origin"], rel["target"]
        x1, y1 = positions[o]
        x2, y2 = positions[t]
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        # Légère courbure vers le centre du graphe pour des arêtes organiques lisibles.
        cx = round(mx + (560.0 - mx) * 0.14, 1)
        cy = round(my + (340.0 - my) * 0.14, 1)
        incident = selected_key in (o, t)
        dom_match = (
            active_domain == "Tous les domaines"
            or NODES[o]["domain"] == active_domain
            or NODES[t]["domain"] == active_domain
        )
        opacity = "0.86" if incident else ("0.18" if dom_match else "0.06")
        width = "2.2" if incident else "0.95"
        stroke = DOMAIN_COLORS.get(NODES[o]["domain"], "#64748b") if incident else "#94a3b8"
        edge_svg.append(
            f'<path class="atlas-mindmap-edge" data-id="{esc(rel["id"])}" '
            f'data-origin="{esc(o)}" data-target="{esc(t)}" '
            f'd="M {x1} {y1} Q {cx} {cy} {x2} {y2}" '
            f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}">'
            f'<title>{esc(NODES[o]["title"])} → {esc(rel["verb"])} → {esc(NODES[t]["title"])}</title></path>'
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
        color = DOMAIN_COLORS.get(dom, "#475569")
        is_selected = key == selected_key
        is_core = key in core
        radius = 10.5 if is_selected else (7.2 if is_core else 5.2)
        dom_match = active_domain == "Tous les domaines" or dom == active_domain
        opacity = (
            "1"
            if (key in neighbors or (active_domain != "Tous les domaines" and dom_match))
            else ("0.56" if dom_match else "0.14")
        )
        stroke = "#0f172a" if is_selected else "#ffffff"
        stroke_w = "3.2" if is_selected else "1.6"
        short_label = node["title"][:26] + ("…" if len(node["title"]) > 26 else "")
        label_opacity = "1" if key in initially_labeled else "0"
        ccx, _ = CLUSTER_CENTERS.get(dom, (560.0, 340.0))
        default_anchor = "end" if (x < ccx - 6 or x > 800) else "start"
        default_tx = round(x - radius - 6, 1) if default_anchor == "end" else round(x + radius + 6, 1)
        tx, ty, anchor = label_coords.get(key, (default_tx, round(y + 4, 1), default_anchor))
        halo = (
            f'<circle cx="{x}" cy="{y}" r="{radius + 6}" fill="{color}" opacity="0.18"/>'
            if is_selected
            else ""
        )
        label_el = (
            f'<text class="atlas-node-label" data-bx="{default_tx}" data-by="{round(y + 4, 1)}" '
            f'x="{tx}" y="{ty}" text-anchor="{anchor}" font-size="{12.5 if is_selected else 11}" '
            f'font-weight="{700 if is_selected else 600}" fill="#0f172a" '
            f'style="opacity:{label_opacity};">{esc(short_label)}</text>'
        )
        node_svg.append(
            f'<g class="atlas-mindmap-node" data-key="{esc(key)}" data-domain="{esc(dom)}" opacity="{opacity}">'
            f'<circle cx="{x}" cy="{y}" r="13" fill="transparent"/>'
            f'{halo}<circle class="atlas-dot" cx="{x}" cy="{y}" r="{radius}" fill="{color}" stroke="{stroke}" stroke-width="{stroke_w}"/>'
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

    # Soft domain halos & clean perimeter pill badges (never overlapping nodes)
    domain_backdrops = []
    domain_labels = []
    for dom in DOMAIN_ORDER:
        cx, cy = CLUSTER_CENTERS[dom]
        color = DOMAIN_COLORS[dom]
        domain_backdrops.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="142" ry="102" fill="{color}" opacity="0.045"/>'
        )
        lx, ly = DOMAIN_HEADER_POS[dom]
        text_w = max(92, len(dom) * 7.6 + 24)
        rx0 = round(lx - text_w / 2, 1)
        ry0 = round(ly - 13, 1)
        domain_labels.append(
            f'<g pointer-events="none">'
            f'<rect x="{rx0}" y="{ry0}" width="{round(text_w, 1)}" height="24" rx="12" '
            f'fill="rgba(255,255,255,0.88)" stroke="{color}" stroke-opacity="0.32" stroke-width="1"/>'
            f'<text x="{lx}" y="{round(ly + 3.5, 1)}" text-anchor="middle" font-size="10.5" '
            f'font-weight="700" letter-spacing="0.6" fill="{color}">{esc(dom.upper())}</text></g>'
        )

    pills = [
        f'<button type="button" class="atlas-domain-pill{" is-active" if active_domain == "Tous les domaines" else ""}" '
        f'data-domain="ALL">Tous ({len(NODES)})</button>'
    ]
    for dom in DOMAIN_ORDER:
        cnt = sum(1 for n in NODES.values() if n["domain"] == dom)
        active_cls = " is-active" if active_domain == dom else ""
        pills.append(
            f'<button type="button" class="atlas-domain-pill{active_cls}" data-domain="{esc(dom)}">'
            f'<span class="atlas-pill-dot" style="background:{DOMAIN_COLORS[dom]};"></span>'
            f"{esc(dom)} ({cnt})</button>"
        )

    sel = nodes_payload.get(selected_key) or next(iter(nodes_payload.values()))
    initial_inspector = (
        f"<strong style='font-size:15px;'>{esc(sel['title'])}</strong> "
        f"<small style='color:#64748b;'>({esc(sel['domain'])} · {esc(sel['kind'])})</small>"
        f"<p style='margin:6px 0 4px;'>{esc(sel['text'])}</p>"
        f"<small style='color:#64748b;'>Cliquez sur un nœud ou une courbe pour lire sa citation sourcée · Survol pour révéler les libellés.</small>"
        f"<blockquote lang='en'>« {esc(sel['quote'])} »</blockquote>"
    )
    payload_json = json.dumps(
        {"nodes": nodes_payload, "edges": edges_payload, "selected": selected_key},
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return (
        '<section class="atlas-mindmap" aria-label="Carte mentale interactive du système de Mario Bunge">'
        '<div class="atlas-mindmap-bar">'
        '<div class="atlas-mindmap-legend">' + "".join(pills) + "</div>"
        '<div class="atlas-mindmap-controls">'
        '<button type="button" data-action="zoom-in" title="Zoomer">Zoom +</button>'
        '<button type="button" data-action="zoom-out" title="Dézoomer">Zoom −</button>'
        '<button type="button" data-action="zoom-reset" title="Réinitialiser la vue">Réinitialiser</button>'
        "</div></div>"
        '<div class="atlas-mindmap-stage">'
        '<svg class="atlas-mindmap-canvas" viewBox="0 0 1120 680" role="img" aria-label="Graphe des concepts de Bunge">'
        + "".join(domain_backdrops)
        + "".join(edge_svg)
        + "".join(node_svg)
        + "".join(domain_labels)
        + "</svg>"
        "</div>"
        '<div class="atlas-mindmap-tip">Molette pour zoomer · Glisser pour déplacer · Cliquer un nœud ou une arête</div>'
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
        color = DOMAIN_COLORS.get(node["domain"], "#2563eb")
        cards.append(
            f'<article class="symbol-entry">'
            f'<header><strong>{esc(node["title"])}</strong>'
            f'<span class="symbol-badge"><span class="symbol-dot" style="background:{color};"></span>'
            f'{esc(node["domain"])} · PDF p. {esc(str(src["page"]))}</span></header>'
            f'<p class="symbol-formula-box formula">{esc(not_["formula"])}</p>'
            f'<p>{esc(not_["gloss"])}</p>'
            f'<small>{esc(not_["status"])}</small>'
            f"</article>"
        )
    return (
        f'<div class="symbol-lexicon">'
        f'<p class="symbol-lexicon-count">{len(entries)} notation(s) collationnée(s)</p>'
        + "".join(cards)
        + "</div>"
    )
