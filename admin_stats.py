# ============================================================
# ADMIN_STATS — Calculs purs pour les commandes admin
# Module sans dépendance Telegram → testable isolément.
# Les temps sont des epochs POSIX (secondes), comme stockés dans le cache.
# ============================================================

from collections import defaultdict


def fmt_uptime(seconds) -> str:
    """Durée 'HhMMmSSs' — heures toujours affichées (status, version, nbusers)."""
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s"


def fmt_duration(seconds) -> str:
    """Durée avec heures masquées si nulles : '5min09s' ou '2h05m09s' (prochainexpire)."""
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}min{s:02d}s"


def cache_age_min(loaded_at, now_ts) -> int:
    """Âge du cache en minutes."""
    return int((now_ts - loaded_at) // 60)


def cache_expire_min(loaded_at, now_ts, ttl) -> int:
    """Minutes restantes avant expiration (0 si déjà expiré)."""
    return max(0, ttl // 60 - cache_age_min(loaded_at, now_ts))


def seconds_until_expire(loaded_at, now_ts, ttl) -> int:
    """Secondes restantes avant expiration (négatif si expiré)."""
    return int(loaded_at + ttl - now_ts)


def top_channels(progs, limit=10):
    """Top chaînes par nombre de programmes. Tri stable → ties en ordre d'apparition."""
    compteur = defaultdict(int)
    for prog in progs:
        cid = prog.get("channel", "")
        if cid:
            compteur[cid] += 1
    return sorted(compteur.items(), key=lambda x: x[1], reverse=True)[:limit]


def epg_quality(progs) -> dict:
    """Comptes de complétude EPG : total + programmes avec desc/category/new/icon."""
    progs = list(progs)
    return {
        "total": len(progs),
        "desc":  sum(1 for p in progs if p.findtext("desc", "").strip()),
        "cat":   sum(1 for p in progs if p.find("category") is not None),
        "new":   sum(1 for p in progs if p.find("new") is not None),
        "img":   sum(1 for p in progs if p.find("icon") is not None),
    }


def pct(n, total) -> str:
    """Pourcentage formaté '12.3%' ; '0.0%' si total nul (évite la division par zéro)."""
    return f"{n / total * 100:.1f}%" if total else "0.0%"


def bar(n, total, w=10) -> str:
    """Barre de progression Unicode de largeur w ; vide si total nul."""
    filled = int(n / total * w) if total else 0
    return "█" * filled + "░" * (w - filled)
