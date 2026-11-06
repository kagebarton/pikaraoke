"""The guests of one run of the app: who joined, and the key and vocal volume they sing at."""

from __future__ import annotations

import secrets
import string
import threading
from dataclasses import dataclass
from typing import Callable

from flask_babel import _

from pikaraoke.lib.preference_manager import PreferenceManager

# Names the app uses for itself: never a guest, and never limited by the per-user song cap.
RESERVED_NAMES = ("Pikaraoke", "Randomizer")
# Beyond this many semitones the pitch shift distorts the song.
KEY_LIMIT = 3

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


def _key(name: str) -> str:
    """Names are the same guest when they differ only in case or surrounding spaces."""
    return name.strip().casefold()


class SingerRegistry:
    """The guests who joined during this run of the app; forgotten when it stops.

    A guest is a name plus a random token the phone keeps in a cookie. Holding the token is
    what proves a phone joined as that name during this run, so a phone from an earlier run, or
    one whose name someone else took since, owns nothing.

    Lock order: registry, then queue, tracker or playback. Nothing may take the registry lock
    while holding one of those, because `update` calls `on_rename` with the registry lock held.
    """

    def __init__(self, preferences: PreferenceManager) -> None:
        self._preferences = preferences
        self._lock = threading.Lock()
        self._guests: dict[str, _Guest] = {}

    def join(self, name: str, settings: SingerSettings) -> tuple[str, str]:
        """Add a guest and return the name they hold and their token.

        A blank name becomes `Anon-` plus four random characters.

        Raises:
            NameTaken: the name is reserved or already held.
        """
        with self._lock:
            name = name.strip() or self._unused_anon_name()
            self._require_free(name)
            token = secrets.token_urlsafe(16)
            self._guests[_key(name)] = _Guest(name, token, settings)
            return name, token

    def update(
        self,
        old_name: str,
        token: str,
        new_name: str,
        settings: SingerSettings,
        on_rename: Callable[[str, str], None],
    ) -> str:
        """Save a guest's settings and spelling, and return the name now held.

        A blank new name keeps the current one. When the spelling changes (a case change
        included, because queue and ownership checks compare names exactly) `on_rename(old,
        new)` runs once, with the registry lock held, so nobody can join as the old name before
        the songs have moved. If it raises, the guest keeps their old name.

        Raises:
            PermissionError: the name and token do not match a guest of this run.
            NameTaken: the new name is reserved or held by another guest.
        """
        with self._lock:
            guest = self._guest_with_token(old_name, token)
            if guest is None:
                raise PermissionError(f"{old_name!r} did not join during this run")
            new_name = new_name.strip() or guest.name
            if _key(new_name) != _key(guest.name):
                self._require_free(new_name)
            if new_name != guest.name:
                on_rename(guest.name, new_name)
                del self._guests[_key(guest.name)]
                guest.name = new_name
                self._guests[_key(new_name)] = guest
            guest.settings = settings
            return guest.name

    def owns(self, name: str | None, token: str | None) -> bool:
        """True when this name and token belong to a guest who joined during this run."""
        with self._lock:
            return self._guest_with_token(name, token) is not None

    def settings_for(self, name: str) -> SingerSettings:
        """The guest's settings, or the house defaults for a name that never joined.

        The house defaults cover the Randomizer, the admin's default user and a stale name.
        This is the one place the house vocal volume is resolved for playback.
        """
        with self._lock:
            guest = self._guests.get(_key(name))
        if guest is not None:
            return guest.settings
        return SingerSettings(0, self._preferences.get_or_default("vocal_volume"))

    def _guest_with_token(self, name: str | None, token: str | None) -> _Guest | None:
        """The guest holding `name` if `token` is theirs. Call with the lock held."""
        if not name or not token:
            return None
        guest = self._guests.get(_key(name))
        # Encode so a non-ASCII cookie value fails the comparison instead of raising.
        if guest and secrets.compare_digest(guest.token.encode(), token.encode()):
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
