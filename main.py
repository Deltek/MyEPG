# ============================================================
# MAIN — Point d'entrée du bot
# ============================================================

import logging
from telegram import Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    TypeHandler
)

from config import BOT_TOKEN
from logger_utils import get_logger
from handlers_admin import (
    post_init, admin_panel, status, ping, version, refresh,
    resetcache, cache_info, stats, testepg, top_chaines, sante,
    logs, memoire, prochainexpire, nbusers, gc_collect
)
from handlers_public import (
    start, aide, maintenant, soir, prime, demain, nuit,
    film, series, sport, sporttnt, live, nouveautes,
    resume, soir5, doublons, trending, chaine, chaines, recherche,
    get_id
)
from callbacks import (
    callback_maintenant_country, callback_maintenant_chaine,
    callback_maintenant_all, callback_soir, callback_film,
    callback_series, callback_sport, callback_sporttnt, callback_nouveautes_day,
    callback_nouveautes, callback_list_chaines,
    callback_search_country, callback_search_page,
    callback_prime, callback_nuit, callback_admin_logs
)
from state import add_user

logger = get_logger()

# ──────────────────────────────────────────
# HANDLERS GLOBAUX
# ──────────────────────────────────────────
async def _track_user(update: Update, context):
    """Enregistre chaque utilisateur (group=-1 : avant tout)."""
    if update.effective_user:
        add_user(update.effective_user.id)

# ──────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────
def main():
    """Initialise et démarre le bot."""
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # ── Tracking utilisateurs (group=-1 = avant tout) ──
    app.add_handler(TypeHandler(Update, _track_user), group=-1)

    # ── Commandes publiques ────────────────
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("aide",       aide))
    app.add_handler(CommandHandler("maintenant", maintenant))
    app.add_handler(CommandHandler("soir",       soir))
    app.add_handler(CommandHandler("prime",      prime))
    app.add_handler(CommandHandler("demain",     demain))
    app.add_handler(CommandHandler("nuit",       nuit))
    app.add_handler(CommandHandler("film",       film))
    app.add_handler(CommandHandler("series",     series))
    app.add_handler(CommandHandler("sport",      sport))
    app.add_handler(CommandHandler("sporttnt",   sporttnt))
    app.add_handler(CommandHandler("live",       live))
    app.add_handler(CommandHandler("nouveautes", nouveautes))
    app.add_handler(CommandHandler("resume",     resume))
    app.add_handler(CommandHandler("soir5",      soir5))
    app.add_handler(CommandHandler("doublons",   doublons))
    app.add_handler(CommandHandler("trending",   trending))
    app.add_handler(CommandHandler("chaine",     chaine))
    app.add_handler(CommandHandler("chaines",    chaines))
    app.add_handler(CommandHandler("recherche",  recherche))
    app.add_handler(CommandHandler("id",         get_id))

    # ── Commandes admin ────────────────────
    app.add_handler(CommandHandler("admin",      admin_panel))
    app.add_handler(CommandHandler("status",     status))
    app.add_handler(CommandHandler("ping",       ping))
    app.add_handler(CommandHandler("version",    version))
    app.add_handler(CommandHandler("refresh",    refresh))
    app.add_handler(CommandHandler("resetcache", resetcache))
    app.add_handler(CommandHandler("cache",      cache_info))
    app.add_handler(CommandHandler("stats",      stats))
    app.add_handler(CommandHandler("testepg",    testepg))
    app.add_handler(CommandHandler("top",        top_chaines))
    app.add_handler(CommandHandler("sante",      sante))
    app.add_handler(CommandHandler("logs",       logs))
    app.add_handler(CommandHandler("memoire",    memoire))
    app.add_handler(CommandHandler("prochainexpire", prochainexpire))
    app.add_handler(CommandHandler("nbusers",    nbusers))
    app.add_handler(CommandHandler("gc",         gc_collect))

    # ── Callbacks ─────────────────────────
    app.add_handler(CallbackQueryHandler(callback_maintenant_country, pattern=r"^now:[a-z]+$"))
    app.add_handler(CallbackQueryHandler(callback_maintenant_chaine,  pattern=r"^now_ch:"))
    app.add_handler(CallbackQueryHandler(callback_maintenant_all,     pattern=r"^now_all:"))
    app.add_handler(CallbackQueryHandler(callback_soir,               pattern=r"^soir:"))
    app.add_handler(CallbackQueryHandler(callback_prime,              pattern=r"^prime_"))
    app.add_handler(CallbackQueryHandler(callback_nuit,               pattern=r"^nuit:"))
    app.add_handler(CallbackQueryHandler(callback_film,               pattern=r"^film"))
    app.add_handler(CallbackQueryHandler(callback_series,             pattern=r"^series"))
    app.add_handler(CallbackQueryHandler(callback_sport,              pattern=r"^sport_"))
    app.add_handler(CallbackQueryHandler(callback_sporttnt,           pattern=r"^sporttnt:"))
    app.add_handler(CallbackQueryHandler(callback_nouveautes_day,     pattern=r"^nouveautes_day:"))
    app.add_handler(CallbackQueryHandler(callback_nouveautes,         pattern=r"^nouveautes:"))
    app.add_handler(CallbackQueryHandler(callback_list_chaines,       pattern=r"^list:"))
    app.add_handler(CallbackQueryHandler(callback_search_country,     pattern=r"^search:"))
    app.add_handler(CallbackQueryHandler(callback_search_page,        pattern=r"^search_page:"))
    app.add_handler(CallbackQueryHandler(callback_admin_logs,         pattern=r"^admin_logs:"))

    logger.info("Bot Programme TV démarré.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
