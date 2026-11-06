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
def on_rename():
    return MagicMock()


@pytest.fixture
def registry(preferences, on_rename):
    return SingerRegistry(preferences, on_rename)


def join(registry, name="Mike", settings=KEY_TWO):
    """A phone with no token yet, saving for the first time."""
    return registry.save(None, name, settings)


class TestJoin:
    def test_a_phone_with_no_token_joins_and_gets_its_name_and_a_token(self, registry):
        name, token = join(registry)

        assert name == "Mike"
        assert token
        assert registry.lookup(token) == ("Mike", KEY_TWO)

    def test_a_token_nobody_holds_joins_instead_of_updating(self, registry):
        name, token = registry.save("from-an-earlier-run", "Mike", KEY_TWO)

        assert name == "Mike"
        assert token != "from-an-earlier-run"
        assert registry.lookup(token) == ("Mike", KEY_TWO)

    def test_join_strips_the_name(self, registry):
        name, _token = join(registry, "  Mike  ")
        assert name == "Mike"

    def test_guests_get_different_tokens(self, registry):
        _, first = join(registry, "Mike")
        _, second = join(registry, "Sue")
        assert first != second

    def test_joining_does_not_call_on_rename(self, registry, on_rename):
        join(registry)
        on_rename.assert_not_called()

    @pytest.mark.parametrize("taken_as", ["Mike", "mike", "MIKE", "  mike "])
    def test_a_name_in_use_is_refused_whatever_its_case(self, registry, taken_as):
        join(registry, "Mike")
        with pytest.raises(NameTaken):
            join(registry, taken_as, SingerSettings(0, 0.4))

    def test_the_refusal_moves_nothing(self, registry):
        _, token = join(registry, "Mike")
        with pytest.raises(NameTaken):
            join(registry, "mike", SingerSettings(-1, 0.1))
        assert registry.lookup(token) == ("Mike", KEY_TWO)

    @pytest.mark.parametrize("name", ["Pikaraoke", "Randomizer", "randomizer", " PIKARAOKE"])
    def test_reserved_names_are_refused(self, registry, name):
        with pytest.raises(NameTaken):
            join(registry, name)

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_name_becomes_an_anon_name_with_the_picked_settings(self, registry, blank):
        name, token = join(registry, blank)
        assert re.fullmatch(r"Anon-[A-Za-z0-9]{4}", name)
        assert registry.lookup(token) == (name, KEY_TWO)

    def test_an_anon_name_is_picked_again_until_it_is_free(self, registry, monkeypatch):
        monkeypatch.setattr(
            "pikaraoke.lib.singers.secrets.choice", MagicMock(side_effect=list("aaaabbbb"))
        )
        first, _ = join(registry, "")
        second, _ = join(registry, "")
        assert (first, second) == ("Anon-aaaa", "Anon-bbbb")

        monkeypatch.setattr(
            "pikaraoke.lib.singers.secrets.choice", MagicMock(side_effect=list("aaaacccc"))
        )
        third, _ = join(registry, "")
        assert third == "Anon-cccc"


class TestLookup:
    def test_a_guests_token_finds_the_name_and_settings_the_registry_holds(self, registry):
        _, token = join(registry, "Mike")
        assert registry.lookup(token) == ("Mike", KEY_TWO)

    def test_a_token_finds_its_own_guest_among_several(self, registry):
        join(registry, "Sue", SingerSettings(0, 0.4))
        _, token = join(registry, "Mike")
        join(registry, "Tom", SingerSettings(1, 0.1))

        assert registry.lookup(token) == ("Mike", KEY_TWO)

    @pytest.mark.parametrize("token", [None, "", "not-the-token"])
    def test_no_token_or_an_unknown_one_finds_nobody(self, registry, token):
        join(registry)
        assert registry.lookup(token) is None

    def test_a_non_ascii_token_finds_nobody_instead_of_raising(self, registry):
        join(registry)
        assert registry.lookup("tökén") is None

    def test_a_new_registry_finds_nobody_from_before(self, preferences, on_rename):
        _, token = join(SingerRegistry(preferences, on_rename))
        after_restart = SingerRegistry(preferences, on_rename)
        assert after_restart.lookup(token) is None


class TestUpdate:
    def test_saving_settings_keeps_the_name_and_token(self, registry, on_rename):
        name, token = join(registry)
        new_settings = SingerSettings(-1, 0.2)

        held = registry.save(token, name, new_settings)

        assert held == ("Mike", token)
        assert registry.lookup(token) == ("Mike", new_settings)
        on_rename.assert_not_called()

    def test_a_rename_moves_the_guest_and_calls_on_rename_once(self, registry, on_rename):
        _, token = join(registry)

        held = registry.save(token, "Michael", KEY_TWO)

        assert held == ("Michael", token)
        on_rename.assert_called_once_with("Mike", "Michael")
        assert registry.lookup(token) == ("Michael", KEY_TWO)
        assert registry.settings_for("Michael") == KEY_TWO

    def test_the_old_name_is_free_after_a_rename(self, registry):
        _, token = join(registry)
        registry.save(token, "Michael", KEY_TWO)

        reused, _token = join(registry, "Mike", SingerSettings(0, 0.4))

        assert reused == "Mike"

    def test_a_case_change_renames_so_queued_songs_follow_the_spelling(self, registry, on_rename):
        _, token = join(registry, "mike")

        held = registry.save(token, "Mike", KEY_TWO)

        assert held == ("Mike", token)
        on_rename.assert_called_once_with("mike", "Mike")

    def test_a_blank_name_keeps_the_current_one(self, registry, on_rename):
        _, token = join(registry)

        held = registry.save(token, "  ", SingerSettings(1, 0.5))

        assert held == ("Mike", token)
        on_rename.assert_not_called()
        assert registry.lookup(token) == ("Mike", SingerSettings(1, 0.5))

    def test_two_saves_with_the_same_token_are_one_guest_even_if_the_second_has_the_old_name(
        self, registry, on_rename
    ):
        """The second save was sent before the first one's reply reached the phone."""
        _, token = join(registry)
        registry.save(token, "Michael", KEY_TWO)

        name, kept_token = registry.save(token, "Mike", SingerSettings(1, 0.1))

        assert (name, kept_token) == ("Mike", token)
        assert registry.lookup(token) == ("Mike", SingerSettings(1, 0.1))
        assert [call.args for call in on_rename.call_args_list] == [
            ("Mike", "Michael"),
            ("Michael", "Mike"),
        ]

    def test_a_save_with_the_name_just_held_is_not_taken_by_the_guest_themselves(self, registry):
        _, token = join(registry)
        registry.save(token, "Michael", KEY_TWO)

        assert registry.save(token, "michael", KEY_TWO) == ("michael", token)

    def test_a_name_another_guest_holds_raises_and_changes_nothing(self, registry, on_rename):
        _, token = join(registry, "Mike")
        join(registry, "Sue", SingerSettings(0, 0.4))

        with pytest.raises(NameTaken):
            registry.save(token, "sue", SingerSettings(-3, 0.0))

        on_rename.assert_not_called()
        assert registry.lookup(token) == ("Mike", KEY_TWO)
        assert registry.settings_for("Sue") == SingerSettings(0, 0.4)

    def test_a_reserved_name_raises(self, registry):
        _, token = join(registry)
        with pytest.raises(NameTaken):
            registry.save(token, "Randomizer", KEY_TWO)

    def test_an_on_rename_that_raises_leaves_the_new_name_and_settings_held(self, preferences):
        """The registry changed first, so it still matches whatever the callback moved."""
        registry = SingerRegistry(preferences, MagicMock(side_effect=RuntimeError("boom")))
        _, token = join(registry)
        new_settings = SingerSettings(-1, 0.2)

        with pytest.raises(RuntimeError, match="boom"):
            registry.save(token, "Michael", new_settings)

        assert registry.lookup(token) == ("Michael", new_settings)
        reused, _ = join(registry, "Mike")
        assert reused == "Mike"

    def test_on_rename_runs_with_the_registry_locked(self, preferences):
        """Nobody can join as the old name before the songs have moved."""
        lock_was_held = []
        registry = SingerRegistry(
            preferences, lambda old, new: lock_was_held.append(registry._lock.locked())
        )
        _, token = join(registry)

        registry.save(token, "Michael", KEY_TWO)

        assert lock_was_held == [True]


class TestSettingsFor:
    def test_a_guest_gets_their_own_settings(self, registry):
        join(registry)
        assert registry.settings_for("Mike") == KEY_TWO

    def test_the_lookup_ignores_case(self, registry):
        join(registry)
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
        join(registry)
        preferences.set("vocal_volume", 0.9)
        assert registry.settings_for("Mike") == KEY_TWO


class TestHouseDefaults:
    def test_key_zero_and_the_house_vocal_volume(self, registry):
        assert registry.house_defaults() == SingerSettings(0, 0.4)

    def test_it_follows_a_changed_preference(self, registry, preferences):
        preferences.set("vocal_volume", 0.9)
        assert registry.house_defaults() == SingerSettings(0, 0.9)
