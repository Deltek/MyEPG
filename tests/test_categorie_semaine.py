import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from analytics import (
    category_matches, make_category_filter, list_categories,
    matching_categories, suggest_categories, filter_day_programmes,
)

TZ_PARIS = ZoneInfo("Europe/Paris")


def prog(channel, start, stop, title, cats=(), new=False):
    p = ET.Element("programme", {"channel": channel, "start": start, "stop": stop})
    ET.SubElement(p, "title").text = title
    for c in cats:
        ET.SubElement(p, "category").text = c
    if new:
        ET.SubElement(p, "new")
    return p


def _utc(day, h, m=0, month=1):
    return f"2024{month:02d}{day:02d}{h:02d}{m:02d}00 +0000"


# ──────────────────────────────────────────────────────────────────────────────
# category_matches / make_category_filter — partiel, casse, accents
# ──────────────────────────────────────────────────────────────────────────────
class TestCategoryMatches:
    def test_partial_match(self):
        p = prog("TF1.fr", _utc(1, 10), _utc(1, 11), "X", cats=["Série documentaire"])
        assert category_matches(p, "documentaire")
        assert category_matches(p, "docu")

    def test_case_and_accents_insensitive(self):
        p = prog("TF1.fr", _utc(1, 10), _utc(1, 11), "X", cats=["Série"])
        assert category_matches(p, "serie")
        assert category_matches(p, "SÉRIE")

    def test_query_accents_against_plain_category(self):
        p = prog("TF1.fr", _utc(1, 10), _utc(1, 11), "X", cats=["Divertissement"])
        assert category_matches(p, "divertissément")

    def test_any_of_multiple_categories(self):
        p = prog("TF1.fr", _utc(1, 10), _utc(1, 11), "X", cats=["Jeunesse", "Dessin animé"])
        assert category_matches(p, "anime")
        assert category_matches(p, "jeunesse")

    def test_no_match(self):
        p = prog("TF1.fr", _utc(1, 10), _utc(1, 11), "X", cats=["Magazine"])
        assert not category_matches(p, "documentaire")

    def test_no_category(self):
        p = prog("TF1.fr", _utc(1, 10), _utc(1, 11), "X")
        assert not category_matches(p, "documentaire")

    def test_empty_or_punctuation_query_matches_nothing(self):
        p = prog("TF1.fr", _utc(1, 10), _utc(1, 11), "X", cats=["Magazine"])
        assert not category_matches(p, "")
        assert not category_matches(p, "!!!")

    def test_make_category_filter(self):
        f = make_category_filter("jeunesse")
        assert f(prog("TF1.fr", _utc(1, 10), _utc(1, 11), "X", cats=["Jeunesse"]))
        assert not f(prog("TF1.fr", _utc(1, 10), _utc(1, 11), "X", cats=["Film"]))


# ──────────────────────────────────────────────────────────────────────────────
# list_categories — fenêtre, comptage, dédoublonnage
# ──────────────────────────────────────────────────────────────────────────────
class TestListCategories:
    START = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    END   = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)

    def test_counts_and_sort(self):
        progs = [
            prog("A", _utc(1, 10), _utc(1, 11), "a", cats=["Documentaire"]),
            prog("A", _utc(1, 11), _utc(1, 12), "b", cats=["documentaire"]),
            prog("B", _utc(1, 12), _utc(1, 13), "c", cats=["Jeunesse"]),
        ]
        assert list_categories(progs, self.START, self.END) == [("Documentaire", 2), ("Jeunesse", 1)]

    def test_same_category_twice_in_one_prog_counts_once(self):
        progs = [prog("A", _utc(1, 10), _utc(1, 11), "a", cats=["Série", "serie"])]
        assert list_categories(progs, self.START, self.END) == [("Série", 1)]

    def test_outside_window_excluded(self):
        progs = [
            prog("A", _utc(2, 10), _utc(2, 11), "demain", cats=["Magazine"]),
            prog("A", _utc(1, 10), _utc(1, 11), "auj", cats=["Film"]),
        ]
        assert list_categories(progs, self.START, self.END) == [("Film", 1)]

    def test_overlapping_window_start_included(self):
        progs = [prog("A", "20231231230000 +0000", _utc(1, 1), "nuit", cats=["Film"])]
        assert list_categories(progs, self.START, self.END) == [("Film", 1)]

    def test_empty_and_invalid(self):
        progs = [
            prog("A", "bad", _utc(1, 11), "x", cats=["Film"]),
            prog("A", _utc(1, 10), _utc(1, 11), "y", cats=["  "]),
        ]
        assert list_categories(progs, self.START, self.END) == []


class TestMatchingAndSuggestions:
    LABELS = ["Documentaire", "Série documentaire", "Jeunesse", "Divertissement", "Magazine"]

    def test_matching_partial(self):
        assert matching_categories("docu", self.LABELS) == ["Documentaire", "Série documentaire"]

    def test_matching_accents(self):
        assert matching_categories("serie", self.LABELS) == ["Série documentaire"]

    def test_matching_unknown(self):
        assert matching_categories("cuisine", self.LABELS) == []

    def test_matching_empty_query(self):
        assert matching_categories("", self.LABELS) == []

    def test_suggestions_for_typo(self):
        assert "Documentaire" in suggest_categories("documantaire", self.LABELS)

    def test_suggestions_none_for_garbage(self):
        assert suggest_categories("zzzzqqq", self.LABELS) == []


# ──────────────────────────────────────────────────────────────────────────────
# filter_day_programmes / build_channel_day — bornes de journée Europe/Paris
# ──────────────────────────────────────────────────────────────────────────────
# Journée Paris du 2024-01-02 (UTC+1) = [2024-01-01 23:00 UTC, 2024-01-02 23:00 UTC)
DAY_START = datetime(2024, 1, 1, 23, 0, tzinfo=timezone.utc)
DAY_END   = datetime(2024, 1, 2, 23, 0, tzinfo=timezone.utc)


class TestFilterDayProgrammes:
    def test_bounds_inclusive_start_exclusive_end(self):
        progs = [
            prog("TF1.fr", _utc(1, 23), _utc(2, 0), "minuit"),    # 00:00 Paris → inclus
            prog("TF1.fr", _utc(2, 23), _utc(3, 0), "minuit J+1"),  # 00:00 Paris J+1 → exclu
            prog("TF1.fr", _utc(1, 22), _utc(1, 23), "veille"),   # finit pile à minuit → exclu
        ]
        titles = [r["title"] for r in filter_day_programmes(progs, DAY_START, DAY_END)]
        assert titles == ["minuit"]

    def test_programme_spanning_midnight_included(self):
        progs = [prog("TF1.fr", _utc(1, 22, 30), _utc(1, 23, 30), "à cheval")]
        assert [r["title"] for r in filter_day_programmes(progs, DAY_START, DAY_END)] == ["à cheval"]

    def test_sorted_and_keys(self):
        progs = [
            prog("TF1.fr", _utc(2, 12), _utc(2, 13), "B", new=True),
            prog("TF1.fr", _utc(2, 8), _utc(2, 9), "A ᴺᵉʷ"),
        ]
        res = filter_day_programmes(progs, DAY_START, DAY_END)
        assert [r["title"] for r in res] == ["A", "B"]
        assert res[1]["new"] is True
        for key in ("start", "stop", "title", "desc", "new"):
            assert key in res[0]

    def test_now_excludes_finished(self):
        now = datetime(2024, 1, 2, 10, 30, tzinfo=timezone.utc)
        progs = [
            prog("TF1.fr", _utc(2, 8), _utc(2, 9), "fini"),
            prog("TF1.fr", _utc(2, 10), _utc(2, 11), "en cours"),
            prog("TF1.fr", _utc(2, 12), _utc(2, 13), "à venir"),
        ]
        titles = [r["title"] for r in filter_day_programmes(progs, DAY_START, DAY_END, now)]
        assert titles == ["en cours", "à venir"]

    def test_invalid_times_skipped(self):
        progs = [prog("TF1.fr", "bad", _utc(2, 9), "x")]
        assert filter_day_programmes(progs, DAY_START, DAY_END) == []


class TestDayWindow:
    def test_winter_day_bounds(self):
        from builders import day_window
        fixed = datetime(2024, 1, 1, 18, 0, tzinfo=TZ_PARIS)
        with patch("builders.now_paris", return_value=fixed):
            start, end, _ = day_window(1)
        assert start == DAY_START and end == DAY_END

    def test_dst_spring_day_is_23h(self):
        from builders import day_window
        fixed = datetime(2024, 3, 30, 12, 0, tzinfo=TZ_PARIS)
        with patch("builders.now_paris", return_value=fixed):
            start, end, _ = day_window(1)  # dimanche 31 mars 2024 (passage à l'heure d'été)
        assert start == datetime(2024, 3, 30, 23, 0, tzinfo=timezone.utc)
        assert end   == datetime(2024, 3, 31, 22, 0, tzinfo=timezone.utc)

    def test_dst_autumn_day_is_25h(self):
        from builders import day_window
        fixed = datetime(2024, 10, 26, 12, 0, tzinfo=TZ_PARIS)
        with patch("builders.now_paris", return_value=fixed):
            start, end, _ = day_window(1)  # dimanche 27 octobre 2024
        assert start == datetime(2024, 10, 26, 22, 0, tzinfo=timezone.utc)
        assert end   == datetime(2024, 10, 27, 23, 0, tzinfo=timezone.utc)


class TestBuildChannelDay:
    XML = """<tv>
      <channel id="TF1.fr"><display-name>FR - TF1</display-name></channel>
      <programme start="20240102080000 +0000" stop="20240102090000 +0000" channel="TF1.fr"><title>Matin J+1</title></programme>
      <programme start="20240102080000 +0000" stop="20240102090000 +0000" channel="M6.fr"><title>Autre chaîne</title></programme>
      <programme start="20240103080000 +0000" stop="20240103090000 +0000" channel="TF1.fr"><title>Matin J+2</title></programme>
    </tv>"""

    def test_only_channel_and_day(self):
        from builders import build_channel_day
        root  = ET.fromstring(self.XML)
        fixed = datetime(2024, 1, 1, 18, 0, tzinfo=TZ_PARIS)
        now   = datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)
        with patch("builders.now_paris", return_value=fixed):
            res, jour_label, now_utc = build_channel_day(root, "TF1.fr", 1, now_utc=now)
        assert [r["title"] for r in res] == ["Matin J+1"]
        assert now_utc == now
        assert isinstance(jour_label, str)


class TestBuildTypeResultsFullDay:
    XML = """<tv>
      <channel id="TF1.fr"><display-name>FR - TF1</display-name></channel>
      <programme start="20240101080000 +0000" stop="20240101090000 +0000" channel="TF1.fr">
        <title>Dessin animé matin</title><category>Jeunesse</category></programme>
      <programme start="20240101190000 +0000" stop="20240101200000 +0000" channel="TF1.fr">
        <title>Docu soir</title><category>Documentaire</category></programme>
    </tv>"""

    def test_full_day_window_with_category_filter(self):
        from builders import build_type_results
        root  = ET.fromstring(self.XML)
        fixed = datetime(2024, 1, 1, 6, 0, tzinfo=TZ_PARIS)
        with patch("builders.now_paris", return_value=fixed):
            res, _, _ = build_type_results(root, 0, make_category_filter("jeunesse"),
                                           ch_set={"TF1.fr"}, hour_start=0, hour_end=0)
            soir, _, _ = build_type_results(root, 0, make_category_filter("jeunesse"), ch_set={"TF1.fr"})
        assert [r["title"] for r in res] == ["Dessin animé matin"]
        assert soir == []  # fenêtre par défaut 19h-00h inchangée


class TestSemaineCallbackData:
    def test_prefix_and_length(self):
        from builders import semaine_callback_prefix
        assert semaine_callback_prefix("fr", "TF1.fr") == "sem:fr:TF1.fr"
        assert semaine_callback_prefix("fr", "X" * 80) is None

    def test_all_aliases_fit_64_bytes(self):
        from builders import semaine_callback_prefix
        from config import CH_ALIASES
        for cid in set(CH_ALIASES.values()):
            country = "gb" if cid.endswith(".uk") else "fr"
            prefix  = semaine_callback_prefix(country, cid)
            assert prefix is not None, cid
            assert len(f"{prefix}:6".encode("utf-8")) <= 64

    def test_callback_parsing_roundtrip(self):
        from builders import semaine_callback_prefix
        data = f"{semaine_callback_prefix('fr', 'CANAL+SPORT.fr')}:3"
        _, country, rest = data.split(":", 2)
        cid, day = rest.rsplit(":", 1)
        assert (country, cid, day) == ("fr", "CANAL+SPORT.fr", "3")

    def test_prefixes_not_captured_by_existing_patterns(self):
        import re
        existing = [r"^now:[a-z]+$", r"^now_ch:", r"^now_all:", r"^soir:", r"^prime_", r"^nuit:",
                    r"^film", r"^series", r"^sport_", r"^sporttnt:", r"^nouveautes_day:",
                    r"^nouveautes:", r"^list:", r"^search:", r"^search_page:", r"^admin_logs:"]
        for data in ("cat:fr:0", "sem:fr:TF1.fr:6"):
            assert not any(re.match(p, data) for p in existing), data
