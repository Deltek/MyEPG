import xml.etree.ElementTree as ET

from admin_stats import (
    fmt_uptime, fmt_duration, cache_age_min, cache_expire_min,
    seconds_until_expire, top_channels, epg_quality, pct, bar,
)

CACHE_TTL = 3600  # 1h, comme config


class TestFmtUptime:
    def test_hours_always_shown(self):
        assert fmt_uptime(2 * 3600 + 5 * 60 + 9) == "2h05m09s"

    def test_zero(self):
        assert fmt_uptime(0) == "0h00m00s"

    def test_under_an_hour_keeps_hours(self):
        assert fmt_uptime(75) == "0h01m15s"

    def test_float_seconds_truncated(self):
        assert fmt_uptime(3661.9) == "1h01m01s"


class TestFmtDuration:
    def test_hours_shown_when_present(self):
        assert fmt_duration(2 * 3600 + 5 * 60 + 9) == "2h05m09s"

    def test_hours_suppressed_when_zero(self):
        assert fmt_duration(5 * 60 + 9) == "5min09s"

    def test_exactly_one_hour(self):
        assert fmt_duration(3600) == "1h00m00s"

    def test_seconds_only(self):
        assert fmt_duration(9) == "0min09s"


class TestCacheAgeExpire:
    def test_age_minutes(self):
        # chargé il y a 10 min
        assert cache_age_min(loaded_at=1000, now_ts=1000 + 600) == 10

    def test_expire_minutes_remaining(self):
        # TTL 60min, âgé de 10min → 50min restantes
        assert cache_expire_min(loaded_at=1000, now_ts=1000 + 600, ttl=CACHE_TTL) == 50

    def test_expire_clamped_to_zero(self):
        # âgé de 2h avec TTL 1h → 0 (pas négatif)
        assert cache_expire_min(loaded_at=1000, now_ts=1000 + 7200, ttl=CACHE_TTL) == 0

    def test_seconds_until_expire_positive(self):
        assert seconds_until_expire(loaded_at=1000, now_ts=1000 + 600, ttl=CACHE_TTL) == 3000

    def test_seconds_until_expire_negative_when_expired(self):
        assert seconds_until_expire(loaded_at=1000, now_ts=1000 + 7200, ttl=CACHE_TTL) == -3600


def _prog(channel):
    return ET.Element("programme", {"channel": channel})


class TestTopChannels:
    def test_counts_and_orders_desc(self):
        progs = [_prog("A.fr")] * 3 + [_prog("B.fr")] * 5 + [_prog("C.fr")]
        top = top_channels(progs)
        assert top == [("B.fr", 5), ("A.fr", 3), ("C.fr", 1)]

    def test_limit_applied(self):
        progs = [_prog("A.fr")] * 3 + [_prog("B.fr")] * 2 + [_prog("C.fr")]
        assert top_channels(progs, limit=2) == [("A.fr", 3), ("B.fr", 2)]

    def test_ignores_empty_channel_id(self):
        progs = [_prog(""), _prog("A.fr"), _prog("A.fr")]
        assert top_channels(progs) == [("A.fr", 2)]

    def test_empty_input(self):
        assert top_channels([]) == []


def _prog_full(channel="X.fr", desc=None, cat=False, new=False, icon=False):
    p = ET.Element("programme", {"channel": channel})
    if desc is not None:
        ET.SubElement(p, "desc").text = desc
    if cat:
        ET.SubElement(p, "category").text = "film"
    if new:
        ET.SubElement(p, "new")
    if icon:
        ET.SubElement(p, "icon")
    return p


class TestEpgQuality:
    def test_counts_all_dimensions(self):
        progs = [
            _prog_full(desc="Une vraie description", cat=True, new=True, icon=True),
            _prog_full(desc="   ", cat=True),       # desc vide après strip → non compté
            _prog_full(),                            # rien
        ]
        q = epg_quality(progs)
        assert q == {"total": 3, "desc": 1, "cat": 2, "new": 1, "img": 1}

    def test_empty(self):
        assert epg_quality([]) == {"total": 0, "desc": 0, "cat": 0, "new": 0, "img": 0}


class TestPct:
    def test_basic(self):
        assert pct(1, 4) == "25.0%"

    def test_zero_total_no_division_error(self):
        assert pct(0, 0) == "0.0%"

    def test_full(self):
        assert pct(10, 10) == "100.0%"


class TestBar:
    def test_half(self):
        assert bar(5, 10, w=10) == "█████░░░░░"

    def test_empty_when_zero_total(self):
        assert bar(0, 0, w=10) == "░" * 10

    def test_full(self):
        assert bar(10, 10, w=10) == "█" * 10
