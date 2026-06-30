import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from zoneinfo import ZoneInfo

TZ_PARIS = ZoneInfo("Europe/Paris")

# Timestamps en 2099 → toujours dans le futur, jamais "en cours"
_START = datetime(2099, 6, 1, 19, 0, 0, tzinfo=timezone.utc)
_STOP  = datetime(2099, 6, 1, 21, 0, 0, tzinfo=timezone.utc)

# Encadre l'instant présent → toujours "en cours"
_PAST   = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_FUTURE = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class TestFormatProgramme:
    def _prog(self, **over):
        base = {"start": _START, "stop": _STOP, "title": "Mon film"}
        base.update(over)
        return base

    def test_title_and_time_range(self):
        from senders import format_programme
        out = format_programme(self._prog())
        assert "Mon film" in out
        # _START 19:00 UTC → 21:00 Paris (CEST) ; _STOP 21:00 UTC → 23:00 Paris
        assert "21:00" in out and "23:00" in out

    def test_en_cours_adds_red_dot(self):
        from senders import format_programme
        out = format_programme(self._prog(start=_PAST, stop=_FUTURE))
        assert out.startswith("🔴 ")

    def test_future_not_en_cours(self):
        from senders import format_programme
        out = format_programme(self._prog())  # 2099 → futur
        assert "🔴" not in out

    def test_new_tag_present(self):
        from senders import format_programme
        out = format_programme(self._prog(new=True))
        assert "🆕" in out

    def test_no_new_tag_by_default(self):
        from senders import format_programme
        out = format_programme(self._prog())
        assert "🆕" not in out

    def test_cat_line(self):
        from senders import format_programme
        out = format_programme(self._prog(cat="Sport"))
        assert "📂" in out and "Sport" in out

    def test_desc_line(self):
        from senders import format_programme
        out = format_programme(self._prog(desc="Une description suffisamment longue"))
        assert "📝" in out

    def test_no_optional_lines_when_absent(self):
        from senders import format_programme
        out = format_programme(self._prog())
        assert "📂" not in out and "📝" not in out


class Collector:
    """Coroutine collectrice — capture chaque appel."""
    def __init__(self):
        self.calls = []

    async def __call__(self, text, **kw):
        self.calls.append(text)


def make_type_result(ch_id="TF1.fr", channel="TF1", title="Film test"):
    return {
        "ch_id": ch_id, "channel": channel, "title": title,
        "start": _START, "stop": _STOP,
        "duree": "2h00", "desc": "", "new": False, "placeholder": False,
    }


def make_soir_result(ch_id="TF1.fr", title="Film du soir"):
    return {
        "ch_id": ch_id, "title": title,
        "start": _START, "stop": _STOP,
        "desc": "", "new": False,
    }


NOW_UTC = datetime.now(tz=timezone.utc)


class TestSendTypeBlocs:
    def test_empty_results_calls_edit_with_error(self):
        from senders import send_type_blocs
        edit = Collector()
        send = Collector()
        asyncio.run(send_type_blocs(
            [], "Lundi", NOW_UTC,
            header="🎬 Test",
            edit_fn=edit, send_fn=send,
        ))
        assert len(edit.calls) == 1
        assert "Aucun" in edit.calls[0]
        assert len(send.calls) == 0

    def test_single_result_uses_edit_fn_only(self):
        from senders import send_type_blocs
        edit = Collector()
        send = Collector()
        asyncio.run(send_type_blocs(
            [make_type_result()], "Lundi", NOW_UTC,
            header="🎬 Test",
            edit_fn=edit, send_fn=send,
        ))
        assert len(edit.calls) == 1
        assert len(send.calls) == 0

    def test_header_appears_in_first_message(self):
        from senders import send_type_blocs
        edit = Collector()
        send = Collector()
        asyncio.run(send_type_blocs(
            [make_type_result()], "Mardi", NOW_UTC,
            header="🎬 *Films du soir*",
            edit_fn=edit, send_fn=send,
        ))
        assert "Films du soir" in edit.calls[0]

    def test_overflow_uses_send_fn(self):
        from senders import send_type_blocs
        # 30 chaînes distinctes avec un titre de 200 chars → dépasse 4000 chars
        results = [
            make_type_result(ch_id=f"Ch{i:02d}.fr", channel=f"Ch{i:02d}", title="X" * 200)
            for i in range(30)
        ]
        edit = Collector()
        send = Collector()
        asyncio.run(send_type_blocs(
            results, "Lundi", NOW_UTC,
            header="🎬 Test",
            edit_fn=edit, send_fn=send,
        ))
        assert len(edit.calls) == 1       # premier bloc → edit
        assert len(send.calls) >= 1       # surplus → send

    def test_title_in_first_message(self):
        from senders import send_type_blocs
        edit = Collector()
        send = Collector()
        asyncio.run(send_type_blocs(
            [make_type_result(title="Mon super film")], "Mercredi", NOW_UTC,
            header="🎬 Test",
            edit_fn=edit, send_fn=send,
        ))
        assert "Mon super film" in edit.calls[0]

    def test_new_tag_added(self):
        from senders import send_type_blocs
        r = make_type_result()
        r["new"] = True
        edit = Collector()
        asyncio.run(send_type_blocs(
            [r], "Jeudi", NOW_UTC,
            header="🎬 Test",
            edit_fn=edit, send_fn=Collector(),
        ))
        assert "🆕" in edit.calls[0]


class TestSendSoirBlocs:
    def test_empty_calls_edit_with_error(self):
        from senders import send_soir_blocs
        edit = Collector()
        send = Collector()
        asyncio.run(send_soir_blocs(
            [], {}, "Lundi", NOW_UTC,
            send_fn=send, edit_fn=edit,
        ))
        assert len(edit.calls) == 1
        assert "Aucun" in edit.calls[0]
        assert len(send.calls) == 0

    def test_single_result_uses_edit_fn_only(self):
        from senders import send_soir_blocs
        channels = {"TF1.fr": "FR - TF1"}
        edit = Collector()
        send = Collector()
        asyncio.run(send_soir_blocs(
            [make_soir_result()], channels, "Lundi", NOW_UTC,
            send_fn=send, edit_fn=edit,
        ))
        assert len(edit.calls) == 1
        assert len(send.calls) == 0

    def test_title_appears_in_message(self):
        from senders import send_soir_blocs
        channels = {"TF1.fr": "FR - TF1"}
        edit = Collector()
        asyncio.run(send_soir_blocs(
            [make_soir_result(title="Série du lundi")], channels, "Lundi", NOW_UTC,
            send_fn=Collector(), edit_fn=edit,
        ))
        assert "Série du lundi" in edit.calls[0]

    def test_overflow_uses_send_fn(self):
        from senders import send_soir_blocs
        # 20 chaînes fictives avec titres de 200 chars → dépasse 4000 chars
        fake_ch = [f"Ch{i:02d}.fr" for i in range(20)]
        channels = {ch: f"Ch{i:02d}" for i, ch in enumerate(fake_ch)}
        results  = [
            make_soir_result(ch_id=ch, title="Y" * 200)
            for ch in fake_ch
        ]
        edit = Collector()
        send = Collector()
        with patch("senders.CH_TNT_FR", fake_ch):
            asyncio.run(send_soir_blocs(
                results, channels, "Lundi", NOW_UTC,
                send_fn=send, edit_fn=edit,
            ))
        assert len(edit.calls) == 1
        assert len(send.calls) >= 1

    def test_new_flag_adds_emoji(self):
        from senders import send_soir_blocs
        channels = {"TF1.fr": "FR - TF1"}
        r = make_soir_result()
        r["new"] = True
        edit = Collector()
        asyncio.run(send_soir_blocs(
            [r], channels, "Lundi", NOW_UTC,
            send_fn=Collector(), edit_fn=edit,
        ))
        assert "🆕" in edit.calls[0]
