# ============================================================
# LOGGER — Configuration du logging et gestion des logs
# ============================================================

import logging
from collections import deque
from datetime import datetime
from config import TZ_PARIS

class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity: int = 50):
        super().__init__()
        self.records = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord):
        if record.levelno >= logging.WARNING:
            self.records.append(record)

_mem_handler = MemoryLogHandler(capacity=50)
_mem_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s — %(message)s", datefmt="%H:%M:%S"
))
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger().addHandler(_mem_handler)

def get_logger():
    return logger

def get_mem_handler():
    return _mem_handler

def format_log_record(record: logging.LogRecord, sanitize_fn) -> str:
    """Formate un enregistrement de log pour affichage."""
    ts = datetime.fromtimestamp(record.created, tz=TZ_PARIS).strftime("%H:%M:%S")
    level = "⚠️" if record.levelno == logging.WARNING else "❌"
    return f"{level} `{ts}` *{sanitize_fn(record.name)}*\n`{sanitize_fn(record.getMessage()[:200])}`"
