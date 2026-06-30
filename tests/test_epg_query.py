import xml.etree.ElementTree as ET

import epg_loader
from epg_query import get_programmes_for_channel

# Year 2099 timestamps ensure programs are in the future (get_programmes_for_channel
# filters out past programs with stop <= now)
FIXTURE_XML = """<tv>
  <channel id="TF1.fr"><display-name>FR - TF1</display-name></channel>
  <channel id="M6.fr"><display-name>FR - M6</display-name></channel>
  <programme start="20990101190000 +0000" stop="20990101210000 +0000" channel="TF1.fr">
    <title>Programme A</title>
    <desc>Description du programme A.</desc>
    <new/>
  </programme>
  <programme start="20990101210000 +0000" stop="20990101220000 +0000" channel="TF1.fr">
    <title>Programme B</title>
  </programme>
  <programme start="20990101190000 +0000" stop="20990101210000 +0000" channel="M6.fr">
    <title>Programme M6</title>
  </programme>
  <programme start="20240101190000 +0000" stop="20240101210000 +0000" channel="TF1.fr">
    <title>Programme passé</title>
  </programme>
</tv>"""


def make_root():
    return ET.fromstring(FIXTURE_XML)


class TestGetProgrammesForChannel:
    def test_returns_only_requested_channel(self):
        root = make_root()
        results = get_programmes_for_channel(root, "TF1.fr")
        titles = [r["title"] for r in results]
        assert "Programme A" in titles
        assert "Programme B" in titles
        assert "Programme M6" not in titles

    def test_excludes_past_programmes(self):
        root = make_root()
        results = get_programmes_for_channel(root, "TF1.fr")
        titles = [r["title"] for r in results]
        assert "Programme passé" not in titles

    def test_respects_limit(self):
        root = make_root()
        results = get_programmes_for_channel(root, "TF1.fr", limit=1)
        assert len(results) == 1

    def test_empty_for_unknown_channel(self):
        root = make_root()
        assert get_programmes_for_channel(root, "Unknown.fr") == []

    def test_result_has_required_keys(self):
        root = make_root()
        results = get_programmes_for_channel(root, "TF1.fr")
        assert len(results) > 0
        prog = results[0]
        for key in ("start", "stop", "title", "desc", "new"):
            assert key in prog

    def test_new_flag_detected(self):
        root = make_root()
        results = get_programmes_for_channel(root, "TF1.fr")
        prog_a = next(r for r in results if r["title"] == "Programme A")
        prog_b = next(r for r in results if r["title"] == "Programme B")
        assert prog_a["new"] is True
        assert prog_b["new"] is False


class TestGetProgrammesIndexBranch:
    """Exerce la branche index-cache (et non le fallback root.findall)."""

    def teardown_method(self):
        epg_loader.reset_cache()  # ne pas polluer les autres tests

    def test_uses_index_not_root(self):
        # root VIDE mais index peuplé → si les résultats existent, c'est l'index qui sert
        empty_root = ET.fromstring("<tv></tv>")
        full_root  = make_root()
        index = {"TF1.fr": full_root.findall("programme")}
        epg_loader._cache["fr"]["index"] = index
        results = get_programmes_for_channel(empty_root, "TF1.fr", country="fr")
        titles = [r["title"] for r in results]
        assert "Programme A" in titles  # vient de l'index, pas du root vide

    def test_index_unknown_channel_empty(self):
        epg_loader._cache["fr"]["index"] = {"TF1.fr": make_root().findall("programme")}
        assert get_programmes_for_channel(ET.fromstring("<tv></tv>"), "M6.fr", country="fr") == []

    def test_missing_start_stop_skipped(self):
        # programme sans start/stop dans l'index → ignoré sans erreur
        bad = ET.Element("programme", {"channel": "TF1.fr"})  # ni start ni stop
        ET.SubElement(bad, "title").text = "Sans horaire"
        epg_loader._cache["fr"]["index"] = {"TF1.fr": [bad]}
        assert get_programmes_for_channel(ET.fromstring("<tv></tv>"), "TF1.fr", country="fr") == []

    def test_invalid_time_skipped(self):
        bad = ET.Element("programme", {"channel": "TF1.fr", "start": "nope", "stop": "nope"})
        ET.SubElement(bad, "title").text = "Heure invalide"
        epg_loader._cache["fr"]["index"] = {"TF1.fr": [bad]}
        assert get_programmes_for_channel(ET.fromstring("<tv></tv>"), "TF1.fr", country="fr") == []
