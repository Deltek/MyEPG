# ============================================================
# RATE LIMITER — Fenêtre glissante anti-flood (sans dépendance Telegram)
# ============================================================

from collections import deque


class RateLimiter:
    """Limiteur à fenêtre glissante par utilisateur, en mémoire.

    - allow(user_id, now)       : True si l'appel est autorisé (et l'enregistre).
    - should_warn(user_id, now) : True une seule fois par fenêtre de blocage,
      pour éviter de répondre « trop de requêtes » en boucle.
    `now` est injecté (secondes, p.ex. time.monotonic()) pour la testabilité.
    """

    def __init__(self, max_calls: int, period: float):
        if max_calls < 1 or period <= 0:
            raise ValueError("max_calls >= 1 et period > 0 requis")
        self.max_calls = max_calls
        self.period    = period
        self._history: dict = {}
        self._warned:  dict = {}

    def _prune(self, user_id, now: float):
        hist = self._history.get(user_id)
        if hist is None:
            return None
        while hist and now - hist[0] >= self.period:
            hist.popleft()
        if not hist:
            del self._history[user_id]
            return None
        return hist

    def allow(self, user_id, now: float) -> bool:
        hist = self._prune(user_id, now)
        if hist is not None and len(hist) >= self.max_calls:
            return False
        if hist is None:
            hist = self._history[user_id] = deque()
        hist.append(now)
        warned = self._warned.get(user_id)
        if warned is not None and now - warned >= self.period:
            del self._warned[user_id]
        return True

    def should_warn(self, user_id, now: float) -> bool:
        last = self._warned.get(user_id)
        if last is not None and now - last < self.period:
            return False
        self._warned[user_id] = now
        return True

    def reset(self):
        self._history.clear()
        self._warned.clear()
