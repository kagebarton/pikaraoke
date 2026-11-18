"""How a lyric source's name reads once qualified, shared by every page that names one."""

from __future__ import annotations

from flask_babel import _


def qualified_name(name: str, *, auto: bool = False, edited: bool = False) -> str:
    """``name`` with its qualifiers in one bracket: "LRCLIB (auto, edited)", never
    "(auto) (edited)". ``auto`` marks the LRCLIB match a download picked by itself;
    ``edited``, lyrics whose words an admin fixed."""
    if auto and edited:
        return _("%(source)s (auto, edited)") % {"source": name}
    if auto:
        return _("%(source)s (auto)") % {"source": name}
    if edited:
        return _("%(source)s (edited)") % {"source": name}
    return name
