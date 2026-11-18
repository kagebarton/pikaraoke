"""Compile every locale's ``messages.po`` to ``messages.mo``, leaving out untranslated plurals.

Used in place of ``pybabel compile`` (see ``pikaraoke/_TRANSLATION.md``). Babel fills
each empty form of an untranslated plural with the English singular or plural by the
form's index, so a language with one plural form (Japanese, Chinese, Korean, Thai,
Indonesian) reads "fills 5 line", and Russian "fills 21 line". Left out of the ``.mo``,
the message falls back to English, which picks its form by the English rule. Fuzzy
entries are left out as ``pybabel compile`` leaves them.
"""

import sys
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

TRANSLATIONS = Path(__file__).resolve().parents[1] / "pikaraoke" / "translations"


def drop_untranslated_plurals(catalog: Catalog) -> int:
    """Delete each plural message none of whose forms is translated; returns how many."""
    untranslated = [m for m in catalog if m.id and m.pluralizable and not any(m.string)]
    for message in untranslated:
        catalog.delete(message.id, message.context)
    return len(untranslated)


def compile_po(po: Path) -> int:
    """Write ``po``'s ``.mo`` beside it; returns how many plurals were left out."""
    with po.open("rb") as f:
        catalog = read_po(f)
    dropped = drop_untranslated_plurals(catalog)
    with po.with_suffix(".mo").open("wb") as f:
        write_mo(f, catalog)
    return dropped


def main() -> int:
    pos = sorted(TRANSLATIONS.glob("*/LC_MESSAGES/messages.po"))
    for po in pos:
        dropped = compile_po(po)
        print(f"{po.relative_to(TRANSLATIONS)}: {dropped} untranslated plurals left out")
    return 0 if pos else 1


if __name__ == "__main__":
    sys.exit(main())
