"""Render tests for the Processing page: what an admin and a guest are handed.

A Flask app with the real templates and the processing, library and song-info
blueprints. The page's rows are drawn by its script from ``/processing/status``,
so these tests look at the page's markup and at the JSON the script reads.
"""

import json
import os
from unittest.mock import MagicMock, patch
from urllib.parse import quote

import pytest
import werkzeug
from flask import Flask
from flask_babel import Babel

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

import pikaraoke
from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.pipeline_tracker import PipelineTracker
from pikaraoke.lib.song_manager import SongManager
from pikaraoke.routes.library import library_bp
from pikaraoke.routes.processing import processing_bp
from pikaraoke.routes.song_info import song_info_bp

ROUTE_PREFIX = "pikaraoke.routes.processing"

# Endpoints base.html and the page's script resolve that these blueprints don't provide.
_STUB_ENDPOINTS = ("home.home", "queue.queue", "search.search", "files.browse", "info.info")
_STUB_RULES = {"files.delete_file": "/files/delete"}

SONG = "/songs/Library Song---abcdefghijk.mp4"


@pytest.fixture
def env():
    pkg_dir = os.path.dirname(pikaraoke.__file__)
    app = Flask(
        __name__,
        template_folder=os.path.join(pkg_dir, "templates"),
        static_folder=os.path.join(pkg_dir, "static"),
    )
    app.secret_key = "test"
    for blueprint in (processing_bp, library_bp, song_info_bp):
        app.register_blueprint(blueprint)
    for endpoint in _STUB_ENDPOINTS:
        app.add_url_rule(f"/__stub/{endpoint}", endpoint=endpoint, view_func=lambda *a, **k: "")
    for endpoint, rule in _STUB_RULES.items():
        app.add_url_rule(rule, endpoint=endpoint, view_func=lambda *a, **k: "")
    Babel(app)
    app.jinja_env.globals.update(
        filename_from_path=SongManager.filename_from_path, url_escape=quote
    )

    processing = MagicMock()
    processing.get_active_job.return_value = None
    processing.get_active_phase.return_value = None
    processing.get_active_elapsed_s.return_value = None
    processing.pending_jobs = []
    download = MagicMock()
    download.active_url = None
    tracker = PipelineTracker(
        download_manager=download,
        processing_manager=processing,
        queue_manager=MagicMock(),
        song_manager=MagicMock(),
        events=EventSystem(),
    )
    karaoke = MagicMock()
    karaoke.pipeline_tracker = tracker
    karaoke.preferences.get.return_value = "PiKaraoke"
    return app, karaoke


def get(env, path, *, admin):
    app, karaoke = env
    with patch(f"{ROUTE_PREFIX}.get_karaoke_instance", return_value=karaoke), patch(
        f"{ROUTE_PREFIX}.is_admin", return_value=admin
    ):
        return app.test_client().get(path)


class TestProcessingPage:
    def test_an_admin_gets_the_jobs_and_library_tools_tabs(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert 'data-tab="jobs"' in body and 'data-tab="tools"' in body
        for chip in ("all", "active", "attention", "finished"):
            assert f'data-filter="{chip}"' in body
        assert 'id="pr-now"' in body and 'id="pr-clear"' in body

    def test_the_library_tab_opens_the_four_song_lists_in_place(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        for name in ("behind", "poor", "no_lyrics", "all"):
            assert f'<button type="button" class="pr-link" data-list="{name}"' in body
            assert f'data-count="{name}"' in body
        assert body.count('class="pr-link" data-list=') == 4
        assert 'href="/library/songs' not in body

    def test_the_library_tab_offers_the_three_bulk_runs_with_their_counts(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        for mode, count in (("stale", "behind"), ("all", "all"), ("reset", "all")):
            button = body[body.index(f'data-mode="{mode}"') :].split("</button>")[0]
            assert f'data-count="{count}"' in button and "disabled" in button
        assert "Regen jobs wait behind new downloads." in body
        assert "Each song's lyric files are backed up first." in body

    def test_the_tab_is_read_from_the_url_before_the_spa_drops_the_hash(self, env):
        """spa-navigation.js rewrites the URL without its hash when it starts, before the
        page's ready handler runs, so a link to /processing#tools must be read at once."""
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert "var firstTab = window.location.hash.replace('#', '');" in body
        assert "showTab(firstTab)" in body
        assert "showTab(window.location.hash" not in body

    def test_the_library_tab_has_a_banner_for_an_open_run_with_an_in_place_discard(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert 'id="pr-run-banner"' in body and 'id="pr-run-continue"' in body
        assert 'href="/library/run"' in body
        assert 'id="pr-run-confirm"' in body and "Discard this run and its picks?" in body

    def test_the_library_tab_has_the_add_playlist_card_that_waits_for_a_link(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert 'id="pr-playlist-url"' in body and 'type="url"' in body
        button = body[body.index('id="pr-playlist-check"') :].split("</button>")[0]
        assert "disabled" in button and "Check playlist" in button
        assert '"/library/playlist"' in body

    def test_a_row_waiting_for_a_pick_has_a_tag_and_a_way_to_the_pick_page(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert '"Needs a pick"' in body and '"Pick lyrics"' in body
        assert '"/library/picks"' in body
        assert "if (has('pick'))" in body
        assert "needspick: 'is-warning is-light'" in body

    def test_a_guests_song_waiting_for_a_pick_is_only_waiting(self, env):
        body = get(env, "/processing", admin=False).get_data(as_text=True)

        assert "isAdmin ? ['needspick', T.needsPick] : ['waiting', T.waiting]" in body
        assert 'id="pr-playlist-url"' not in body and "/library/picks" not in body

    def test_the_page_takes_fill_from_the_shared_file(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        tag = '<script src="/static/library-pages.js"></script>'
        assert tag in body and body.index(tag) < body.index("var isAdmin")
        assert "function fill(" not in body
        assert "var fill = libraryPages.fill;" in body

    def test_the_banner_says_ready_to_queue_once_every_pick_is_made(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert "(run.to_pick - run.picked > 0 ? T.runPicks : T.runReady)" in body

    def test_a_guest_gets_no_tabs_chips_or_library_links(self, env):
        body = get(env, "/processing", admin=False).get_data(as_text=True)

        assert "data-tab=" not in body and "data-filter=" not in body
        assert 'id="pr-tools"' not in body and "/library/" not in body
        assert "Library tools" not in body

    def test_a_guest_gets_no_run_controls(self, env):
        body = get(env, "/processing", admin=False).get_data(as_text=True)

        assert "data-mode=" not in body and 'id="pr-run-banner"' not in body
        assert "/library/run" not in body

    def test_a_guest_gets_the_intro_and_three_headed_sections(self, env):
        body = get(env, "/processing", admin=False).get_data(as_text=True)

        assert "Songs being downloaded and prepared for karaoke." in body
        for section in ("Getting ready", "Ready", "Problems"):
            assert f"{section} (<span" in body
        assert "Library maintenance" not in body

    def test_a_guest_is_not_handed_the_admin_routes(self, env):
        body = get(env, "/processing", admin=False).get_data(as_text=True)

        for admin_only in ("/processing/attention", "/processing/song/retry", "/files/delete"):
            assert admin_only not in body
        assert "/processing/ITEM_ID/cancel" not in body
        assert "/processing/user/cancel" in body

    def test_the_page_script_has_no_window_confirm_and_no_tiling_code(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert "window.confirm" not in body
        assert "tiling" not in body
        assert "reverse()" not in body

    def test_the_script_rebinds_its_handlers_and_socket_listener_for_the_spa(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert "$(document).off('.processing')" in body
        assert "window.socket.off('pipeline_updated')" in body

    def test_a_confirm_closes_when_the_server_stops_offering_its_action(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert "pruneState(allRows());" in body
        assert "if (state.confirming[key] && !offers(row, state.confirming[key]))" in body
        assert "if (offers(row, 'delete'))" in body

    def test_the_poor_list_label_shows_one_percent_sign(self, env):
        body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert "Looks poor (15%+ lines guessed)" in body

    def test_the_poor_list_label_follows_the_rule(self, env):
        with patch(f"{ROUTE_PREFIX}.POOR_GUESSED_SHARE", 0.2):
            body = get(env, "/processing", admin=True).get_data(as_text=True)

        assert "Looks poor (20%+ lines guessed)" in body


class TestStatusJson:
    @staticmethod
    def queue_regen(karaoke, path=SONG):
        karaoke.pipeline_tracker._events.emit(
            "regen_queued", {"song_path": path, "label": "Regenerate", "job": MagicMock()}
        )
        karaoke.pipeline_tracker._processing_manager.pending_jobs = [path]

    def test_an_admin_reads_the_regen_row_with_its_group_and_position(self, env):
        _, karaoke = env
        self.queue_regen(karaoke)

        [row] = json.loads(get(env, "/processing/status", admin=True).get_data(as_text=True))

        assert (row["kind"], row["label"], row["group"], row["position"]) == (
            "regen",
            "Regenerate",
            "active",
            1,
        )

    def test_a_guest_reads_no_regen_row(self, env):
        _, karaoke = env
        self.queue_regen(karaoke)

        rows = json.loads(get(env, "/processing/status", admin=False).get_data(as_text=True))

        assert rows == []
