"""Unit tests for SingerRegistry: the guests of one run and the settings their songs start at."""

import re
from unittest.mock import MagicMock

import pytest

from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.lib.singers import NameTaken, SingerRegistry, SingerSettings

KEY_TWO = SingerSettings(semitones=2, vocal_volume=0.7)


@pytest.fixture
def preferences(tmp_path):
    return PreferenceManager(config_file_path=str(tmp_path / "config.ini"))


@pytest.fixture
def registry(preferences):
    return SingerRegistry(preferences)


class TestJoin:
    def test_join_returns_the_name_and_a_token_that_owns_it(self, registry):
        name, token = registry.join("Mike", KEY_TWO)
        assert name == "Mike"
        assert token
        assert registry.owns("Mike", token)

    def test_join_strips_the_name(self, registry):
        name, _token = registry.join("  Mike  ", KEY_TWO)
        assert name == "Mike"

    def test_guests_get_different_tokens(self, registry):
        _, first = registry.join("Mike", KEY_TWO)
        _, second = registry.join("Sue", KEY_TWO)
        assert first != second

    @pytest.mark.parametrize("taken_as", ["Mike", "mike", "MIKE", "  mike "])
    def test_a_name_in_use_is_refused_whatever_its_case(self, registry, taken_as):
        registry.join("Mike", KEY_TWO)
        with pytest.raises(NameTaken):
            registry.join(taken_as, SingerSettings(0, 0.4))

    def test_the_refusal_moves_nothing(self, registry):
        _, token = registry.join("Mike", KEY_TWO)
        with pytest.raises(NameTaken):
            registry.join("mike", SingerSettings(-1, 0.1))
        assert registry.owns("Mike", token)
        assert registry.settings_for("Mike") == KEY_TWO

    @pytest.mark.parametrize("name", ["Pikaraoke", "Randomizer", "randomizer", " PIKARAOKE"])
    def test_reserved_names_are_refused(self, registry, name):
        with pytest.raises(NameTaken):
            registry.join(name, KEY_TWO)

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_name_becomes_an_anon_name_with_the_picked_settings(self, registry, blank):
        name, token = registry.join(blank, KEY_TWO)
        assert re.fullmatch(r"Anon-[A-Za-z0-9]{4}", name)
        assert registry.owns(name, token)
        assert registry.settings_for(name) == KEY_TWO

    def test_an_anon_name_is_picked_again_until_it_is_free(self, registry, monkeypatch):
        monkeypatch.setattr(
            "pikaraoke.lib.singers.secrets.choice", MagicMock(side_effect=list("aaaabbbb"))
        )
        first, _ = registry.join("", KEY_TWO)
        second, _ = registry.join("", KEY_TWO)
        assert (first, second) == ("Anon-aaaa", "Anon-bbbb")

        monkeypatch.setattr(
            "pikaraoke.lib.singers.secrets.choice", MagicMock(side_effect=list("aaaacccc"))
        )
        third, _ = registry.join("", KEY_TWO)
        assert third == "Anon-cccc"


class TestOwns:
    def test_a_wrong_token_owns_nothing(self, registry):
        registry.join("Mike", KEY_TWO)
        assert not registry.owns("Mike", "not-the-token")

    def test_an_unknown_name_owns_nothing(self, registry):
        _, token = registry.join("Mike", KEY_TWO)
        assert not registry.owns("Sue", token)

    @pytest.mark.parametrize("name, token", [(None, "t"), ("Mike", None), ("", "t"), ("Mike", "")])
    def test_a_missing_cookie_owns_nothing(self, registry, name, token):
        registry.join("Mike", KEY_TWO)
        assert not registry.owns(name, token)

    def test_a_non_ascii_token_fails_the_check_instead_of_raising(self, registry):
        registry.join("Mike", KEY_TWO)
        assert not registry.owns("Mike", "tökén")

    def test_a_new_registry_owns_nothing_from_before(self, registry, preferences):
        name, token = registry.join("Mike", KEY_TWO)
        after_restart = SingerRegistry(preferences)
        assert not after_restart.owns(name, token)


class TestUpdate:
    def test_saving_settings_keeps_the_name_and_token(self, registry):
        name, token = registry.join("Mike", KEY_TWO)
        on_rename = MagicMock()
        new_settings = SingerSettings(-1, 0.2)

        held = registry.update(name, token, "Mike", new_settings, on_rename)

        assert held == "Mike"
        assert registry.owns("Mike", token)
        assert registry.settings_for("Mike") == new_settings
        on_rename.assert_not_called()

    def test_a_rename_moves_the_guest_and_calls_on_rename_once(self, registry):
        name, token = registry.join("Mike", KEY_TWO)
        on_rename = MagicMock()

        held = registry.update(name, token, "Michael", KEY_TWO, on_rename)

        assert held == "Michael"
        on_rename.assert_called_once_with("Mike", "Michael")
        assert registry.owns("Michael", token)
        assert not registry.owns("Mike", token)
        assert registry.settings_for("Michael") == KEY_TWO

    def test_the_old_name_is_free_after_a_rename(self, registry):
        name, token = registry.join("Mike", KEY_TWO)
        registry.update(name, token, "Michael", KEY_TWO, MagicMock())

        reused, _token = registry.join("Mike", SingerSettings(0, 0.4))

        assert reused == "Mike"

    def test_a_case_change_renames_so_queued_songs_follow_the_spelling(self, registry):
        name, token = registry.join("mike", KEY_TWO)
        on_rename = MagicMock()

        held = registry.update(name, token, "Mike", KEY_TWO, on_rename)

        assert held == "Mike"
        on_rename.assert_called_once_with("mike", "Mike")
        assert registry.owns("Mike", token)

    def test_a_blank_new_name_keeps_the_current_one(self, registry):
        name, token = registry.join("Mike", KEY_TWO)
        on_rename = MagicMock()

        held = registry.update(name, token, "  ", SingerSettings(1, 0.5), on_rename)

        assert held == "Mike"
        on_rename.assert_not_called()
        assert registry.settings_for("Mike") == SingerSettings(1, 0.5)

    def test_a_taken_name_raises_and_moves_nothing(self, registry):
        name, token = registry.join("Mike", KEY_TWO)
        registry.join("Sue", SingerSettings(0, 0.4))
        on_rename = MagicMock()

        with pytest.raises(NameTaken):
            registry.update(name, token, "sue", SingerSettings(-3, 0.0), on_rename)

        on_rename.assert_not_called()
        assert registry.owns("Mike", token)
        assert registry.settings_for("Mike") == KEY_TWO
        assert registry.settings_for("Sue") == SingerSettings(0, 0.4)

    def test_a_reserved_name_raises(self, registry):
        name, token = registry.join("Mike", KEY_TWO)
        with pytest.raises(NameTaken):
            registry.update(name, token, "Randomizer", KEY_TWO, MagicMock())

    def test_a_wrong_token_is_refused_and_changes_nothing(self, registry):
        name, _ = registry.join("Mike", KEY_TWO)
        on_rename = MagicMock()

        with pytest.raises(PermissionError):
            registry.update(name, "not-the-token", "Michael", SingerSettings(0, 0.0), on_rename)

        on_rename.assert_not_called()
        assert registry.settings_for("Mike") == KEY_TWO

    def test_a_failed_move_leaves_the_old_name_held(self, registry):
        name, token = registry.join("Mike", KEY_TWO)

        with pytest.raises(RuntimeError):
            registry.update(
                name, token, "Michael", KEY_TWO, MagicMock(side_effect=RuntimeError("boom"))
            )

        assert registry.owns("Mike", token)
        assert not registry.owns("Michael", token)

    def test_on_rename_runs_with_the_registry_locked(self, registry):
        """Nobody can join as the old name before the songs have moved."""
        name, token = registry.join("Mike", KEY_TWO)
        lock_was_held = []

        def on_rename(old: str, new: str) -> None:
            lock_was_held.append(registry._lock.locked())

        registry.update(name, token, "Michael", KEY_TWO, on_rename)

        assert lock_was_held == [True]


class TestSettingsFor:
    def test_a_guest_gets_their_own_settings(self, registry):
        registry.join("Mike", KEY_TWO)
        assert registry.settings_for("Mike") == KEY_TWO

    def test_the_lookup_ignores_case(self, registry):
        registry.join("Mike", KEY_TWO)
        assert registry.settings_for("MIKE") == KEY_TWO

    @pytest.mark.parametrize("name", ["Randomizer", "Pikaraoke", "Nobody"])
    def test_a_name_that_never_joined_gets_the_house_defaults(self, registry, name):
        assert registry.settings_for(name) == SingerSettings(0, 0.4)

    def test_the_house_default_follows_a_changed_preference(self, registry, preferences):
        preferences.set("vocal_volume", 0.9)
        assert registry.settings_for("Randomizer") == SingerSettings(0, 0.9)

    def test_a_guest_keeps_what_they_saved_when_the_house_default_changes(
        self, registry, preferences
    ):
        registry.join("Mike", KEY_TWO)
        preferences.set("vocal_volume", 0.9)
        assert registry.settings_for("Mike") == KEY_TWO
