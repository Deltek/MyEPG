# ============================================================
# HANDLERS_PUBLIC — Handlers des commandes publiques
# ============================================================

from datetime import datetime, timedelta, timezone
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import TZ_PARIS, CH_TNT_FR, CH_SPORT_FR, CH_SPORT_BY_COUNTRY, EPG_SOURCES, SEARCH_PAGE_SIZE, PAGE_SIZE
from utils import (
    now_paris, get_ch_id_by_name, sanitize_md, clean_name, _normalize, _strip_accents,
    is_sport_filler, is_epg_placeholder, is_film, is_serie
)
from epg_loader import load_epg
from epg_query import get_programmes_for_channel, format_programme
from builders import build_soir_results, build_type_results, build_sport_results
from senders import send_soir_blocs, send_type_blocs
from keyboards import country_keyboard, day_keyboard, chaines_rapides_keyboard
from logger_utils import logger

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📺 *Bot Programme TV*\n\n"
        "• /maintenant `[chaîne|sport]` – En ce moment\n"
        "• /soir       – Soirée TNT FR 🌃\n"
        "• /prime `[pays]` – Prime time 20h–22h30 🌟\n"
        "• /demain     – Programme de demain soir\n"
        "• /nuit       – Programme de la nuit 00h–06h 🌙\n"
        "• /film       – Films ce soir 🎬\n"
        "• /series     – Séries ce soir 📺\n"
        "• /sport `[pays]` – Sport du jour ⚽\n"
        "• /live       – Lives en cours 🔴\n"
        "• /nouveautes – Inédits du jour 🆕\n"
        "• /resume     – Résumé compact maintenant 📋\n"
        "• /soir5      – Les 5 prochains soirs 🗓\n"
        "• /doublons   – Doublons TNT 🔁\n"
        "• /trending   – Titres tendance du jour 📈\n"
        "• /chaine `<nom>` – Prochains programmes\n"
        "• /chaines    – Parcourir les chaînes\n"
        "• /recherche `<mot>` – Rechercher\n"
        "• /aide       – Cette aide\n\n"
        "🌍 Pays : `fr` 🇫🇷  |  `gb` 🇬🇧\n"
        "Ex: `/sport gb`  `/prime fr`  `/maintenant arte`",
        parse_mode="Markdown"
    )

async def aide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def _send_maintenant_chaine(reply_fn, country: str, cid: str):
    """Affiche le programme en cours d'une chaîne."""
    try:
        root     = load_epg(country)
        now      = datetime.now(tz=timezone.utc)
        from utils import get_channels
        channels = get_channels(root)
        nom      = clean_name(channels.get(cid, cid))
        progs    = get_programmes_for_channel(root, cid, limit=10)
        current  = next((p for p in progs if p["start"] <= now < p["stop"]), None)
        nxt      = next((p for p in progs if p["start"] > now), None)
        if not current:
            await reply_fn(f"❌ Aucun programme en cours sur *{sanitize_md(nom)}*.", parse_mode="Markdown")
            return
        new_tag = " 🆕" if current.get("new") else ""
        texte   = (
            f"📺 *{sanitize_md(nom)}*\n"
            f"🔴 ▶️ {sanitize_md(current['title'])}{new_tag}\n"
        )
        h_start = current["start"].astimezone(TZ_PARIS).strftime("%H:%M")
        h_stop  = current["stop"].astimezone(TZ_PARIS).strftime("%H:%M")
        from utils import duree_str
        texte  += f"🕐 {h_start}–{h_stop}  ⏱ {duree_str(now, current['stop'])} restant\n"
        if current.get("desc"):
            texte += f"📝 {sanitize_md(current['desc'])}\n"
        if nxt:
            h       = nxt["start"].astimezone(TZ_PARIS).strftime("%H:%M")
            nxt_tag = " 🆕" if nxt.get("new") else ""
            texte  += f"\n⏭ À {h} : _{sanitize_md(nxt['title'])}{nxt_tag}_"
        await reply_fn(texte, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Erreur _send_maintenant_chaine")
        await reply_fn(f"❌ Erreur : {e}")

async def _maintenant_sport(update: Update):
    """Affiche les sports en cours."""
    msg = await update.message.reply_text("⚽ Chargement du sport en cours…")
    try:
        root      = load_epg("fr")
        now_utc   = datetime.now(tz=timezone.utc)
        from utils import get_channels, duree_str
        channels  = get_channels(root)
        ch_order  = {ch: i for i, ch in enumerate(CH_SPORT_FR)}
        results   = []
        for prog in root.findall("programme"):
            cid = prog.get("channel", "")
            if cid not in ch_order:
                continue
            try:
                from utils import parse_xmltv_time
                start = parse_xmltv_time(prog.get("start", ""))
                stop  = parse_xmltv_time(prog.get("stop",  ""))
            except ValueError:
                continue
            if not (start <= now_utc < stop):
                continue
            from utils import clean_title, clean_desc
            title = clean_title(prog.findtext("title", default=""))
            if is_sport_filler(title):
                continue
            desc = prog.findtext("desc") or ""
            results.append({
                "start": start, "stop": stop, "title": title,
                "desc": clean_desc(desc, title),
                "channel": clean_name(channels.get(cid, cid)), "ch_id": cid,
                "duree_reste": duree_str(now_utc, stop),
                "placeholder": is_epg_placeholder(title, desc),
            })
        if not results:
            await msg.edit_text("❌ Aucun programme sport en cours.")
            return
        results.sort(key=lambda x: ch_order.get(x["ch_id"], 99))
        heure = now_utc.astimezone(TZ_PARIS).strftime("%H:%M")
        texte = f"⚽ *Sport en ce moment* à {heure} — {len(results)} chaîne(s)\n\n"
        for r in results:
            h_start  = r["start"].astimezone(TZ_PARIS).strftime("%H:%M")
            h_stop   = r["stop"].astimezone(TZ_PARIS).strftime("%H:%M")
            ph_tag   = " ⚠️" if r.get("placeholder") else ""
            texte   += f"📺 *{sanitize_md(r['channel'])}*\n"
            texte   += f"🔴 {h_start}–{h_stop} (reste {r['duree_reste']})  {sanitize_md(r['title'])}{ph_tag}\n"
            if r.get("desc") and not r.get("placeholder"):
                texte += f"   📝 {sanitize_md(r['desc'])}\n"
            texte   += "\n"
        if len(texte) > 4096:
            texte = texte[:4090] + "…"
        await msg.edit_text(texte, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Erreur : {e}")

async def maintenant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        if context.args[0].lower() == "sport":
            await _maintenant_sport(update)
            return
        nom_saisi = " ".join(context.args)
        cid       = get_ch_id_by_name(nom_saisi)
        if not cid:
            await update.message.reply_text(
                f"❌ Chaîne *{sanitize_md(nom_saisi)}* introuvable.\n"
                "Ex: tf1, m6, arte, bein1, eurosport, bbc1…\nOu: /maintenant sport",
                parse_mode="Markdown"
            )
            return
        country = "gb" if cid.endswith(".uk") else "fr"
        await _send_maintenant_chaine(update.message.reply_text, country, cid)
        return
    await update.message.reply_text(
        "🌍 *En ce moment – Quel pays ?*", parse_mode="Markdown",
        reply_markup=country_keyboard("now")
    )

async def soir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 *Quel soir ?*", parse_mode="Markdown",
        reply_markup=day_keyboard("soir")
    )

async def film(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Films – Quel jour ?*", parse_mode="Markdown",
        reply_markup=day_keyboard("film")
    )

async def series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📺 *Séries – Quel jour ?*", parse_mode="Markdown",
        reply_markup=day_keyboard("series")
    )

async def sport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pays = "fr"
    if context.args and context.args[0].lower() in EPG_SOURCES:
        pays = context.args[0].lower()
    await update.message.reply_text(
        f"⚽ *Sport – Quel jour ?* ({EPG_SOURCES[pays]['label']})",
        parse_mode="Markdown",
        reply_markup=day_keyboard(f"sport_{pays}")
    )

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filtre = None
    if context.args:
        filtre = context.args[0].lower()
    
    msg = await update.message.reply_text("🔴 Recherche des lives sport en cours…")
    try:
        root      = load_epg("fr")
        now_utc   = datetime.now(tz=timezone.utc)
        from utils import get_channels, duree_str, clean_title, clean_desc
        channels  = get_channels(root)
        ch_order  = {ch: i for i, ch in enumerate(CH_SPORT_FR)}
        sport_set = set(CH_SPORT_FR)
        results   = []
        
        for prog in root.findall("programme"):
            cid = prog.get("channel", "")
            if cid not in sport_set:
                continue
            if filtre == "canal" and not cid.startswith("CANAL+") and cid != "C+SPORT.fr":
                continue
            try:
                from utils import parse_xmltv_time
                start = parse_xmltv_time(prog.get("start", ""))
                stop  = parse_xmltv_time(prog.get("stop",  ""))
            except ValueError:
                continue
            if not (start <= now_utc < stop):
                continue
            title = clean_title(prog.findtext("title", default=""))
            if is_sport_filler(title):
                continue
            desc = prog.findtext("desc") or ""
            results.append({
                "start": start, "stop": stop, "title": title,
                "desc": clean_desc(desc, title),
                "channel": clean_name(channels.get(cid, cid)), "ch_id": cid,
                "duree_reste": duree_str(now_utc, stop),
                "placeholder": is_epg_placeholder(title, desc),
            })
        
        if not results:
            filtre_txt = f" ({filtre.upper()})" if filtre else ""
            await msg.edit_text(f"❌ Aucun live sport en cours{filtre_txt}.")
            return
        
        results.sort(key=lambda x: ch_order.get(x["ch_id"], 99))
        heure = now_utc.astimezone(TZ_PARIS).strftime("%H:%M")
        filtre_txt = f" ({filtre.upper()})" if filtre else ""
        texte = f"🔴 *Lives sport en cours*{filtre_txt} à {heure} — {len(results)} chaîne(s)\n\n"
        for r in results:
            h_start = r["start"].astimezone(TZ_PARIS).strftime("%H:%M")
            h_stop  = r["stop"].astimezone(TZ_PARIS).strftime("%H:%M")
            ph_tag  = " ⚠️" if r.get("placeholder") else ""
            texte  += f"📺 *{sanitize_md(r['channel'])}*\n"
            texte  += f"🔴 {h_start}–{h_stop} _(reste {r['duree_reste']})_  {sanitize_md(r['title'])}{ph_tag}\n"
            if r.get("desc") and not r.get("placeholder"):
                texte += f"   📝 {sanitize_md(r['desc'])}\n"
            texte += "\n"
        if len(texte) > 4096:
            texte = texte[:4090] + "…"
        await msg.edit_text(texte, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Erreur /live")
        await msg.edit_text(f"❌ Erreur : {e}")

async def nouveautes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆕 *Inédits – Quel jour ?*", parse_mode="Markdown",
        reply_markup=day_keyboard("nouveautes_day")
    )

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 Ton user ID : `{update.effective_user.id}`", parse_mode="Markdown"
    )
