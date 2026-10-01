# ============================================================
# ANALYTICS — Logiques pures EPG (doublons, tendances, recherche)
# Module sans dépendance Telegram → testable isolément.
# ============================================================

import difflib
from collections import Counter, defaultdict

from config import TZ_PARIS
from utils import (
    parse_xmltv_time, clean_title, clean_desc, clean_name,
    _normalize, _strip_accents,
)

def compute_doublons(progs, channels: dict, now_utc, end_utc, tz=TZ_PARIS):
    """Regroupe les titres diffusés sur >1 chaîne dans la fenêtre [now_utc, end_utc).

    Retourne une liste de (titre, [labels chaîne]) triée par nombre de chaînes décroissant.
    NB : un même titre deux fois sur la même chaîne compte pour 2 (comportement préservé).
    """
    title_map = defaultdict(list)
    for prog in progs:
        cid = prog.get("channel", "")
        try:
            start = parse_xmltv_time(prog.get("start", ""))
        except ValueError:
            continue
        if not (now_utc <= start < end_utc):
            continue
        title = clean_title(prog.findtext("title", default=""))
        nom   = clean_name(channels.get(cid, cid))
        h     = start.astimezone(tz).strftime("%H:%M")
        title_map[title].append(f"{nom} ({h})")
    doublons_list = [(t, chs) for t, chs in title_map.items() if len(chs) > 1]
    doublons_list.sort(key=lambda x: -len(x[1]))
    return doublons_list

def compute_trending(progs, now_utc, end_utc, top_n=15, min_count=2):
    """Compte les titres qui chevauchent la fenêtre [now_utc, end_utc).

    Retourne le top `top_n` (most_common) puis filtre `n >= min_count`.
    NB : le cap top_n est appliqué AVANT le filtre min_count (comportement préservé).
    """
    counter = Counter()
    for prog in progs:
        try:
            start = parse_xmltv_time(prog.get("start", ""))
            stop  = parse_xmltv_time(prog.get("stop",  ""))
        except ValueError:
            continue
        if start >= end_utc or stop <= now_utc:
            continue
        title = clean_title(prog.findtext("title", default=""))
        if title:
            counter[title] += 1
    return [(t, n) for t, n in counter.most_common(top_n) if n >= min_count]

def search_programmes(progs, channels: dict, mot: str):
    """Filtre les programmes dont le titre ou la description contient `mot` (normalisé).

    Retourne une liste de dicts résultat triée par heure de début.
    """
    mot_norm = _normalize(_strip_accents(mot))
    results  = []
    for prog in progs:
        cid   = prog.get("channel", "")
        title = clean_title(prog.findtext("title", default=""))
        desc  = prog.findtext("desc") or ""
        if mot_norm not in _normalize(_strip_accents(title)) and mot_norm not in _normalize(_strip_accents(desc)):
            continue
        try:
            start = parse_xmltv_time(prog.get("start", ""))
            stop  = parse_xmltv_time(prog.get("stop",  ""))
        except ValueError:
            continue
        results.append({
            "start": start, "stop": stop, "title": title,
            "desc": clean_desc(desc, title),
            "channel": clean_name(channels.get(cid, cid)), "ch_id": cid,
        })
    results.sort(key=lambda x: x["start"])
    return results


def paginate(items, page, page_size):
    """Découpe `items` pour la page demandée.

    Retourne (items_page, total, has_prev, has_next).
    has_next indique l'existence d'une page suivante non vide.
    """
    total      = len(items)
    start      = page * page_size
    page_items = items[start:start + page_size]
    has_prev   = page > 0
    has_next   = start + page_size < total
    return page_items, total, has_prev, has_next


# ──────────────────────────────────────────
# CATÉGORIES (/categorie)
# ──────────────────────────────────────────
def _norm_cat(s: str) -> str:
    """Normalise un libellé/requête de catégorie (minuscule, sans accents ni ponctuation)."""
    return _normalize(_strip_accents(s or ""))

def category_matches(prog, query: str) -> bool:
    """True si une des <category> du programme contient `query` (partiel, insensible casse/accents)."""
    q = _norm_cat(query)
    if not q:
        return False
    return any(q in _norm_cat(c.text) for c in prog.findall("category") if c.text)

def make_category_filter(query: str):
    """Retourne un filter_fn(prog) utilisable par build_type_results."""
    return lambda prog: category_matches(prog, query)

def list_categories(progs, start_utc, end_utc):
    """Liste les catégories des programmes qui chevauchent [start_utc, end_utc).

    Dédoublonnage insensible casse/accents (premier libellé rencontré conservé).
    Retourne [(libellé, nb_programmes)] trié par nombre décroissant puis libellé.
    """
    counter = Counter()
    labels  = {}
    for prog in progs:
        try:
            start = parse_xmltv_time(prog.get("start", ""))
            stop  = parse_xmltv_time(prog.get("stop",  ""))
        except ValueError:
            continue
        if start >= end_utc or stop <= start_utc:
            continue
        seen = set()
        for c in prog.findall("category"):
            key = _norm_cat(c.text)
            if not key or key in seen:
                continue
            seen.add(key)
            labels.setdefault(key, c.text.strip())
            counter[key] += 1
    return sorted(((labels[k], n) for k, n in counter.items()), key=lambda x: (-x[1], x[0].lower()))

def matching_categories(query: str, labels) -> list:
    """Libellés contenant `query` (partiel, insensible casse/accents), dans l'ordre d'entrée."""
    q = _norm_cat(query)
    if not q:
        return []
    return [label for label in labels if q in _norm_cat(label)]

def suggest_categories(query: str, labels, n: int = 5, cutoff: float = 0.5) -> list:
    """Suggestions fuzzy (difflib) de libellés de catégories proches de `query`."""
    by_norm = {}
    for label in labels:
        by_norm.setdefault(_norm_cat(label), label)
    matches = difflib.get_close_matches(_norm_cat(query), list(by_norm), n=n, cutoff=cutoff)
    return [by_norm[m] for m in matches]


# ──────────────────────────────────────────
# JOURNÉE D'UNE CHAÎNE (/semaine)
# ──────────────────────────────────────────
def filter_day_programmes(progs, start_utc, end_utc, now_utc=None):
    """Programmes d'une journée [start_utc, end_utc) : débutant dans la fenêtre, ou en cours à son ouverture.

    Si `now_utc` est fourni, les programmes déjà terminés sont écartés.
    Retourne une liste de dicts triée par heure de début.
    """
    results = []
    for prog in progs:
        try:
            start = parse_xmltv_time(prog.get("start", ""))
            stop  = parse_xmltv_time(prog.get("stop",  ""))
        except ValueError:
            continue
        if not (start_utc <= start < end_utc or start < start_utc < stop):
            continue
        if now_utc is not None and stop <= now_utc:
            continue
        title = clean_title(prog.findtext("title", default="Inconnu"))
        desc  = prog.findtext("desc") or ""
        results.append({
            "start": start, "stop": stop, "title": title,
            "desc": clean_desc(desc, title),
            "new": prog.find("new") is not None,
        })
    results.sort(key=lambda x: x["start"])
    return results
