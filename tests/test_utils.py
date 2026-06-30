import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

from utils import (
    parse_xmltv_time, clean_name, clean_title, clean_desc,
    sanitize_md, truncate, duree_str,
    is_sport_filler, is_nouveautes_filler, is_film, is_serie,
    get_channels, get_ch_id_by_name,
    get_categories, is_epg_placeholder, now_paris,
)


class TestParseXmltvTime:
    def test_positive_offset(self):
        dt = parse_xmltv_time("20240101120000 +0100")
        assert dt == datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)

    def test_negative_offset(self):
        dt = parse_xmltv_time("20240101120000 -0500")
        assert dt == datetime(2024, 1, 1, 17, 0, 0, tzinfo=timezone.utc)

    def test_utc_offset(self):
        dt = parse_xmltv_time("20240615200000 +0000")
        assert dt.replace(tzinfo=timezone.utc) == datetime(2024, 6, 15, 20, 0, 0, tzinfo=timezone.utc)


class TestCleanName:
    def test_removes_fr_prefix(self):
        assert clean_name("FR - TF1") == "TF1"

    def test_no_prefix(self):
        assert clean_name("Arte") == "Arte"

    def test_strips_whitespace(self):
        assert clean_name("  FR - M6  ") == "M6"


class TestCleanTitle:
    def test_removes_new_superscript(self):
        assert clean_title("Mon film ᴺᵉʷ") == "Mon film"

    def test_adds_space_before_year(self):
        assert clean_title("Film2024") == "Film 2024"

    def test_preserves_existing_space_before_year(self):
        assert clean_title("Film 2024") == "Film 2024"

    def test_no_change(self):
        assert clean_title("Programme normal") == "Programme normal"


class TestCleanDesc:
    def test_too_short(self):
        assert clean_desc("Court.", "titre") == ""

    def test_starts_with_title(self):
        assert clean_desc("Mon titre est le début", "Mon titre") == ""

    def test_normal_description(self):
        desc = "Une belle description qui est assez longue pour passer le filtre."
        result = clean_desc(desc, "Titre différent")
        assert result != ""

    def test_empty_desc(self):
        assert clean_desc("", "titre") == ""


class TestSanitizeMd:
    def test_escapes_asterisk(self):
        assert "\\*" in sanitize_md("*gras*")

    def test_escapes_underscore(self):
        assert "\\_" in sanitize_md("_italique_")

    def test_escapes_backtick(self):
        assert "\\`" in sanitize_md("`code`")

    def test_no_special_chars(self):
        assert sanitize_md("texte normal") == "texte normal"


class TestTruncate:
    def test_short_text_unchanged(self):
        assert truncate("Court", 50) == "Court"

    def test_long_text_truncated(self):
        text = "Un texte bien trop long " * 10
        result = truncate(text, 50)
        assert len(result) <= 52
        assert result.endswith("…")


class TestDureeStr:
    def test_hours_and_minutes(self):
        start = datetime(2024, 1, 1, 20, 0, tzinfo=timezone.utc)
        stop  = datetime(2024, 1, 1, 21, 30, tzinfo=timezone.utc)
        assert duree_str(start, stop) == "1h30"

    def test_full_hours(self):
        start = datetime(2024, 1, 1, 20, 0, tzinfo=timezone.utc)
        stop  = datetime(2024, 1, 1, 22, 0, tzinfo=timezone.utc)
        assert duree_str(start, stop) == "2h00"

    def test_minutes_only(self):
        start = datetime(2024, 1, 1, 20, 0, tzinfo=timezone.utc)
        stop  = datetime(2024, 1, 1, 20, 45, tzinfo=timezone.utc)
        assert duree_str(start, stop) == "45min"


class TestIsSportFiller:
    def test_avant_match(self):
        assert is_sport_filler("Avant-match de la soirée") is True

    def test_bein_promo(self):
        assert is_sport_filler("BeIN Sports, le plus grand") is True

    def test_real_sport(self):
        assert is_sport_filler("Ligue des Champions") is False

    def test_case_insensitive(self):
        assert is_sport_filler("AVANT-MATCH finale") is True


class TestIsNouveautesFiller:
    def test_jt(self):
        assert is_nouveautes_filler("JT 20h") is True

    def test_meteo(self):
        assert is_nouveautes_filler("Météo de la semaine") is True

    def test_real_show(self):
        assert is_nouveautes_filler("La Casa de Papel") is False

    def test_journal(self):
        assert is_nouveautes_filler("Journal de 13h") is True


class TestIsFilm:
    def test_by_film_category(self):
        prog = ET.fromstring(
            '<programme start="20240101200000 +0000" stop="20240101220000 +0000" channel="TF1.fr">'
            "<title>Un film</title><category>Film</category></programme>"
        )
        assert is_film(prog) is True

    def test_by_duration_over_75_min(self):
        # 80 minutes = 1h20, above the 75 min threshold (20:00 → 21:20)
        prog = ET.fromstring(
            '<programme start="20240101200000 +0000" stop="20240101212000 +0000" channel="TF1.fr">'
            "<title>Long programme</title></programme>"
        )
        assert is_film(prog) is True

    def test_not_film_if_serie(self):
        prog = ET.fromstring(
            '<programme start="20240101200000 +0000" stop="20240101210000 +0000" channel="TF1.fr">'
            "<title>Show</title>"
            '<episode-num system="xmltv_ns">0.0.0/1</episode-num></programme>'
        )
        assert is_film(prog) is False

    def test_not_film_short(self):
        prog = ET.fromstring(
            '<programme start="20240101200000 +0000" stop="20240101200500 +0000" channel="TF1.fr">'
            "<title>Court</title></programme>"
        )
        assert is_film(prog) is False


class TestIsSerie:
    def test_by_serie_category(self):
        prog = ET.fromstring(
            '<programme start="20240101200000 +0000" stop="20240101210000 +0000" channel="TF1.fr">'
            "<title>Ma série</title><category>Série</category></programme>"
        )
        assert is_serie(prog) is True

    def test_by_episode_num(self):
        prog = ET.fromstring(
            '<programme start="20240101200000 +0000" stop="20240101210000 +0000" channel="TF1.fr">'
            "<title>Show</title>"
            '<episode-num system="xmltv_ns">0.0.0/1</episode-num></programme>'
        )
        assert is_serie(prog) is True

    def test_by_title_episode_pattern(self):
        prog = ET.fromstring(
            '<programme start="20240101200000 +0000" stop="20240101210000 +0000" channel="TF1.fr">'
            "<title>Show S01E05</title></programme>"
        )
        assert is_serie(prog) is True

    def test_not_serie(self):
        prog = ET.fromstring(
            '<programme start="20240101200000 +0000" stop="20240101220000 +0000" channel="TF1.fr">'
            "<title>Film normal</title></programme>"
        )
        assert is_serie(prog) is False


class TestGetChannels:
    def test_extracts_channels(self):
        root = ET.fromstring(
            "<tv>"
            '<channel id="TF1.fr"><display-name>FR - TF1</display-name></channel>'
            '<channel id="M6.fr"><display-name>FR - M6</display-name></channel>'
            "</tv>"
        )
        channels = get_channels(root)
        assert channels["TF1.fr"] == "FR - TF1"
        assert channels["M6.fr"] == "FR - M6"
        assert len(channels) == 2


class TestGetChIdByName:
    def test_known_alias(self):
        assert get_ch_id_by_name("tf1") == "TF1.fr"
        assert get_ch_id_by_name("m6") == "M6.fr"

    def test_case_insensitive(self):
        assert get_ch_id_by_name("TF1") == "TF1.fr"

    def test_unknown_returns_none(self):
        assert get_ch_id_by_name("chaine_inconnue") is None


def _prog_with_cats(*cats):
    p = ET.Element("programme")
    for c in cats:
        e = ET.SubElement(p, "category")
        e.text = c
    return p


class TestGetCategories:
    def test_single_category(self):
        assert get_categories(_prog_with_cats("sport")) == "sport"

    def test_multiple_categories_joined(self):
        assert get_categories(_prog_with_cats("film", "drame")) == "film · drame"

    def test_no_category_returns_empty(self):
        assert get_categories(_prog_with_cats()) == ""

    def test_empty_text_ignored(self):
        p = ET.Element("programme")
        ET.SubElement(p, "category")  # pas de .text
        ET.SubElement(p, "category").text = "sport"
        assert get_categories(p) == "sport"


class TestIsEpgPlaceholder:
    def test_colon_in_title_never_placeholder(self):
        # un ":" signale un vrai contenu (ex. "Foot: PSG-OM")
        assert is_epg_placeholder("Football: PSG-OM", "") is False

    def test_generic_sport_word_is_placeholder(self):
        assert is_epg_placeholder("Football", "") is True

    def test_generic_word_accent_case_insensitive(self):
        assert is_epg_placeholder("ATHLETISME", "") is True

    def test_real_title_not_placeholder(self):
        assert is_epg_placeholder("Documentaire animalier", "") is False

    def test_placeholder_desc_prefix(self):
        assert is_epg_placeholder("Le match", "Suivez un match d'une compétition de football") is True

    def test_colon_overrides_placeholder_desc(self):
        assert is_epg_placeholder("Match: détails", "Suivez un match d'une compétition") is False


class TestNowParis:
    def test_timezone_aware_paris(self):
        n = now_paris()
        assert n.tzinfo is not None
        assert "Paris" in str(n.tzinfo)

    def test_close_to_utc_now(self):
        delta = abs((now_paris() - datetime.now(timezone.utc)).total_seconds())
        assert delta < 5
