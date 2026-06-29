# ============================================================
# KEYBOARDS — Générateurs de claviers inline Telegram
# ============================================================

from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import EPG_SOURCES, TZ_PARIS
from utils import now_paris

def country_keyboard(action: str) -> InlineKeyboardMarkup:
    """Crée un clavier pays (France/UK)."""
    buttons = []
    for code, src in EPG_SOURCES.items():
        cb = f"{action}:{code}:0" if action == "list" else f"{action}:{code}"
        buttons.append(InlineKeyboardButton(src["label"], callback_data=cb))
    rows = [buttons]
    if action == "search":
        rows.append([InlineKeyboardButton("🌍 Tous les pays", callback_data="search:all")])
    return InlineKeyboardMarkup(rows)

def day_keyboard(action: str) -> InlineKeyboardMarkup:
    """Crée un clavier jour (aujourd'hui, demain, etc.)."""
    now_local = now_paris()
    keyboard  = []
    for i in range(7):
        jour  = now_local + timedelta(days=i)
        label = "Aujourd'hui" if i == 0 else ("Demain" if i == 1 else jour.strftime("%A %d %B"))
        keyboard.append([InlineKeyboardButton(label.capitalize(), callback_data=f"{action}:{i}")])
    return InlineKeyboardMarkup(keyboard)

def nouveautes_type_keyboard(day_offset: int) -> InlineKeyboardMarkup:
    """Crée un clavier type inédits (Sport/TNT)."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⚽ Sport",  callback_data=f"nouveautes:sport:{day_offset}"),
        InlineKeyboardButton("📺 TNT FR", callback_data=f"nouveautes:tnt:{day_offset}"),
    ]])

def chaines_rapides_keyboard(country: str) -> InlineKeyboardMarkup:
    """Crée un clavier chaînes rapides."""
    if country == "fr":
        chaines = [
            ("TF1", "TF1.fr"), ("France 2", "France2.fr"), ("France 3", "France3.fr"),
            ("France 5", "France5.fr"), ("M6", "M6.fr"), ("Arte", "Arte.fr"),
            ("C8", "C8.fr"), ("W9", "W9.fr"), ("beIN 1", "beINSPORTS1.fr"),
            ("Eurosport", "EUROSPORT1.fr"), ("RMC Sport", "RMCSport1.fr"),
            ("L'Équipe", "L'Equipe.fr"),
        ]
    else:
        chaines = [
            ("BBC One", "BBC1.uk"), ("BBC Two", "BBC2.uk"), ("ITV", "ITV.uk"),
            ("Channel 4", "Channel4.uk"), ("Channel 5", "Channel5.uk"), ("E4", "E4.uk"),
            ("Film4", "Film4.uk"), ("Dave", "Dave.uk"),
            ("Sky Sports", "SkySportsMainEvent.uk"), ("Sky F1", "SkySportsF1.uk"),
            ("TNT Sports", "TNTSports1.uk"), ("Eurosport", "Eurosport1.uk"),
        ]
    rows = []
    for i in range(0, len(chaines), 3):
        rows.append([
            InlineKeyboardButton(label, callback_data=f"now_ch:{country}:{cid}")
            for label, cid in chaines[i:i+3]
        ])
    rows.append([InlineKeyboardButton("📡 Toutes les chaînes vedettes", callback_data=f"now_all:{country}")])
    return InlineKeyboardMarkup(rows)
