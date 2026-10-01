# ============================================================
# PERSO — Favoris et alertes par utilisateur (logique pure, sans Telegram)
#   Les "stores" sont les dicts persistants de state.get_user_store(uid).
# ============================================================

import re
from datetime import timedelta

from utils import parse_xmltv_time, clean_title, is_epg_placeholder, is_sport_filler, _strip_accents

MAX_FAVORIS          = 5
MAX_ALERTES          = 10
ALERT_MIN_LEN        = 3
ALERT_WINDOW         = timedelta(minutes=60)   # notifie si le programme démarre dans l'heure
ALERT_MAX_MATCHES    = 5                       # matches max par alerte et par notification
ALERT_SEEN_RETENTION = timedelta(days=1)

# ──────────────────────────────────────────
# FAVORIS
# ──────────────────────────────────────────
def get_favoris(store: dict) -> list[str]:
    return store.get("favoris", [])

def add_favori(store: dict, cid: str) -> str:
    """Ajoute une chaîne. Retourne 'added', 'exists' ou 'full'."""
    favs = store.setdefault("favoris", [])
    if cid in favs:
        return "exists"
    if len(favs) >= MAX_FAVORIS:
        return "full"
    favs.append(cid)
    return "added"

def remove_favori(store: dict, cid: str) -> bool:
    favs = store.get("favoris", [])
    if cid not in favs:
        return False
    favs.remove(cid)
    return True

# ──────────────────────────────────────────
# ALERTES
# ──────────────────────────────────────────
def normalize_query(text: str) -> str:
    """'  Ligue  des CHAMPIONS ' → 'ligue des champions' (sans accents)."""
    return re.sub(r"\s+", " ", _strip_accents(text or "").lower()).strip()

def get_alertes(store: dict) -> list[dict]:
    return store.get("alertes", [])

def add_alerte(store: dict, country: str, query: str) -> str:
    """Ajoute une alerte. Retourne 'added', 'exists', 'full' ou 'invalid'."""
    q = normalize_query(query)
    if len(q) < ALERT_MIN_LEN:
        return "invalid"
    alertes = store.setdefault("alertes", [])
    if any(a["q"] == q and a["country"] == country for a in alertes):
        return "exists"
    if len(alertes) >= MAX_ALERTES:
        return "full"
    alertes.append({"q": q, "country": country})
    return "added"

def remove_alerte(store: dict, query: str) -> bool:
    """Supprime toutes les alertes correspondant au texte (tous pays)."""
    q       = normalize_query(query)
    alertes = store.get("alertes", [])
    kept    = [a for a in alertes if a["q"] != q]
    if len(kept) == len(alertes):
        return False
    store["alertes"] = kept
    return True

def scan_upcoming(index: dict, now, window: timedelta = ALERT_WINDOW, channels=None) -> list[dict]:
    """Programmes (hors placeholders) qui démarrent dans [now, now + window[.

    index : {channel_id → [programme_elem]} (cf. epg_loader.get_epg_index).
    channels : restreint le scan à ces channel_id (None = toutes).
    """
    end, results = now + window, []
    for cid, progs in index.items():
        if channels is not None and cid not in channels:
            continue
        for prog in progs:
            try:
                start = parse_xmltv_time(prog.get("start", ""))
            except ValueError:
                continue
            if not (now <= start < end):
                continue
            title = clean_title(prog.findtext("title", default=""))
            if not title or is_sport_filler(title) or is_epg_placeholder(title, prog.findtext("desc") or ""):
                continue
            results.append({"cid": cid, "title": title, "norm": normalize_query(title), "start": start})
    results.sort(key=lambda r: (r["start"], r["cid"]))
    return results

def _seen_key(alerte: dict, match: dict) -> str:
    return f"{alerte['country']}|{alerte['q']}|{match['cid']}|{int(match['start'].timestamp())}"

def collect_notifications(store: dict, upcoming_by_country: dict, now) -> list[tuple[dict, list[dict], int]]:
    """Retourne [(alerte, matches, nb_autres)] jamais notifiés et les marque tous comme vus.

    Au plus ALERT_MAX_MATCHES matches par alerte ; le surplus est compté dans nb_autres
    (et marqué vu, pour ne pas renvoyer de notification au tour suivant).
    upcoming_by_country : {pays → scan_upcoming(...)}. Purge les clés vues trop anciennes.
    """
    cutoff = int((now - ALERT_SEEN_RETENTION).timestamp())
    seen   = [k for k in store.get("alertes_vues", []) if int(k.rsplit("|", 1)[1]) >= cutoff]
    seen_set, out = set(seen), []
    for alerte in get_alertes(store):
        matches = [
            m for m in upcoming_by_country.get(alerte["country"], [])
            if alerte["q"] in m["norm"] and _seen_key(alerte, m) not in seen_set
        ]
        if not matches:
            continue
        for m in matches:
            key = _seen_key(alerte, m)
            seen.append(key)
            seen_set.add(key)
        out.append((alerte, matches[:ALERT_MAX_MATCHES], max(0, len(matches) - ALERT_MAX_MATCHES)))
    if seen or "alertes_vues" in store:
        store["alertes_vues"] = seen
    return out

# ──────────────────────────────────────────
# FORMATAGE (MarkdownV2)
# ──────────────────────────────────────────
def pick_ce_soir(progs: list[dict], now, tz):
    """Premier programme démarrant entre 20h30 et 21h30 (heure locale) aujourd'hui, après now."""
    local = now.astimezone(tz)
    lo    = local.replace(hour=20, minute=30, second=0, microsecond=0)
    hi    = local.replace(hour=21, minute=30, second=0, microsecond=0)
    return next((p for p in progs if p["start"] > now and lo <= p["start"].astimezone(tz) <= hi), None)

def format_favori_bloc(nom: str, progs: list[dict], now, tz) -> str:
    """Bloc d'une chaîne favorite : en cours, suivant, ce soir."""
    from utils import sanitize_md, duree_str

    def _h(dt):
        return dt.astimezone(tz).strftime("%H:%M")

    current = next((p for p in progs if p["start"] <= now < p["stop"]), None)
    nxt     = next((p for p in progs if p["start"] > now), None)
    soir    = pick_ce_soir(progs, now, tz)
    lignes  = [f"📺 *{sanitize_md(nom)}*"]
    if current:
        lignes.append(f"🔴 {sanitize_md(current['title'])}  _\\(reste {sanitize_md(duree_str(now, current['stop']))}\\)_")
    if nxt:
        lignes.append(f"⏭ {_h(nxt['start'])}  {sanitize_md(nxt['title'])}")
    if soir and soir is not nxt:
        lignes.append(f"🌙 {_h(soir['start'])}  {sanitize_md(soir['title'])}")
    if len(lignes) == 1:
        lignes.append("_Aucun programme à venir_")
    return "\n".join(lignes)

def format_alerte_notification(alerte: dict, matches: list[dict], channels: dict, tz, autres: int = 0) -> str:
    """Message de notification d'une alerte."""
    from utils import sanitize_md, clean_name
    lignes = [f"🔔 *Alerte « {sanitize_md(alerte['q'])} »*\n"]
    for m in matches:
        nom = clean_name(channels.get(m["cid"], m["cid"]))
        lignes.append(f"📺 *{sanitize_md(nom)}* — {m['start'].astimezone(tz).strftime('%H:%M')}  {sanitize_md(m['title'])}")
    if autres:
        lignes.append(f"_\\+{autres} autre\\(s\\)_")
    return "\n".join(lignes)
