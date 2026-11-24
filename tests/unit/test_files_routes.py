"""Render tests for the /browse (files) page and the song edit, rename and delete routes.

Browse is checked through the rendered rows and links, not CSS values: the route files each song
under a letter by artist or by song, and the template draws the strip, the rows' three states
and the admin's menu from what the route hands it.
"""

import os
from html.parser import HTMLParser
from unittest.mock import MagicMock, patch
from urllib.parse import quote

import pytest
import werkzeug
from flask import Flask
from flask_babel import Babel

import pikaraoke

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.lib.queue_hold import QueueHold
from pikaraoke.lib.queue_manager import QueueManager
from pikaraoke.lib.song_manager import SongManager
from pikaraoke.routes.admin import admin_bp
from pikaraoke.routes.files import files_bp

SONGS = [
    "/songs/Artist - Song One---abc123def45.mp4",
    "/songs/Band - Failed Track---mno345pqr67.mp4",
    "/songs/Queued - Waiting---ghi789stu90.mp4",
    "/songs/Live - Now Processing---jkl012vwx34.mp4",
]


@pytest.fixture
def app():
    """A Flask app that can render files.html end to end.

    files.html extends base.html, which resolves several blueprints via
    url_for; stub the endpoints the templates reference so url_for succeeds
    without pulling in every real blueprint. admin_bp is real: it gives every
    page the `admin` flag.
    """
    pkg_dir = os.path.dirname(pikaraoke.__file__)
    test_app = Flask(
        __name__,
        template_folder=os.path.join(pkg_dir, "templates"),
        static_folder=os.path.join(pkg_dir, "static"),
    )
    test_app.secret_key = "test"  # flash() needs a session
    test_app.config["ADMIN_PASSWORD"] = None  # admin_bp's context processor reads it
    test_app.register_blueprint(files_bp)
    test_app.register_blueprint(admin_bp)
    for endpoint in (
        "home.home",
        "queue.queue",
        "search.search",
        "info.info",
        "processing.processing",
        "queue.enqueue",
        "batch_song_renamer.browse",
        "song_info.song_info",
    ):
        test_app.add_url_rule(f"/__stub/{endpoint}", endpoint=endpoint, view_func=lambda: "")

    # Babel wires both the route's flask_babel.gettext and the template {% trans %}.
    Babel(test_app)
    test_app.jinja_env.globals.update(
        filename_from_path=SongManager.filename_from_path, url_escape=quote
    )
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


def _mock_karaoke(songs):
    k = MagicMock()
    k.song_manager.songs = list(songs)
    k.song_manager.filename_from_path = SongManager.filename_from_path
    k.library_tools.is_busy.return_value = False
    k.library_tools.is_waiting_for_pick.return_value = False
    return k


# --- A small page reader: the rendered rows and links, not the markup around them ---------------

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source"}


class _Node:
    def __init__(self, tag: str, attrs: dict, parent: "_Node | None") -> None:
        self.tag, self.attrs, self.parent, self.children = tag, attrs, parent, []

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    @property
    def text(self) -> str:
        return " ".join(
            " ".join(c if isinstance(c, str) else c.text for c in self.children).split()
        )

    def find_all(self, tag: str | None = None, cls: str | None = None, **attrs) -> list["_Node"]:
        found = []
        for child in self.children:
            if isinstance(child, str):
                continue
            if (
                (tag is None or child.tag == tag)
                and (cls is None or cls in child.classes)
                and all(child.attrs.get(k.replace("_", "-")) == v for k, v in attrs.items())
            ):
                found.append(child)
            found.extend(child.find_all(tag, cls, **attrs))
        return found


class _Page(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.html = html
        self.root = _Node("root", {}, None)
        self._open = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs), self._open)
        self._open.children.append(node)
        if tag not in _VOID:
            self._open = node

    def handle_endtag(self, tag):
        node = self._open
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self._open = node.parent

    def handle_data(self, data):
        self._open.children.append(data)

    def find_all(self, *args, **kwargs):
        return self.root.find_all(*args, **kwargs)

    @property
    def rows(self) -> list[tuple[str, ...]]:
        """Each row as (top line, bottom line, slot): a one-line row has an empty bottom line."""
        out = []
        for row in self.root.find_all(cls="sr-row"):
            top = (row.find_all(cls="sr-title") or row.find_all(cls="sr-one"))[0].text
            sub = row.find_all(cls="sr-sub")
            [slot] = row.find_all(cls="sr-slot")
            out.append((top, sub[0].text if sub else "", slot.text))
        return out

    @property
    def strip(self) -> dict[str, _Node]:
        """The strip's entries by label."""
        [nav] = self.find_all("nav", aria_label="Songs by letter")
        return {entry.text: entry for entry in nav.find_all(cls="bp-letter")}

    @property
    def label(self) -> str:
        return self.find_all(cls="bp-label")[0].text

    @property
    def chosen_mode(self) -> str:
        [toggle] = self.find_all(cls="bp-toggle")
        [chosen] = [a for a in toggle.find_all("a") if a.attrs.get("aria-current") == "true"]
        return chosen.text


def _song(name: str, n: int) -> str:
    return f"/songs/{name}---{n:011d}.mp4"


def _karaoke(tmp_path, songs, *, states=None, busy=(), picking=()):
    """A fake karaoke with real parts: the queue hold over a real queue, and a library whose
    pipeline states, busy songs and lyrics picks come from the test."""
    events = EventSystem()
    preferences = PreferenceManager(config_file_path=str(tmp_path / "config.ini"))
    queue_manager = QueueManager(preferences=preferences, events=events)
    library_tools = MagicMock()
    library_tools.is_busy.side_effect = lambda path: path in busy
    library_tools.is_waiting_for_pick.side_effect = lambda path: path in picking
    k = _mock_karaoke(songs)
    pipeline = states or {}
    k.song_manager.get_paths_by_pipeline_state.side_effect = lambda wanted: [
        path for path, state in pipeline.items() if state in wanted
    ]
    k.library_tools = library_tools
    k.queue_hold = QueueHold(queue_manager, events, library_tools, k.song_manager)
    return k


@pytest.fixture
def browse(client, tmp_path, monkeypatch):
    """Fetch /browse as a guest or an admin and read the page. The same client keeps its cookies
    from one call to the next."""

    def fetch(songs, *, admin=False, query="", **karaoke_args):
        k = _karaoke(tmp_path, songs, **karaoke_args)
        monkeypatch.setattr("pikaraoke.routes.files.get_karaoke_instance", lambda: k)
        monkeypatch.setattr("pikaraoke.routes.files.get_site_name", lambda: "PiKaraoke")
        monkeypatch.setattr("pikaraoke.routes.files.is_admin", lambda: admin)
        monkeypatch.setattr("pikaraoke.routes.admin.is_admin", lambda: admin)
        response = client.get("/browse" + query)
        assert response.status_code == 200
        return _Page(response.get_data(as_text=True))

    return fetch


LIBRARY = [
    _song("Queen - Bohemian Rhapsody", 1),
    _song("Queen - Another One Bites the Dust", 2),
    _song("Bee Gees - Stayin' Alive", 3),
    _song("Blondie - Heart of Glass", 4),
    _song("Billie Eilish - Bad Guy", 5),
    _song("Britney Spears - ...Baby One More Time", 6),
    _song("Bad Romance | Lady Gaga", 7),
    _song("'Defying Gravity'", 8),
    _song("Yesterday", 9),
]
HASH_SONGS = [_song("99 Luftballons", 10), _song("周杰倫 - 晴天", 11)]


def test_by_artist_is_the_default_and_the_top_line_is_the_artist(browse):
    page = browse(LIBRARY)

    assert page.chosen_mode == "By artist"
    assert page.label == "B artists"
    assert page.rows == [
        ("Bee Gees", "Stayin' Alive", "Queue"),
        ("Billie Eilish", "Bad Guy", "Queue"),
        ("Blondie", "Heart of Glass", "Queue"),
        ("Britney Spears", "...Baby One More Time", "Queue"),
    ]


def test_by_song_files_a_song_under_its_own_letter(browse):
    page = browse(LIBRARY, query="?by=song&letter=b")

    assert page.chosen_mode == "By song"
    assert page.label == "B songs"
    assert page.rows == [
        ("...Baby One More Time", "Britney Spears", "Queue"),
        ("Bad Guy", "Billie Eilish", "Queue"),
        ("Bad Romance", "Lady Gaga", "Queue"),
        ("Bohemian Rhapsody", "Queen", "Queue"),
    ]


def test_queen_is_under_q_by_artist_and_a_song_under_b_by_song(browse):
    by_artist = browse(LIBRARY, query="?by=artist&letter=q")
    by_song = browse(LIBRARY, query="?by=song&letter=a")

    assert by_artist.rows[0][:2] == ("Queen", "Another One Bites the Dust")
    assert by_artist.rows[1][:2] == ("Queen", "Bohemian Rhapsody")
    assert by_song.rows == [("Another One Bites the Dust", "Queen", "Queue")]


@pytest.mark.parametrize("by", ["artist", "song"])
def test_a_name_with_no_split_is_one_line_under_its_first_letter(browse, by):
    yesterday = browse(LIBRARY, query=f"?by={by}&letter=y")
    defying = browse(LIBRARY, query=f"?by={by}&letter=d")

    assert yesterday.rows == [("Yesterday", "", "Queue")]
    assert defying.rows == [("'Defying Gravity'", "", "Queue")]


def test_a_raw_youtube_title_is_split_by_the_parser(browse):
    by_artist = browse(LIBRARY, query="?by=artist&letter=l")
    by_song = browse(LIBRARY, query="?by=song&letter=b")

    assert by_artist.rows == [("Lady Gaga", "Bad Romance", "Queue")]
    assert ("Bad Romance", "Lady Gaga", "Queue") in by_song.rows


def test_the_hash_entry_holds_digits_and_other_scripts(browse):
    page = browse(LIBRARY + HASH_SONGS, query="?letter=numeric")

    assert page.label == "# artists"
    assert page.rows == [
        ("99 Luftballons", "", "Queue"),
        ("周杰倫", "晴天", "Queue"),
    ]


def test_the_strip_links_letters_with_songs_and_disables_the_rest(browse):
    page = browse(LIBRARY + HASH_SONGS, query="?by=song&letter=b")
    strip = page.strip

    assert list(strip) == ["#", *"ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    assert strip["B"].tag == "a" and strip["B"].attrs["aria-current"] == "page"
    assert strip["B"].attrs["href"] == "/browse?by=song&letter=b"
    assert strip["#"].attrs["href"] == "/browse?by=song&letter=numeric"
    assert strip["Y"].tag == "a" and "aria-current" not in strip["Y"].attrs
    for empty in ("C", "X", "Z"):
        assert strip[empty].tag == "span"
        assert strip[empty].attrs["aria-disabled"] == "true"
        assert "href" not in strip[empty].attrs


def test_the_toggle_keeps_the_letter(browse):
    page = browse(LIBRARY, query="?by=artist&letter=q")
    [toggle] = page.find_all(cls="bp-toggle")

    assert [a.attrs["href"] for a in toggle.find_all("a")] == [
        "/browse?by=artist&letter=q",
        "/browse?by=song&letter=q",
    ]


def test_the_first_visit_opens_the_hash_entry_when_it_has_songs(browse):
    assert browse(LIBRARY + HASH_SONGS).label == "# artists"


def test_a_missing_or_empty_letter_gives_the_first_one_with_songs(browse):
    songs = [_song("Queen - Bohemian Rhapsody", 1), _song("Zedd - Clarity", 2)]

    assert browse(songs).label == "Q artists"
    assert browse(songs, query="?letter=b").label == "Q artists"
    assert browse(songs, query="?letter=1").label == "Q artists"
    assert browse(songs, query="?by=bogus").chosen_mode == "By artist"


def test_a_capital_letter_in_the_url_is_the_same_letter(browse):
    songs = [_song("Queen - Bohemian Rhapsody", 1), _song("Zedd - Clarity", 2)]

    assert browse(songs, query="?letter=Z").label == "Z artists"
    assert browse(songs, query="?letter=NUMERIC").label == "Q artists"


def test_the_mode_and_letter_are_remembered_for_a_plain_visit(browse):
    first = browse(LIBRARY, query="?by=song&letter=y")
    again = browse(LIBRARY)

    assert first.rows == again.rows == [("Yesterday", "", "Queue")]
    assert again.chosen_mode == "By song"


def test_a_remembered_letter_that_has_emptied_falls_back(browse):
    browse(LIBRARY, query="?by=artist&letter=q")

    page = browse([s for s in LIBRARY if "Queen" not in s])

    assert page.label == "B artists"


def test_an_unknown_cookie_value_is_not_used(client, browse):
    client.set_cookie("browse_by", "bogus")
    client.set_cookie("browse_letter", "zz")

    page = browse(LIBRARY)

    assert page.chosen_mode == "By artist" and page.label == "B artists"


# --- The three states of a row ------------------------------------------------------------------


def _states_library():
    ready, busy_ready = _song("Ready - Song", 1), _song("Busy - Ready Song", 2)
    held, picking = _song("Held - Processing Song", 3), _song("Pick - Lyrics Song", 4)
    stuck, failed = _song("Stuck - Never Finished", 5), _song("Failed - Broken Song", 6)
    return {
        "songs": [ready, busy_ready, held, picking, stuck, failed],
        "states": {held: "pending", picking: "pending", stuck: "pending", failed: "failed"},
        "busy": {busy_ready, held},
        "picking": {picking},
    }


def test_an_admin_sees_ready_processing_and_needs_fix(browse):
    library = _states_library()
    slots = {}
    for letter in "bhprsf":  # one letter per song's artist
        page = browse(**library, admin=True, query=f"?letter={letter}")
        slots.update({top: slot for top, _, slot in page.rows})

    assert slots == {
        "Busy": "Queue",  # ready and busy is a plain Queue
        "Held": "Queue processing",
        "Pick": "Queue processing",
        "Ready": "Queue",
        "Stuck": "needs fix",
        "Failed": "needs fix",
    }


def test_a_needs_fix_row_has_no_queue_link_and_the_others_do(browse):
    page = browse(**_states_library(), admin=True, query="?letter=s")

    [row] = page.find_all(cls="sr-row")
    assert not row.find_all("a")
    assert row.find_all(cls="is-fix")

    page = browse(**_states_library(), admin=True, query="?letter=h")
    [link] = page.find_all(cls="add-song-link")
    assert link.attrs["href"].startswith("/__stub/queue.enqueue?song=/songs/Held")
    assert link.attrs["href"].endswith("&user=")
    assert "is-success" in link.classes


# --- Who sees what ------------------------------------------------------------------------------


def test_a_guest_never_sees_a_song_that_needs_a_fix(browse):
    library = _states_library()

    for letter in "sf":  # where the two needs-fix songs are filed: nothing there for a guest
        page = browse(**library, query=f"?letter={letter}")
        assert page.label == "B artists"
        assert all(slot != "needs fix" for _, _, slot in page.rows)


def test_a_letter_holding_only_needs_fix_songs_is_disabled_for_a_guest_only(browse):
    library = _states_library()

    guest = browse(**library).strip
    admin = browse(**library, admin=True).strip

    assert guest["S"].tag == "span" and guest["F"].tag == "span"
    assert admin["S"].tag == "a" and admin["F"].tag == "a"


def test_a_guest_has_no_gear_menu_info_or_batch_edit(browse):
    page = browse(SONGS)

    assert not page.find_all(cls="sr-gear")
    assert not page.find_all(id="browse-options")
    assert "Edit all songs" not in page.html and "Song info" not in page.html


def test_an_admin_has_a_gear_per_row_and_one_menu(browse):
    page = browse(LIBRARY, admin=True)

    assert len(page.find_all(cls="sr-gear")) == len(page.rows) == 4
    [menu] = page.find_all(id="browse-options")
    [edit] = menu.find_all(id="browse-options-edit")
    [info] = menu.find_all(id="browse-options-info")
    assert (edit.text, info.text) == ("Edit song", "Song info")
    assert "no-spa" in info.classes
    assert "Edit all songs" in page.html


def test_the_gear_carries_the_song_and_the_row_text_for_the_menu(browse):
    page = browse(LIBRARY, admin=True, query="?letter=b")

    [gear] = [g for g in page.find_all(cls="sr-gear") if "Bee" in g.attrs["data-title"]]
    assert gear.attrs["data-title"] == "Bee Gees · Stayin' Alive"
    assert gear.attrs["data-song"] == quote(LIBRARY[2], safe="/")
    assert gear.attrs["aria-label"] == "Options"


def test_the_menus_edit_link_returns_to_this_mode_and_letter(browse):
    html = browse(LIBRARY, admin=True, query="?by=song&letter=b").html

    assert '"/files/edit"' in html
    assert f'"{quote("/browse?by=song&letter=b")}"' in html


# --- Edges --------------------------------------------------------------------------------------


def test_an_empty_library_renders_with_every_letter_disabled(browse):
    page = browse([])

    assert page.rows == []
    assert "No songs in this list." in page.html
    assert len(page.strip) == 27
    assert all(entry.tag == "span" for entry in page.strip.values())


def test_the_page_sets_the_cookies_it_shows_with_a_long_life(client, browse):
    browse(LIBRARY + HASH_SONGS, query="?by=song&letter=numeric")

    assert client.get_cookie("browse_by").value == "song"
    assert client.get_cookie("browse_letter").value == "numeric"
    assert client.get_cookie("browse_letter").max_age == 10 * 365 * 24 * 3600


def test_no_letter_cookie_is_set_when_there_are_no_songs(client, browse):
    browse([])

    assert client.get_cookie("browse_by").value == "artist"
    assert client.get_cookie("browse_letter") is None


@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_edit_page_links_to_the_song_info(mock_get, _site, _admin, client):
    k = _mock_karaoke(SONGS)
    k.queue_manager.is_song_in_queue.return_value = False
    mock_get.return_value = k

    resp = client.get("/files/edit", query_string={"song": SONGS[0]})

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/__stub/song_info.song_info?song=" in body
    assert "Song info" in body


@patch("pikaraoke.routes.files.is_admin", return_value=False)
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_a_guest_cannot_rename_a_song(mock_get, _admin, client):
    k = _mock_karaoke(SONGS)
    k.queue_manager.is_song_in_queue.return_value = False
    mock_get.return_value = k

    resp = client.post(
        "/files/edit", data={"old_file_name": SONGS[0], "new_file_name": "Stolen Name"}
    )

    assert resp.status_code == 302
    k.song_manager.rename.assert_not_called()


def _flashes(client):
    with client.session_transaction() as sess:
        return [(category, message) for category, message in sess.get("_flashes", [])]


def _admin_karaoke():
    k = _mock_karaoke(SONGS)
    k.queue_manager.is_song_in_queue.return_value = False
    return k


@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_rename_passes_the_name_with_the_youtube_id_to_the_manager(mock_get, _admin, client):
    mock_get.return_value = k = _admin_karaoke()

    client.post("/files/edit", data={"old_file_name": SONGS[0], "new_file_name": "Better Name"})

    k.song_manager.rename.assert_called_once_with(SONGS[0], "Better Name---abc123def45")
    assert _flashes(client)[0][0] == "is-warning"


@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_rename_onto_a_taken_name_flashes_that_it_exists(mock_get, _admin, client):
    mock_get.return_value = k = _admin_karaoke()
    k.song_manager.rename.side_effect = FileExistsError("taken")

    resp = client.post(
        "/files/edit", data={"old_file_name": SONGS[0], "new_file_name": "Taken Name"}
    )

    assert resp.status_code == 302
    ((category, message),) = _flashes(client)
    assert category == "is-danger"
    assert "Filename already exists" in message
    assert "Taken Name---abc123def45.mp4" in message


@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_rename_to_a_blank_name_flashes_that_it_is_empty(mock_get, _admin, client):
    mock_get.return_value = k = _admin_karaoke()
    k.song_manager.rename.side_effect = ValueError("blank")

    client.post("/files/edit", data={"old_file_name": SONGS[0], "new_file_name": ""})

    ((category, message),) = _flashes(client)
    assert category == "is-danger"
    assert "can't be empty" in message


@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_delete_that_fails_flashes_an_error_not_success(mock_get, _admin, client):
    mock_get.return_value = k = _admin_karaoke()
    k.song_manager.delete.side_effect = OSError("disk full")

    client.get("/files/delete", query_string={"song": SONGS[0]})

    ((category, message),) = _flashes(client)
    assert category == "is-danger"
    assert "disk full" in message


BUSY_REASONS = ["is_busy", "is_waiting_for_pick"]


def _busy_karaoke(reason):
    """An admin's karaoke whose library tools report SONGS[0] busy for ``reason``."""
    k = _admin_karaoke()
    getattr(k.library_tools, reason).return_value = True
    return k


@pytest.mark.parametrize("reason", BUSY_REASONS)
@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_delete_refuses_a_song_still_processing(mock_get, _admin, client, reason):
    mock_get.return_value = k = _busy_karaoke(reason)

    client.get("/files/delete", query_string={"song": SONGS[0]})

    k.song_manager.delete.assert_not_called()
    ((category, message),) = _flashes(client)
    assert category == "is-danger"
    assert SONGS[0] in message


@pytest.mark.parametrize("reason", BUSY_REASONS)
@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_edit_page_refuses_a_song_still_processing(mock_get, _site, _admin, client, reason):
    mock_get.return_value = _busy_karaoke(reason)

    resp = client.get("/files/edit", query_string={"song": SONGS[0]})

    assert resp.status_code == 302
    assert _flashes(client)[0][0] == "is-danger"


@pytest.mark.parametrize("reason", BUSY_REASONS)
@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_rename_refuses_a_song_still_processing(mock_get, _admin, client, reason):
    mock_get.return_value = k = _busy_karaoke(reason)

    client.post("/files/edit", data={"old_file_name": SONGS[0], "new_file_name": "Better Name"})

    k.song_manager.rename.assert_not_called()
    ((category, message),) = _flashes(client)
    assert category == "is-danger"
    assert SONGS[0] in message


@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_delete_acts_on_a_song_that_is_not_processing(mock_get, _admin, client):
    mock_get.return_value = k = _admin_karaoke()

    client.get("/files/delete", query_string={"song": SONGS[0]})

    k.song_manager.delete.assert_called_once_with(SONGS[0])
