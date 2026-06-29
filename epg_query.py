# ============================================================
# EPG_QUERY — Requêtes sur l'EPG (filtrage, extraction)
# ============================================================

from datetime import datetime, timedelta, timezone
from config import TZ_PARIS
from utils import parse_xmltv_time, get_channels, clean_title, clean_desc, get_categories, duree_str

def get_programmes_for_channel(root, channel_id: str, limit: int = 8, country: str = "fr") -> list:
    """Extrait les prochains programmes d'une chaîne."""
    from epg_loader import get_epg_index
    index = get_epg_index(country)
    candidates = index.get(channel_id, []) if index else [
        p for p in root.findall("programme") if p.get("channel") == channel_id
    ]
    now     = datetime.now(tz=timezone.utc)
    results = []
    for prog in candidates:
        start_str = prog.get("start", "")
        stop_str  = prog.get("stop",  "")
        if not start_str or not stop_str:
            continue
        try:
            stop  = parse_xmltv_time(stop_str)
            start = parse_xmltv_time(start_str)
        except ValueError:
            continue
        if stop > now:
            title = clean_title(prog.findtext("title", default="Inconnu"))
            desc  = prog.findtext("desc") or ""
            results.append({
                "start": start, "stop": stop, "title": title,
                "desc": clean_desc(desc, title), "cat": get_categories(prog),
                "new": prog.find("new") is not None,
            })
        if len(results) >= limit:
            break
    return results

