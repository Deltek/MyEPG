# ============================================================
# TMDB — Enrichissement des films (synopsis, note, année)
# ============================================================
#
# Sans clé TMDB_API_KEY : no-op complet (aucun appel réseau).
# Aucune dépendance Telegram — testable sans le bot.

import asyncio
import difflib
import re
import time

import config
from logger_utils import logger
from utils import truncate, _strip_accents

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_TIMEOUT    = 4.0           # secondes, par requête
TMDB_MAX_FILMS  = 15            # nombre max de lookups par commande
TTL_FOUND       = 24 * 3600     # cache d'un film trouvé
TTL_NOT_FOUND   = 6 * 3600      # cache d'un « pas trouvé »
CACHE_MAX_SIZE  = 2000
MIN_SIMILARITY  = 0.75          # en dessous : résultat jugé non pertinent
MIN_VOTES       = 5             # en dessous : note non affichée
SHORT_DESC_LEN  = 40            # description EPG jugée trop courte en dessous

# {(titre_normalisé, année|None) → (expire_at, données|None)}
_cache: dict = {}


def _api_key() -> str:
    return (getattr(config, "TMDB_API_KEY", "") or "").strip()


def is_enabled() -> bool:
    """True si une clé TMDB est configurée."""
    return bool(_api_key())


def normalize_title(title: str) -> str:
    """Normalise un titre : minuscules, sans accents ni ponctuation, espaces compactés."""
    t = _strip_accents(title or "").lower()
    t = re.sub(r"[^\w]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _year_of(date_str) -> int | None:
    m = re.match(r"\s*(\d{4})", str(date_str or ""))
    return int(m.group(1)) if m else None


def pick_best(results: list, title: str, year: int | None = None) -> dict | None:
    """Choisit le résultat TMDB le plus pertinent (titre proche, année, popularité)."""
    target = normalize_title(title)
    best, best_score = None, 0.0
    for r in results or []:
        names = {normalize_title(r.get("title", "")), normalize_title(r.get("original_title", ""))}
        names.discard("")
        if not names:
            continue
        sim = max(difflib.SequenceMatcher(None, target, n).ratio() for n in names)
        if sim < MIN_SIMILARITY:
            continue
        score = sim * 10
        if target in names:
            score += 5
        r_year = _year_of(r.get("release_date"))
        if year and r_year:
            if r_year == year:
                score += 4
            elif abs(r_year - year) == 1:
                score += 2
        score += min(r.get("vote_count") or 0, 1000) / 1000
        if score > best_score:
            best, best_score = r, score
    return best


def _extract(r: dict) -> dict:
    return {
        "title":        r.get("title") or r.get("original_title") or "",
        "overview":     (r.get("overview") or "").strip(),
        "vote_average": float(r.get("vote_average") or 0),
        "vote_count":   int(r.get("vote_count") or 0),
        "year":         _year_of(r.get("release_date")),
    }


def _cache_get(key):
    entry = _cache.get(key)
    if entry is None:
        return False, None
    expire_at, data = entry
    if expire_at < time.monotonic():
        _cache.pop(key, None)
        return False, None
    return True, data


def _cache_set(key, data):
    if len(_cache) >= CACHE_MAX_SIZE:
        now = time.monotonic()
        for k in [k for k, (exp, _) in _cache.items() if exp < now]:
            _cache.pop(k, None)
        while len(_cache) >= CACHE_MAX_SIZE:
            _cache.pop(next(iter(_cache)))
    ttl = TTL_FOUND if data else TTL_NOT_FOUND
    _cache[key] = (time.monotonic() + ttl, data)


def clear_cache():
    _cache.clear()


def _is_bearer(key: str) -> bool:
    """Jeton « API Read Access Token » (v4, JWT) → header Bearer ; sinon clé v3 en paramètre."""
    return key.startswith("eyJ")


def _make_client():
    import httpx
    key     = _api_key()
    headers = {"Authorization": f"Bearer {key}"} if _is_bearer(key) else {}
    return httpx.AsyncClient(timeout=TMDB_TIMEOUT, headers=headers)


def _safe_err(e: Exception) -> str:
    """Description d'erreur sans URL (la clé v3 y figurerait en query string)."""
    status = getattr(getattr(e, "response", None), "status_code", None)
    return f"{type(e).__name__}" + (f" (HTTP {status})" if status else "")


async def lookup(client, title: str, year: int | None = None) -> dict | None:
    """Recherche un film sur TMDB (avec cache). Toute erreur → None, non mise en cache."""
    key = (normalize_title(title), year)
    if not key[0]:
        return None
    hit, data = _cache_get(key)
    if hit:
        return data
    params = {"query": title, "language": "fr-FR", "include_adult": "false"}
    api_key = _api_key()
    if not _is_bearer(api_key):
        params["api_key"] = api_key
    if year:
        params["year"] = year
    try:
        r = await client.get(TMDB_SEARCH_URL, params=params)
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results and year:
            # L'année EPG est parfois celle de diffusion, pas de sortie : on réessaie sans
            params.pop("year")
            r = await client.get(TMDB_SEARCH_URL, params=params)
            r.raise_for_status()
            results = r.json().get("results") or []
        best = pick_best(results, title, year)
        data = _extract(best) if best else None
    except Exception as e:
        logger.warning(f"TMDB lookup échoué pour « {title} » : {_safe_err(e)}")
        return None
    _cache_set(key, data)
    return data


def merge(prog: dict, data: dict | None, max_len: int = 120) -> dict:
    """Fusionne les données TMDB dans un programme (in place) : note, année, synopsis si besoin."""
    if not data:
        return prog
    if data.get("year"):
        prog["tmdb_year"] = data["year"]
    if data.get("vote_count", 0) >= MIN_VOTES and data.get("vote_average", 0) > 0:
        prog["tmdb_rating"] = round(data["vote_average"], 1)
    overview = data.get("overview") or ""
    if overview and len(prog.get("desc") or "") < SHORT_DESC_LEN:
        prog["desc"] = truncate(overview, max_len)
    return prog


async def enrich_films(progs: list, limit: int = TMDB_MAX_FILMS) -> list:
    """Enrichit (in place) jusqu'à `limit` films via TMDB. No-op sans clé. Ne lève jamais."""
    if not progs or not is_enabled():
        return progs
    try:
        targets = sorted(progs, key=lambda p: p.get("start") or 0)[:limit]
        client  = _make_client()
        async with client:
            datas = await asyncio.gather(
                *(lookup(client, p.get("title", ""), p.get("year")) for p in targets),
                return_exceptions=True,
            )
        for p, d in zip(targets, datas):
            if isinstance(d, dict):
                merge(p, d)
    except Exception as e:
        logger.warning(f"TMDB enrichissement indisponible : {_safe_err(e)}")
    return progs


def tmdb_tag(prog: dict) -> str:
    """Suffixe brut (non échappé) « (1999) ⭐ 7.4 » pour l'affichage, ou chaîne vide."""
    parts = []
    if prog.get("tmdb_year"):
        parts.append(f"({prog['tmdb_year']})")
    if prog.get("tmdb_rating"):
        parts.append(f"⭐ {prog['tmdb_rating']:.1f}")
    return " ".join(parts)
