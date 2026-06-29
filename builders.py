# ============================================================
# BUILDERS — Construction des résultats filtrés EPG
# ============================================================

from datetime import datetime, timedelta, timezone
from collections import defaultdict
import xml.etree.ElementTree as ET

from config import TZ_PARIS, CH_TNT_FR, CH_SPORT_FR, CH_TNT_BY_COUNTRY, CH_SPORT_BY_COUNTRY
from utils import parse_xmltv_time, get_channels, clean_title, clean_desc, get_categories, duree_str, is_sport_filler, is_epg_placeholder
from utils import now_paris

def _time_window(day_offset: int, hour_start: int = 19, hour_end: int = 0):
    """Crée une fenêtre temps (jour + heures)."""
    base     = now_paris() + timedelta(days=day_offset)
    start_dt = base.replace(hour=hour_start, minute=0, second=0, microsecond=0)
    end_dt   = base.replace(hour=hour_end,   minute=0, second=0, microsecond=0) + timedelta(
        days=(1 if hour_end <= hour_start else 0)
    )
    jour_label = base.strftime("%A %d %B").capitalize()
    return start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc), jour_label

def build_soir_results(root, day_offset: int):
    """Construit les résultats pour soirée TNT FR (19h-00h)."""
    channels                       = get_channels(root)
    now_utc                        = datetime.now(tz=timezone.utc)
    start_utc, end_utc, jour_label = _time_window(day_offset, 19, 0)
    ch_tnt_set                     = set(CH_TNT_FR)
    results                        = []
    
    for prog in root.findall("programme"):
        cid = prog.get("channel", "")
        if cid not in ch_tnt_set:
            continue
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

def build_type_results(root, day_offset: int, filter_fn, min_duration: int = 0, ch_set: set = None):
    """Construit les résultats avec filtre personnalisé (films, séries, etc.)."""
    channels                       = get_channels(root)
    now_utc                        = datetime.now(tz=timezone.utc)
    start_utc, end_utc, jour_label = _time_window(day_offset, 19, 0)
    search_set                     = ch_set if ch_set is not None else set(CH_TNT_FR)
    results                        = []
    
    for prog in root.findall("programme"):
        cid = prog.get("channel", "")
        if cid not in search_set:
            continue
        if filter_fn is not None and not filter_fn(prog):
            continue
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
                "channel": channels.get(cid, cid).replace("FR - ", "").strip(),
                "ch_id": cid,
                "cats": get_categories(prog), "duree": duree_str(start, stop),
                "new": prog.find("new") is not None,
            })
    
    return results, jour_label, now_utc

def build_sport_results(root, day_offset: int, ch_list: list = None):
    """Construit les résultats sport avec détection fillers."""
    if ch_list is None:
        ch_list = CH_SPORT_FR
    
    channels                       = get_channels(root)
    now_utc                        = datetime.now(tz=timezone.utc)
    start_utc, end_utc, jour_label = _time_window(day_offset, 6, 0)
    sport_set                      = set(ch_list)
    results                        = []
    
    for prog in root.findall("programme"):
        cid = prog.get("channel", "")
        if cid not in sport_set:
            continue
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
                "channel": channels.get(cid, cid).replace("FR - ", "").strip(),
                "ch_id": cid,
                "cats": get_categories(prog), "duree": duree_str(start, stop),
                "new": prog.find("new") is not None,
                "placeholder": is_epg_placeholder(title, desc),
            })
    
    return results, jour_label, now_utc
