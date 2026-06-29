# ============================================================
# BUILDERS — Construction des résultats filtrés EPG
# ============================================================

from datetime import datetime, timedelta, timezone
from collections import defaultdict
import xml.etree.ElementTree as ET

from config import TZ_PARIS, CH_TNT_FR, CH_SPORT_FR, CH_TNT_BY_COUNTRY, CH_SPORT_BY_COUNTRY
from utils import (
    parse_xmltv_time, get_channels, clean_title, clean_desc, get_categories,
    duree_str, is_sport_filler, is_epg_placeholder, is_nouveautes_filler, clean_name, now_paris
)

def _get_channels(root, country: str) -> dict:
    """Retourne le dict channels depuis le cache ou reconstruit depuis root."""
    from epg_loader import get_epg_channels
    cached = get_epg_channels(country)
    return cached if cached else get_channels(root)

def _iter_progs(root, cid_set: set, country: str):
    """Itère les programmes des chaînes demandées via l'index cache (ou root.findall en fallback)."""
    from epg_loader import get_epg_index
    index = get_epg_index(country)
    if index:
        for cid in cid_set:
            yield from index.get(cid, [])
    else:
        for prog in root.findall("programme"):
            if prog.get("channel", "") in cid_set:
                yield prog

def _time_window(day_offset: int, hour_start: int = 19, hour_end: int = 0):
    """Crée une fenêtre temps (jour + heures)."""
    base     = now_paris() + timedelta(days=day_offset)
    start_dt = base.replace(hour=hour_start, minute=0, second=0, microsecond=0)
    end_dt   = base.replace(hour=hour_end,   minute=0, second=0, microsecond=0) + timedelta(
        days=(1 if hour_end <= hour_start else 0)
    )
    jour_label = base.strftime("%A %d %B").capitalize()
    return start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc), jour_label

def build_soir_results(root, day_offset: int, country: str = "fr"):
    """Construit les résultats pour soirée TNT FR (19h-00h)."""
    channels                       = _get_channels(root, country)
    now_utc                        = datetime.now(tz=timezone.utc)
    start_utc, end_utc, jour_label = _time_window(day_offset, 19, 0)
    ch_tnt_set                     = set(CH_TNT_FR)
    results                        = []

    for prog in _iter_progs(root, ch_tnt_set, country):
        cid       = prog.get("channel", "")
        start_str = prog.get("start", "")
        stop_str  = prog.get("stop",  "")
        if not start_str or not stop_str:
            continue
        try:
            start = parse_xmltv_time(start_str)
            stop  = parse_xmltv_time(stop_str)
        except ValueError:
            continue
        if start_utc <= start < end_utc:
            title = clean_title(prog.findtext("title", default="Inconnu"))
            desc  = prog.findtext("desc") or ""
            results.append({
                "start": start, "stop": stop, "title": title,
                "desc": clean_desc(desc, title), "channel": channels.get(cid, cid),
                "ch_id": cid, "new": prog.find("new") is not None,
            })

    return results, channels, jour_label, now_utc

def build_type_results(root, day_offset: int, filter_fn, min_duration: int = 0, ch_set: set = None, country: str = "fr"):
    """Construit les résultats avec filtre personnalisé (films, séries, etc.)."""
    channels                       = _get_channels(root, country)
    now_utc                        = datetime.now(tz=timezone.utc)
    start_utc, end_utc, jour_label = _time_window(day_offset, 19, 0)
    search_set                     = ch_set if ch_set is not None else set(CH_TNT_FR)
    results                        = []

    for prog in _iter_progs(root, search_set, country):
        if filter_fn is not None and not filter_fn(prog):
            continue
        cid       = prog.get("channel", "")
        start_str = prog.get("start", "")
        stop_str  = prog.get("stop",  "")
        if not start_str or not stop_str:
            continue
        try:
            start = parse_xmltv_time(start_str)
            stop  = parse_xmltv_time(stop_str)
        except ValueError:
            continue
        if start_utc <= start < end_utc:
            mins = int((stop - start).total_seconds() // 60)
            if mins < min_duration:
                continue
            title = clean_title(prog.findtext("title", default="Inconnu"))
            desc  = prog.findtext("desc") or ""
            results.append({
                "start": start, "stop": stop, "title": title,
                "desc": clean_desc(desc, title),
                "channel": clean_name(channels.get(cid, cid)),
                "ch_id": cid,
                "cats": get_categories(prog), "duree": duree_str(start, stop),
                "new": prog.find("new") is not None,
            })

    return results, jour_label, now_utc

def build_sport_results(root, day_offset: int, ch_list: list = None, country: str = "fr"):
    """Construit les résultats sport avec détection fillers."""
    if ch_list is None:
        ch_list = CH_SPORT_FR

    channels                       = _get_channels(root, country)
    now_utc                        = datetime.now(tz=timezone.utc)
    start_utc, end_utc, jour_label = _time_window(day_offset, 6, 0)
    sport_set                      = set(ch_list)
    results                        = []

    for prog in _iter_progs(root, sport_set, country):
        cid       = prog.get("channel", "")
        start_str = prog.get("start", "")
        stop_str  = prog.get("stop",  "")
        if not start_str or not stop_str:
            continue
        try:
            start = parse_xmltv_time(start_str)
            stop  = parse_xmltv_time(stop_str)
        except ValueError:
            continue
        if stop <= now_utc:
            continue
        if start_utc <= start < end_utc:
            title = clean_title(prog.findtext("title", default="Inconnu"))
            if is_sport_filler(title):
                continue
            desc = prog.findtext("desc") or ""
            results.append({
                "start": start, "stop": stop, "title": title,
                "desc": clean_desc(desc, title),
                "channel": clean_name(channels.get(cid, cid)),
                "ch_id": cid,
                "cats": get_categories(prog), "duree": duree_str(start, stop),
                "new": prog.find("new") is not None,
                "placeholder": is_epg_placeholder(title, desc),
            })

    return results, jour_label, now_utc

def build_maintenant_sport(root, filtre: str = None, country: str = "fr") -> list:
    """Construit les résultats sport/live en cours (optionnellement filtré)."""
    now_utc   = datetime.now(tz=timezone.utc)
    channels  = _get_channels(root, country)
    ch_order  = {ch: i for i, ch in enumerate(CH_SPORT_FR)}
    sport_set = set(CH_SPORT_FR)
    if filtre == "canal":
        sport_set = {cid for cid in sport_set if cid.startswith("CANAL+") or cid == "C+SPORT.fr"}
    results   = []
    for prog in _iter_progs(root, sport_set, country):
        cid = prog.get("channel", "")
        try:
            start = parse_xmltv_time(prog.get("start", ""))
            stop  = parse_xmltv_time(prog.get("stop",  ""))
        except ValueError:
            continue
        if not (start <= now_utc < stop):
            continue
        title = clean_title(prog.findtext("title", default=""))
        if is_sport_filler(title):
            continue
        desc = prog.findtext("desc") or ""
        results.append({
            "start": start, "stop": stop, "title": title,
            "desc": clean_desc(desc, title),
            "channel": clean_name(channels.get(cid, cid)), "ch_id": cid,
            "duree_reste": duree_str(now_utc, stop),
            "placeholder": is_epg_placeholder(title, desc),
        })
    results.sort(key=lambda x: ch_order.get(x["ch_id"], 99))
    return results

def build_nouveautes_tnt(root, day_offset: int, country: str = "fr"):
    """Construit les inédits TNT FR pour une soirée (19h-00h)."""
    channels                       = _get_channels(root, country)
    now_utc                        = datetime.now(tz=timezone.utc)
    start_utc, end_utc, jour_label = _time_window(day_offset, 19, 0)
    ch_set                         = set(CH_TNT_FR)
    results                        = []
    for prog in _iter_progs(root, ch_set, country):
        if prog.find("new") is None:
            continue
        cid = prog.get("channel", "")
        try:
            start = parse_xmltv_time(prog.get("start", ""))
            stop  = parse_xmltv_time(prog.get("stop",  ""))
        except ValueError:
            continue
        if not (start_utc <= start < end_utc):
            continue
        title = clean_title(prog.findtext("title", default=""))
        if is_nouveautes_filler(title):
            continue
        desc = prog.findtext("desc") or ""
        results.append({
            "start": start, "stop": stop, "title": title,
            "desc": clean_desc(desc, title),
            "channel": clean_name(channels.get(cid, cid)),
            "ch_id": cid, "cats": get_categories(prog),
            "duree": duree_str(start, stop), "new": True, "placeholder": False,
        })
    return results, jour_label, now_utc

def build_prime_results(root, day_offset: int, ch_set: set = None, country: str = "fr"):
    """Construit les résultats prime time (20h-22h30) TNT FR."""
    channels   = _get_channels(root, country)
    now_utc    = datetime.now(tz=timezone.utc)
    base       = now_paris() + timedelta(days=day_offset)
    jour_label = base.strftime("%A %d %B").capitalize()
    start_utc  = base.replace(hour=20, minute=0,  second=0, microsecond=0).astimezone(timezone.utc)
    end_utc    = base.replace(hour=22, minute=30, second=0, microsecond=0).astimezone(timezone.utc)
    search_set = ch_set if ch_set is not None else set(CH_TNT_FR)
    results    = []
    for prog in _iter_progs(root, search_set, country):
        cid       = prog.get("channel", "")
        start_str = prog.get("start", "")
        stop_str  = prog.get("stop",  "")
        if not start_str or not stop_str:
            continue
        try:
            start = parse_xmltv_time(start_str)
            stop  = parse_xmltv_time(stop_str)
        except ValueError:
            continue
        if start_utc <= start < end_utc:
            title = clean_title(prog.findtext("title", default="Inconnu"))
            desc  = prog.findtext("desc") or ""
            results.append({
                "start": start, "stop": stop, "title": title,
                "desc": clean_desc(desc, title),
                "channel": clean_name(channels.get(cid, cid)),
                "ch_id": cid, "cats": get_categories(prog),
                "duree": duree_str(start, stop),
                "new": prog.find("new") is not None,
            })
    return results, jour_label, now_utc

def build_nuit_results(root, day_offset: int, ch_list: list = None, country: str = "fr"):
    """Construit les résultats nuit (00h-06h) TNT FR."""
    if ch_list is None:
        ch_list = CH_TNT_FR
    channels                       = _get_channels(root, country)
    now_utc                        = datetime.now(tz=timezone.utc)
    start_utc, end_utc, jour_label = _time_window(day_offset, 0, 6)
    search_set                     = set(ch_list)
    results                        = []
    for prog in _iter_progs(root, search_set, country):
        cid       = prog.get("channel", "")
        start_str = prog.get("start", "")
        stop_str  = prog.get("stop",  "")
        if not start_str or not stop_str:
            continue
        try:
            start = parse_xmltv_time(start_str)
            stop  = parse_xmltv_time(stop_str)
        except ValueError:
            continue
        if start_utc <= start < end_utc:
            title = clean_title(prog.findtext("title", default="Inconnu"))
            desc  = prog.findtext("desc") or ""
            results.append({
                "start": start, "stop": stop, "title": title,
                "desc": clean_desc(desc, title),
                "channel": clean_name(channels.get(cid, cid)),
                "ch_id": cid, "cats": get_categories(prog),
                "duree": duree_str(start, stop),
                "new": prog.find("new") is not None,
            })
    return results, jour_label, now_utc
