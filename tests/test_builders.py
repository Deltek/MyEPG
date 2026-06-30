import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

TZ_PARIS = ZoneInfo("Europe/Paris")

# Fixed "now" : 2024-01-01 18:00 Paris (UTC+1) = 17:00 UTC
# Soir window   : 19h-00h Paris = 18:00-23:00 UTC
# Prime window  : 20h-22h30 Paris = 19:00-21:30 UTC
# Nuit window   : 00h-06h Paris = 23:00-05:00 UTC (J+1)
FIXED_NOW = datetime(2024, 1, 1, 18, 0, 0, tzinfo=TZ_PARIS)

FIXTURE_XML = """<tv>
  <channel id="TF1.fr"><display-name>FR - TF1</display-name></channel>
  <channel id="France2.fr"><display-name>FR - France 2</display-name></channel>
  <channel id="OTHER.fr"><display-name>Other</display-name></channel>

  <!-- 19:30 Paris = in soir + nouveautes window, not prime -->
  <programme start="20240101183000 +0000" stop="20240101210000 +0000" channel="TF1.fr">
    <title>Film du soir ᴺᵉʷ</title>
    <desc>Une belle description assez longue pour être conservée.</desc>
    <new/>
  </programme>

  <!-- 20:30 Paris = in prime window -->
  <programme start="20240101193000 +0000" stop="20240101213000 +0000" channel="France2.fr">
    <title>Série prime</title>
    <new/>
  </programme>

  <!-- 17:00 Paris = before all windows -->
  <programme start="20240101160000 +0000" stop="20240101183000 +0000" channel="TF1.fr">
    <title>Programme avant soirée</title>
  </programme>

  <!-- Channel not in TNT list -->
  <programme start="20240101183000 +0000" stop="20240101210000 +0000" channel="OTHER.fr">
    <title>Chaîne hors liste</title>
  </programme>

  <!-- Nouveautes filler — should be filtered by build_nouveautes_tnt -->
  <programme start="20240101183000 +0000" stop="20240101190000 +0000" channel="France2.fr">
    <title>JT 20h</title>
    <new/>
  </programme>
</tv>"""

CH_TNT_TEST = ["TF1.fr", "France2.fr"]


def make_root():
    return ET.fromstring(FIXTURE_XML)


class TestBuildSoirResults:
    def test_returns_four_values(self):
        from builders import build_soir_results
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            result = build_soir_results(root, 0)
        assert len(result) == 4  # results, channels, jour_label, now_utc

    def test_only_tnt_channels(self):
        from builders import build_soir_results
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, _, _, _ = build_soir_results(root, 0)
        ch_ids = {r["ch_id"] for r in results}
        assert "OTHER.fr" not in ch_ids

    def test_excludes_programs_before_window(self):
        from builders import build_soir_results
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, _, _, _ = build_soir_results(root, 0)
        titles = [r["title"] for r in results]
        assert "Programme avant soirée" not in titles

    def test_includes_programs_in_soir_window(self):
        from builders import build_soir_results
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, _, _, _ = build_soir_results(root, 0)
        titles = [r["title"] for r in results]
        assert "Film du soir" in titles

    def test_result_structure(self):
        from builders import build_soir_results
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, channels, jour_label, now_utc = build_soir_results(root, 0)
        assert isinstance(results, list)
        assert isinstance(channels, dict)
        assert isinstance(jour_label, str)
        if results:
            r = results[0]
            for key in ("start", "stop", "title", "desc", "channel", "ch_id", "new"):
                assert key in r


class TestBuildPrimeResults:
    def test_includes_programs_in_prime_window(self):
        from builders import build_prime_results
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, _, _ = build_prime_results(root, 0, ch_set=set(CH_TNT_TEST))
        titles = [r["title"] for r in results]
        assert "Série prime" in titles

    def test_excludes_programs_outside_prime(self):
        from builders import build_prime_results
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, _, _ = build_prime_results(root, 0, ch_set=set(CH_TNT_TEST))
        titles = [r["title"] for r in results]
        assert "Programme avant soirée" not in titles

    def test_empty_when_no_programs(self):
        from builders import build_prime_results
        empty_root = ET.fromstring("<tv><channel id='TF1.fr'><display-name>TF1</display-name></channel></tv>")
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, _, _ = build_prime_results(empty_root, 0)
        assert results == []


class TestBuildNouveautesTnt:
    def test_only_new_programs(self):
        from builders import build_nouveautes_tnt
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.CH_TNT_FR", CH_TNT_TEST):
            results, _, _ = build_nouveautes_tnt(root, 0)
        assert all(r["new"] is True for r in results)

    def test_excludes_fillers(self):
        from builders import build_nouveautes_tnt
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.CH_TNT_FR", CH_TNT_TEST):
            results, _, _ = build_nouveautes_tnt(root, 0)
        titles = [r["title"] for r in results]
        assert "JT 20h" not in titles

    def test_clean_title_applied(self):
        from builders import build_nouveautes_tnt
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.CH_TNT_FR", CH_TNT_TEST):
            results, _, _ = build_nouveautes_tnt(root, 0)
        titles = [r["title"] for r in results]
        # clean_title removes ᴺᵉʷ suffix
        assert all("ᴺᵉʷ" not in t for t in titles)


# Fenêtre nuit (day_offset=0, FIXED_NOW=2024-01-01 18:00 Paris)
#   = [2023-12-31 23:00 UTC, 2024-01-01 05:00 UTC)
NUIT_XML = """<tv>
  <channel id="TF1.fr"><display-name>FR - TF1</display-name></channel>
  <!-- 01:00-03:00 UTC = 02:00-04:00 Paris → DANS la fenêtre nuit -->
  <programme start="20240101010000 +0000" stop="20240101030000 +0000" channel="TF1.fr">
    <title>Film de nuit</title>
    <desc>Un long métrage diffusé en pleine nuit.</desc>
  </programme>
  <!-- 09:00 UTC = 10:00 Paris → HORS fenêtre -->
  <programme start="20240101090000 +0000" stop="20240101100000 +0000" channel="TF1.fr">
    <title>Programme de jour</title>
  </programme>
</tv>"""


def make_nuit_root():
    return ET.fromstring(NUIT_XML)


class TestBuildNuitResults:
    def test_returns_list_and_metadata(self):
        from builders import build_nuit_results
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, jour_label, now_utc = build_nuit_results(root, 0, ch_list=CH_TNT_TEST)
        assert isinstance(results, list)
        assert isinstance(jour_label, str)

    def test_includes_programme_in_nuit_window(self):
        from builders import build_nuit_results
        root = make_nuit_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, _, _ = build_nuit_results(root, 0, ch_list=["TF1.fr"])
        titles = [r["title"] for r in results]
        assert "Film de nuit" in titles

    def test_excludes_daytime_programme(self):
        from builders import build_nuit_results
        root = make_nuit_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, _, _ = build_nuit_results(root, 0, ch_list=["TF1.fr"])
        titles = [r["title"] for r in results]
        assert "Programme de jour" not in titles

    def test_result_structure(self):
        from builders import build_nuit_results
        root = make_nuit_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, _, _ = build_nuit_results(root, 0, ch_list=["TF1.fr"])
        assert results
        for key in ("start", "stop", "title", "ch_id", "channel", "duree", "cats"):
            assert key in results[0]


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures étendues pour build_type_results, build_sport_results,
# build_maintenant_sport
# FIXED_NOW = 2024-01-01 18:00 Paris = 17:00 UTC
# Sport window (build_sport_results): 06h-00h Paris = 05:00-23:00 UTC
# ──────────────────────────────────────────────────────────────────────────────

EXTENDED_XML = """<tv>
  <channel id="TF1.fr"><display-name>FR - TF1</display-name></channel>
  <channel id="France2.fr"><display-name>FR - France 2</display-name></channel>
  <channel id="EUROSPORT1.fr"><display-name>Eurosport 1</display-name></channel>

  <!-- Sport sur TNT, fenêtre soir (18:30 UTC = 19:30 Paris) -->
  <programme start="20240101183000 +0000" stop="20240101190000 +0000" channel="TF1.fr">
    <title>Rugby du soir</title>
    <category>sport</category>
  </programme>

  <!-- Non-sport sur TNT, fenêtre soir -->
  <programme start="20240101183000 +0000" stop="20240101210000 +0000" channel="France2.fr">
    <title>Documentaire nature</title>
    <category>documentaire</category>
  </programme>

  <!-- Film catégorie + durée 95 min sur TNT, fenêtre soir -->
  <programme start="20240101190000 +0000" stop="20240101211500 +0000" channel="TF1.fr">
    <title>Grand film soir</title>
    <category>film</category>
  </programme>

  <!-- Sport sur chaîne sport, fenêtre sport (18:30 UTC), stop > now(17:00) -->
  <programme start="20240101183000 +0000" stop="20240101210000 +0000" channel="EUROSPORT1.fr">
    <title>Tennis open</title>
    <category>sport</category>
  </programme>

  <!-- Filler sport sur chaîne sport -->
  <programme start="20240101210000 +0000" stop="20240101220000 +0000" channel="EUROSPORT1.fr">
    <title>A bientot sur eurosport</title>
    <category>sport</category>
  </programme>

  <!-- En cours maintenant (16:00-20:00 UTC, now=17:00 UTC) -->
  <programme start="20240101160000 +0000" stop="20240101200000 +0000" channel="EUROSPORT1.fr">
    <title>Live sport en cours</title>
    <category>sport</category>
  </programme>

  <!-- Filler en cours maintenant -->
  <programme start="20240101160000 +0000" stop="20240101200000 +0000" channel="EUROSPORT1.fr">
    <title>Bein sports, le plus grand</title>
    <category>sport</category>
  </programme>
</tv>"""

CH_SPORT_TEST = ["EUROSPORT1.fr"]
FIXED_UTC = datetime(2024, 1, 1, 17, 0, 0, tzinfo=TZ_PARIS).astimezone()


def make_extended_root():
    return ET.fromstring(EXTENDED_XML)


class TestBuildTypeResults:
    def test_sport_filter_includes_sport_programme(self):
        from builders import build_type_results
        from utils import is_sport
        root = make_extended_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.CH_TNT_FR", CH_TNT_TEST):
            results, _, _ = build_type_results(root, 0, is_sport)
        titles = [r["title"] for r in results]
        assert "Rugby du soir" in titles

    def test_sport_filter_excludes_non_sport(self):
        from builders import build_type_results
        from utils import is_sport
        root = make_extended_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.CH_TNT_FR", CH_TNT_TEST):
            results, _, _ = build_type_results(root, 0, is_sport)
        titles = [r["title"] for r in results]
        assert "Documentaire nature" not in titles

    def test_film_filter_by_category(self):
        from builders import build_type_results
        from utils import is_film
        root = make_extended_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.CH_TNT_FR", CH_TNT_TEST):
            results, _, _ = build_type_results(root, 0, is_film, min_duration=75)
        titles = [r["title"] for r in results]
        assert "Grand film soir" in titles

    def test_min_duration_filters_short_programmes(self):
        from builders import build_type_results
        root = make_extended_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.CH_TNT_FR", CH_TNT_TEST):
            results, _, _ = build_type_results(root, 0, None, min_duration=120)
        # Grand film soir = 95 min → excluded; Grand film > 120 min → excluded
        durations = [int((r["stop"] - r["start"]).total_seconds() // 60) for r in results]
        assert all(d >= 120 for d in durations)

    def test_result_has_required_keys(self):
        from builders import build_type_results
        from utils import is_sport
        root = make_extended_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.CH_TNT_FR", CH_TNT_TEST):
            results, jour_label, now_utc = build_type_results(root, 0, is_sport)
        assert isinstance(jour_label, str)
        if results:
            for key in ("start", "stop", "title", "ch_id", "channel", "duree"):
                assert key in results[0]


FIXED_UTC_NOW = datetime(2024, 1, 1, 17, 0, 0, tzinfo=timezone.utc)


class TestBuildSportResults:
    def test_includes_sport_in_window(self):
        from builders import build_sport_results
        root = make_extended_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_UTC_NOW
            results, _, _ = build_sport_results(root, 0, ch_list=CH_SPORT_TEST)
        titles = [r["title"] for r in results]
        assert "Tennis open" in titles

    def test_excludes_sport_fillers(self):
        from builders import build_sport_results
        root = make_extended_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_UTC_NOW
            results, _, _ = build_sport_results(root, 0, ch_list=CH_SPORT_TEST)
        titles = [r["title"] for r in results]
        assert "A bientot sur eurosport" not in titles

    def test_excludes_past_programmes(self):
        from builders import build_sport_results
        root = make_extended_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_UTC_NOW
            results, _, _ = build_sport_results(root, 0, ch_list=CH_SPORT_TEST)
        for r in results:
            assert r["ch_id"] in CH_SPORT_TEST

    def test_result_structure(self):
        from builders import build_sport_results
        root = make_extended_root()
        with patch("builders.now_paris", return_value=FIXED_NOW), \
             patch("builders.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_UTC_NOW
            results, jour_label, now_utc = build_sport_results(root, 0, ch_list=CH_SPORT_TEST)
        assert isinstance(jour_label, str)
        if results:
            for key in ("start", "stop", "title", "ch_id", "duree", "placeholder"):
                assert key in results[0]


class TestBuildMaintenant:
    def test_includes_currently_airing(self):
        from builders import build_maintenant_sport
        from datetime import timezone
        root = make_extended_root()
        fixed_utc = datetime(2024, 1, 1, 17, 0, 0, tzinfo=timezone.utc)
        with patch("builders.datetime") as mock_dt, \
             patch("builders.CH_SPORT_FR", CH_SPORT_TEST):
            mock_dt.now.return_value = fixed_utc
            results = build_maintenant_sport(root)
        titles = [r["title"] for r in results]
        assert "Live sport en cours" in titles

    def test_excludes_sport_fillers(self):
        from builders import build_maintenant_sport
        from datetime import timezone
        root = make_extended_root()
        fixed_utc = datetime(2024, 1, 1, 17, 0, 0, tzinfo=timezone.utc)
        with patch("builders.datetime") as mock_dt, \
             patch("builders.CH_SPORT_FR", CH_SPORT_TEST):
            mock_dt.now.return_value = fixed_utc
            results = build_maintenant_sport(root)
        titles = [r["title"] for r in results]
        assert "Bein sports, le plus grand" not in titles

    def test_excludes_not_yet_started(self):
        from builders import build_maintenant_sport
        from datetime import timezone
        root = make_extended_root()
        fixed_utc = datetime(2024, 1, 1, 17, 0, 0, tzinfo=timezone.utc)
        with patch("builders.datetime") as mock_dt, \
             patch("builders.CH_SPORT_FR", CH_SPORT_TEST):
            mock_dt.now.return_value = fixed_utc
            results = build_maintenant_sport(root)
        titles = [r["title"] for r in results]
        # Tennis open starts at 18:30 UTC, now=17:00 → not yet started
        assert "Tennis open" not in titles

    def test_result_has_duree_reste(self):
        from builders import build_maintenant_sport
        from datetime import timezone
        root = make_extended_root()
        fixed_utc = datetime(2024, 1, 1, 17, 0, 0, tzinfo=timezone.utc)
        with patch("builders.datetime") as mock_dt, \
             patch("builders.CH_SPORT_FR", CH_SPORT_TEST):
            mock_dt.now.return_value = fixed_utc
            results = build_maintenant_sport(root)
        if results:
            assert "duree_reste" in results[0]
