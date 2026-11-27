"""Recherche académique externe (OpenAlex & Europe PMC), activée intelligemment hors corpus Bunge."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from urllib.parse import quote

USER_AGENT = "BungeRAG/5.0 (+https://huggingface.co/spaces/alexisgirard/bungerag)"
HTTP_TIMEOUT = 6

# Déclencheurs explicites de littérature scientifique ou faits empiriques contemporains (post-2020)
_EXPLICIT_STUDY_RE = re.compile(
    r"\b(?:"
    r"etude[s]?|papier[s]?|article[s]? scientifique[s]?|litterature scientifique|"
    r"meta[- ]?analyse[s]?|essai[s]? clinique[s]?|essai[s]? controle[s]?|"
    r"revue[s]? systematique[s]?|preuve[s]? empirique[s]?|donnees empiriques|"
    r"experience[s]? recente[s]?|recherche[s]? recente[s]?|statistique[s]? clinique[s]?|"
    r"aujourd['’]?hui|actuel(?:le)?[s]?|recent(?:e)?[s]?|contemporain(?:e)?[s]?|"
    r"202[0-9]|en clinique|patients?"
    r")\b"
)

_CONTEMPORARY_SCI_RE = re.compile(
    r"\b(?:"
    r"llm|gpt[- ]?\d?|llama|claude|gemini|chatgpt|transformer|deep learning|"
    r"modele[s]? de (?:langage|pointe)|reseau[x]? de neurones|"
    r"intelligence artificielle|conscience artificielle|"
    r"neuroscience[s]?|neurobiologie|irmf|fmri|connectome|organoide[s]?|"
    r"psychanalyse|homeopathie|placebo[s]?|crispr|epigenetique|"
    r"mecanique quantique|physique quantique|changement climatique|climat|"
    r"economie comportementale"
    r")\b"
)

_PURE_EXEGESIS_RE = re.compile(
    r"^(?:que dit|qu['’]?est[- ]ce que|comment definit|quelle est la definition|ou bunge|dans quel livre)"
)

_BIOMED_RE = re.compile(
    r"\b(?:"
    r"psychanalyse|clinique|therap\w*|patient[s]?|placebo[s]?|homeopathie|"
    r"cerveau|brain|neuro\w*|synap\w*|plastic\w*|psycholog\w*|psychiatr\w*|"
    r"biolog\w*|cellul\w*|genet\w*|crispr|epigenet\w*|medic\w*|sante|health"
    r")\b"
)

_FILLER_RE = re.compile(
    r"\b(?:"
    r"mario bunge|bunge|bung[eé]en(?:ne)?s?|selon|chez|cadre|ok|mais|nan|non|oui|"
    r"car|donc|alors|pourtant|justement|meme|pour|le|la|les|un|une|des|du|de|d|"
    r"en|et|ou|que|qui|quoi|est|sont|c|ce|cet|cette|ces|ca|cela|pas|plus|tres|"
    r"tout|tous|toute|toutes|dans|sur|avec|sans|par|comme|si|on|va|dire|lambda|"
    r"peut|peuvent|etre|avoir|fait|faire|avoir|bon|vraiment|beaucoup|apres|etc"
    r")\b"
)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def should_search_academic(
    message: str, turns: list[dict] | None = None, *, mode: str = "auto"
) -> tuple[bool, str]:
    """Décide intelligemment s’il est pertinent d’interroger la littérature scientifique externe."""
    clean_mode = (mode or "auto").strip().lower()
    if clean_mode in {"off", "false", "0", "none"}:
        return False, ""
    if clean_mode in {"force", "on", "always"}:
        return True, "demandée par le lecteur"

    folded = _fold(message).strip()
    if len(folded) < 10:
        return False, ""

    has_explicit = bool(_EXPLICIT_STUDY_RE.search(folded))
    has_contemporary = bool(_CONTEMPORARY_SCI_RE.search(folded))

    # Si c'est une pure question d'exégèse textuelle sur Bunge sans enjeu empirique/actuel, ne pas déclencher.
    if _PURE_EXEGESIS_RE.search(folded) and not (has_explicit or has_contemporary):
        return False, ""

    if has_explicit:
        return True, "données empiriques ou études scientifiques évoquées"
    if has_contemporary:
        return True, "sujet scientifique ou technologique contemporain"

    # En relance multi-tours, hériter uniquement si la relance reste technique/empirique
    if turns:
        prev_folded = _fold(turns[-1].get("user", ""))
        if _CONTEMPORARY_SCI_RE.search(prev_folded) and re.search(
            r"\b(?:complexe|cerveau|parametre|resultat|efficac|revolution|experience|preuve|test)\b",
            folded,
        ):
            return True, "suite d’un débat scientifique ou technologique contemporain"

    return False, ""


def _reconstruct_abstract(inverted_index: dict | None, max_chars: int = 420) -> str:
    if not isinstance(inverted_index, dict) or not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        if not isinstance(idxs, list):
            continue
        for pos in idxs:
            if isinstance(pos, int) and pos < 160:
                positions.append((pos, str(word)))
    if not positions:
        return ""
    positions.sort(key=lambda pair: pair[0])
    text = " ".join(word for _, word in positions)
    text = " ".join(text.split())
    return (text[:max_chars].rstrip() + "…") if len(text) > max_chars else text


def _clean_html_text(raw: str, max_chars: int = 420) -> str:
    stripped = re.sub(r"<[^>]+>", " ", raw or "")
    clean = " ".join(stripped.split())
    return (clean[:max_chars].rstrip() + "…") if len(clean) > max_chars else clean


def build_academic_query(
    message: str, turns: list[dict] | None = None, *, translator=None
) -> str:
    """Construit une requête anglaise courte et ciblée pour OpenAlex / Europe PMC."""
    raw = " ".join((message or "").split())[:350]
    if turns and len(raw) < 70:
        anchor = " ".join((turns[-1].get("user") or "").split())[:140]
        raw = f"{anchor} {raw}".strip()

    # Retirer les références méta à Bunge pour chercher les concepts scientifiques eux-mêmes
    cleaned = re.sub(r"\b(?:mario\s+)?bunge(?:en(?:ne)?s?)?\b", "", raw, flags=re.I)
    cleaned = " ".join(cleaned.split()) or raw

    if translator is not None:
        try:
            english = translator(cleaned)
        except Exception:
            english = cleaned
    else:
        try:
            from library import translate

            english = translate(cleaned)
        except Exception:
            english = cleaned

    # Normaliser quelques termes courants mal traduits pour la recherche académique
    en = " ".join((english or cleaned).split())
    folded_src = _fold(raw)
    extras = []
    if re.search(r"\b(?:llm|modele[s]? de langage|modele[s]? de pointe|gpt|llama|claude)\b", folded_src):
        extras.append("large language model")
    if "cerveau" in folded_src and "brain" not in en.lower():
        extras.append("brain")
    if "psychanalys" in folded_src and "psychoanalysis" not in en.lower():
        extras.append("psychoanalysis efficacy")
    if "quantique" in folded_src and "quantum" not in en.lower():
        extras.append("quantum mechanics")

    # Réduire aux 12 mots les plus informatifs
    tokens = re.findall(r"[A-Za-z0-9'-]{3,}", en)
    stop_en = {
        "the", "and", "for", "that", "this", "with", "from", "into", "about", "what",
        "does", "are", "not", "but", "can", "how", "why", "even", "just", "very",
        "only", "more", "than", "their", "they", "them", "its", "your", "our", "have",
        "has", "had", "was", "were", "will", "would", "could", "should", "because",
        "whereas", "while", "really", "actually", "according", "framework",
    }
    picked = []
    for tok in tokens:
        low = tok.lower()
        if low in stop_en or low in {p.lower() for p in picked}:
            continue
        picked.append(tok)
        if len(picked) >= 10:
            break
    query = " ".join(extras + picked).strip()
    if len(query) < 6:
        fallback_words = [w for w in re.findall(r"[^\W\d_]{4,}", _fold(cleaned)) if not _FILLER_RE.fullmatch(w)]
        query = " ".join(fallback_words[:8]) or cleaned[:120]
    return query[:180]


def _query_openalex(query: str, getter, limit: int = 3) -> list[dict]:
    url = (
        "https://api.openalex.org/works"
        f"?search={quote(query)}"
        f"&per-page={max(limit + 2, 5)}"
        "&filter=has_abstract:true,from_publication_date:2015-01-01"
        "&sort=relevance_score:desc"
    )
    resp = getter(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=HTTP_TIMEOUT)
    if getattr(resp, "status_code", 0) != 200:
        return []
    data = resp.json() if callable(getattr(resp, "json", None)) else json.loads(resp.text)
    papers = []
    for w in data.get("results") or ():
        title = " ".join((w.get("title") or "").split())
        year = w.get("publication_year")
        doi = (w.get("doi") or "").strip()
        primary = (w.get("primary_location") or {})
        landing = (primary.get("landing_page_url") or "").strip()
        paper_url = doi if doi.startswith("https://") else (landing if landing.startswith("https://") else "")
        if not title or not paper_url:
            continue
        authorships = w.get("authorships") or []
        names = [
            (a.get("author") or {}).get("display_name", "").strip()
            for a in authorships[:3]
            if (a.get("author") or {}).get("display_name")
        ]
        authors = ", ".join(names) + (" et al." if len(authorships) > 3 else "")
        venue = ((primary.get("source") or {}).get("display_name") or "").strip()
        abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))
        papers.append(
            {
                "title": title[:220],
                "authors": authors or "Auteur non renseigné",
                "year": int(year) if year else None,
                "venue": venue[:120],
                "url": paper_url,
                "doi": doi.replace("https://doi.org/", "") if "doi.org/" in doi else "",
                "cited_by": int(w.get("cited_by_count") or 0),
                "abstract": abstract,
                "provider": "OpenAlex",
            }
        )
        if len(papers) >= limit:
            break
    return papers


def _query_europe_pmc(query: str, getter, limit: int = 2) -> list[dict]:
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        f"?query={quote(query)}&format=json&resultType=core&pageSize={max(limit + 1, 3)}"
    )
    resp = getter(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=HTTP_TIMEOUT)
    if getattr(resp, "status_code", 0) != 200:
        return []
    data = resp.json() if callable(getattr(resp, "json", None)) else json.loads(resp.text)
    papers = []
    for w in ((data.get("resultList") or {}).get("result") or ()):
        title = _clean_html_text(w.get("title") or "", max_chars=220).rstrip(".")
        doi = (w.get("doi") or "").strip()
        pmid = (w.get("pmid") or "").strip()
        paper_url = (
            f"https://doi.org/{doi}"
            if doi
            else (f"https://europepmc.org/article/MED/{pmid}" if pmid else "")
        )
        if not title or not paper_url:
            continue
        authors = " ".join((w.get("authorString") or "").split())[:120] or "Auteur non renseigné"
        year_raw = str(w.get("pubYear") or "")
        year = int(year_raw) if year_raw.isdigit() else None
        venue = " ".join((w.get("journalTitle") or "").split())[:120]
        abstract = _clean_html_text(w.get("abstractText") or "")
        papers.append(
            {
                "title": title,
                "authors": authors,
                "year": year,
                "venue": venue,
                "url": paper_url,
                "doi": doi,
                "cited_by": int(w.get("citedByCount") or 0),
                "abstract": abstract,
                "provider": "Europe PMC",
            }
        )
        if len(papers) >= limit:
            break
    return papers


@lru_cache(maxsize=64)
def _cached_fetch(query: str, include_biomed: bool, limit: int) -> tuple[dict, ...]:
    import requests

    getter = requests.get
    return tuple(_fetch_merged(query, include_biomed, limit, getter))


def _fetch_merged(query: str, include_biomed: bool, limit: int, getter) -> list[dict]:
    papers: list[dict] = []
    seen: set[str] = set()

    def add(items: list[dict]):
        for item in items:
            key = (item.get("doi") or _fold(item.get("title", ""))[:60]).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            papers.append(item)
            if len(papers) >= limit:
                return

    try:
        add(_query_openalex(query, getter, limit=limit))
    except Exception:
        pass
    if include_biomed and len(papers) < limit:
        try:
            add(_query_europe_pmc(query, getter, limit=limit - len(papers)))
        except Exception:
            pass
    elif not papers:
        try:
            add(_query_europe_pmc(query, getter, limit=limit))
        except Exception:
            pass

    numbered = []
    for idx, p in enumerate(papers[:limit], 1):
        copy = dict(p)
        copy["id"] = f"ext{idx}"
        numbered.append(copy)
    return numbered


def search_academic_papers(
    message: str,
    turns: list[dict] | None = None,
    *,
    limit: int = 3,
    http_get=None,
    translator=None,
) -> list[dict]:
    """Interroge OpenAlex (et Europe PMC si biomédical/repli) et renvoie jusqu’à `limit` études vérifiées."""
    query = build_academic_query(message, turns, translator=translator)
    if len(query) < 4:
        return []
    include_biomed = bool(_BIOMED_RE.search(_fold(f"{message} {query}")))
    if http_get is None:
        try:
            return [dict(p) for p in _cached_fetch(query, include_biomed, limit)]
        except Exception:
            return []
    return _fetch_merged(query, include_biomed, limit, http_get)
