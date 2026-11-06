"""The guests of one run of the app: who joined, and the key and vocal volume they sing at."""

from __future__ import annotations

import secrets
import string
import threading
import unicodedata
from dataclasses import dataclass
from typing import Callable

from flask_babel import _

from pikaraoke.lib.preference_manager import PreferenceManager

# Names the app uses for itself: never a guest, and never limited by the per-user song cap.
RESERVED_NAMES = ("Pikaraoke", "Randomizer")
# Beyond this many semitones the pitch shift distorts the song.
KEY_LIMIT = 3
# Longest name a guest can take, in characters. The name rides in a 4 KB cookie and on screen.
NAME_LIMIT = 30

_RESERVED_KEYS = frozenset(name.casefold() for name in RESERVED_NAMES)
_ANON_ALPHABET = string.ascii_letters + string.digits


class NameTaken(Exception):
    """The name is reserved or held by another guest. The message is for the guest to read."""


@dataclass(frozen=True)
class SingerSettings:
    """What a guest's songs start at: key in semitones, vocal volume from 0.0 to 1.0."""

    semitones: int
    vocal_volume: float


@dataclass
class _Guest:
    name: str
    token: str
    settings: SingerSettings


def _spelling(name: str) -> str:
    """The name as kept: no surrounding spaces, and one Unicode form for accented letters."""
    return unicodedata.normalize("NFC", name.strip())


def _key(name: str) -> str:
    """Names are the same guest when they differ only in case, spaces or Unicode form."""
    return unicodedata.normalize("NFC", _spelling(name).casefold())


class SingerRegistry:
    """The guests who joined during this run of the app; forgotten when it stops.

    A guest is a name plus a random token the phone keeps in a cookie. The token alone says which
    guest a phone is, so a phone whose name cookie is out of date still finds its own guest, and
    a token from an earlier run finds nobody.

    Lock order: registry, then queue, tracker or playback. Nothing may take the registry lock
    while holding one of those, because `save` calls `on_rename` with the registry lock held.
    Nothing called from `on_rename` may call the registry either: its lock is not reentrant.
    """

    def __init__(
        self, preferences: PreferenceManager, on_rename: Callable[[str, str], None]
    ) -> None:
        self._preferences = preferences
        self._on_rename = on_rename
        self._lock = threading.Lock()
        self._guests: dict[str, _Guest] = {}

    def save(self, token: str | None, name: str, settings: SingerSettings) -> tuple[str, str]:
        """Save the settings of the guest this token belongs to, or join a new guest.

        Returns the name the guest now holds and their token (an existing guest keeps theirs).
        A blank name keeps a guest's current name, and gives a new guest `Anon-` plus four random
        characters. When a guest's spelling changes (a case change included, because the queue and
        ownership checks compare names exactly) the registry changes first, then `on_rename(old,
        new)` runs once with the registry lock held, so nobody can join as the old name before
        the songs have moved. `on_rename` must not raise: the moves are in-memory loops and the
        notifications are caught by the caller. If a move did raise, the songs not yet moved
        would stay under the old name, which is free again, and the exception reaches the caller
        of `save`.

        Raises:
            NameTaken: the name is reserved or held by another guest.
        """
        with self._lock:
            guest = self._guest_with_token(token)
            if guest is None:
                return self._join(name, settings)
            self._update(guest, name, settings)
            return guest.name, guest.token

    def lookup(self, token: str | None) -> tuple[str, SingerSettings] | None:
        """The name the registry holds for this token's guest, and their settings; else None."""
        with self._lock:
            guest = self._guest_with_token(token)
            return (guest.name, guest.settings) if guest else None

    def settings_for(self, name: str) -> SingerSettings:
        """The settings of the guest holding exactly this name, else the house defaults.

        The queue, the tracker and the ownership checks compare names exactly, so a name that
        differs only in case is not the guest's songs. The house defaults cover the Randomizer,
        the admin's default user and a stale name. This is the one place the house vocal volume
        is resolved for playback.
        """
        with self._lock:
            guest = self._guests.get(_key(name))
            if guest is not None and guest.name == name:
                return guest.settings
        return self.house_defaults()

    def house_defaults(self) -> SingerSettings:
        """What a name that never joined sings at: key 0 and the house vocal volume."""
        return SingerSettings(0, self._preferences.get_or_default("vocal_volume"))

    def _join(self, name: str, settings: SingerSettings) -> tuple[str, str]:
        """Call with the lock held."""
        name = _spelling(name) or self._unused_anon_name()
        self._require_free(name)
        token = secrets.token_urlsafe(16)
        self._guests[_key(name)] = _Guest(name, token, settings)
        return name, token

    def _update(self, guest: _Guest, name: str, settings: SingerSettings) -> None:
        """Call with the lock held."""
        new_name = _spelling(name) or guest.name
        if _key(new_name) != _key(guest.name):
            self._require_free(new_name)
        old_name = guest.name
        del self._guests[_key(old_name)]
        guest.name = new_name
        guest.settings = settings
        self._guests[_key(new_name)] = guest
        if new_name != old_name:
            self._on_rename(old_name, new_name)

    def _guest_with_token(self, token: str | None) -> _Guest | None:
        """The guest this token belongs to. Call with the lock held."""
        if not token:
            return None
        # Encode so a non-ASCII cookie value fails the comparison instead of raising.
        candidate = token.encode()
        for guest in self._guests.values():
            if secrets.compare_digest(guest.token.encode(), candidate):
                return guest
        return None

    def _require_free(self, name: str) -> None:
        """Call with the lock held."""
        if _key(name) in _RESERVED_KEYS or _key(name) in self._guests:
            # MSG: Shown on the join form when the name is reserved or another guest already uses it
            raise NameTaken(_("That name is already taken. Please choose another."))

    def _unused_anon_name(self) -> str:
        """Call with the lock held."""
        while True:
            suffix = "".join(secrets.choice(_ANON_ALPHABET) for _position in range(4))
            if _key(f"Anon-{suffix}") not in self._guests:
                return f"Anon-{suffix}"
