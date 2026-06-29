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
    name_low = name.lower().strip()
    aliases  = {
        "tf1": "TF1.fr", "france 2": "France2.fr", "france2": "France2.fr",
        "f2": "France2.fr", "france 3": "France3.fr", "france3": "France3.fr",
        "f3": "France3.fr", "france 5": "France5.fr", "france5": "France5.fr",
        "f5": "France5.fr", "m6": "M6.fr", "arte": "Arte.fr", "c8": "C8.fr",
        "w9": "W9.fr", "tmc": "TMC.fr", "tfx": "TFX.fr",
        "nrj12": "NRJ12.fr", "nrj 12": "NRJ12.fr", "lcp": "LCP.fr",
        "france 4": "France4.fr", "france4": "France4.fr", "f4": "France4.fr",
        "bfm": "BFMTV.fr", "bfmtv": "BFMTV.fr", "cnews": "CNews.fr",
        "cstar": "CStar.fr", "gulli": "Gulli.fr",
        "tf1sf": "TF1Series-Films.fr", "tf1 séries": "TF1Series-Films.fr",
        "l'equipe": "L'Equipe.fr", "lequipe": "L'Equipe.fr",
        "6ter": "6ter.fr", "rmc story": "RMCSTORY.fr", "rmcstory": "RMCSTORY.fr",
        "rmc découverte": "RMCDecouverte.fr", "rmcd": "RMCDecouverte.fr",
        "chérie 25": "Cherie25.fr", "cherie25": "Cherie25.fr", "lci": "LCI.fr",
        "france info": "franceinfo.fr", "franceinfo": "franceinfo.fr",
        "paris première": "ParisPremiere.fr", "paris1ere": "ParisPremiere.fr",
        "rtl9": "RTL9.fr", "eurosport": "EUROSPORT1.fr",
        "eurosport 1": "EUROSPORT1.fr", "eurosport1": "EUROSPORT1.fr",
        "eurosport 2": "EUROSPORT2.fr", "eurosport2": "EUROSPORT2.fr",
        "bein 1": "beINSPORTS1.fr", "bein1": "beINSPORTS1.fr",
        "bein 2": "beINSPORTS2.fr", "bein2": "beINSPORTS2.fr",
        "bein 3": "beINSPORTS3.fr", "bein3": "beINSPORTS3.fr",
        "rmc sport": "RMCSport1.fr", "rmc sport 1": "RMCSport1.fr",
        "rmc sport 2": "RMCSport2.fr", "kombat": "KombatSport.fr",
        "equidia": "Equidia.fr", "ol tv": "OLTV.fr", "oltv": "OLTV.fr",
        "golfe tv": "GolfeTV.fr", "golfe": "GolfeTV.fr",
        "bbc1": "BBC1.uk", "bbc 1": "BBC1.uk", "bbc2": "BBC2.uk", "bbc 2": "BBC2.uk",
        "itv": "ITV.uk", "channel 4": "Channel4.uk", "channel4": "Channel4.uk",
        "channel 5": "Channel5.uk", "channel5": "Channel5.uk",
        "e4": "E4.uk", "film4": "Film4.uk", "dave": "Dave.uk",
        "sky sports": "SkySportsMainEvent.uk", "sky f1": "SkySportsF1.uk",
        "tnt sports": "TNTSports1.uk", "tnt sports 1": "TNTSports1.uk",
        "tnt sports 2": "TNTSports2.uk",
    }
    return aliases.get(name_low)
