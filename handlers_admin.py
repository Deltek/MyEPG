# ============================================================
# HANDLERS_ADMIN — Handlers des commandes admin
# ============================================================

import os
import sys
import time
import gc
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from telegram import Update, BotCommand, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, Application

from config import BOT_VERSION, ADMIN_USER_ID, CACHE_TTL, EPG_SOURCES, CH_TNT_FR, CH_SPORT_FR, CH_TNT_BY_COUNTRY, CH_SPORT_BY_COUNTRY, TZ_PARIS
from state import BOT_START_TS, get_known_users
from decorators import admin_only
from logger_utils import logger, get_mem_handler
from utils import sanitize_md, clean_name, _strip_accents
from epg_loader import load_epg, get_cache, get_cache_prev, reset_cache
import xml.etree.ElementTree as ET
import requests

# ──────────────────────────────────────────
# POST_INIT — Enregistrement des commandes
# ──────────────────────────────────────────
async def post_init(app: Application) -> None:
    """Configure les commandes du bot au démarrage."""
    # Commandes publiques
    await app.bot.set_my_commands([
        BotCommand("maintenant",  "En ce moment sur les chaînes"),
        BotCommand("soir",        "Programme de la soirée TNT FR"),
        BotCommand("prime",       "Prime time 20h–22h30"),
        BotCommand("demain",      "Programme de demain soir"),
        BotCommand("nuit",        "Programme de la nuit 00h–06h"),
        BotCommand("film",        "Films de la soirée"),
        BotCommand("series",      "Séries de la soirée"),
        BotCommand("sport",       "Sport du jour"),
        BotCommand("live",        "Lives en cours (canal, bein, rmc, ...)"),
        BotCommand("nouveautes",  "Inédits du jour"),
        BotCommand("resume",      "Résumé compact en ce moment"),
        BotCommand("soir5",       "Aperçu des 5 prochains soirs"),
        BotCommand("doublons",    "Programmes en doublon TNT"),
        BotCommand("trending",    "Titres tendance du jour"),
        BotCommand("chaine",      "Prochains programmes d'une chaîne"),
        BotCommand("chaines",     "Parcourir toutes les chaînes"),
        BotCommand("recherche",   "Rechercher un programme"),
        BotCommand("aide",        "Afficher l'aide"),
    ])

    # Commandes admin (si ADMIN_USER_ID est défini)
    if ADMIN_USER_ID:
        await app.bot.set_my_commands([
            BotCommand("admin",             "Panneau admin 🔧"),
            BotCommand("status",            "Vue synthétique 📊"),
            BotCommand("ping",              "Latence 🏓"),
            BotCommand("version",           "Version & uptime 📦"),
            BotCommand("refresh",           "Recharger cache 🔄"),
            BotCommand("resetcache",        "Vider cache 🧹"),
            BotCommand("cache",             "État du cache 💾"),
            BotCommand("stats",             "Stats EPG 📊"),
            BotCommand("testepg",           "Tester source EPG 🔌"),
            BotCommand("top",               "Top 10 chaînes 🏆"),
            BotCommand("sante",             "Qualité EPG 🩺"),
            BotCommand("logs",              "Erreurs 📋"),
            BotCommand("memoire",           "Mémoire 🧠"),
            BotCommand("prochainexpire",    "Expiration caches ⏳"),
            BotCommand("nbusers",           "Utilisateurs 👥"),
            BotCommand("gc",               "GC Python 🧹"),
            BotCommand("id",               "User ID 🆔"),
        ], scope=BotCommandScopeChat(chat_id=ADMIN_USER_ID))

    logger.info("Commandes BotFather enregistrées.")

# ──────────────────────────────────────────
# ADMIN PANEL
# ──────────────────────────────────────────
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime_s = int(time.time() - BOT_START_TS)
    h, rem   = divmod(uptime_s, 3600)
    m, s     = divmod(rem, 60)
    cache    = get_cache()
    cache_fr = "✅" if cache["fr"]["tree"] else "❌"
    cache_gb = "✅" if cache["gb"]["tree"] else "❌"
    await update.message.reply_text(
        f"🔧 *Panneau Admin – v{BOT_VERSION}*\n"
        f"⏱ Uptime : `{h}h{m:02d}m{s:02d}s`\n"
        f"💾 Cache : 🇫🇷 {cache_fr}  🇬🇧 {cache_gb}\n\n"
        "• /status • /ping • /version • /refresh `[pays]`\n"
        "• /resetcache • /cache • /stats • /testepg `[pays]`\n"
        "• /top `[pays]` • /sante `[pays]`\n"
        "• /logs • /memoire • /prochainexpire • /nbusers\n"
        "• /gc • /id",
        parse_mode="Markdown"
    )

@admin_only
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime_s = int(time.time() - BOT_START_TS)
    h, rem   = divmod(uptime_s, 3600)
    m, s     = divmod(rem, 60)
    cache_lines = []
    cache = get_cache()
    for country, entry in cache.items():
        flag = EPG_SOURCES[country]["label"]
        if entry["tree"] is None:
            cache_lines.append(f"  {flag} ❌ non chargé")
        else:
            age_min    = int((datetime.now().timestamp() - entry["loaded_at"]) // 60)
            expire_min = max(0, CACHE_TTL // 60 - age_min)
            nb_prog    = len(entry["tree"].findall("programme"))
            cache_lines.append(f"  {flag} ✅ {nb_prog} prog · expire dans {expire_min}min")

    records      = list(get_mem_handler().records)
    last_err_txt = "Aucune"
    if records:
        r            = records[-1]
        ts           = datetime.fromtimestamp(r.created, tz=TZ_PARIS).strftime("%H:%M:%S")
        last_err_txt = f"`{ts}` {sanitize_md(r.getMessage()[:80])}"

    await update.message.reply_text(
        f"📊 *Status – v{BOT_VERSION}*\n\n"
        f"⏱ Uptime : `{h}h{m:02d}m{s:02d}s`\n"
        f"👥 Users : {len(get_known_users())}\n\n"
        f"💾 *Cache :*\n" + "\n".join(cache_lines) + "\n\n"
        f"📋 *Dernière erreur :*\n  {last_err_txt}",
        parse_mode="Markdown"
    )

@admin_only
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t0  = time.time()
    msg = await update.message.reply_text("🏓 …")
    ms  = int((time.time() - t0) * 1000)
    await msg.edit_text(f"🏓 Pong — {ms}ms")

@admin_only
async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime_s = int(time.time() - BOT_START_TS)
    h, rem   = divmod(uptime_s, 3600)
    m, s     = divmod(rem, 60)
    await update.message.reply_text(
        f"📦 *Bot Programme TV*\n"
        f"  Version : `{BOT_VERSION}`\n"
        f"  Uptime  : `{h}h{m:02d}m{s:02d}s`\n"
        f"  Python  : `{sys.version.split()[0]}`",
        parse_mode="Markdown"
    )

@admin_only
async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pays_cibles = list(EPG_SOURCES.keys())
    if context.args:
        p = context.args[0].lower()
        if p not in EPG_SOURCES:
            await update.message.reply_text(
                f"❌ Pays inconnu : `{p}`", parse_mode="Markdown"
            )
            return
        pays_cibles = [p]
    label = ", ".join(EPG_SOURCES[p]["label"] for p in pays_cibles)
    msg   = await update.message.reply_text(f"🔄 Rechargement {label}…")
    try:
        cache = get_cache()
        for country in pays_cibles:
            cache[country]["tree"]      = None
            cache[country]["loaded_at"] = 0
            load_epg(country)
        await msg.edit_text(f"✅ Cache rechargé : {label}")
    except Exception as e:
        await msg.edit_text(f"❌ Erreur : {e}")

@admin_only
async def resetcache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cache = get_cache()
    cache_prev = get_cache_prev()
    caches_actifs = sum(1 for e in cache.values() if e["tree"] is not None)
    snapshots     = sum(1 for e in cache_prev.values() if e["titles"])
    reset_cache()
    await update.message.reply_text(
        f"🧹 *Cache reset*\n\n"
        f"  💾 Caches EPG     : {caches_actifs} → 0\n"
        f"  📸 Snapshots diff : {snapshots} → 0\n\n"
        f"⚠️ Rechargement à la prochaine demande.\n"
        f"💡 `/refresh` pour forcer immédiatement.",
        parse_mode="Markdown"
    )

@admin_only
async def cache_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lignes = ["💾 *État du cache EPG*\n"]
    cache = get_cache()
    for country, entry in cache.items():
        flag = EPG_SOURCES[country]["label"]
        if entry["tree"] is None:
            lignes.append(f"{flag} — ❌ Non chargé")
            continue
        root       = entry["tree"]
        nb_ch      = len(root.findall("channel"))
        nb_prog    = len(root.findall("programme"))
        size_kb    = int(len(ET.tostring(root)) / 1024)
        loaded_at  = datetime.fromtimestamp(entry["loaded_at"], tz=TZ_PARIS)
        expire_at  = datetime.fromtimestamp(entry["loaded_at"] + CACHE_TTL, tz=TZ_PARIS)
        age_min    = int((datetime.now().timestamp() - entry["loaded_at"]) // 60)
        expire_min = max(0, CACHE_TTL // 60 - age_min)
        lignes.append(
            f"{flag} ✅\n"
            f"  📡 {nb_ch} chaînes  |  📋 {nb_prog} programmes\n"
            f"  📦 ~{size_kb} Ko\n"
            f"  🕐 Chargé à {loaded_at.strftime('%H:%M:%S')}\n"
            f"  ⏳ Expire à {expire_at.strftime('%H:%M:%S')} _(dans {expire_min}min)_"
        )
    await update.message.reply_text("\n\n".join(lignes), parse_mode="Markdown")

@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lignes = ["📊 *Statistiques EPG*\n"]
    cache = get_cache()
    for country, entry in cache.items():
        flag = EPG_SOURCES[country]["label"]
        if entry["tree"] is None:
            lignes.append(f"{flag} — ❌ Non chargé")
            continue
        root      = entry["tree"]
        nb_ch     = len(root.findall("channel"))
        nb_prog   = len(root.findall("programme"))
        loaded_at = datetime.fromtimestamp(entry["loaded_at"], tz=TZ_PARIS)
        age_min   = int((datetime.now().timestamp() - entry["loaded_at"]) // 60)
        expire    = max(0, CACHE_TTL // 60 - age_min)
        lignes.append(
            f"{flag}\n"
            f"  📡 {nb_ch} chaînes  |  📋 {nb_prog} programmes\n"
            f"  🕐 Chargé à {loaded_at.strftime('%H:%M:%S')} "
            f"_(il y a {age_min}min, expire dans {expire}min)_"
        )
    await update.message.reply_text("\n\n".join(lignes), parse_mode="Markdown")

@admin_only
async def testepg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pays_cibles = list(EPG_SOURCES.keys())
    if context.args:
        p = context.args[0].lower()
        if p not in EPG_SOURCES:
            await update.message.reply_text(f"❌ Pays inconnu : `{p}`", parse_mode="Markdown")
            return
        pays_cibles = [p]
    msg    = await update.message.reply_text("🔌 Test de connexion EPG…")
    lignes = ["🔌 *Test EPG*\n"]
    for country in pays_cibles:
        flag = EPG_SOURCES[country]["label"]
        url  = EPG_SOURCES[country]["url"]
        try:
            t0    = time.time()
            r     = requests.get(url, timeout=15, stream=True)
            r.raise_for_status()
            chunk = next(r.iter_content(chunk_size=4096), b"")
            ms    = int((time.time() - t0) * 1000)
            r.close()
            lignes.append(f"{flag} ✅  ⏱ {ms}ms  📥 {len(chunk)} B")
        except requests.Timeout:
            lignes.append(f"{flag} ❌ Timeout (>15s)")
        except Exception as e:
            lignes.append(f"{flag} ❌ `{str(e)[:100]}`")
    await msg.edit_text("\n\n".join(lignes), parse_mode="Markdown")

@admin_only
async def top_chaines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pays = context.args[0].lower() if context.args and context.args[0].lower() in EPG_SOURCES else "fr"
    msg  = await update.message.reply_text("🏆 Calcul du top chaînes…")
    try:
        root     = load_epg(pays)
        from utils import get_channels
        channels = get_channels(root)
        compteur = defaultdict(int)
        for prog in root.findall("programme"):
            cid = prog.get("channel", "")
            if cid:
                compteur[cid] += 1
        top   = sorted(compteur.items(), key=lambda x: x[1], reverse=True)[:10]
        flag  = EPG_SOURCES[pays]["label"]
        texte = f"🏆 *Top 10 – {flag}*\n\n"
        for i, (cid, nb) in enumerate(top, 1):
            nom    = clean_name(channels.get(cid, cid))
            texte += f"{i}\\. *{sanitize_md(nom)}* — {nb} programmes\n"
        await msg.edit_text(texte, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Erreur : {e}")

@admin_only
async def sante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pays = context.args[0].lower() if context.args and context.args[0].lower() in EPG_SOURCES else "fr"
    msg  = await update.message.reply_text("🩺 Analyse qualité EPG…")
    try:
        root  = load_epg(pays)
        flag  = EPG_SOURCES[pays]["label"]
        progs = root.findall("programme")
        total = len(progs)
        if not total:
            await msg.edit_text("❌ Aucun programme chargé.")
            return
        avec_desc = sum(1 for p in progs if p.findtext("desc", "").strip())
        avec_cat  = sum(1 for p in progs if p.find("category") is not None)
        avec_new  = sum(1 for p in progs if p.find("new") is not None)
        avec_img  = sum(1 for p in progs if p.find("icon") is not None)

        def pct(n): return f"{n / total * 100:.1f}%"
        def bar(n, t, w=10): return "█" * int(n / t * w) + "░" * (w - int(n / t * w))

        await msg.edit_text(
            f"🩺 *Qualité EPG – {flag}*\n_{total} programmes_\n\n"
            f"📝 Description  `{bar(avec_desc, total)}` {pct(avec_desc)}\n"
            f"📂 Catégorie    `{bar(avec_cat,  total)}` {pct(avec_cat)}\n"
            f"🆕 Tag nouveau  `{bar(avec_new,  total)}` {pct(avec_new)}\n"
            f"🖼 Image        `{bar(avec_img,  total)}` {pct(avec_img)}\n",
            parse_mode="Markdown"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Erreur : {e}")

@admin_only
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = list(get_mem_handler().records)
    if not records:
        await update.message.reply_text("✅ Aucune erreur en mémoire.")
        return
    lignes = []
    for r in records[-10:]:
        level = "⚠️" if r.levelno == 30 else "❌"
        ts    = datetime.fromtimestamp(r.created, tz=TZ_PARIS).strftime("%H:%M:%S")
        lignes.append(f"{level} `{ts}` *{sanitize_md(r.name)}*\n`{sanitize_md(r.getMessage()[:200])}`")
    texte  = f"📋 *Dernières erreurs* ({len(records)} en mémoire)\n\n" + "\n\n".join(lignes)
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Vider les logs", callback_data="admin_logs:clear")
    ]])
    await update.message.reply_text(texte[:4096], parse_mode="Markdown", reply_markup=markup)

@admin_only
async def memoire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🧠 Calcul mémoire…")
    try:
        try:
            import psutil
            proc       = psutil.Process(os.getpid())
            mem        = proc.memory_info()
            rss_mb     = mem.rss / 1024 / 1024
            vms_mb     = mem.vms / 1024 / 1024
            pct        = proc.memory_percent()
            has_psutil = True
        except ImportError:
            import resource
            rss_mb     = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            vms_mb     = pct = 0
            has_psutil = False
        cache_lines = []
        cache = get_cache()
        for country, entry in cache.items():
            flag = EPG_SOURCES[country]["label"]
            if entry["tree"] is None:
                cache_lines.append(f"  {flag} ❌ non chargé")
            else:
                size_kb = len(ET.tostring(entry["tree"])) / 1024
                cache_lines.append(f"  {flag} ~{size_kb:.0f} Ko")
        texte = f"🧠 *Mémoire*\n\n  📦 RSS : `{rss_mb:.1f} Mo`\n"
        if has_psutil:
            texte += f"  📦 VMS : `{vms_mb:.1f} Mo`\n  📊 Usage : `{pct:.2f}%`\n"
        texte += "\n💾 *Cache XML :*\n" + "\n".join(cache_lines)
        await msg.edit_text(texte, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Erreur : {e}")

@admin_only
async def prochainexpire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now_ts   = datetime.now().timestamp()
    lignes   = ["⏳ *Expiration des caches*\n"]
    prochain = None
    cache = get_cache()
    for country, entry in cache.items():
        flag = EPG_SOURCES[country]["label"]
        if entry["tree"] is None or entry["loaded_at"] == 0:
            lignes.append(f"{flag} — ❌ non chargé")
            continue
        expire_ts = entry["loaded_at"] + CACHE_TTL
        expire_dt = datetime.fromtimestamp(expire_ts, tz=TZ_PARIS)
        reste_s   = int(expire_ts - now_ts)
        if reste_s <= 0:
            lignes.append(f"{flag} — ⚠️ *Expiré*")
        else:
            h, rem = divmod(reste_s, 3600)
            m, s   = divmod(rem, 60)
            duree  = f"{h}h{m:02d}m{s:02d}s" if h else f"{m}min{s:02d}s"
            lignes.append(f"{flag} — ✅ expire à *{expire_dt.strftime('%H:%M:%S')}* _(dans {duree})_")
            if prochain is None or expire_ts < prochain:
                prochain = expire_ts
    if prochain:
        p_dt    = datetime.fromtimestamp(prochain, tz=TZ_PARIS)
        reste_p = int(prochain - now_ts)
        hh, rem = divmod(reste_p, 3600)
        mm, ss  = divmod(rem, 60)
        duree_p = f"{hh}h{mm:02d}m{ss:02d}s" if hh else f"{mm}min{ss:02d}s"
        lignes.append(f"\n🔔 Prochain dans *{duree_p}* à {p_dt.strftime('%H:%M:%S')}")
    await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")

@admin_only
async def nbusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime_s = int(time.time() - BOT_START_TS)
    h, rem   = divmod(uptime_s, 3600)
    m, s     = divmod(rem, 60)
    total    = len(get_known_users())
    is_admin = ADMIN_USER_ID in get_known_users()
    await update.message.reply_text(
        f"👥 *Utilisateurs distincts*\n\n"
        f"  Depuis le démarrage : *{total}*\n"
        f"  ⏱ Uptime : `{h}h{m:02d}m{s:02d}s`\n"
        f"  🔧 Admin compté : {'✅' if is_admin else '❌'}\n"
        f"  _{total - (1 if is_admin else 0)} utilisateur(s) hors admin_",
        parse_mode="Markdown"
    )

@admin_only
async def gc_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🧹 Garbage collection…")
    try:
        try:
            import psutil
            proc   = psutil.Process(os.getpid())
            before = proc.memory_info().rss / 1024 / 1024
            has_p  = True
        except ImportError:
            import resource
            before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            has_p  = False
        collected = gc.collect()
        if has_p:
            after = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        else:
            after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        diff_mb = before - after
        signe   = "📉" if diff_mb > 0.1 else ("📈" if diff_mb < -0.1 else "➡️")
        await msg.edit_text(
            f"🧹 *Garbage Collection*\n\n"
            f"  🗑 Objets : `{collected}`\n"
            f"  📦 Avant : `{before:.1f} Mo`  →  Après : `{after:.1f} Mo`\n"
            f"  {signe} `{abs(diff_mb):.1f} Mo` "
            f"{'libérés' if diff_mb > 0.1 else ('ajoutés' if diff_mb < -0.1 else 'stable')}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Erreur : {e}")
