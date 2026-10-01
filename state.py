# ============================================================
# STATE — État global du bot, persisté en JSON
#   (utilisateurs connus, compteur de commandes, données par utilisateur)
# ============================================================

import json
import os
import time
from collections import Counter
from pathlib import Path

from logger_utils import logger

DATA_FILE = Path(os.getenv("MYEPG_DATA_DIR", Path(__file__).parent / "data")) / "state.json"

_known_users: set[int] = set()
_command_counter: Counter = Counter()
_user_store: dict[int, dict] = {}
_dirty = False
BOT_START_TS = time.time()

# ──────────────────────────────────────────
# UTILISATEURS
# ──────────────────────────────────────────
def add_user(user_id: int) -> bool:
    """Enregistre un utilisateur connu. Retourne True s'il est nouveau."""
    global _dirty
    if user_id in _known_users:
        return False
    _known_users.add(user_id)
    _dirty = True
    return True

def get_known_users() -> set[int]:
    """Retourne l'ensemble des utilisateurs connus."""
    return _known_users

def reset_known_users():
    """Réinitialise le registre utilisateurs."""
    global _known_users, _dirty
    _known_users = set()
    _dirty = True

# ──────────────────────────────────────────
# COMPTEUR DE COMMANDES
# ──────────────────────────────────────────
def normalize_command(text: str) -> str | None:
    """'/Sport@MyBot gb' → 'sport'. None si le texte n'est pas une commande."""
    if not text or not text.startswith("/") or len(text) < 2 or text[1].isspace():
        return None
    cmd = text[1:].split(maxsplit=1)[0]
    cmd = cmd.split("@", 1)[0].lower()
    return cmd or None

def track_command(cmd: str):
    """Incrémente le compteur d'une commande."""
    global _dirty
    _command_counter[cmd] += 1
    _dirty = True

def get_top_commands(n: int = 10) -> list[tuple[str, int]]:
    """Top n des commandes les plus utilisées."""
    return _command_counter.most_common(n)

def get_total_commands() -> int:
    return sum(_command_counter.values())

# ──────────────────────────────────────────
# DONNÉES PAR UTILISATEUR (favoris, alertes…)
# ──────────────────────────────────────────
def get_user_store(user_id: int) -> dict:
    """Dict persistant propre à un utilisateur (créé à la demande)."""
    return _user_store.setdefault(user_id, {})

def iter_user_stores():
    """Itère sur (user_id, dict) — utilisé par les jobs (alertes)."""
    return list(_user_store.items())

def mark_dirty():
    """Signale une modification à persister (après écriture dans un user store)."""
    global _dirty
    _dirty = True

# ──────────────────────────────────────────
# PERSISTANCE
# ──────────────────────────────────────────
def to_dict() -> dict:
    return {
        "users":    sorted(_known_users),
        "commands": dict(_command_counter),
        "user_store": {str(uid): data for uid, data in _user_store.items() if data},
    }

def from_dict(data: dict):
    """Remplace l'état courant par le contenu d'un dict (format to_dict)."""
    global _known_users, _command_counter, _user_store, _dirty
    _known_users     = {int(u) for u in data.get("users", [])}
    _command_counter = Counter({str(k): int(v) for k, v in data.get("commands", {}).items()})
    _user_store      = {int(uid): d for uid, d in data.get("user_store", {}).items()}
    _dirty           = False

def load_state(path: Path = None):
    """Charge l'état depuis le disque. Fichier absent ou corrompu → état vide."""
    path = Path(path or DATA_FILE)
    if not path.exists():
        return
    try:
        from_dict(json.loads(path.read_text(encoding="utf-8")))
        logger.info(f"État chargé : {len(_known_users)} utilisateurs.")
    except (OSError, ValueError, TypeError, AttributeError) as e:
        logger.warning(f"État illisible ({path}) : {e} — démarrage à vide.")

def save_state(path: Path = None, force: bool = False) -> bool:
    """Écrit l'état sur disque (atomique) s'il a changé. Retourne True si écrit."""
    global _dirty
    if not _dirty and not force:
        return False
    path = Path(path or DATA_FILE)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(to_dict(), ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        _dirty = False
        return True
    except OSError as e:
        logger.error(f"Échec sauvegarde état ({path}) : {e}")
        return False

def reset_state():
    """Vide tout l'état en mémoire (tests)."""
    from_dict({})
