# ============================================================
# DECORATORS — Décorateurs pour les handlers (auth, anti-flood, etc.)
# ============================================================

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING

from config import ADMIN_USER_ID, RATE_LIMIT_MAX_CALLS, RATE_LIMIT_PERIOD
from rate_limiter import RateLimiter

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

RATE_LIMIT_MSG = "⏳ Trop de requêtes, réessaie dans quelques secondes."

# Historique partagé par tous les handlers décorés avec @rate_limit (en mémoire)
_rate_limiter = RateLimiter(RATE_LIMIT_MAX_CALLS, RATE_LIMIT_PERIOD)

def admin_only(func):
    """Décorateur : restreint l'accès à l'administrateur."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("⛔ Accès réservé à l'administrateur.")
            return
        return await func(update, context)
    return wrapper

def rate_limit(func=None, *, limiter: RateLimiter = None):
    """Décorateur anti-flood (#56) : limite les appels coûteux par utilisateur.

    Fonctionne pour les commandes et les callbacks. Admin exempté.
    Un seul avertissement par fenêtre ; les appels bloqués suivants sont ignorés
    (les callbacks reçoivent quand même un answer() vide pour stopper le spinner).
    Utilisable en `@rate_limit` ou `@rate_limit(limiter=RateLimiter(...))`.
    """
    def decorator(f):
        @functools.wraps(f)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            lim  = limiter or _rate_limiter
            user = update.effective_user
            if user is None or user.id == ADMIN_USER_ID:
                return await f(update, context, *args, **kwargs)
            now = time.monotonic()
            if lim.allow(user.id, now):
                return await f(update, context, *args, **kwargs)
            warn  = lim.should_warn(user.id, now)
            query = update.callback_query
            if query is not None:
                if warn:
                    await query.answer(RATE_LIMIT_MSG)
                else:
                    await query.answer()
            elif warn and update.effective_message is not None:
                await update.effective_message.reply_text(RATE_LIMIT_MSG)
            return None
        return wrapper
    if func is not None:
        return decorator(func)
    return decorator
