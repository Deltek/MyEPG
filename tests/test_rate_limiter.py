import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from rate_limiter import RateLimiter


class TestRateLimiter:
    def test_allows_up_to_max_calls(self):
        rl = RateLimiter(3, 30)
        assert [rl.allow(1, t) for t in (0, 1, 2)] == [True, True, True]

    def test_blocks_when_limit_reached(self):
        rl = RateLimiter(3, 30)
        for t in (0, 1, 2):
            rl.allow(1, t)
        assert rl.allow(1, 3) is False
        assert rl.allow(1, 29.9) is False

    def test_window_expiration(self):
        rl = RateLimiter(2, 30)
        rl.allow(1, 0)
        rl.allow(1, 10)
        assert rl.allow(1, 20) is False
        assert rl.allow(1, 30) is True   # l'appel de t=0 a expiré
        assert rl.allow(1, 31) is False  # t=10 et t=30 encore dans la fenêtre

    def test_blocked_calls_not_recorded(self):
        rl = RateLimiter(1, 10)
        rl.allow(1, 0)
        for t in range(1, 10):
            assert rl.allow(1, t) is False
        assert rl.allow(1, 10) is True

    def test_users_are_independent(self):
        rl = RateLimiter(1, 30)
        assert rl.allow(1, 0) is True
        assert rl.allow(1, 1) is False
        assert rl.allow(2, 1) is True

    def test_single_warning_per_window(self):
        rl = RateLimiter(1, 30)
        rl.allow(1, 0)
        assert rl.allow(1, 1) is False
        assert rl.should_warn(1, 1) is True
        assert rl.should_warn(1, 5) is False
        assert rl.should_warn(1, 30) is False
        assert rl.should_warn(1, 31) is True

    def test_warning_rearmed_after_recovery(self):
        rl = RateLimiter(1, 10)
        rl.allow(1, 0)
        assert rl.should_warn(1, 1) is True
        assert rl.allow(1, 11) is True
        assert rl.allow(1, 12) is False
        assert rl.should_warn(1, 12) is True

    def test_memory_released_when_window_empty(self):
        rl = RateLimiter(2, 10)
        rl.allow(1, 0)
        rl._prune(1, 100)
        assert 1 not in rl._history

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            RateLimiter(0, 10)
        with pytest.raises(ValueError):
            RateLimiter(1, 0)


def _update(user_id, callback=False):
    msg   = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(answer=AsyncMock()) if callback else None
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=msg, callback_query=query,
    )


class TestRateLimitDecorator:
    def _decorated(self, max_calls=2):
        from decorators import rate_limit

        async def handler(update, context):
            """doc handler"""
            return "ok"
        return rate_limit(limiter=RateLimiter(max_calls, 30))(handler)

    def test_preserves_metadata_and_coroutine(self):
        h = self._decorated()
        assert h.__name__ == "handler"
        assert h.__doc__ == "doc handler"
        assert asyncio.iscoroutinefunction(h)

    def test_message_warned_once(self):
        h   = self._decorated(max_calls=1)
        upd = _update(42)
        with patch("decorators.ADMIN_USER_ID", 1):
            assert asyncio.run(h(upd, None)) == "ok"
            assert asyncio.run(h(upd, None)) is None
            assert asyncio.run(h(upd, None)) is None
        assert upd.effective_message.reply_text.await_count == 1

    def test_callback_answered_on_every_blocked_call(self):
        h   = self._decorated(max_calls=1)
        upd = _update(42, callback=True)
        with patch("decorators.ADMIN_USER_ID", 1):
            asyncio.run(h(upd, None))
            assert upd.callback_query.answer.await_count == 0  # le handler répond lui-même
            asyncio.run(h(upd, None))
            asyncio.run(h(upd, None))
        calls = upd.callback_query.answer.await_args_list
        assert len(calls) == 2
        assert calls[0].args and "Trop de requêtes" in calls[0].args[0]
        assert not calls[1].args
        upd.effective_message.reply_text.assert_not_awaited()

    def test_admin_exempt(self):
        h   = self._decorated(max_calls=1)
        upd = _update(7)
        with patch("decorators.ADMIN_USER_ID", 7):
            for _ in range(5):
                assert asyncio.run(h(upd, None)) == "ok"
        upd.effective_message.reply_text.assert_not_awaited()

    def test_bare_decorator_uses_shared_limiter(self):
        from decorators import rate_limit

        @rate_limit
        async def cmd(update, context):
            return "ok"
        assert cmd.__name__ == "cmd"
        assert asyncio.iscoroutinefunction(cmd)

    def test_combined_with_admin_only(self):
        from decorators import admin_only, rate_limit

        @admin_only
        @rate_limit
        async def cmd(update, context):
            """admin cmd"""
            return "ok"
        assert cmd.__name__ == "cmd"
        assert cmd.__doc__ == "admin cmd"
        upd = _update(7)
        upd.message = upd.effective_message
        with patch("decorators.ADMIN_USER_ID", 7):
            assert asyncio.run(cmd(upd, None)) == "ok"
