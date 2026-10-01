import asyncio
import json

import pytest

import state
from broadcast import broadcast_to


@pytest.fixture(autouse=True)
def clean_state():
    state.reset_state()
    yield
    state.reset_state()


class TestNormalizeCommand:
    def test_simple(self):
        assert state.normalize_command("/sport") == "sport"

    def test_args_and_botname(self):
        assert state.normalize_command("/Sport@MyEPGBot gb") == "sport"

    def test_not_a_command(self):
        assert state.normalize_command("bonjour") is None
        assert state.normalize_command("") is None
        assert state.normalize_command(None) is None

    def test_slash_alone(self):
        assert state.normalize_command("/") is None
        assert state.normalize_command("/ sport") is None


class TestUsersAndCounter:
    def test_add_user_returns_new(self):
        assert state.add_user(1) is True
        assert state.add_user(1) is False
        assert state.get_known_users() == {1}

    def test_top_commands(self):
        for cmd in ["sport", "film", "sport", "soir", "sport", "film"]:
            state.track_command(cmd)
        assert state.get_top_commands(2) == [("sport", 3), ("film", 2)]
        assert state.get_total_commands() == 6

    def test_user_store_created_on_demand(self):
        state.get_user_store(42)["favoris"] = ["TF1.fr"]
        assert state.iter_user_stores() == [(42, {"favoris": ["TF1.fr"]})]


class TestPersistence:
    def test_roundtrip(self, tmp_path):
        f = tmp_path / "state.json"
        state.add_user(1)
        state.add_user(2)
        state.track_command("sport")
        state.get_user_store(2)["favoris"] = ["TF1.fr"]
        assert state.save_state(f) is True

        state.reset_state()
        assert state.get_known_users() == set()

        state.load_state(f)
        assert state.get_known_users() == {1, 2}
        assert state.get_top_commands() == [("sport", 1)]
        assert state.get_user_store(2) == {"favoris": ["TF1.fr"]}

    def test_save_skipped_when_clean(self, tmp_path):
        f = tmp_path / "state.json"
        state.add_user(1)
        assert state.save_state(f) is True
        assert state.save_state(f) is False
        assert state.save_state(f, force=True) is True

    def test_creates_parent_dir_and_no_tmp_left(self, tmp_path):
        f = tmp_path / "sub" / "state.json"
        state.add_user(1)
        state.save_state(f)
        assert json.loads(f.read_text())["users"] == [1]
        assert not f.with_suffix(".tmp").exists()

    def test_missing_file_is_empty(self, tmp_path):
        state.load_state(tmp_path / "absent.json")
        assert state.get_known_users() == set()

    def test_corrupt_file_is_empty(self, tmp_path):
        f = tmp_path / "state.json"
        f.write_text("{pas du json")
        state.add_user(9)
        state.load_state(f)
        assert state.get_known_users() == {9}  # état courant conservé

    def test_empty_user_stores_not_saved(self, tmp_path):
        f = tmp_path / "state.json"
        state.get_user_store(5)
        state.add_user(5)
        state.save_state(f)
        assert json.loads(f.read_text())["user_store"] == {}


class TestBroadcast:
    def test_counts_statuses_and_errors(self):
        async def send(uid):
            if uid == 3:
                raise RuntimeError("boom")
            return "blocked" if uid == 2 else "ok"

        res = asyncio.run(broadcast_to([1, 2, 3, 4], send, delay=0))
        assert res == {"ok": 2, "blocked": 1, "error": 1}

    def test_empty(self):
        async def send(uid):
            return "ok"

        assert asyncio.run(broadcast_to([], send, delay=0)) == {}
