import asyncio
from datetime import datetime, timezone

import pytest

import tmdb

_START = datetime(2099, 6, 1, 19, 0, 0, tzinfo=timezone.utc)
_STOP  = datetime(2099, 6, 1, 21, 0, 0, tzinfo=timezone.utc)


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status   = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        return self._payload


class FakeClient:
    """Client httpx factice : enregistre les appels, renvoie une réponse par titre."""

    def __init__(self, responses=None, exc=None):
        self.responses = responses or {}
        self.exc       = exc
        self.calls     = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        self.calls.append(params)
        if self.exc:
            raise self.exc
        return _Resp({"results": self.responses.get(params["query"], [])})


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    tmdb.clear_cache()
    monkeypatch.setattr(tmdb.config, "TMDB_API_KEY", "fake-key", raising=False)
    yield
    tmdb.clear_cache()


def _install(monkeypatch, client):
    monkeypatch.setattr(tmdb, "_make_client", lambda: client)
    return client


def _prog(title="Le Fabuleux Destin d'Amélie Poulain", desc="", **over):
    p = {"start": _START, "stop": _STOP, "title": title, "desc": desc, "duree": "2h00"}
    p.update(over)
    return p


_AMELIE = {
    "title": "Le Fabuleux Destin d'Amélie Poulain", "original_title": "Le Fabuleux Destin d'Amélie Poulain",
    "overview": "Amélie, une jeune serveuse dans un bar de Montmartre, décide de changer la vie des gens.",
    "vote_average": 7.86, "vote_count": 11000, "release_date": "2001-04-25",
}


class TestNoKey:
    def test_no_key_no_network(self, monkeypatch):
        monkeypatch.setattr(tmdb.config, "TMDB_API_KEY", "")

        def boom():
            raise AssertionError("aucun client ne doit être créé sans clé")
        monkeypatch.setattr(tmdb, "_make_client", boom)
        progs = [_prog(desc="")]
        asyncio.run(tmdb.enrich_films(progs))
        assert progs[0] == _prog(desc="")
        assert not tmdb.is_enabled()


class TestEnrich:
    def test_found_merges_rating_year_overview(self, monkeypatch):
        client = _install(monkeypatch, FakeClient({_AMELIE["title"]: [_AMELIE]}))
        progs  = [_prog()]
        asyncio.run(tmdb.enrich_films(progs))
        p = progs[0]
        assert p["tmdb_rating"] == 7.9
        assert p["tmdb_year"] == 2001
        assert p["desc"].startswith("Amélie, une jeune serveuse")
        assert client.calls[0]["language"] == "fr-FR"
        assert client.calls[0]["api_key"] == "fake-key"

    def test_long_epg_desc_kept(self, monkeypatch):
        _install(monkeypatch, FakeClient({_AMELIE["title"]: [_AMELIE]}))
        epg = "Une description EPG déjà bien fournie et largement suffisante pour l'affichage."
        progs = [_prog(desc=epg)]
        asyncio.run(tmdb.enrich_films(progs))
        assert progs[0]["desc"] == epg
        assert progs[0]["tmdb_rating"] == 7.9

    def test_overview_truncated(self, monkeypatch):
        long = dict(_AMELIE, overview="mot " * 200)
        _install(monkeypatch, FakeClient({_AMELIE["title"]: [long]}))
        progs = [_prog()]
        asyncio.run(tmdb.enrich_films(progs))
        assert len(progs[0]["desc"]) <= 121 and progs[0]["desc"].endswith("…")

    def test_year_passed_when_known(self, monkeypatch):
        client = _install(monkeypatch, FakeClient({_AMELIE["title"]: [_AMELIE]}))
        asyncio.run(tmdb.enrich_films([_prog(year=2001)]))
        assert client.calls[0]["year"] == 2001

    def test_low_votes_no_rating(self, monkeypatch):
        few = dict(_AMELIE, vote_count=2)
        _install(monkeypatch, FakeClient({_AMELIE["title"]: [few]}))
        progs = [_prog()]
        asyncio.run(tmdb.enrich_films(progs))
        assert "tmdb_rating" not in progs[0]
        assert progs[0]["tmdb_year"] == 2001

    def test_limit_caps_lookups(self, monkeypatch):
        client = _install(monkeypatch, FakeClient())
        progs  = [_prog(title=f"Film numero {i}") for i in range(30)]
        asyncio.run(tmdb.enrich_films(progs, limit=15))
        assert len(client.calls) == 15


class TestAuth:
    def test_v4_token_not_in_query(self, monkeypatch):
        monkeypatch.setattr(tmdb.config, "TMDB_API_KEY", "eyJhbGciOi.fake.jwt")
        client = _install(monkeypatch, FakeClient())
        asyncio.run(tmdb.enrich_films([_prog()]))
        assert "api_key" not in client.calls[0]

    def test_error_log_has_no_secret(self, monkeypatch, caplog):
        _install(monkeypatch, FakeClient(exc=RuntimeError("https://x/?api_key=fake-key")))
        asyncio.run(tmdb.enrich_films([_prog()]))
        assert "fake-key" not in caplog.text


class TestFallback:
    def test_exception_falls_back(self, monkeypatch):
        _install(monkeypatch, FakeClient(exc=TimeoutError("timeout")))
        progs = [_prog(desc="Desc EPG")]
        asyncio.run(tmdb.enrich_films(progs))
        assert progs[0]["desc"] == "Desc EPG"
        assert "tmdb_rating" not in progs[0]

    def test_errors_not_cached(self, monkeypatch):
        _install(monkeypatch, FakeClient(exc=RuntimeError("down")))
        asyncio.run(tmdb.enrich_films([_prog()]))
        assert tmdb._cache == {}

    def test_client_creation_failure_is_silent(self, monkeypatch):
        def broken():
            raise ImportError("no httpx")
        monkeypatch.setattr(tmdb, "_make_client", broken)
        progs = [_prog(desc="x")]
        asyncio.run(tmdb.enrich_films(progs))
        assert progs[0]["desc"] == "x"

    def test_not_found(self, monkeypatch):
        _install(monkeypatch, FakeClient())
        progs = [_prog(desc="")]
        asyncio.run(tmdb.enrich_films(progs))
        assert progs[0]["desc"] == ""
        assert "tmdb_year" not in progs[0]


class TestCache:
    def test_cache_hit_no_second_call(self, monkeypatch):
        client = _install(monkeypatch, FakeClient({_AMELIE["title"]: [_AMELIE]}))
        asyncio.run(tmdb.enrich_films([_prog()]))
        asyncio.run(tmdb.enrich_films([_prog(title="le fabuleux destin d'amelie poulain")]))
        assert len(client.calls) == 1

    def test_not_found_is_cached(self, monkeypatch):
        client = _install(monkeypatch, FakeClient())
        asyncio.run(tmdb.enrich_films([_prog(title="Inconnu au bataillon")]))
        asyncio.run(tmdb.enrich_films([_prog(title="Inconnu au bataillon")]))
        assert len(client.calls) == 1

    def test_expired_entry_refetched(self, monkeypatch):
        client = _install(monkeypatch, FakeClient())
        asyncio.run(tmdb.enrich_films([_prog(title="Inconnu")]))
        for k, (_, d) in list(tmdb._cache.items()):
            tmdb._cache[k] = (0, d)
        asyncio.run(tmdb.enrich_films([_prog(title="Inconnu")]))
        assert len(client.calls) == 2


class TestNormalize:
    def test_accents_case_punct(self):
        assert tmdb.normalize_title("  L'Été  MEURTRIER !") == "l ete meurtrier"

    def test_equivalent_titles(self):
        assert tmdb.normalize_title("Amélie Poulain") == tmdb.normalize_title("amelie-poulain")

    def test_empty(self):
        assert tmdb.normalize_title("") == ""


class TestPickBest:
    def test_exact_title_beats_popular_other(self):
        res = [
            {"title": "Alien, le retour", "vote_count": 9000, "release_date": "1986-07-18"},
            {"title": "Alien", "vote_count": 500, "release_date": "1979-05-25"},
        ]
        assert tmdb.pick_best(res, "Alien")["release_date"].startswith("1979")

    def test_year_disambiguates_remake(self):
        res = [
            {"title": "Dune", "vote_count": 900, "release_date": "1984-12-14"},
            {"title": "Dune", "vote_count": 800, "release_date": "2021-09-15"},
        ]
        assert tmdb.pick_best(res, "Dune", 2021)["release_date"].startswith("2021")

    def test_original_title_match(self):
        res = [{"title": "Le Parrain", "original_title": "The Godfather", "release_date": "1972-03-14"}]
        assert tmdb.pick_best(res, "The Godfather") is not None

    def test_unrelated_rejected(self):
        res = [{"title": "Totalement autre chose", "vote_count": 5000}]
        assert tmdb.pick_best(res, "Alien") is None

    def test_empty(self):
        assert tmdb.pick_best([], "Alien") is None


class TestDisplay:
    def test_tag(self):
        assert tmdb.tmdb_tag({"tmdb_year": 1999, "tmdb_rating": 7.4}) == "(1999) ⭐ 7.4"
        assert tmdb.tmdb_tag({}) == ""

    def test_format_programme_escapes(self):
        from senders import format_programme
        out = format_programme(_prog(title="Matrix", tmdb_year=1999, tmdb_rating=8.2))
        assert "\\(1999\\) ⭐ 8\\.2" in out

    def test_format_programme_without_tmdb_unchanged(self):
        from senders import format_programme
        assert "⭐" not in format_programme(_prog(title="Matrix"))

    def test_send_type_blocs_shows_tag(self):
        from senders import send_type_blocs
        sent = []

        async def edit(t):
            sent.append(t)
        r = _prog(title="Matrix", tmdb_year=1999, tmdb_rating=8.2, ch_id="TF1.fr", channel="TF1")
        asyncio.run(send_type_blocs([r], "Lundi", _START, "🎬 *Films*", edit_fn=edit, send_fn=edit))
        assert "Matrix  \\(1999\\) ⭐ 8\\.2" in sent[0]


class TestGetYear:
    def test_get_year(self):
        import xml.etree.ElementTree as ET
        from utils import get_year
        assert get_year(ET.fromstring("<programme><date>1999</date></programme>")) == 1999
        assert get_year(ET.fromstring("<programme><date>20210915</date></programme>")) == 2021
        assert get_year(ET.fromstring("<programme/>")) is None
