"""Pré-remplissage sourcé et durci SSRF des faits contemporains pour l’Atelier."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from datetime import date
from html import unescape
from urllib.parse import quote, urlsplit

USER_AGENT = "BungeRAG/4.0 (+https://huggingface.co/spaces/alexisgirard/bungerag)"
MAX_BYTES = 262_144


def _is_forbidden_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_https_url(url: str, *, resolve_dns: bool = True) -> str:
    """Autorise uniquement une URL HTTPS publique (protection SSRF)."""
    clean = (url or "").strip()
    if not clean or len(clean) > 600 or any(c.isspace() for c in clean):
        raise ValueError("Indiquez une URL HTTPS publique valide.")
    parsed = urlsplit(clean)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Seules les adresses HTTPS publiques sont acceptées.")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Les hôtes locaux ou privés sont interdits.")
    try:
        if _is_forbidden_ip(host):
            raise ValueError("Les adresses IP locales ou privées sont interdites.")
    except ValueError as exc:
        if "interdites" in str(exc):
            raise
    if resolve_dns:
        try:
            infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError(f"Hôte inaccessible : {host}") from exc
        for info in infos:
            if _is_forbidden_ip(info[4][0]):
                raise ValueError("L’adresse résout vers un réseau privé interdit.")
    return clean


def _extract_html_summary(body: str) -> tuple[str, str, str]:
    title_m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    title = " ".join(unescape(title_m.group(1)).split())[:180] if title_m else ""
    desc_m = re.search(
        r'<meta[^>]+(?:name=["\']description["\']|property=["\']og:description["\'])[^>]+content=["\']([^"\']+)["\']',
        body,
        re.I,
    )
    desc = " ".join(unescape(desc_m.group(1)).split())[:420] if desc_m else ""
    date_m = re.search(
        r'(?:article:published_time|datePublished|dateModified)[^0-9]{0,30}(20\d{2}-\d{2}-\d{2})',
        body,
        re.I,
    )
    published = date_m.group(1) if date_m else date.today().isoformat()
    return title, desc, published


def fetch_contemporary_fact(query_or_url: str, *, http_get=None, resolve_dns: bool = True) -> dict:
    """Pré-remplit un fait contemporain daté depuis une URL HTTPS publique ou Wikipédia."""
    raw = " ".join((query_or_url or "").split())
    if len(raw) < 3:
        raise ValueError("Indiquez une URL HTTPS publique ou un sujet contemporain (3 caractères minimum).")
    if http_get is None:
        import requests

        getter = requests.get
    else:
        getter = http_get

    if raw.startswith("https://") or raw.startswith("http://") or "://" in raw:
        url = validate_public_https_url(raw, resolve_dns=resolve_dns)
        resp = getter(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=8,
            allow_redirects=False,
        )
        if getattr(resp, "status_code", 200) >= 400:
            raise ValueError(f"La source a répondu HTTP {resp.status_code}.")
        body = (resp.text or "")[:MAX_BYTES]
        title, desc, published = _extract_html_summary(body)
        summary = desc or title or f"Page consultée sur {urlsplit(url).hostname}"
        return {
            "text": summary[:600],
            "url": url,
            "published": published,
            "title": title or urlsplit(url).hostname,
        }

    # Mode sujet : API REST publique Wikipédia (FR puis EN, sans clé API).
    slug = quote(raw.replace(" ", "_"), safe="")
    for lang in ("fr", "en"):
        api_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}"
        resp = getter(
            api_url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=8,
            allow_redirects=True,
        )
        if getattr(resp, "status_code", 0) != 200:
            continue
        data = resp.json() if callable(getattr(resp, "json", None)) else json.loads(resp.text)
        extract = " ".join((data.get("extract") or "").split())[:550]
        page_url = (
            data.get("content_urls", {}).get("desktop", {}).get("page")
            or f"https://{lang}.wikipedia.org/wiki/{slug}"
        )
        ts = (data.get("timestamp") or "")[:10]
        published = ts if re.fullmatch(r"\d{4}-\d{2}-\d{2}", ts) else date.today().isoformat()
        if extract:
            return {
                "text": extract,
                "url": page_url,
                "published": published,
                "title": data.get("title") or raw,
            }
    raise ValueError(
        "Aucune notice Wikipédia trouvée pour ce sujet. Collez directement une URL HTTPS publique."
    )
