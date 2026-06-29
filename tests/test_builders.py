import xml.etree.ElementTree as ET
from datetime import datetime
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


class TestBuildNuitResults:
    def test_returns_list_and_metadata(self):
        from builders import build_nuit_results
        root = make_root()
        with patch("builders.now_paris", return_value=FIXED_NOW):
            results, jour_label, now_utc = build_nuit_results(root, 0, ch_list=CH_TNT_TEST)
        assert isinstance(results, list)
        assert isinstance(jour_label, str)
