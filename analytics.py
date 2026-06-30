# ============================================================
# ANALYTICS — Logiques pures EPG (doublons, tendances, recherche)
# Module sans dépendance Telegram → testable isolément.
# ============================================================

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
