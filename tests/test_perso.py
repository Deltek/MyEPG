import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import perso
from perso import (
    add_favori, remove_favori, get_favoris,
    add_alerte, remove_alerte, get_alertes, normalize_query,
    scan_upcoming, collect_notifications, pick_ce_soir,
    format_favori_bloc, format_alerte_notification,
)

TZ_PARIS = ZoneInfo("Europe/Paris")
NOW = datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)  # 18:00 Paris


def _prog(cid, start, stop, title, desc=""):
    p = ET.Element("programme", channel=cid, start=start, stop=stop)
    ET.SubElement(p, "title").text = title
    if desc:
        ET.SubElement(p, "desc").text = desc
    return p


INDEX = {
    "TF1.fr": [
        _prog("TF1.fr", "20240101163000 +0000", "20240101171500 +0000", "Football : avant-match"),  # déjà commencé
        _prog("TF1.fr", "20240101172000 +0000", "20240101190000 +0000", "Football : Ligue des Champions"),
        _prog("TF1.fr", "20240101180000 +0000", "20240101190000 +0000", "Football : après-match"),  # hors fenêtre
    ],
    "France2.fr": [
        _prog("France2.fr", "20240101173000 +0000", "20240101180000 +0000", "Télématin Spécial"),
        _prog("France2.fr", "20240101174000 +0000", "20240101180000 +0000", "Football"),  # placeholder générique
        _prog("France2.fr", "bad", "bad", "Cassé"),
        _prog("France2.fr", "20240101174500 +0000", "20240101180000 +0000", "beIN SPORTS, le plus grand des spectacles"),
    ],
}


class TestFavoris:
    def test_add_exists_full(self):
        store = {}
        assert add_favori(store, "TF1.fr") == "added"
        assert add_favori(store, "TF1.fr") == "exists"
        for i in range(perso.MAX_FAVORIS - 1):
            assert add_favori(store, f"C{i}.fr") == "added"
        assert add_favori(store, "Arte.fr") == "full"
        assert len(get_favoris(store)) == perso.MAX_FAVORIS

    def test_remove(self):
        store = {"favoris": ["TF1.fr"]}
        assert remove_favori(store, "TF1.fr") is True
        assert remove_favori(store, "TF1.fr") is False
        assert remove_favori({}, "TF1.fr") is False


class TestAlertesCrud:
    def test_normalize(self):
        assert normalize_query("  Ligue  des CHAMPIONS ") == "ligue des champions"
        assert normalize_query("Télé") == "tele"

    def test_add_invalid_exists_full(self):
        store = {}
        assert add_alerte(store, "fr", "ab") == "invalid"
        assert add_alerte(store, "fr", "Foot") == "added"
        assert add_alerte(store, "fr", "  FOOT ") == "exists"
        assert add_alerte(store, "gb", "foot") == "added"  # autre pays
        for i in range(perso.MAX_ALERTES - 2):
            add_alerte(store, "fr", f"mot{i}")
        assert add_alerte(store, "fr", "encore") == "full"

    def test_remove_all_countries(self):
        store = {}
        add_alerte(store, "fr", "foot")
        add_alerte(store, "gb", "foot")
        add_alerte(store, "fr", "rugby")
        assert remove_alerte(store, "FOOT") is True
        assert [a["q"] for a in get_alertes(store)] == ["rugby"]
        assert remove_alerte(store, "foot") is False


class TestScanUpcoming:
    def test_window_and_placeholders(self):
        res = scan_upcoming(INDEX, NOW, timedelta(minutes=60))
        assert [r["title"] for r in res] == ["Football : Ligue des Champions", "Télématin Spécial"]
        assert res[1]["norm"] == "telematin special"

    def test_channel_filter(self):
        res = scan_upcoming(INDEX, NOW, channels={"France2.fr"})
        assert [r["cid"] for r in res] == ["France2.fr"]

    def test_empty_index(self):
        assert scan_upcoming({}, NOW) == []


class TestCollectNotifications:
    def _upcoming(self):
        return {"fr": scan_upcoming(INDEX, NOW)}

    def test_match_then_dedup(self):
        store = {}
        add_alerte(store, "fr", "ligue des champions")
        add_alerte(store, "fr", "telematin")
        add_alerte(store, "gb", "football")  # pas de données GB
        out = collect_notifications(store, self._upcoming(), NOW)
        assert [(a["q"], [m["cid"] for m in ms], n) for a, ms, n in out] == [
            ("ligue des champions", ["TF1.fr"], 0),
            ("telematin", ["France2.fr"], 0),
        ]
        assert collect_notifications(store, self._upcoming(), NOW) == []

    def test_accent_insensitive(self):
        store = {}
        add_alerte(store, "fr", "Télématin")
        assert len(collect_notifications(store, self._upcoming(), NOW)) == 1

    def test_seen_keys_pruned(self):
        store = {"alertes": [], "alertes_vues": [
            f"fr|x|TF1.fr|{int((NOW - timedelta(days=2)).timestamp())}",
            f"fr|x|TF1.fr|{int(NOW.timestamp())}",
        ]}
        collect_notifications(store, {}, NOW)
        assert len(store["alertes_vues"]) == 1

    def test_max_matches(self):
        upcoming = {"fr": [
            {"cid": f"C{i}.fr", "title": "Foot", "norm": "foot", "start": NOW + timedelta(minutes=i)}
            for i in range(10)
        ]}
        store = {}
        add_alerte(store, "fr", "foot")
        (_, matches, autres), = collect_notifications(store, upcoming, NOW)
        assert len(matches) == perso.ALERT_MAX_MATCHES
        assert autres == 10 - perso.ALERT_MAX_MATCHES
        assert collect_notifications(store, upcoming, NOW) == []  # surplus marqué vu


def _p(h_start, h_stop, title):
    day = datetime(2024, 1, 1, tzinfo=TZ_PARIS)
    return {
        "start": day.replace(hour=h_start[0], minute=h_start[1]),
        "stop":  day.replace(hour=h_stop[0], minute=h_stop[1]),
        "title": title,
    }


class TestFormat:
    PROGS = [_p((17, 30), (18, 30), "JT"), _p((18, 30), (20, 50), "Jeu"), _p((20, 50), (22, 40), "Film (1999)")]

    def test_pick_ce_soir(self):
        assert pick_ce_soir(self.PROGS, NOW, TZ_PARIS)["title"] == "Film (1999)"
        late = datetime(2024, 1, 1, 21, 0, tzinfo=timezone.utc)  # 22h Paris
        assert pick_ce_soir(self.PROGS, late, TZ_PARIS) is None

    def test_bloc(self):
        txt = format_favori_bloc("TF1", self.PROGS, NOW, TZ_PARIS)
        assert txt.splitlines() == [
            "📺 *TF1*",
            "🔴 JT  _\\(reste 30min\\)_",
            "⏭ 18:30  Jeu",
            "🌙 20:50  Film \\(1999\\)",
        ]

    def test_bloc_empty(self):
        assert "Aucun programme" in format_favori_bloc("TF1", [], NOW, TZ_PARIS)

    def test_notification(self):
        m = {"cid": "TF1.fr", "title": "Foot : PSG-OM", "start": NOW + timedelta(minutes=20)}
        txt = format_alerte_notification({"q": "psg", "country": "fr"}, [m], {"TF1.fr": "FR - TF1"}, TZ_PARIS)
        assert txt == "🔔 *Alerte « psg »*\n\n📺 *TF1* — 18:20  Foot : PSG\\-OM"
        txt = format_alerte_notification({"q": "psg", "country": "fr"}, [m], {}, TZ_PARIS, autres=3)
        assert txt.endswith("_\\+3 autre\\(s\\)_")
