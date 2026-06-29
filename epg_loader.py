# ============================================================
# EPG_LOADER — Chargement et gestion du cache EPG
# ============================================================

import gzip
from collections import defaultdict
from datetime import datetime
from io import BytesIO
import xml.etree.ElementTree as ET

from config import EPG_SOURCES, CACHE_TTL
from logger_utils import logger

_cache = {
    "fr": {"tree": None, "loaded_at": 0, "channels": {}, "index": {}},
    "gb": {"tree": None, "loaded_at": 0, "channels": {}, "index": {}},
}
_cache_prev = {
    "fr": {"titles": set()},
    "gb": {"titles": set()},
}

async def load_epg(country: str) -> ET.Element:
    """Charge l'EPG pour un pays (avec cache). Async pour ne pas bloquer l'event loop."""
    now   = datetime.now().timestamp()
    entry = _cache[country]
    src   = EPG_SOURCES[country]

    if entry["tree"] is None or (now - entry["loaded_at"]) > CACHE_TTL:
        from utils import clean_title

        if entry["tree"] is not None:
            _cache_prev[country]["titles"] = {
                clean_title(p.findtext("title", default=""))
                for p in entry["tree"].findall("programme")
            }

        logger.info(f"Téléchargement EPG {country.upper()}…")
        try:
            import httpx
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await client.get(src["url"], timeout=30)
            r.raise_for_status()
            root = ET.parse(BytesIO(gzip.decompress(r.content))).getroot()
            entry["tree"]     = root
            entry["channels"] = {
                ch.get("id", ""): ch.findtext("display-name", default=ch.get("id", ""))
                for ch in root.findall("channel")
            }
            idx = defaultdict(list)
            for prog in root.findall("programme"):
                idx[prog.get("channel", "")].append(prog)
            entry["index"]     = dict(idx)
            entry["loaded_at"] = now
            logger.info(f"EPG {country.upper()} chargé.")
        except Exception as e:
            logger.error(f"Échec chargement EPG {country.upper()} : {e}")
            raise

    return entry["tree"]

def get_cache(country: str = None):
    """Retourne le cache (ou tout le cache si country=None)."""
    return _cache[country] if country else _cache

def get_cache_prev(country: str = None):
    """Retourne le snapshot précédent du cache."""
    return _cache_prev[country] if country else _cache_prev

def reset_cache():
    """Réinitialise complètement le cache EPG."""
    for country in _cache:
        _cache[country] = {"tree": None, "loaded_at": 0, "channels": {}, "index": {}}
        _cache_prev[country]["titles"] = set()

def get_epg_channels(country: str) -> dict:
    """Retourne le dict {channel_id → display-name} du cache."""
    return _cache[country].get("channels", {})

def get_epg_index(country: str) -> dict:
    """Retourne l'index {channel_id → [programme_elem]} du cache."""
    return _cache[country].get("index", {})
