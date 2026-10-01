# ============================================================
# BROADCAST — Diffusion d'un message à tous les utilisateurs (sans Telegram)
# ============================================================

import asyncio
from collections import Counter

# Telegram : ~30 msg/s max vers des chats distincts
BROADCAST_DELAY = 0.05

def command_payload(text: str) -> str:
    """'/broadcast\nLigne 1\nLigne 2' → 'Ligne 1\nLigne 2' (sauts de ligne internes conservés)."""
    parts = (text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""

async def broadcast_to(user_ids, send_fn, delay: float = BROADCAST_DELAY) -> Counter:
    """Appelle send_fn(user_id) pour chaque utilisateur, espacé de `delay`.

    send_fn retourne un statut ('ok', 'blocked', …) ; toute exception compte
    comme 'error'. Retourne un Counter {statut: nb}.
    """
    results = Counter()
    for i, uid in enumerate(user_ids):
        if i and delay:
            await asyncio.sleep(delay)
        try:
            results[await send_fn(uid)] += 1
        except Exception:
            results["error"] += 1
    return results
