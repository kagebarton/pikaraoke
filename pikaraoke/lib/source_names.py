"""How a lyric source reads in words, shared by every page that names one."""

from __future__ import annotations

from flask_babel import _

from pikaraoke.lib.library_regen import (
    CUSTOM_ORIGIN,
    LRC_AUTO_ORIGIN,
    LRC_ORIGIN,
    MOVIE_ORIGIN,
)


def origin_names() -> dict[str, str]:
    """Each bundle ``lyrics.origin`` that names a source, in words; both LRCLIB origins
    read "LRCLIB", which :func:`qualified_name` marks auto where a page tells them apart."""
    return {
        "genius": _("Genius"),
        CUSTOM_ORIGIN: _("Custom lyrics"),
        MOVIE_ORIGIN: _("Movie subtitles"),
        LRC_ORIGIN: "LRCLIB",
        LRC_AUTO_ORIGIN: "LRCLIB",
        "srt": _("YouTube captions"),
    }


def qualified_name(name: str, *, origin: str | None = None, edited: bool = False) -> str:
    """``name`` with its qualifiers in one bracket: "LRCLIB (auto, edited)", never
    "(auto) (edited)". An ``origin`` of the LRCLIB match a download picked by itself reads
    auto; ``edited`` marks lyrics whose words an admin fixed."""
    auto = origin == LRC_AUTO_ORIGIN
    if auto and edited:
        return _("%(source)s (auto, edited)") % {"source": name}
    if auto:
        return _("%(source)s (auto)") % {"source": name}
    if edited:
        return _("%(source)s (edited)") % {"source": name}
    return name
