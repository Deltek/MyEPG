import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from analytics import compute_doublons, compute_trending, search_programmes

# Fenêtre de référence : now = 2024-01-01 17:00 UTC
NOW = datetime(2024, 1, 1, 17, 0, 0, tzinfo=timezone.utc)


def _utc(h, m=0, day=1):
    return f"2024010{day}{h:02d}{m:02d}00 +0000"


def prog(channel, start, stop, title, desc=""):
    """Crée un <programme> ElementTree."""
    p = ET.Element("programme", {"channel": channel, "start": start, "stop": stop})
    t = ET.SubElement(p, "title")
    t.text = title
    if desc:
        d = ET.SubElement(p, "desc")
        d.text = desc
    return p


CHANNELS = {"TF1.fr": "FR - TF1", "France2.fr": "FR - France 2", "M6.fr": "FR - M6"}


# ──────────────────────────────────────────────────────────────────────────────
# compute_doublons — fenêtre [NOW, NOW+6h) = [17:00, 23:00)
# ──────────────────────────────────────────────────────────────────────────────
class TestComputeDoublons:
    def setup_method(self):
        self.end = datetime(2024, 1, 1, 23, 0, 0, tzinfo=timezone.utc)

    def test_same_title_two_channels_is_doublon(self):
        progs = [
            prog("TF1.fr",     _utc(18), _utc(20), "Match Foot"),
            prog("France2.fr", _utc(19), _utc(21), "Match Foot"),
        ]
        res = compute_doublons(progs, CHANNELS, NOW, self.end)
        assert len(res) == 1
        title, chans = res[0]
        assert title == "Match Foot"
        assert len(chans) == 2

    def test_single_channel_not_doublon(self):
        progs = [prog("TF1.fr", _utc(18), _utc(20), "Solo Show")]
        res = compute_doublons(progs, CHANNELS, NOW, self.end)
        assert res == []

    def test_before_window_excluded(self):
        # start 16:00 < now 17:00
        progs = [
            prog("TF1.fr",     _utc(16), _utc(18), "Avant"),
            prog("France2.fr", _utc(16), _utc(18), "Avant"),
        ]
        res = compute_doublons(progs, CHANNELS, NOW, self.end)
        assert res == []

    def test_start_exactly_at_now_included(self):
        # borne basse inclusive : now_utc <= start
        progs = [
            prog("TF1.fr",     _utc(17), _utc(19), "Pile Maintenant"),
            prog("France2.fr", _utc(17), _utc(19), "Pile Maintenant"),
        ]
        res = compute_doublons(progs, CHANNELS, NOW, self.end)
        assert len(res) == 1

    def test_start_exactly_at_end_excluded(self):
        # borne haute exclusive : start < end_utc
        progs = [
            prog("TF1.fr",     _utc(23), _utc(23, 30), "Pile Fin"),
            prog("France2.fr", _utc(23), _utc(23, 30), "Pile Fin"),
        ]
        res = compute_doublons(progs, CHANNELS, NOW, self.end)
        assert res == []

    def test_same_title_twice_same_channel_counts_twice(self):
        # comportement préservé : 2 diffusions même chaîne = 2 labels
        progs = [
            prog("TF1.fr", _utc(18), _utc(19), "Rediff"),
            prog("TF1.fr", _utc(20), _utc(21), "Rediff"),
        ]
        res = compute_doublons(progs, CHANNELS, NOW, self.end)
        assert len(res) == 1
        assert len(res[0][1]) == 2

    def test_sorted_by_channel_count_desc(self):
        progs = [
            prog("TF1.fr",     _utc(18), _utc(19), "Deux"),
            prog("France2.fr", _utc(18), _utc(19), "Deux"),
            prog("TF1.fr",     _utc(19), _utc(20), "Trois"),
            prog("France2.fr", _utc(19), _utc(20), "Trois"),
            prog("M6.fr",      _utc(19), _utc(20), "Trois"),
        ]
        res = compute_doublons(progs, CHANNELS, NOW, self.end)
        assert [t for t, _ in res] == ["Trois", "Deux"]


# ──────────────────────────────────────────────────────────────────────────────
# compute_trending — fenêtre overlap [NOW, NOW+24h)
# ──────────────────────────────────────────────────────────────────────────────
class TestComputeTrending:
    def setup_method(self):
        self.end = datetime(2024, 1, 2, 17, 0, 0, tzinfo=timezone.utc)

    def test_title_aired_twice_is_trending(self):
        progs = [
            prog("TF1.fr",     _utc(18), _utc(19), "Série A"),
            prog("France2.fr", _utc(20), _utc(21), "Série A"),
        ]
        res = compute_trending(progs, NOW, self.end)
        assert ("Série A", 2) in res

    def test_single_airing_filtered_out(self):
        progs = [prog("TF1.fr", _utc(18), _utc(19), "Unique")]
        res = compute_trending(progs, NOW, self.end)
        assert res == []

    def test_already_started_but_running_included(self):
        # #17/#18 : démarré avant now mais stop > now → DOIT être compté
        progs = [
            prog("TF1.fr",     _utc(16), _utc(18), "En Cours"),  # 16:00→18:00, now=17:00
            prog("France2.fr", _utc(19), _utc(20), "En Cours"),
        ]
        res = compute_trending(progs, NOW, self.end)
        assert ("En Cours", 2) in res

    def test_ended_before_now_excluded(self):
        # stop 17:00 == now → stop <= now_utc → exclu
        progs = [
            prog("TF1.fr",     _utc(15), _utc(17), "Fini"),
            prog("France2.fr", _utc(15), _utc(17), "Fini"),
        ]
        res = compute_trending(progs, NOW, self.end)
        assert res == []

    def test_starts_at_end_excluded(self):
        # start == end_utc → start >= end_utc → exclu
        progs = [
            prog("TF1.fr",     _utc(17, day=2), _utc(18, day=2), "Trop Tard"),
            prog("France2.fr", _utc(17, day=2), _utc(18, day=2), "Trop Tard"),
        ]
        res = compute_trending(progs, NOW, self.end)
        assert res == []

    def test_top_n_cap_applied(self):
        progs = [
            prog("TF1.fr",     _utc(18), _utc(19), "A"),
            prog("France2.fr", _utc(18), _utc(19), "A"),
            prog("TF1.fr",     _utc(19), _utc(20), "B"),
            prog("France2.fr", _utc(19), _utc(20), "B"),
        ]
        res = compute_trending(progs, NOW, self.end, top_n=1)
        assert len(res) == 1


# ──────────────────────────────────────────────────────────────────────────────
# search_programmes
# ──────────────────────────────────────────────────────────────────────────────
class TestSearchProgrammes:
    def test_match_in_title(self):
        progs = [prog("TF1.fr", _utc(18), _utc(20), "Star Wars")]
        res = search_programmes(progs, CHANNELS, "star")
        assert len(res) == 1
        assert res[0]["title"] == "Star Wars"

    def test_match_in_desc(self):
        progs = [prog("TF1.fr", _utc(18), _utc(20), "Film X", desc="Avec Luke Skywalker")]
        res = search_programmes(progs, CHANNELS, "skywalker")
        assert len(res) == 1

    def test_accent_and_case_insensitive(self):
        progs = [prog("TF1.fr", _utc(18), _utc(20), "Les Misérables")]
        res = search_programmes(progs, CHANNELS, "MISERABLES")
        assert len(res) == 1

    def test_no_match_excluded(self):
        progs = [prog("TF1.fr", _utc(18), _utc(20), "Documentaire")]
        res = search_programmes(progs, CHANNELS, "introuvable")
        assert res == []

    def test_results_sorted_by_start(self):
        progs = [
            prog("TF1.fr",     _utc(21), _utc(22), "Match tardif"),
            prog("France2.fr", _utc(18), _utc(19), "Match tôt"),
        ]
        res = search_programmes(progs, CHANNELS, "match")
        assert [r["title"] for r in res] == ["Match tôt", "Match tardif"]

    def test_invalid_time_skipped(self):
        progs = [
            prog("TF1.fr", "bad-time", "also-bad", "Match cassé"),
            prog("France2.fr", _utc(18), _utc(19), "Match ok"),
        ]
        res = search_programmes(progs, CHANNELS, "match")
        assert [r["title"] for r in res] == ["Match ok"]
