"""Route and render tests for Song Info, regenerate, repair and the library song lists.

A Flask app with the two blueprints and the real templates, over a ``tmp_path``
library with real bundles and a real ``LibraryTools``; only the processing
manager is a mock, so a queued job is whatever ``enqueue_regen`` was handed.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import quote

import pytest
import werkzeug
from flask import Flask
from flask_babel import Babel

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

import pikaraoke
from pikaraoke.lib import lrclib
from pikaraoke.lib.alignment_capture import SCHEMA_VERSION
from pikaraoke.lib.genius import GeniusSong, GeniusUnavailable
from pikaraoke.lib.library_regen import CaptionCheck
from pikaraoke.lib.library_tools import LibraryTools
from pikaraoke.lib.song_list import SongList
from pikaraoke.lib.song_manager import SongManager
from pikaraoke.routes.library import library_bp
from pikaraoke.routes.song_info import song_info_bp

# Endpoints base.html resolves via url_for that neither blueprint provides.
_STUB_ENDPOINTS = (
    "home.home",
    "queue.queue",
    "search.search",
    "search.lyrics_search",
    "files.browse",
    "info.info",
    "processing.processing",
)

GENIUS = {"id": 7, "title": "Defying Gravity", "artist": "Kristin Chenoweth"}
LRCLIB_MATCH = {
    "id": 5,
    "trackName": "Defying Gravity",
    "artistName": "Chenoweth & Menzel",
    "duration": 354.0,
}


def write_bundle(folder: Path, stem: str, root: Path | None = None, **fields) -> None:
    bundle = {"schema_version": SCHEMA_VERSION, "captured_at": "2026-10-19T18:03:52+00:00"}
    bundle.update(fields)
    path = (root or folder) / "alignment_debug" / f"{stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle), encoding="utf-8")


def poor_genius_bundle(**overrides) -> dict:
    """51 of 89 lines timed, LRCLIB's 5:54 match against a 4:17 video, fill refused."""
    fields = {
        "lyrics": {
            "origin": "genius",
            "genius": GENIUS,
            "lrclib": LRCLIB_MATCH,
            "ytasr": {"asr_file": "subtitles/x.en.asr.json3"},
            "lines": ["one"],
        },
        "pipeline_decisions": {"method_used": "joint"},
        "joint_stats": {
            "align_won": 22,
            "transcribe_won": 13,
            "ytasr_won": 16,
            "evidence_veto": {"n_vetoed": 0},
            "lrclib_fill": {"eligible": False, "reason": "arm_a_bail", "filled_lids": []},
        },
        "output_summary": {"line_count": 89, "lines_with_words": 51},
        "media_duration_s": 257.23,
    }
    fields.update(overrides)
    return fields


def caption_bundle() -> dict:
    return {
        "lyrics": {"origin": "srt"},
        "pipeline_decisions": {"method_used": "cue_align"},
        "output_summary": {"line_count": 39, "lines_with_words": 39},
        "media_duration_s": 200.0,
    }


class Env:
    """The app, its library folder and the knobs a test turns."""

    def __init__(self, tmp_path: Path):
        self.folder = tmp_path
        self.admin = True
        self.songs = SongList()
        self.processing = MagicMock()
        self.processing.get_active_job.return_value = None
        self.processing.pending_jobs = []
        self.processing.enqueue_regen.return_value = True
        self.genius = MagicMock()

        song_manager = MagicMock()
        song_manager.songs = self.songs
        song_manager.filename_from_path = SongManager.filename_from_path
        self.k = MagicMock()
        self.k.song_manager = song_manager
        self.k.library_tools = LibraryTools(
            self.processing, song_manager, str(tmp_path), self.genius
        )

        pkg_dir = os.path.dirname(pikaraoke.__file__)
        self.app = Flask(
            __name__,
            template_folder=os.path.join(pkg_dir, "templates"),
            static_folder=os.path.join(pkg_dir, "static"),
        )
        self.app.secret_key = "test"
        self.app.register_blueprint(song_info_bp)
        self.app.register_blueprint(library_bp)
        for endpoint in _STUB_ENDPOINTS:
            self.app.add_url_rule(
                f"/__stub/{endpoint}", endpoint=endpoint, view_func=lambda *a, **k: ""
            )
        Babel(self.app)
        self.app.jinja_env.globals.update(
            filename_from_path=SongManager.filename_from_path, url_escape=quote
        )
        self.client = self.app.test_client()

    def add_song(self, name: str, bundle: dict | None = None) -> str:
        """Put a video in the library (with a bundle when given); returns its path string."""
        video = self.folder / name
        video.write_bytes(b"")
        self.songs.add(str(video))
        if bundle is not None:
            write_bundle(self.folder, video.stem, **bundle)
        return str(video)

    def page(self, song: str):
        return self.client.get("/song_info", query_string={"song": song})

    def regenerate(self, song):
        return self.client.post("/song_info/regenerate", json={"song": song})


@pytest.fixture
def env(tmp_path, monkeypatch):
    e = Env(tmp_path)
    for module in ("song_info", "library"):
        prefix = f"pikaraoke.routes.{module}"
        monkeypatch.setattr(f"{prefix}.get_karaoke_instance", lambda: e.k)
        monkeypatch.setattr(f"{prefix}.get_site_name", lambda: "PiKaraoke")
        monkeypatch.setattr(f"{prefix}.is_admin", lambda: e.admin)
    return e


def text(response) -> str:
    return response.get_data(as_text=True)


class TestSongInfoAccess:
    def test_a_guest_is_sent_back_to_the_browser(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        env.admin = False

        response = env.page(song)

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/__stub/files.browse")

    def test_a_path_outside_the_library_is_rejected(self, env):
        env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        outside = env.folder / "elsewhere.mp4"
        outside.write_bytes(b"")

        assert env.page(str(outside)).status_code == 400
        assert env.client.get("/song_info").status_code == 400


class TestSongInfoPage:
    def test_a_poor_genius_song_shows_its_tiles(self, env):
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())))

        assert "Genius" in html and "up to date" in html
        assert "57%" in html and "38 guessed" in html
        assert "Not used" in html and "97 s longer" in html
        # Timed and LRCLIB are flagged; Lyrics is not.
        assert html.count("si-tile is-warn") == 2
        assert "mqdefault.jpg" in html and "aaaaaaaaaaa" in html
        assert "4:17" in html

    def test_picks_tab_lists_the_genius_and_lrclib_choices(self, env):
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())))

        assert "Genius lyrics" in html
        assert "Defying Gravity" in html and "Kristin Chenoweth" in html
        assert "https://genius.com/songs/7" in html
        assert "Defying Gravity · Chenoweth &amp; Menzel · 5:54" in html
        assert "YouTube auto-captions used" in html

    def test_alignment_tab_counts_and_bar(self, env):
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())))

        assert "of 89 lines timed word by word" in html
        assert "The other 38 are placed between their neighbours." in html
        for legend in ("Lyric aligner 22", "Transcription 13", "YouTube captions 16", "Guessed 38"):
            assert legend in html
        assert "LRCLIB fill" not in html  # nothing was filled
        # Each width is its count over the line count, unadjusted.
        assert "width: 24.719%" in html and "width: 42.697%" in html

    def test_alignment_tab_explains_the_lrclib_fit_and_the_route(self, env):
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())))

        assert "The match is 5:54; this video is 4:17 (97 s longer)." in html
        assert "Not used: its line times didn&#39;t line up with this video." in html
        assert "the lyric aligner, a transcription and YouTube&#39;s auto-captions." in html

    def test_a_used_match_says_how_many_lines_it_filled(self, env):
        bundle = poor_genius_bundle()
        bundle["joint_stats"]["lrclib_fill"] = {"eligible": True, "filled_lids": [3, 9]}
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", bundle)))

        assert "fills 2 lines" in html
        assert "Used: it filled 2 lines." in html
        assert "LRCLIB fill 2" in html
        assert html.count("si-tile is-warn") == 1  # only Timed: LRCLIB worked

    def test_a_skipped_match_is_the_admins_choice_on_disk(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        lrclib.write_skip_marker(lrclib.lrc_path(Path(song)))
        html = text(env.page(song))

        assert "skipped by you" in html
        assert "Skipped: you chose no match." in html
        assert "The match is" not in html

    def test_no_match_found(self, env):
        bundle = poor_genius_bundle()
        bundle["lyrics"] = {"origin": "genius", "genius": GENIUS, "lines": ["one"]}
        bundle["joint_stats"]["lrclib_fill"] = {}
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", bundle)))

        assert "no match found" in html
        assert "No LRCLIB match was found." in html

    def test_a_short_length_gap_names_the_reason_instead(self, env):
        bundle = poor_genius_bundle(media_duration_s=352.0)
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", bundle)))

        tiles = html.split('class="tabs is-fullwidth si-tabs"')[0].split("</style>")[-1]
        assert "lines didn&#39;t line up" in tiles
        assert "s longer" not in tiles
        assert "(2 s longer)" in html  # the Alignment tab still gives the exact gap

    def test_a_caption_song(self, env):
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle())))

        assert "YouTube captions" in html
        assert "Genius songs only" in html
        assert "si-tile is-warn" not in html
        assert "https://genius.com" not in html  # no Genius row
        assert "Timed 39" in html and "Guessed" not in html
        assert "timed against the caption" in html
        assert "LRCLIB fit" not in html

    def test_a_song_behind_says_which_version(self, env):
        bundle = {**caption_bundle(), "schema_version": SCHEMA_VERSION - 1}
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", bundle)))

        assert f"behind (v{SCHEMA_VERSION - 1})" in html

    def test_a_transcribed_song_has_no_alignment_tab_but_can_regenerate(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4")
        (env.folder / "karaoke").mkdir()
        (env.folder / "karaoke" / "A---aaaaaaaaaaa.ass").write_text("", encoding="utf-8")
        html = text(env.page(song))

        assert "No lyrics" in html
        assert 'data-tab="alignment"' not in html
        assert 'id="regenerate"' in html

    def test_an_unprocessed_song_has_nothing_to_regenerate_from(self, env):
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4")))

        assert "Not processed" in html
        assert 'id="regenerate"' not in html

    def test_a_song_that_is_not_a_video(self, env):
        song = env.folder / "Track---aaaaaaaaaaa.mp3"
        song.write_bytes(b"")
        env.songs.add(str(song))
        html = text(env.page(str(song)))

        assert "Lyrics tools work on video songs only." in html
        assert "si-tile" not in html.split("</style>")[-1]
        assert 'id="regenerate"' not in html

    def test_a_busy_song_has_its_button_disabled_and_a_way_to_the_queue(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        env.processing.pending_jobs = [song]
        html = text(env.page(song))

        assert 'id="regenerate" class="button si-btn" disabled' in html
        assert "This song has a regen waiting or running." in html
        assert "/__stub/processing.processing" in html

    def test_an_idle_song_can_regenerate(self, env):
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())))

        assert 'id="regenerate" class="button si-btn">' in html
        assert "regen waiting or running" not in html


class TestSongInfoHistory:
    def song_with_backups(self, env) -> str:
        stem = "A---aaaaaaaaaaa"
        song = env.add_song(f"{stem}.mp4", poor_genius_bundle())
        no_lrclib = poor_genius_bundle()
        no_lrclib["lyrics"] = {"origin": "genius", "genius": GENIUS, "lines": ["one"]}
        write_bundle(
            env.folder,
            stem,
            root=env.folder / "regen_backup_20261019T175506Z",
            schema_version=10,
            captured_at="2026-09-21T10:00:00+00:00",
            **poor_genius_bundle(),
        )
        write_bundle(
            env.folder,
            stem,
            root=env.folder / "regen_backup_20260921T170629Z",
            schema_version=8,
            captured_at="2026-07-16T10:00:00+00:00",
            **no_lrclib,
        )
        return song

    def test_versions_are_listed_newest_first_each_under_its_folder(self, env):
        html = text(env.page(self.song_with_backups(env)))
        history = html.split('id="tab-history"')[1]

        assert history.index("19 Oct 2026") < history.index("21 Sep 2026")
        assert history.index("21 Sep 2026") < history.index("16 Jul 2026")
        assert "regen_backup_20261019T175506Z" in history
        assert "regen_backup_20260921T170629Z" in history
        assert ">v11<" in history and ">v10<" in history and ">v8<" in history
        assert "51 of 89 lines" in history
        assert "A version saved in several backups is listed once" in history

    def test_a_version_notes_what_it_added(self, env):
        history = text(env.page(self.song_with_backups(env))).split('id="tab-history"')[1]

        # v10 gained LRCLIB over v8; v11 and v10 hold the same picks.
        assert "LRCLIB 5:54 added" in history
        assert history.count("si-chg") == 1
        assert "no LRCLIB" in history

    def test_a_match_without_a_length_is_still_a_match(self, env):
        bundle = poor_genius_bundle()
        bundle["lyrics"]["lrclib"] = {"id": 5, "trackName": "Defying Gravity"}
        history = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", bundle)))
        history = history.split('id="tab-history"')[1]

        assert "LRCLIB<" in history
        assert "no LRCLIB" not in history

    def test_no_backups_shows_the_empty_state(self, env):
        history = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())))
        history = history.split('id="tab-history"')[1]

        assert "19 Oct 2026" in history
        assert "No earlier versions yet." in history


class TestRegenerateRoute:
    def test_a_guest_cannot(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        env.admin = False

        response = env.regenerate(song)

        assert response.status_code == 403
        assert response.get_json()["success"] is False
        env.processing.enqueue_regen.assert_not_called()

    @pytest.mark.parametrize("body", [{"song": None}, {"song": ["a"]}, {}, [1]])
    def test_a_missing_or_malformed_song_is_rejected(self, env, body):
        env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())

        response = env.client.post("/song_info/regenerate", json=body)

        assert response.status_code == 400
        assert response.get_json()["success"] is False

    def test_a_path_outside_the_library_is_rejected_and_nothing_is_backed_up(self, env):
        env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        outside = env.folder / "elsewhere.mp4"  # regenerable, but not in the library
        outside.write_bytes(b"")
        write_bundle(env.folder, outside.stem, **poor_genius_bundle())

        assert env.regenerate(str(outside)).status_code == 400
        env.processing.enqueue_regen.assert_not_called()
        assert not list(env.folder.glob("regen_backup_*"))

    def test_queues_one_job_and_backs_up_only_that_song(self, env):
        mine = env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        env.add_song("B---bbbbbbbbbbb.mp4", poor_genius_bundle())

        response = env.regenerate(mine)

        assert response.get_json() == {"success": True}
        env.processing.enqueue_regen.assert_called_once()
        regen = env.processing.enqueue_regen.call_args.args[0]
        assert str(regen.song.song_path) == mine
        assert regen.label == "Regenerate" and regen.reset is False
        [backup] = env.folder.glob("regen_backup_*")
        assert [p.name for p in (backup / "alignment_debug").iterdir()] == ["A---aaaaaaaaaaa.json"]

    def test_a_busy_song_is_refused(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        env.processing.get_active_job.return_value = song

        response = env.regenerate(song)

        assert response.status_code == 400
        assert "waiting or running" in response.get_json()["error"]
        env.processing.enqueue_regen.assert_not_called()

    def test_a_song_with_no_pick_says_to_repair_it_first(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4")

        response = env.regenerate(song)

        assert response.status_code == 400
        assert "Repair lyrics" in response.get_json()["error"]


class TestOverviewRoute:
    def test_counts(self, env):
        env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle())
        env.add_song("B---bbbbbbbbbbb.mp4", poor_genius_bundle())
        env.add_song("C---ccccccccccc.mp4")

        counts = env.client.get("/library/overview").get_json()

        assert counts == {"behind": 0, "poor": 1, "no_lyrics": 0, "all": 3}

    def test_a_guest_gets_403_json(self, env):
        env.admin = False

        response = env.client.get("/library/overview")

        assert response.status_code == 403
        assert response.get_json()["success"] is False


class TestSongListsRoute:
    def test_each_row_links_to_song_info_with_its_subline(self, env):
        env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        env.add_song("B---bbbbbbbbbbb.mp4", caption_bundle())

        poor = text(env.client.get("/library/songs?list=poor"))
        assert "Songs that look poor" in poor
        assert "38 of 89 lines guessed" in poor
        assert '<span class="ls-name">A</span>' in poor  # the display name drops the id
        assert "/song_info?song=" in poor and "aaaaaaaaaaa.mp4" in poor
        assert "bbbbbbbbbbb" not in poor

        everything = text(env.client.get("/library/songs?list=all"))
        assert "Up to date" in everything
        assert "aaaaaaaaaaa.mp4" in everything and "bbbbbbbbbbb.mp4" in everything

    def test_sublines_for_the_other_lists(self, env):
        env.add_song("A---aaaaaaaaaaa.mp4", {**caption_bundle(), "schema_version": 9})
        song = env.add_song("B---bbbbbbbbbbb.mp4")
        (env.folder / "karaoke").mkdir()
        (env.folder / "karaoke" / "B---bbbbbbbbbbb.ass").write_text("", encoding="utf-8")
        env.add_song("C---ccccccccccc.mp4")

        assert "Version 9" in text(env.client.get("/library/songs?list=behind"))
        assert "Transcribed" in text(env.client.get("/library/songs?list=no_lyrics"))
        everything = text(env.client.get("/library/songs?list=all"))
        assert "Behind (v9)" in everything
        assert "No lyrics" in everything
        assert "Not processed" in everything
        assert Path(song).exists()

    def test_an_empty_list_says_so(self, env):
        env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle())

        assert "No songs in this list." in text(env.client.get("/library/songs?list=behind"))

    def test_an_unknown_list_is_rejected(self, env):
        assert env.client.get("/library/songs?list=bogus").status_code == 400
        assert env.client.get("/library/songs").status_code == 400

    def test_a_guest_is_sent_back_to_the_browser(self, env):
        env.admin = False

        response = env.client.get("/library/songs?list=all")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/__stub/files.browse")


LYRICS = "Line one here\nLine two here\nLine three here\nLine four here"
GENIUS_SONG = GeniusSong(text=LYRICS, title="Defying Gravity", artist="Idina Menzel")


def synced(*lines: str) -> str:
    return "".join(f"[00:{10 + 4 * i:02d}.00] {line}\n" for i, line in enumerate(lines))


def lrclib_record(record_id: int, *lines: str, duration: float = 250.0) -> dict:
    return {
        "id": record_id,
        "trackName": "Defying Gravity",
        "artistName": "Idina Menzel",
        "albumName": "Wicked",
        "duration": duration,
        "syncedLyrics": synced(*lines),
    }


def card(html: str, source: str) -> str:
    """The markup of one lyric-source card on the repair page."""
    start = html.index(f'data-source="{source}"')
    return html[start : html.index("</label>", start)]


def script(html: str) -> str:
    """The repair page's own script block."""
    start = html.rindex("<script>", 0, html.index("var SONG"))
    return html[start : html.index("</script>", start)]


class TestRepairButton:
    def test_a_video_song_links_to_the_repair_page(self, env):
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())))

        assert 'id="repair"' in html
        assert 'data-href="/song_info/repair?song=' in html
        assert 'id="repair" class="button is-primary si-btn" data-href' in html
        assert "disabled>Repair lyrics" not in html

    def test_a_song_with_no_pick_can_still_be_repaired(self, env):
        html = text(env.page(env.add_song("A---aaaaaaaaaaa.mp4")))

        assert 'id="repair"' in html
        assert 'id="regenerate"' not in html

    def test_a_busy_song_has_it_disabled(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        env.processing.pending_jobs = [song]

        assert "disabled>Repair lyrics" in text(env.page(song))

    def test_a_song_that_is_not_a_video_has_no_button(self, env):
        song = env.folder / "Track---aaaaaaaaaaa.mp3"
        song.write_bytes(b"")
        env.songs.add(str(song))

        assert 'id="repair"' not in text(env.page(str(song)))


class TestRepairPage:
    def page(self, env, song):
        return env.client.get("/song_info/repair", query_string={"song": song})

    def test_a_guest_is_sent_back_to_the_browser(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        env.admin = False

        response = self.page(env, song)

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/__stub/files.browse")

    def test_a_path_outside_the_library_is_rejected(self, env):
        env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())
        outside = env.folder / "elsewhere.mp4"
        outside.write_bytes(b"")

        assert self.page(env, str(outside)).status_code == 400
        assert env.client.get("/song_info/repair").status_code == 400

    def test_a_song_that_is_not_a_video_goes_back_to_song_info(self, env):
        song = env.folder / "Track---aaaaaaaaaaa.mp3"
        song.write_bytes(b"")
        env.songs.add(str(song))

        response = self.page(env, str(song))

        assert response.status_code == 302
        assert response.headers["Location"].startswith("/song_info?song=")

    def test_a_genius_song_is_current_on_the_genius_card(self, env):
        html = text(self.page(env, env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())))

        assert 'var CURRENT_SOURCE = "genius"' in html
        assert "var CURRENT_GENIUS_ID = 7" in html
        assert "rp-tag" in card(html, "genius")
        assert "rp-tag" not in card(html, "caption")
        assert "rp-tag" not in card(html, "transcribe")

    def test_a_caption_song_is_current_on_the_caption_card(self, env):
        html = text(self.page(env, env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle())))

        assert 'var CURRENT_SOURCE = "caption"' in html
        assert "rp-tag" in card(html, "caption")
        assert "rp-tag" not in card(html, "genius")

    def test_a_transcribed_song_is_current_on_the_transcribe_card(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4")
        (env.folder / "karaoke").mkdir()
        (env.folder / "karaoke" / "A---aaaaaaaaaaa.ass").write_text("", encoding="utf-8")

        html = text(self.page(env, song))

        assert 'var CURRENT_SOURCE = "transcribe"' in html
        assert "rp-tag" in card(html, "transcribe")

    def test_an_unprocessed_song_has_no_current_source(self, env):
        html = text(self.page(env, env.add_song("A---aaaaaaaaaaa.mp4")))

        assert "var CURRENT_SOURCE = null" in html
        assert all("rp-tag" not in card(html, s) for s in ("caption", "genius", "transcribe"))

    def test_the_page_knows_whether_the_song_has_a_youtube_id(self, env):
        with_id = text(self.page(env, env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle())))
        without = text(self.page(env, env.add_song("No Id Song.mp4", caption_bundle())))

        assert "var HAS_YOUTUBE_ID = true" in with_id
        assert "var HAS_YOUTUBE_ID = false" in without

    def test_the_length_rule_comes_from_song_info(self, env):
        html = text(self.page(env, env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())))

        assert "var NOTED_S = 5;" in html

    def test_a_caption_check_that_found_nothing_does_not_rule_out_a_failed_check(self, env):
        html = text(self.page(env, env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle())))

        assert "No usable English caption found. If YouTube is busy, reload the page" in html
        assert "This video has no English caption." not in html

    def test_a_new_genius_pick_drops_the_lrclib_search_still_loading(self, env):
        code = script(text(self.page(env, env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle()))))
        start = code.index("function geniusOption")
        handler = code[start : code.index("return label;", start)]

        assert "state.lrclibSeq++;" in handler

    def test_text_from_genius_and_lrclib_goes_in_as_text_never_as_markup(self, env):
        code = script(text(self.page(env, env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle()))))

        assert ".html(" not in code
        assert ".innerHTML" not in code


class TestCaptionCheckRoute:
    def check(self, env, song):
        return env.client.get("/song_info/caption_check", query_string={"song": song})

    def test_a_guest_gets_403_json(self, env):
        song = env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle())
        env.admin = False

        response = self.check(env, song)

        assert response.status_code == 403
        assert response.get_json()["success"] is False

    def test_a_path_outside_the_library_is_rejected(self, env):
        outside = env.folder / "elsewhere---aaaaaaaaaaa.mp4"
        outside.write_bytes(b"")

        assert self.check(env, str(outside)).status_code == 400

    def test_reports_what_the_caption_check_found(self, env, monkeypatch):
        song = env.add_song("A---aaaaaaaaaaa.mp4", caption_bundle())
        checked = MagicMock(return_value=CaptionCheck(found=True, wpm=12.5, passed=False))
        monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", checked)

        response = self.check(env, song)

        assert response.get_json() == {"found": True, "passed": False, "wpm": 12.5}
        checked.assert_called_once()

    def test_a_song_with_no_youtube_id_is_a_400_with_the_reason(self, env, monkeypatch):
        song = env.add_song("No Id Song.mp4", caption_bundle())
        monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", MagicMock())

        response = self.check(env, song)

        assert response.status_code == 400
        assert "no YouTube ID" in response.get_json()["error"]


class TestGeniusLyricsRoute:
    def lyrics(self, env, genius_id):
        return env.client.get("/song_info/genius_lyrics", query_string={"id": genius_id})

    def test_a_guest_gets_403_json(self, env):
        env.admin = False

        response = self.lyrics(env, 7)

        assert response.status_code == 403
        env.genius.fetch_song.assert_not_called()

    @pytest.mark.parametrize("genius_id", ["", "abc", "7.5"])
    def test_an_id_that_is_not_a_number_is_rejected(self, env, genius_id):
        assert self.lyrics(env, genius_id).status_code == 400
        assert env.client.get("/song_info/genius_lyrics").status_code == 400
        env.genius.fetch_song.assert_not_called()

    def test_returns_the_title_artist_and_text(self, env):
        env.genius.fetch_song.return_value = GENIUS_SONG

        response = self.lyrics(env, 7)

        assert response.get_json() == {
            "title": "Defying Gravity",
            "artist": "Idina Menzel",
            "text": LYRICS,
        }

    def test_a_second_request_for_the_same_song_does_not_scrape_again(self, env):
        env.genius.fetch_song.return_value = GENIUS_SONG

        self.lyrics(env, 7)
        self.lyrics(env, 7)

        env.genius.fetch_song.assert_called_once_with(7)

    def test_a_song_genius_cannot_return_is_a_502_with_a_message(self, env):
        env.genius.fetch_song.side_effect = GeniusUnavailable("token not configured")

        response = self.lyrics(env, 7)

        assert response.status_code == 502
        body = response.get_json()
        assert body["success"] is False
        assert "Genius didn't return" in body["error"]
        assert "token" not in body["error"]


class TestLrclibSearchRoute:
    @pytest.fixture
    def song(self, env, monkeypatch):
        env.genius.fetch_song.return_value = GENIUS_SONG
        self.searches = []
        self.records = []

        def fake_search(track, artist):
            self.searches.append((track, artist))
            return self.records

        monkeypatch.setattr(lrclib, "search", fake_search)
        return env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())

    def search(self, env, song, **params):
        query = {"song": song, "genius_id": 7, "title": "defying gravity", "artist": "menzel"}
        query.update(params)
        return env.client.get("/song_info/lrclib_search", query_string=query)

    def test_a_guest_gets_403_json(self, env, song):
        env.admin = False

        assert self.search(env, song).status_code == 403
        assert self.searches == []

    def test_a_path_outside_the_library_is_rejected(self, env, song):
        outside = env.folder / "elsewhere.mp4"
        outside.write_bytes(b"")

        assert self.search(env, str(outside)).status_code == 400
        assert self.searches == []

    @pytest.mark.parametrize("genius_id", ["", "abc"])
    def test_a_genius_id_that_is_not_a_number_is_rejected(self, env, song, genius_id):
        assert self.search(env, song, genius_id=genius_id).status_code == 400
        assert self.searches == []

    def test_searches_for_the_typed_terms_and_marks_best_and_current(self, env, song):
        lrclib.write_lrc(lrclib.lrc_path(Path(song)), lrclib_record(5, "Line one here"))
        self.records = [
            lrclib_record(5, "Line one here", "Line two here", duration=354.0),
            lrclib_record(6, "Line one here", "Line two here", "Line three here", "Line four here"),
        ]

        body = self.search(env, song, title=" defying gravity ", artist="").get_json()

        assert self.searches == [("defying gravity", "")]
        assert body["video_duration_s"] == 257.23
        current, best = body["candidates"]
        assert (current["id"], current["best"], current["current"]) == (5, False, True)
        assert (best["id"], best["best"], best["current"]) == (6, True, False)
        assert (current["mapped"], best["mapped"], best["sheet_lines"]) == (2, 4, 4)
        assert current["duration_diff_s"] == 97
        assert best["syncedLyrics"] == self.records[1]["syncedLyrics"]

    def test_no_matches_is_an_empty_list(self, env, song):
        assert self.search(env, song).get_json()["candidates"] == []

    def test_genius_lyrics_that_cannot_be_fetched_are_a_502(self, env, song):
        env.genius.fetch_song.side_effect = GeniusUnavailable("down")

        response = self.search(env, song)

        assert response.status_code == 502
        assert response.get_json()["success"] is False


class TestRepairRoute:
    @pytest.fixture
    def song(self, env):
        env.genius.fetch_song.return_value = GENIUS_SONG
        return env.add_song("A---aaaaaaaaaaa.mp4", poor_genius_bundle())

    def repair(self, env, song, **body):
        return env.client.post("/song_info/repair", json={"song": song, **body})

    def queued(self, env):
        env.processing.enqueue_regen.assert_called_once()
        return env.processing.enqueue_regen.call_args.args[0]

    def test_a_guest_cannot(self, env, song):
        env.admin = False

        response = self.repair(env, song, source="transcribe")

        assert response.status_code == 403
        env.processing.enqueue_regen.assert_not_called()

    @pytest.mark.parametrize("body", [{"song": None}, {"song": ["a"]}, {}, [1]])
    def test_a_missing_or_malformed_song_is_rejected(self, env, song, body):
        assert env.client.post("/song_info/repair", json=body).status_code == 400
        env.processing.enqueue_regen.assert_not_called()

    def test_a_path_outside_the_library_is_rejected_and_nothing_is_backed_up(self, env, song):
        outside = env.folder / "elsewhere.mp4"
        outside.write_bytes(b"")
        write_bundle(env.folder, outside.stem, **poor_genius_bundle())

        assert self.repair(env, str(outside), source="transcribe").status_code == 400
        env.processing.enqueue_regen.assert_not_called()
        assert not list(env.folder.glob("regen_backup_*"))

    def test_each_source_queues_its_plan_as_a_repair_that_wipes_first(self, env, song):
        for source, kind in (("caption", "fetch"), ("transcribe", "transcribe")):
            env.processing.enqueue_regen.reset_mock()

            assert self.repair(env, song, source=source).get_json() == {"success": True}

            regen = self.queued(env)
            assert regen.song.plan.kind == kind
            assert (regen.label, regen.reset) == ("Repair", True)
            assert str(regen.song.song_path) == song

    def test_a_genius_pick_queues_a_sidecar_plan_and_backs_up_only_that_song(self, env, song):
        env.add_song("B---bbbbbbbbbbb.mp4", poor_genius_bundle())

        response = self.repair(env, song, source="genius", genius_id=8)

        assert response.get_json() == {"success": True}
        plan = self.queued(env).song.plan
        assert (plan.kind, plan.genius_id) == ("sidecar", 8)
        [backup] = env.folder.glob("regen_backup_*")
        assert [p.name for p in (backup / "alignment_debug").iterdir()] == ["A---aaaaaaaaaaa.json"]

    def test_an_lrclib_id_queues_that_record(self, env, song, monkeypatch):
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: lrclib_record(record_id, "x"))

        self.repair(env, song, source="genius", genius_id=8, lrclib_id=42)

        assert self.queued(env).song.plan.lrclib_record["id"] == 42

    def test_skipping_lrclib_queues_the_skip(self, env, song):
        self.repair(env, song, source="genius", genius_id=8, lrclib_skip=True)

        plan = self.queued(env).song.plan
        assert plan.lrclib_skip is True and plan.lrclib_record is None

    def test_a_match_lrclib_does_not_return_queues_nothing(self, env, song, monkeypatch):
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: None)

        response = self.repair(env, song, source="genius", genius_id=8, lrclib_id=42)

        assert response.status_code == 400
        assert "LRCLIB didn't return that match" in response.get_json()["error"]
        env.processing.enqueue_regen.assert_not_called()
        assert not list(env.folder.glob("regen_backup_*"))

    @pytest.mark.parametrize(
        "body",
        [
            {"source": "genius", "genius_id": "8"},
            {"source": "genius", "genius_id": True},
            {"source": "genius", "genius_id": 8, "lrclib_id": 5.5},
            {"source": "genius", "genius_id": 8, "lrclib_id": "5"},
            {"source": "genius", "genius_id": 8, "lrclib_skip": "yes"},
        ],
    )
    def test_ids_and_flags_of_the_wrong_type_are_rejected(self, env, song, body):
        response = self.repair(env, song, **body)

        assert response.status_code == 400
        env.processing.enqueue_regen.assert_not_called()

    @pytest.mark.parametrize("body", [{}, {"source": "lyrics-from-the-moon"}, {"source": None}])
    def test_an_unknown_source_is_rejected(self, env, song, body):
        response = self.repair(env, song, **body)

        assert response.status_code == 400
        assert "Unknown lyric source" in response.get_json()["error"]

    def test_a_genius_pick_without_an_id_is_rejected(self, env, song):
        response = self.repair(env, song, source="genius")

        assert response.status_code == 400
        assert "Pick a Genius song" in response.get_json()["error"]

    def test_a_busy_song_is_refused(self, env, song):
        env.processing.get_active_job.return_value = song

        response = self.repair(env, song, source="transcribe")

        assert response.status_code == 400
        assert "waiting or running" in response.get_json()["error"]
        env.processing.enqueue_regen.assert_not_called()
