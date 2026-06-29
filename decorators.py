# ============================================================
# DECORATORS — Décorateurs pour les handlers (auth, etc.)
# ============================================================

from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_USER_ID

def admin_only(func):
    """Décorateur : restreint l'accès à l'administrateur."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("⛔ Accès réservé à l'administrateur.")
            return
        return await func(update, context)
    return wrapper
