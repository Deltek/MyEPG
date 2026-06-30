# ============================================================
# CALLBACKS — Gestionnaires de callbacks (buttons inline)
# ============================================================

from datetime import datetime, timezone
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes

from config import EPG_SOURCES, TZ_PARIS, CH_TNT_FR, CH_SPORT_FR, CH_TNT_BY_COUNTRY, CH_SPORT_BY_COUNTRY, PAGE_SIZE, SEARCH_PAGE_SIZE
from utils import sanitize_md, clean_name, _normalize, _strip_accents, parse_xmltv_time, get_channels, clean_title, clean_desc, get_categories, duree_str, is_film, is_serie, is_sport, is_nouveautes_filler
from epg_loader import load_epg, get_epg_channels, get_epg_index
from epg_query import get_programmes_for_channel
from builders import (
    build_soir_results, build_type_results, build_sport_results,
    build_nouveautes_tnt, build_prime_results, build_nuit_results
)
from senders import send_soir_blocs, send_type_blocs
from keyboards import chaines_rapides_keyboard
from epg_search import do_recherche
from logger_utils import logger

def _channels(root, country: str) -> dict:
    cached = get_epg_channels(country)
    return cached if cached else get_channels(root)

def make_fns(query) -> dict:
    """Retourne {edit_fn, send_fn} bindés sur query (MarkdownV2)."""
    return {
        "edit_fn": lambda t, **kw: query.edit_message_text(t, parse_mode="MarkdownV2", **kw),
        "send_fn": lambda t, **kw: query.message.reply_text(t, parse_mode="MarkdownV2", **kw),
    }

async def callback_maintenant_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    country = query.data.split(":", 1)[1]
    flag    = EPG_SOURCES[country]["label"]
    await query.edit_message_text(
        f"📺 *En ce moment – {flag}*\nQuelle chaîne ?",
        parse_mode="MarkdownV2",
        reply_markup=chaines_rapides_keyboard(country)
    )

async def callback_maintenant_chaine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, country, cid = query.data.split(":", 2)
    await query.edit_message_text("⏳ Chargement…")
    from handlers_public import _send_maintenant_chaine
    await _send_maintenant_chaine(query.edit_message_text, country, cid)

async def callback_maintenant_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    country = query.data.split(":", 1)[1]
    await query.edit_message_text(f"⏳ Chargement {EPG_SOURCES[country]['label']}…")
    try:
        root     = await load_epg(country)
        now      = datetime.now(tz=timezone.utc)
        channels = _channels(root, country)
        texte    = f"📡 *En ce moment – {EPG_SOURCES[country]['label']}*\n\n"
        for cid in EPG_SOURCES[country]["vedettes"]:
            progs   = get_programmes_for_channel(root, cid, limit=10, country=country)
            current = next((p for p in progs if p["start"] <= now < p["stop"]), None)
            nxt     = next((p for p in progs if p["start"] > now), None)
            nom     = clean_name(channels.get(cid, cid))
            if current:
                new_tag = " 🆕" if current.get("new") else ""
                h_stop  = current["stop"].astimezone(TZ_PARIS).strftime("%H:%M")
                texte  += f"📺 *{sanitize_md(nom)}*\n🔴 {sanitize_md(current['title'])}{new_tag} _\\(–{h_stop}\\)_\n"
                if nxt:
                    h_nxt   = nxt["start"].astimezone(TZ_PARIS).strftime("%H:%M")
                    nxt_tag = " 🆕" if nxt.get("new") else ""
                    texte  += f"⏭ À {h_nxt} : _{sanitize_md(nxt['title'])}{nxt_tag}_\n"
            else:
                texte += f"📺 *{sanitize_md(nom)}* — aucun programme\n"
            texte += "\n"
        if len(texte) > 4000:
            texte = texte[:4000].rsplit("\n", 1)[0] + "\n…"
        await query.edit_message_text(texte, parse_mode="MarkdownV2")
    except Exception as e:
        logger.exception("Erreur callback_maintenant_all")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_soir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    day_offset = int(query.data.split(":", 1)[1])
    await query.edit_message_text("⏳ Chargement…")
    try:
        root     = await load_epg("fr")
        results, channels, jour_label, now_utc = build_soir_results(root, day_offset)
        await send_soir_blocs(
            results, channels, jour_label, now_utc,
            **make_fns(query),
        )
    except Exception as e:
        logger.exception("Erreur callback")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_film(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    action, day_str = query.data.split(":", 1)
    pays       = action.split("_")[1] if "_" in action else "fr"
    day_offset = int(day_str)
    flag       = EPG_SOURCES[pays]["label"]
    await query.edit_message_text("⏳ Chargement des films…")
    try:
        ch_set            = set(CH_TNT_BY_COUNTRY.get(pays, CH_TNT_FR))
        root              = await load_epg(pays)
        results, jour_label, now_utc = build_type_results(root, day_offset, is_film, min_duration=75, ch_set=ch_set, country=pays)
        await send_type_blocs(
            results, jour_label, now_utc,
            header=f"🎬 *Films de la soirée – {flag}*",
            **make_fns(query),
        )
    except Exception as e:
        logger.exception("Erreur callback")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    action, day_str = query.data.split(":", 1)
    pays       = action.split("_")[1] if "_" in action else "fr"
    day_offset = int(day_str)
    flag       = EPG_SOURCES[pays]["label"]
    await query.edit_message_text("⏳ Chargement des séries…")
    try:
        ch_set            = set(CH_TNT_BY_COUNTRY.get(pays, CH_TNT_FR))
        root              = await load_epg(pays)
        results, jour_label, now_utc = build_type_results(root, day_offset, is_serie, ch_set=ch_set, country=pays)
        await send_type_blocs(
            results, jour_label, now_utc,
            header=f"📺 *Séries de la soirée – {flag}*",
            **make_fns(query),
        )
    except Exception as e:
        logger.exception("Erreur callback")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_sport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    action, day_str = query.data.split(":", 1)
    pays       = action.split("_")[1] if "_" in action else "fr"
    day_offset = int(day_str)
    await query.edit_message_text("⏳ Chargement du sport…")
    try:
        ch_list           = CH_SPORT_BY_COUNTRY.get(pays, CH_SPORT_FR)
        root              = await load_epg(pays)
        results, jour_label, now_utc = build_sport_results(root, day_offset, ch_list, country=pays)
        flag              = EPG_SOURCES[pays]["label"]
        await send_type_blocs(
            results, jour_label, now_utc,
            header=f"⚽ *Sport – {flag}* — {len(results)} programme\\(s\\)",
            **make_fns(query),
            ch_order_list=ch_list,
        )
    except Exception as e:
        logger.exception("Erreur callback")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_nouveautes_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from keyboards import nouveautes_type_keyboard
    query      = update.callback_query
    await query.answer()
    day_offset = int(query.data.split(":", 1)[1])
    await query.edit_message_text(
        "🆕 *Inédits – Quel type ?*", parse_mode="MarkdownV2",
        reply_markup=nouveautes_type_keyboard(day_offset)
    )

async def callback_nouveautes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    _, type_str, day_str = query.data.split(":")
    day_offset = int(day_str)
    await query.edit_message_text("⏳ Chargement des inédits…")
    try:
        if type_str == "sport":
            root              = await load_epg("fr")
            results, jour_label, now_utc = build_sport_results(root, day_offset, CH_SPORT_FR)
            results           = [r for r in results if not is_nouveautes_filler(r["title"])]
            await send_type_blocs(
                results, jour_label, now_utc,
                header="🆕 *Inédits Sport*",
                **make_fns(query),
                ch_order_list=CH_SPORT_FR,
            )
        else:
            root              = await load_epg("fr")
            results, jour_label, now_utc = build_nouveautes_tnt(root, day_offset)
            await send_type_blocs(
                results, jour_label, now_utc,
                header="🆕 *Inédits TNT FR*",
                **make_fns(query),
            )
    except Exception as e:
        logger.exception("Erreur callback")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_list_chaines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    country    = parts[1]
    page       = int(parts[2]) if len(parts) > 2 else 0
    await query.edit_message_text("⏳ Chargement…")
    try:
        root     = await load_epg(country)
        channels = _channels(root, country)
        all_ch   = sorted(channels.items(), key=lambda x: clean_name(x[1]).lower())
        flag     = EPG_SOURCES[country]["label"]
        total    = len(all_ch)
        start_i  = page * PAGE_SIZE
        page_ch  = all_ch[start_i:start_i + PAGE_SIZE]
        texte    = f"📋 *Chaînes – {flag}*\n_{total} chaînes — page {page + 1}_\n\n"
        texte   += "\n".join(
            f"  `{cid}` — {sanitize_md(clean_name(nom))}"
            for cid, nom in page_ch
        )
        buttons = []
        if page > 0:
            buttons.append(InlineKeyboardButton("◀️", callback_data=f"list:{country}:{page-1}"))
        if start_i + PAGE_SIZE < total:
            buttons.append(InlineKeyboardButton("▶️", callback_data=f"list:{country}:{page+1}"))
        markup = InlineKeyboardMarkup([buttons]) if buttons else None
        if len(texte) > 4096:
            texte = texte[:4090] + "…"
        await query.edit_message_text(texte, parse_mode="MarkdownV2", reply_markup=markup)
    except Exception as e:
        logger.exception("Erreur callback")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_search_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pays  = query.data.split(":", 1)[1]
    mot   = context.user_data.get("search_mot", "")
    if not mot:
        await query.edit_message_text("❌ Mot-clé perdu. Relance /recherche.", parse_mode="MarkdownV2")
        return
    await query.edit_message_text(f"🔍 Recherche de *{sanitize_md(mot)}*…", parse_mode="MarkdownV2")
    if pays == "all":
        for p in EPG_SOURCES:
            await do_recherche(update, mot, p, context=context)
    else:
        await do_recherche(update, mot, pays, context=context)

async def callback_search_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, pays, page_str = query.data.split(":", 2)
    page = int(page_str)
    mot  = context.user_data.get("search_mot", "")
    if not mot:
        await query.edit_message_text("❌ Mot\\-clé perdu\\. Relance /recherche\\.", parse_mode="MarkdownV2")
        return
    await query.edit_message_text(f"🔍 Page {page + 1}…")
    await do_recherche(update, mot, pays, page, context=context)

async def callback_prime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, day_str = query.data.split(":", 1)
    pays       = action.split("_", 1)[1]  # "prime_fr" → "fr"
    day_offset = int(day_str)
    await query.edit_message_text("⏳ Chargement du prime time…")
    try:
        root              = await load_epg(pays)
        results, jour_label, now_utc = build_prime_results(root, day_offset, country=pays)
        flag              = EPG_SOURCES[pays]["label"]
        await send_type_blocs(
            results, jour_label, now_utc,
            header=f"🌟 *Prime time 20h–22h30 – {flag}*",
            **make_fns(query),
        )
    except Exception as e:
        logger.exception("Erreur callback")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_nuit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day_offset = int(query.data.split(":", 1)[1])
    await query.edit_message_text("⏳ Chargement de la nuit…")
    try:
        root              = await load_epg("fr")
        results, jour_label, now_utc = build_nuit_results(root, day_offset)
        await send_type_blocs(
            results, jour_label, now_utc,
            header="🌙 *Nuit 00h–06h – TNT FR*",
            **make_fns(query),
        )
    except Exception as e:
        logger.exception("Erreur callback")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_sporttnt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    day_offset = int(query.data.split(":", 1)[1])
    await query.edit_message_text("⏳ Chargement du sport TNT…")
    try:
        root = await load_epg("fr")
        results, jour_label, now_utc = build_type_results(root, day_offset, is_sport)
        await send_type_blocs(
            results, jour_label, now_utc,
            header=f"🏟 *Sport – TNT FR* — {len(results)} programme\\(s\\)",
            **make_fns(query),
        )
    except Exception as e:
        logger.exception("Erreur callback")
        await query.edit_message_text("❌ Une erreur est survenue, réessaie dans quelques instants.")

async def callback_admin_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import ADMIN_USER_ID
    from logger_utils import get_mem_handler
    query = update.callback_query
    if query.from_user.id != ADMIN_USER_ID:
        await query.answer("⛔ Accès refusé.", show_alert=True)
        return
    await query.answer()
    get_mem_handler().records.clear()
    await query.edit_message_text("🗑 Logs vidés.")
