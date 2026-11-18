"""The catalog compile leaves untranslated plurals to English instead of Babel's fill-in."""

import gettext

from scripts.compile_translations import compile_po

ONE_FORM_PO = """\
msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"
"Language: ja_JP\\n"
"Plural-Forms: nplurals=1; plural=0;\\n"

msgid "fills %(num)d line"
msgid_plural "fills %(num)d lines"
msgstr[0] ""

msgid "%(num)d word"
msgid_plural "%(num)d words"
msgstr[0] "%(num)d mot"

msgid "Lyrics"
msgstr "Paroles"

#, fuzzy
msgid "Timed"
msgstr "Chronométré"
"""


PARTLY_TRANSLATED_PO = """\
msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"
"Language: ru_RU\\n"
"Plural-Forms: nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
"(n%100<10 || n%100>=20) ? 1 : 2);\\n"

msgid "%(num)d line"
msgid_plural "%(num)d lines"
msgstr[0] "%(num)d строка"
msgstr[1] ""
msgstr[2] ""
"""


def compiled(tmp_path, text: str) -> gettext.GNUTranslations:
    po = tmp_path / "messages.po"
    po.write_text(text, encoding="utf-8")
    compile_po(po)
    with (tmp_path / "messages.mo").open("rb") as f:
        return gettext.GNUTranslations(f)


def test_an_untranslated_plural_falls_back_to_english_in_a_one_form_language(tmp_path):
    t = compiled(tmp_path, ONE_FORM_PO)

    assert t.ngettext("fills %(num)d line", "fills %(num)d lines", 5) == "fills %(num)d lines"
    assert t.ngettext("fills %(num)d line", "fills %(num)d lines", 1) == "fills %(num)d line"


def test_translated_messages_are_kept_and_fuzzy_ones_left_out(tmp_path):
    t = compiled(tmp_path, ONE_FORM_PO)

    assert t.ngettext("%(num)d word", "%(num)d words", 5) == "%(num)d mot"
    assert t.gettext("Lyrics") == "Paroles"
    assert t.gettext("Timed") == "Timed"


def test_it_reports_how_many_plurals_it_left_out(tmp_path):
    po = tmp_path / "messages.po"
    po.write_text(ONE_FORM_PO, encoding="utf-8")

    assert compile_po(po) == 1


def test_a_partly_translated_plural_is_left_to_english_not_mixed(tmp_path):
    t = compiled(tmp_path, PARTLY_TRANSLATED_PO)

    assert t.ngettext("%(num)d line", "%(num)d lines", 1) == "%(num)d line"
    assert t.ngettext("%(num)d line", "%(num)d lines", 5) == "%(num)d lines"
