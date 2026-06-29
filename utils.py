# ============================================================
# UTILS — Fonctions utilitaires (parsing, nettoyage, etc.)
# ============================================================

import re
import unicodedata
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from config import TZ_PARIS, _SPORT_TITLES_BLACKLIST, _NOUVEAUTES_BLACKLIST, _GENERIC_SPORT_WORDS, _EPG_PLACEHOLDER_DESCS

def parse_xmltv_time(s: str) -> datetime:
    """Parse un timestamp XMLTV (format: YYYYMMDDHHMMSS +HHMM)."""
    dt_str, tz_str = s.strip().split(" ")
    dt     = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
    sign   = 1 if tz_str[0] == "+" else -1
    offset = timedelta(hours=int(tz_str[1:3]), minutes=int(tz_str[3:5]))
    return dt.replace(tzinfo=timezone(sign * offset))

def now_paris() -> datetime:
    """Retourne l'heure actuelle à Paris."""
    return datetime.now(tz=TZ_PARIS)

def get_channels(root: ET.Element) -> dict:
    """Extrait le dictionnaire des chaînes (id -> display-name)."""
    return {
        ch.get("id", ""): ch.findtext("display-name", default=ch.get("id", ""))
        for ch in root.findall("channel")
    }

def clean_name(name: str) -> str:
    """Nettoie le nom d'une chaîne (supprime préfixe 'FR - ')."""
    return name.replace("FR - ", "").strip()

def clean_title(title: str) -> str:
    """Nettoie le titre d'un programme (supprime tags ᴺᵉʷ, ajoute espaces)."""
    title = title.replace(" ᴺᵉʷ", "").replace("ᴺᵉʷ", "").strip()
    return re.sub(r"(?<! )(\d{4})$", r" \1", title)

def _normalize(s: str) -> str:
    """Normalise une chaîne pour recherche (minuscule, no accents, no special chars)."""
    return re.sub(r'[^\w]', '', s.lower())

def _strip_accents(s: str) -> str:
    """Supprime les accents d'une chaîne."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

def sanitize_md(text: str) -> str:
    """Échappe les caractères spéciaux Markdown."""
    for ch in ('*', '_', '`', '['):
        text = text.replace(ch, f'\\{ch}')
    return text

def truncate(text: str, max_len: int = 120) -> str:
    """Tronque un texte à une longueur maximale."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(' ', 1)[0].rstrip('.,;:') + "…"

def clean_desc(desc: str, title: str, max_len: int = 120) -> str:
    """Nettoie une description (supprime les doublons avec title, tronque)."""
    desc = desc.strip()
    if len(desc) < 15:
        return ""
    if desc.lower().startswith(title.lower()[:20]):
        return ""
    lines = desc.splitlines()
    if lines and _normalize(lines[-1]) == _normalize(title):
        lines = lines[:-1]
    desc = "\n".join(lines).strip()
    if len(desc) < 15:
        return ""
    return truncate(desc, max_len)

def get_categories(prog_elem) -> str:
    """Extrait les catégories d'un programme."""
    cats = [c.text for c in prog_elem.findall("category") if c.text]
    return " · ".join(cats) if cats else ""

def duree_str(start: datetime, stop: datetime) -> str:
    """Formate la durée entre deux datetimes."""
    mins = max(0, int((stop - start).total_seconds() // 60))
    return f"{mins // 60}h{mins % 60:02d}" if mins >= 60 else f"{mins}min"

# Blacklists normalisées (pré-calculées pour performance)
_BLACKLIST_NORMALIZED     = [_strip_accents(b) for b in _SPORT_TITLES_BLACKLIST]
_NOUVEAUTES_BL_NORMALIZED = [_strip_accents(b) for b in _NOUVEAUTES_BLACKLIST]

def is_sport_filler(title: str) -> bool:
    """Détecte si un titre est un filler sport."""
    t = _strip_accents(title.lower().strip())
    return any(t.startswith(b) for b in _BLACKLIST_NORMALIZED)

def is_nouveautes_filler(title: str) -> bool:
    """Détecte si un titre est un filler (news, météo, etc.)."""
    t = _strip_accents(title.lower().strip())
    return any(t.startswith(b) for b in _NOUVEAUTES_BL_NORMALIZED)

def is_epg_placeholder(title: str, desc: str) -> bool:
    """Détecte si un programme est un placeholder EPG."""
    if ":" in title:
        return False
    t = _strip_accents(title.lower().strip())
    if t in _GENERIC_SPORT_WORDS:
        return True
    if desc:
        d = _strip_accents(desc.lower())
        if any(d.startswith(p) for p in _EPG_PLACEHOLDER_DESCS):
            return True
    return False

_RE_EPISODE  = re.compile(r'\bS\d+\s*E\d+\b', re.IGNORECASE)
_RE_EPISODE2 = re.compile(r'\bsaison\s*\d+\b', re.IGNORECASE)

def _has_episode(prog_elem) -> bool:
    """Détecte si un programme contient des infos d'épisode."""
    if prog_elem.find("episode-num") is not None:
        return True
    title = prog_elem.findtext("title", default="")
    desc  = prog_elem.findtext("desc",  default="")
    return bool(
        _RE_EPISODE.search(title) or _RE_EPISODE.search(desc) or
        _RE_EPISODE2.search(title)
    )

def is_serie(prog_elem) -> bool:
    """Détecte si un programme est une série."""
    cats = [c.text.lower() for c in prog_elem.findall("category") if c.text]
    if any(k in c for c in cats for k in ("série", "serie", "feuilleton", "sitcom", "soap")):
        return True
    return _has_episode(prog_elem)

def is_film(prog_elem) -> bool:
    """Détecte si un programme est un film."""
    cats = [c.text.lower() for c in prog_elem.findall("category") if c.text]
    if any("film" in c or "movie" in c or "cinéma" in c for c in cats):
        return True
    if _has_episode(prog_elem):
        return False
    start_str = prog_elem.get("start", "")
    stop_str  = prog_elem.get("stop",  "")
    if start_str and stop_str:
        try:
            start = parse_xmltv_time(start_str)
            stop  = parse_xmltv_time(stop_str)
            if int((stop - start).total_seconds() // 60) >= 75:
                return True
        except ValueError:
            pass
    return False

def get_ch_id_by_name(name: str) -> str | None:
    """Trouve le channel ID à partir du nom (aliases)."""
    from config import CH_ALIASES
    return CH_ALIASES.get(name.lower().strip())
