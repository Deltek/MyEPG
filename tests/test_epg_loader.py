import xml.etree.ElementTree as ET

import epg_loader
from epg_loader import (
    get_epg_channels, get_epg_index, get_cache, get_cache_prev, reset_cache,
)


class TestEpgLoaderCache:
    def setup_method(self):
        reset_cache()  # isolation : repart d'un cache vide

    def teardown_method(self):
        reset_cache()  # ne pas polluer les tests fallback (epg_query, builders)

    def test_fresh_cache_getters_empty(self):
        assert get_epg_channels("fr") == {}
        assert get_epg_index("fr") == {}

    def test_get_epg_channels_returns_cached(self):
        epg_loader._cache["fr"]["channels"] = {"TF1.fr": "FR - TF1"}
        assert get_epg_channels("fr") == {"TF1.fr": "FR - TF1"}

    def test_get_epg_index_returns_cached(self):
        prog = ET.Element("programme", {"channel": "TF1.fr"})
        epg_loader._cache["fr"]["index"] = {"TF1.fr": [prog]}
        idx = get_epg_index("fr")
        assert "TF1.fr" in idx and idx["TF1.fr"] == [prog]

    def test_reset_clears_channels_and_index(self):
        epg_loader._cache["fr"]["channels"] = {"TF1.fr": "FR - TF1"}
        epg_loader._cache["fr"]["index"] = {"TF1.fr": []}
        reset_cache()
        assert get_epg_channels("fr") == {}
        assert get_epg_index("fr") == {}

    def test_get_cache_all_vs_country(self):
        full = get_cache()              # tout le cache
        assert "fr" in full and "gb" in full
        entry = get_cache("fr")         # une seule entrée
        assert "tree" in entry and "index" in entry

    def test_get_cache_prev_structure(self):
        prev = get_cache_prev("fr")
        assert "titles" in prev
        assert isinstance(prev["titles"], set)
