# ============================================================
# STATE — État global du bot (cache utilisateurs, etc.)
# ============================================================

import time

_known_users: set[int] = set()
BOT_START_TS = time.time()

def add_user(user_id: int):
    """Enregistre un utilisateur connu."""
    _known_users.add(user_id)

def get_known_users() -> set[int]:
    """Retourne l'ensemble des utilisateurs connus."""
    return _known_users

def reset_known_users():
    """Réinitialise le registre utilisateurs."""
    global _known_users
    _known_users = set()
