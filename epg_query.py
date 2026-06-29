# ============================================================
# EPG_QUERY — Requêtes sur l'EPG (filtrage, extraction)
# ============================================================

from datetime import datetime, timedelta, timezone
from config import TZ_PARIS
from utils import parse_xmltv_time, get_channels, clean_title, clean_desc, get_categories, duree_str

def get_programmes_for_channel(root, channel_id: str, limit: int = 8) -> list:
    """Extrait les prochains programmes d'une chaîne."""
    now     = datetime.now(tz=timezone.utc)
    results = []
    for prog in root.findall("programme"):
        if prog.get("channel") != channel_id:
            continue
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

def format_programme(prog: dict) -> str:
    """Formate un programme pour affichage."""
    from utils import sanitize_md
    
    now      = datetime.now(tz=timezone.utc)
    h_start  = prog["start"].astimezone(TZ_PARIS).strftime("%H:%M")
    h_stop   = prog["stop"].astimezone(TZ_PARIS).strftime("%H:%M")
    en_cours = "🔴 " if prog["start"] <= now < prog["stop"] else ""
    new_tag  = " 🆕" if prog.get("new") else ""
    title    = sanitize_md(prog["title"])
    texte    = f"{en_cours}🕐 *{h_start}–{h_stop}*  {title}{new_tag}\n"
    if prog.get("cat"):
        texte += f"   📂 _{sanitize_md(prog['cat'])}_\n"
    if prog.get("desc"):
        texte += f"   📝 {sanitize_md(prog['desc'])}\n"
    return texte
