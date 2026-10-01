# ============================================================
# HANDLERS_PERSO — Favoris (/favoris) et alertes (/alerte, /alertes)
# ============================================================

import difflib
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from config import TZ_PARIS, EPG_SOURCES, CH_ALIASES, CH_TNT_BY_COUNTRY, CH_SPORT_BY_COUNTRY
from utils import get_ch_id_by_name, sanitize_md, clean_name, get_channels
from epg_loader import load_epg, get_epg_channels, get_epg_index
from epg_query import get_programmes_for_channel
from state import get_user_store, iter_user_stores, mark_dirty, save_state
from perso import (
    MAX_FAVORIS, MAX_ALERTES, ALERT_MIN_LEN, ALERT_WINDOW,
    get_favoris, add_favori, remove_favori,
    get_alertes, add_alerte, remove_alerte,
    scan_upcoming, collect_notifications,
    format_favori_bloc, format_alerte_notification,
)
from decorators import rate_limit
from logger_utils import logger

ALERT_CHECK_INTERVAL = 600  # secondes entre deux scans des alertes

def _country_of(cid: str) -> str:
    return "gb" if cid.endswith(".uk") else "fr"

def _channel_names(country: str) -> dict:
    cached = get_epg_channels(country)
    if cached:
        return cached
    from epg_loader import get_cache
    root = get_cache(country)["tree"]
    return get_channels(root) if root is not None else {}

def _unknown_channel_text(nom_saisi: str) -> str:
    suggestions = difflib.get_close_matches(nom_saisi.lower().strip(), CH_ALIASES.keys(), n=5, cutoff=0.5)
    hint = (
        f"\nSuggestions : {', '.join(sanitize_md(s) for s in suggestions)}"
        if suggestions else "\nEx: tf1, m6, arte, bbc1…"
    )
    return f"❌ Chaîne *{sanitize_md(nom_saisi)}* introuvable\\." + hint

# ──────────────────────────────────────────
# /FAVORIS
# ──────────────────────────────────────────
_FAVORIS_USAGE = (
    "⭐ *Favoris*\n\n"
    "/favoris — résumé de tes chaînes favorites\n"
    "/favoris ajouter `<chaîne>`\n"
    "/favoris supprimer `<chaîne>`\n"
    "/favoris liste\n\n"
    f"Jusqu'à {MAX_FAVORIS} chaînes\\. Ex: `/favoris ajouter arte`"
)

@rate_limit
async def favoris(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    store   = get_user_store(update.effective_user.id)
    args    = context.args or []
    action  = args[0].lower() if args else ""

    if action in ("ajouter", "add", "supprimer", "suppr", "del", "retirer"):
        nom_saisi = " ".join(args[1:])
        if not nom_saisi:
            await message.reply_text(_FAVORIS_USAGE, parse_mode="MarkdownV2")
            return
        cid = get_ch_id_by_name(nom_saisi)
        if not cid:
            await message.reply_text(_unknown_channel_text(nom_saisi), parse_mode="MarkdownV2")
            return
        nom = sanitize_md(clean_name(_channel_names(_country_of(cid)).get(cid, cid.rsplit(".", 1)[0])))
        if action in ("ajouter", "add"):
            res = add_favori(store, cid)
            texte = {
                "added":  f"⭐ *{nom}* ajoutée aux favoris\\.",
                "exists": f"ℹ️ *{nom}* est déjà dans tes favoris\\.",
                "full":   f"❌ Maximum {MAX_FAVORIS} favoris — supprime\\-en un d'abord\\.",
            }[res]
        else:
            res   = remove_favori(store, cid)
            texte = f"🗑 *{nom}* retirée des favoris\\." if res else f"ℹ️ *{nom}* n'est pas dans tes favoris\\."
        if res in ("added", True):
            mark_dirty()
            save_state()
        await message.reply_text(texte, parse_mode="MarkdownV2")
        return

    favs = get_favoris(store)
    if action == "liste":
        if not favs:
            await message.reply_text("Aucun favori\\. Ex: `/favoris ajouter tf1`", parse_mode="MarkdownV2")
            return
        noms = [clean_name(_channel_names(_country_of(c)).get(c, c.rsplit(".", 1)[0])) for c in favs]
        await message.reply_text(
            "⭐ *Tes favoris*\n\n" + "\n".join(f"• {sanitize_md(n)}" for n in noms),
            parse_mode="MarkdownV2"
        )
        return
    if action or not favs:
        await message.reply_text(_FAVORIS_USAGE, parse_mode="MarkdownV2")
        return

    msg = await message.reply_text("⭐ Chargement de tes favoris…")
    try:
        now    = datetime.now(tz=timezone.utc)
        blocs  = []
        for cid in favs:
            country = _country_of(cid)
            root    = await load_epg(country)
            nom     = clean_name(_channel_names(country).get(cid, cid))
            progs   = get_programmes_for_channel(root, cid, limit=30, country=country)
            blocs.append(format_favori_bloc(nom, progs, now, TZ_PARIS))
        heure = now.astimezone(TZ_PARIS).strftime("%H:%M")
        await msg.edit_text(f"⭐ *Tes favoris* — {heure}\n\n" + "\n\n".join(blocs), parse_mode="MarkdownV2")
    except Exception:
        logger.exception("Erreur /favoris")
        await msg.edit_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

# ──────────────────────────────────────────
# /ALERTE, /ALERTES
# ──────────────────────────────────────────
_ALERTE_USAGE = (
    "🔔 *Alertes*\n\n"
    "/alerte `[pays] <mot>` — notification quand un programme contenant ce mot démarre dans l'heure\n"
    "/alerte supprimer `<mot>`\n"
    "/alertes — liste de tes alertes\n\n"
    f"Jusqu'à {MAX_ALERTES} alertes\\. Ex: `/alerte ligue des champions`, `/alerte gb snooker`"
)

async def alerte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    store   = get_user_store(update.effective_user.id)
    args    = context.args or []
    if not args:
        await message.reply_text(_ALERTE_USAGE, parse_mode="MarkdownV2")
        return

    if args[0].lower() in ("supprimer", "suppr", "del", "retirer"):
        mot = " ".join(args[1:])
        if remove_alerte(store, mot):
            mark_dirty()
            save_state()
            await message.reply_text(f"🗑 Alerte *{sanitize_md(mot)}* supprimée\\.", parse_mode="MarkdownV2")
        else:
            await message.reply_text(f"ℹ️ Aucune alerte *{sanitize_md(mot)}*\\. Voir /alertes", parse_mode="MarkdownV2")
        return

    country = "fr"
    if len(args) > 1 and args[0].lower() in EPG_SOURCES:
        country, args = args[0].lower(), args[1:]
    mot = " ".join(args)
    res = add_alerte(store, country, mot)
    if res == "added":
        mark_dirty()
        save_state()
    flag  = EPG_SOURCES[country]["label"].split()[0]
    texte = {
        "added":   f"🔔 Alerte {flag} *{sanitize_md(mot)}* enregistrée\\. "
                   f"Je te préviens quand un programme correspondant démarre dans l'heure\\.",
        "exists":  f"ℹ️ L'alerte *{sanitize_md(mot)}* existe déjà\\.",
        "full":    f"❌ Maximum {MAX_ALERTES} alertes — supprime\\-en une d'abord\\.",
        "invalid": f"❌ Le mot\\-clé doit faire au moins {ALERT_MIN_LEN} caractères\\.",
    }[res]
    await message.reply_text(texte, parse_mode="MarkdownV2")

async def alertes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lst = get_alertes(get_user_store(update.effective_user.id))
    if not lst:
        await update.effective_message.reply_text(
            "Aucune alerte\\. Ex: `/alerte ligue des champions`", parse_mode="MarkdownV2"
        )
        return
    lignes = [
        f"• {EPG_SOURCES[a['country']]['label'].split()[0]} {sanitize_md(a['q'])}" for a in lst
    ]
    await update.effective_message.reply_text(
        "🔔 *Tes alertes*\n\n" + "\n".join(lignes) + "\n\n_Supprimer : /alerte supprimer \\<mot\\>_",
        parse_mode="MarkdownV2"
    )

async def alert_job(context: ContextTypes.DEFAULT_TYPE):
    """Job périodique : notifie les programmes correspondant aux alertes qui démarrent dans l'heure."""
    stores = [(uid, s) for uid, s in iter_user_stores() if get_alertes(s)]
    if not stores:
        return
    countries = {a["country"] for _, s in stores for a in get_alertes(s)}
    now       = datetime.now(tz=timezone.utc)
    upcoming  = {}
    for country in countries:
        try:
            await load_epg(country)
            channels = set(CH_TNT_BY_COUNTRY.get(country, [])) | set(CH_SPORT_BY_COUNTRY.get(country, []))
            upcoming[country] = scan_upcoming(get_epg_index(country), now, ALERT_WINDOW, channels or None)
        except Exception as e:
            logger.warning(f"Alertes : EPG {country.upper()} indisponible ({e})")
    changed = False
    for uid, store in stores:
        for alerte_, matches, autres in collect_notifications(store, upcoming, now):
            changed = True
            texte = format_alerte_notification(alerte_, matches, _channel_names(alerte_["country"]), TZ_PARIS, autres)
            try:
                await context.bot.send_message(chat_id=uid, text=texte, parse_mode="MarkdownV2")
            except Exception as e:
                logger.warning(f"Alerte non envoyée à {uid} : {e}")
    if changed:
        mark_dirty()
