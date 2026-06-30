# ============================================================
# EPG_SEARCH — Recherche full-text paginée dans l'EPG
# ============================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from config import TZ_PARIS, EPG_SOURCES, SEARCH_PAGE_SIZE
from utils import (
    sanitize_md, clean_name, _normalize, _strip_accents,
    parse_xmltv_time, get_channels, clean_title, clean_desc
)
from epg_loader import load_epg, get_epg_channels
from logger_utils import logger

def _channels(root, country: str) -> dict:
    cached = get_epg_channels(country)
    return cached if cached else get_channels(root)

async def do_recherche(update: Update, mot: str, pays: str, page: int = 0, context=None):
    """Effectue une recherche EPG et envoie les résultats paginés."""
    query = update.callback_query
    try:
        cache_key = (mot, pays)
        user_data = context.user_data if context else {}
        cache     = user_data.setdefault("search_cache", {})
        if cache_key not in cache:
            root     = await load_epg(pays)
            channels = _channels(root, pays)
            mot_norm = _normalize(_strip_accents(mot))
            results  = []
            for prog in root.findall("programme"):
                cid   = prog.get("channel", "")
                title = clean_title(prog.findtext("title", default=""))
                desc  = prog.findtext("desc") or ""
                if mot_norm not in _normalize(_strip_accents(title)) and mot_norm not in _normalize(_strip_accents(desc)):
                    continue
                try:
                    start = parse_xmltv_time(prog.get("start", ""))
                    stop  = parse_xmltv_time(prog.get("stop",  ""))
                except ValueError:
                    continue
                results.append({
                    "start": start, "stop": stop, "title": title,
                    "desc": clean_desc(desc, title),
                    "channel": clean_name(channels.get(cid, cid)), "ch_id": cid,
                })
            results.sort(key=lambda x: x["start"])
            cache[cache_key] = results
        results = cache[cache_key]
        flag         = EPG_SOURCES[pays]["label"]
        total        = len(results)
        start_i      = page * SEARCH_PAGE_SIZE
        page_results = results[start_i:start_i + SEARCH_PAGE_SIZE]
        if not page_results:
            await query.message.reply_text(
                f"🔍 *{sanitize_md(mot)}* — {flag}\n❌ Aucun résultat\\.",
                parse_mode="MarkdownV2"
            )
            return
        texte = f"🔍 *{sanitize_md(mot)}* — {flag}\n_{total} résultat\\(s\\) — page {page + 1}_\n\n"
        for r in page_results:
            h_start = r["start"].astimezone(TZ_PARIS).strftime("%d/%m %H:%M")
            h_stop  = r["stop"].astimezone(TZ_PARIS).strftime("%H:%M")
            texte  += f"📺 *{sanitize_md(r['channel'])}*  🕐 {h_start}–{h_stop}\n"
            texte  += f"▶️ {sanitize_md(r['title'])}\n"
            if r.get("desc"):
                texte += f"   📝 {sanitize_md(r['desc'])}\n"
            texte += "\n"
        buttons = []
        if page > 0:
            buttons.append(InlineKeyboardButton("◀️", callback_data=f"search_page:{pays}:{page-1}"))
        if start_i + SEARCH_PAGE_SIZE < total:
            buttons.append(InlineKeyboardButton("▶️", callback_data=f"search_page:{pays}:{page+1}"))
        markup = InlineKeyboardMarkup([buttons]) if buttons else None
        if len(texte) > 4000:
            texte = texte[:4000].rsplit("\n", 1)[0] + "\n…"
        await query.message.reply_text(texte, parse_mode="MarkdownV2", reply_markup=markup)
    except Exception as e:
        logger.exception("Erreur do_recherche")
        await query.message.reply_text("❌ Une erreur est survenue, réessaie dans quelques instants.")
