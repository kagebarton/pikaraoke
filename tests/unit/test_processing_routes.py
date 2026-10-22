"""Tests for processing routes — ownership gating, admin-only endpoints, user cancel."""

import json
from unittest.mock import MagicMock, patch

import pytest
import werkzeug
from flask import Flask

# Monkeypatch werkzeug.__version__ for Flask compatibility if missing
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.pipeline_tracker import PipelineItem, PipelineTracker
from pikaraoke.lib.processing_manager import ProcessingManager
from pikaraoke.routes.processing import processing_bp

ROUTE_PREFIX = "pikaraoke.routes.processing"


def _make_tracker():
    """Create a real PipelineTracker with mocked managers and an event system."""
    events = EventSystem()
    mock_dm = MagicMock()
    mock_dm.active_url = None
    mock_pm = MagicMock()
    mock_pm.get_active_job.return_value = None
    mock_pm.get_active_phase.return_value = None
    mock_pm.pending_jobs = []
    mock_pm.get_active_elapsed_s.return_value = None
    mock_qm = MagicMock()
    mock_sm = MagicMock()
    return PipelineTracker(
        download_manager=mock_dm,
        processing_manager=mock_pm,
        queue_manager=mock_qm,
        song_manager=mock_sm,
        events=events,
    )


@pytest.fixture
def app():
    """Create a Flask app for testing."""
    test_app = Flask(__name__)
    test_app.secret_key = "test"
    test_app.register_blueprint(processing_bp)
    test_app.extensions["babel"] = MagicMock()
    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestGetItemUser:
    """Tests for PipelineTracker.get_item_user()."""

    def test_returns_user_for_known_item(self):
        tracker = _make_tracker()
        item = PipelineItem(title="Test Song", url="https://example.com", user="Alice")
        tracker._items.append(item)
        assert tracker.get_item_user(item.id) == "Alice"

    def test_returns_none_for_unknown_item(self):
        tracker = _make_tracker()
        assert tracker.get_item_user("nonexistent-id") is None


class TestAdminCancelEndpoint:
    """Tests for POST /processing/<item_id>/cancel (admin only)."""

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=False)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_non_admin_gets_403(self, mock_get_instance, mock_is_admin, mock_gettext, client):
        """Non-admin hitting the admin cancel endpoint gets 403."""
        mock_karaoke = MagicMock()
        mock_get_instance.return_value = mock_karaoke

        response = client.post("/processing/some-id/cancel")

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_admin_can_cancel(self, mock_get_instance, mock_is_admin, mock_gettext, client):
        """Admin can cancel any item via the admin endpoint."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        # Make item cancellable — set download_status to active
        item.download_status = "active"
        tracker._items.append(item)

        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker = tracker
        mock_get_instance.return_value = mock_karaoke

        response = client.post(f"/processing/{item.id}/cancel")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=False)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_error_response_is_json(self, mock_get_instance, mock_is_admin, mock_gettext, client):
        """Admin-gated endpoints return application/json via jsonify()."""
        mock_karaoke = MagicMock()
        mock_get_instance.return_value = mock_karaoke

        response = client.post("/processing/some-id/cancel")

        assert response.content_type.startswith("application/json")


class TestAdminRemoveEndpoint:
    """Tests for POST /processing/<item_id>/remove (admin only)."""

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=False)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_non_admin_gets_403(self, mock_get_instance, mock_is_admin, mock_gettext, client):
        """Non-admin hitting the admin remove endpoint gets 403."""
        mock_karaoke = MagicMock()
        mock_get_instance.return_value = mock_karaoke

        response = client.post("/processing/some-id/remove")

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data["success"] is False

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_admin_can_remove(self, mock_get_instance, mock_is_admin, mock_gettext, client):
        """Admin can remove any item via the admin endpoint."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        item.download_status = "complete"
        item.processing_status = "complete"
        item.song_path = "/songs/test.mp4"
        tracker._items.append(item)

        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker = tracker
        mock_get_instance.return_value = mock_karaoke

        response = client.post(f"/processing/{item.id}/remove")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True


class TestUserCancelEndpoint:
    """Tests for POST /processing/user/cancel (user self-cancel)."""

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_user_cancel_own_item_succeeds(self, mock_get_instance, mock_gettext, client):
        """User with matching cookie can cancel their own item."""
        tracker = _make_tracker()
        item = PipelineItem(title="My Song", url="https://example.com", user="Alice")
        item.download_status = "active"
        tracker._items.append(item)

        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker = tracker
        mock_get_instance.return_value = mock_karaoke

        # Flask test client sets cookies via the setter interface
        with client.session_transaction():
            pass
        client.set_cookie("user", "Alice")

        response = client.post(
            "/processing/user/cancel",
            data={"id": item.id},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_user_cancel_other_users_item_fails(self, mock_get_instance, mock_gettext, client):
        """User cannot cancel another user's item — cookie doesn't match."""
        tracker = _make_tracker()
        item = PipelineItem(title="Their Song", url="https://example.com", user="Bob")
        item.download_status = "active"
        tracker._items.append(item)

        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker = tracker
        mock_get_instance.return_value = mock_karaoke

        client.set_cookie("user", "Alice")

        response = client.post(
            "/processing/user/cancel",
            data={"id": item.id},
        )

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data["success"] is False

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_spoof_form_field_ignored(self, mock_get_instance, mock_gettext, client):
        """Server reads identity from cookie, not form data.

        Attacker posts user=Bob in the form body but has user=Alice cookie.
        The server must use the cookie, so this should fail with 403.
        """
        tracker = _make_tracker()
        item = PipelineItem(title="Victim Song", url="https://example.com", user="Bob")
        item.download_status = "active"
        tracker._items.append(item)

        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker = tracker
        mock_get_instance.return_value = mock_karaoke

        client.set_cookie("user", "Alice")

        # Form field "user" is deliberately included but must be ignored
        response = client.post(
            "/processing/user/cancel",
            data={"id": item.id, "user": "Bob"},
        )

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data["success"] is False
        # The item must still be in the tracker — the spoof attempt must not
        # have modified server-side state at all.
        assert len(tracker._items) == 1
        assert tracker._items[0].id == item.id

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_no_user_cookie_gets_403(self, mock_get_instance, mock_gettext, client):
        """User with no user cookie at all gets 403 on user cancel."""
        tracker = _make_tracker()
        item = PipelineItem(title="Song", url="https://example.com", user="Alice")
        item.download_status = "active"
        tracker._items.append(item)

        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker = tracker
        mock_get_instance.return_value = mock_karaoke

        response = client.post(
            "/processing/user/cancel",
            data={"id": item.id},
        )

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data["success"] is False

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_nonexistent_item_gets_403(self, mock_get_instance, mock_gettext, client):
        """Cancel of a nonexistent item returns 403 (owner is None)."""
        tracker = _make_tracker()

        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker = tracker
        mock_get_instance.return_value = mock_karaoke

        client.set_cookie("user", "Alice")

        response = client.post(
            "/processing/user/cancel",
            data={"id": "nonexistent-id"},
        )

        assert response.status_code == 403

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_error_response_is_json(self, mock_get_instance, mock_gettext, client):
        """User cancel error responses have application/json content type."""
        tracker = _make_tracker()
        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker = tracker
        mock_get_instance.return_value = mock_karaoke

        response = client.post(
            "/processing/user/cancel",
            data={"id": "some-id"},
        )

        assert response.content_type.startswith("application/json")


class TestEnqueueStaysOpen:
    """Tests that /processing/<item_id>/enqueue remains open to all users."""

    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_non_admin_can_enqueue(self, mock_get_instance, client):
        """Non-admin can still POST /processing/<id>/enqueue (stays open)."""
        tracker = _make_tracker()
        item = PipelineItem(title="Done Song", url="https://example.com", user="Bob")
        item.download_status = "complete"
        item.processing_status = "complete"
        item.song_path = "/songs/test.mp4"
        tracker._items.append(item)

        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker = tracker
        mock_get_instance.return_value = mock_karaoke

        response = client.post(f"/processing/{item.id}/enqueue")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True


class TestProcessingSkippedEvent:
    """processing_skipped from ProcessingManager clears the item from PipelineTracker."""

    def test_blocked_word_item_removed_from_tracker(self):
        """When processing_skipped fires, the matching item is removed from _items."""
        events = EventSystem()
        tracker = _make_tracker()

        # Simulate a song that made it to the download-complete stage
        item = PipelineItem(title="Demo Song", url="https://example.com", user="Bob")
        item.download_status = "complete"
        item.song_path = "/songs/Demo Song---abc123.mp4"
        tracker._items.append(item)

        assert len(tracker._items) == 1

        events.on("processing_skipped", tracker._on_processing_skipped)
        events.emit("processing_skipped", "/songs/Demo Song---abc123.mp4")

        assert len(tracker._items) == 0

    def test_processing_skipped_only_removes_matching_item(self):
        """processing_skipped removes only the item with the matching song_path."""
        tracker = _make_tracker()

        item_a = PipelineItem(title="Song A", url="https://example.com/a", user="Bob")
        item_a.song_path = "/songs/A---abc123.mp4"
        item_b = PipelineItem(title="Song B", url="https://example.com/b", user="Carol")
        item_b.song_path = "/songs/B---xyz456.mp4"
        tracker._items = [item_a, item_b]

        tracker._on_processing_skipped("/songs/A---abc123.mp4")

        assert len(tracker._items) == 1
        assert tracker._items[0].song_path == "/songs/B---xyz456.mp4"


class TestActionsField:
    """Server-computed actions list eliminates client-side auth re-derivation."""

    def test_cancel_action_for_active_download_owner(self):
        """Owner sees 'cancel' when their item has an active download."""
        tracker = _make_tracker()
        item = PipelineItem(title="My Song", url="https://example.com", user="Alice")
        item.download_status = "active"
        tracker._items.append(item)

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["actions"] == ["cancel"]

    def test_cancel_action_hidden_for_non_owner(self):
        """Non-owner non-admin sees no cancel for someone else's active download."""
        tracker = _make_tracker()
        item = PipelineItem(title="Their Song", url="https://example.com", user="Bob")
        item.download_status = "active"
        tracker._items.append(item)

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["actions"] == []

    def test_admin_sees_cancel_for_any_item(self):
        """Admin sees 'cancel' for any user's active download."""
        tracker = _make_tracker()
        item = PipelineItem(title="Their Song", url="https://example.com", user="Bob")
        item.download_status = "active"
        tracker._items.append(item)

        status = tracker.get_status(admin=True, user="Alice")
        assert status[0]["actions"] == ["cancel"]

    def test_remove_action_admin_only_on_terminal_item(self):
        """Admin sees 'remove' on a completed item; regular user does not."""
        tracker = _make_tracker()
        item = PipelineItem(title="Done Song", url="https://example.com", user="Bob")
        item.download_status = "complete"
        item.processing_status = "complete"
        item.song_path = "/songs/done.mp4"
        tracker._items.append(item)

        admin_status = tracker.get_status(admin=True, user="Bob")
        assert "remove" in admin_status[0]["actions"]

        user_status = tracker.get_status(admin=False, user="Bob")
        assert "remove" not in user_status[0]["actions"]

    def test_enqueue_action_on_completed_item(self):
        """Both admin and user see 'enqueue' when both stages are complete."""
        tracker = _make_tracker()
        item = PipelineItem(title="Done Song", url="https://example.com", user="Bob")
        item.download_status = "complete"
        item.processing_status = "complete"
        item.song_path = "/songs/done.mp4"
        tracker._items.append(item)

        admin_status = tracker.get_status(admin=True, user="Alice")
        assert "enqueue" in admin_status[0]["actions"]

        user_status = tracker.get_status(admin=False, user="Alice")
        assert "enqueue" in user_status[0]["actions"]

    def test_no_actions_while_cancelling(self):
        """No actions are available while an item is in cancelling state."""
        tracker = _make_tracker()
        item = PipelineItem(title="Cancelling Song", url="https://example.com", user="Alice")
        item.cancelling = True
        item.processing_status = "cancelling"
        tracker._items.append(item)

        status = tracker.get_status(admin=True, user="Alice")
        assert status[0]["actions"] == []

    def test_cancel_on_processing_pending(self):
        """Owner sees 'cancel' when their item is pending processing."""
        tracker = _make_tracker()
        item = PipelineItem(title="My Song", url="https://example.com", user="Alice")
        item.download_status = "complete"
        item.processing_status = "pending"
        item.song_path = "/songs/mine.mp4"
        tracker._items.append(item)
        # Make the processing manager report this song as pending
        tracker._processing_manager.pending_jobs = ["/songs/mine.mp4"]

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["actions"] == ["cancel"]

    def test_admin_sees_cancel_and_remove_on_error_item(self):
        """Admin sees both 'cancel' (matching error status) and 'remove' on an error item.

        An error item has download_status=error which matches the remove condition
        (terminal). It does not match the cancel condition (active/pending).
        """
        tracker = _make_tracker()
        item = PipelineItem(title="Error Song", url="https://example.com", user="Bob")
        item.download_status = "error"
        item.processing_status = "error"
        item.song_path = "/songs/error.mp4"
        item.error_message = "Download failed"
        tracker._items.append(item)

        admin_status = tracker.get_status(admin=True, user="Bob")
        assert "remove" in admin_status[0]["actions"]
        assert "cancel" not in admin_status[0]["actions"]


class TestRemoveImpliesCancel:
    """remove() routes through cancel() for non-terminal items."""

    def test_remove_active_processing_routes_to_cancel(self):
        """remove() on an item with active processing calls cancel() instead."""
        tracker = _make_tracker()
        item = PipelineItem(title="Active Song", url="https://example.com", user="Bob")
        item.download_status = "complete"
        item.processing_status = "active"
        item.song_path = "/songs/active.mp4"
        tracker._items.append(item)
        # Make the processing manager report this song as active
        tracker._processing_manager.get_active_job.return_value = "/songs/active.mp4"

        # remove() should route to cancel(), which sets cancelling=True
        result = tracker.remove(item.id)
        assert result is True
        # Item should still be in the list with cancelling=True
        assert len(tracker._items) == 1
        assert tracker._items[0].cancelling is True

    def test_remove_pending_download_routes_to_cancel(self):
        """remove() on a pending download calls cancel() instead of direct removal."""
        tracker = _make_tracker()
        item = PipelineItem(title="Pending Song", url="https://example.com", user="Bob")
        item.download_status = "pending"
        tracker._items.append(item)

        result = tracker.remove(item.id)
        assert result is True
        # cancel() removes the item immediately for pending downloads
        assert len(tracker._items) == 0

    def test_remove_terminal_item_removes_directly(self):
        """remove() on a completed item removes it directly (no cancel needed)."""
        tracker = _make_tracker()
        item = PipelineItem(title="Done Song", url="https://example.com", user="Bob")
        item.download_status = "complete"
        item.processing_status = "complete"
        item.song_path = "/songs/done.mp4"
        tracker._items.append(item)

        result = tracker.remove(item.id)
        assert result is True
        assert len(tracker._items) == 0

    def test_remove_nonexistent_returns_false(self):
        """remove() on a nonexistent item returns False."""
        tracker = _make_tracker()
        result = tracker.remove("nonexistent-id")
        assert result is False


class TestOnChangeCallback:
    """PipelineTracker fires on_change callback after mutations."""

    def test_on_change_called_on_download_queued(self):
        """on_change fires when a new item is queued."""
        calls = []
        tracker = _make_tracker()
        tracker._on_change = lambda: calls.append(1)

        tracker._on_download_queued(
            {
                "title": "Test Song",
                "video_url": "https://example.com",
                "user": "Alice",
            }
        )

        assert len(calls) == 1
        assert len(tracker._items) == 1

    def test_on_change_called_on_processing_complete(self):
        """on_change fires when processing completes."""
        calls = []
        tracker = _make_tracker()
        tracker._on_change = lambda: calls.append(1)

        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        item.song_path = "/songs/test.mp4"
        tracker._items.append(item)

        tracker._on_processing_complete({"song_path": "/songs/test.mp4", "lyric_method": None})

        assert len(calls) == 1

    def test_on_change_not_called_when_none(self):
        """No crash when on_change is None (default)."""
        tracker = _make_tracker()
        # Should not raise
        tracker._on_download_queued(
            {
                "title": "Test Song",
                "video_url": "https://example.com",
                "user": "Alice",
            }
        )

    def test_on_change_exception_does_not_crash(self):
        """A failing on_change callback is caught and logged."""
        calls = []
        tracker = _make_tracker()
        tracker._on_change = lambda: 1 / 0  # Will raise ZeroDivisionError

        # Should not raise — the exception is caught
        tracker._on_download_queued(
            {
                "title": "Test Song",
                "video_url": "https://example.com",
                "user": "Alice",
            }
        )

        # The item should still be added despite the callback failure
        assert len(tracker._items) == 1


class TestProcessingPhase:
    """Tests for processing_phase field in status responses."""

    def test_phase_none_when_not_active(self):
        """processing_phase is None when no job is active."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        item.song_path = "/songs/test.mp4"
        item.download_status = "complete"
        item.processing_status = "complete"
        tracker._items.append(item)

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["processing_phase"] is None

    def test_phase_populated_when_active(self):
        """processing_phase is set when the item is the active job."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        item.song_path = "/songs/test.mp4"
        item.download_status = "complete"
        tracker._items.append(item)
        tracker._processing_manager.get_active_job.return_value = "/songs/test.mp4"
        tracker._processing_manager.get_active_phase.return_value = "stem_separation"

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["processing_status"] == "active"
        assert status[0]["processing_phase"] == "stem_separation"

    def test_phase_changes_with_stage(self):
        """processing_phase updates when the pipeline stage changes."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        item.song_path = "/songs/test.mp4"
        item.download_status = "complete"
        tracker._items.append(item)
        tracker._processing_manager.get_active_job.return_value = "/songs/test.mp4"

        # First call: extract phase
        tracker._processing_manager.get_active_phase.return_value = "extract"
        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["processing_phase"] == "extract"

        # Second call: transcode phase
        tracker._processing_manager.get_active_phase.return_value = "transcode"
        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["processing_phase"] == "transcode"

    def test_phase_cleared_on_completion(self):
        """processing_phase is None after processing completes."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        item.song_path = "/songs/test.mp4"
        item.download_status = "complete"
        item.processing_phase = "stem_separation"
        tracker._items.append(item)

        # Simulate processing_complete event
        tracker._on_processing_complete({"song_path": "/songs/test.mp4", "lyric_method": None})

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["processing_status"] == "complete"
        assert status[0]["processing_phase"] is None

    def test_phase_cleared_on_error(self):
        """processing_phase is None after processing errors."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        item.song_path = "/songs/test.mp4"
        item.download_status = "complete"
        item.processing_phase = "transcode"
        tracker._items.append(item)

        tracker._on_processing_error({"song_path": "/songs/test.mp4", "error": "boom"})

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["processing_status"] == "error"
        assert status[0]["processing_phase"] is None

    def test_phase_none_for_waiting_item(self):
        """processing_phase is None when item hasn't started processing."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        # No song_path yet — download not complete
        tracker._items.append(item)

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["processing_status"] == "waiting"
        assert status[0]["processing_phase"] is None

    def test_phase_none_for_pending_item(self):
        """processing_phase is None when item is pending processing."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        item.song_path = "/songs/test.mp4"
        item.download_status = "complete"
        tracker._items.append(item)
        tracker._processing_manager.pending_jobs = ["/songs/test.mp4"]

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["processing_status"] == "pending"
        assert status[0]["processing_phase"] is None

    def test_phase_none_when_cancelling(self):
        """processing_phase is None when item is in cancelling state."""
        tracker = _make_tracker()
        item = PipelineItem(title="Test", url="https://example.com", user="Alice")
        item.song_path = "/songs/test.mp4"
        item.download_status = "complete"
        item.processing_phase = "stem_separation"
        item.cancelling = True
        tracker._items.append(item)

        status = tracker.get_status(admin=False, user="Alice")
        assert status[0]["processing_status"] == "cancelling"
        assert status[0]["processing_phase"] is None

    def test_pipeline_stage_changed_fires_notify(self):
        """pipeline_stage_changed event fires _notify_change."""
        calls = []
        tracker = _make_tracker()
        tracker._on_change = lambda: calls.append(1)
        tracker._on_pipeline_stage_changed()
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Regen and process rows, and the retry / dismiss / clear-finished actions
# ---------------------------------------------------------------------------

LIB_PATH = "/songs/Library Song---abcdefghijk.mp4"


def _queue_regen(tracker, path=LIB_PATH, label="Repair"):
    """Announce a regen job the way ProcessingManager.enqueue_regen does."""
    job = MagicMock(name="regen job")
    tracker._events.emit("regen_queued", {"song_path": path, "label": label, "job": job})
    item = next(i for i in tracker._items if i.kind == "regen" and i.song_path == path)
    return item, job


def _announce_processing(tracker, path=LIB_PATH):
    tracker._events.emit("processing_queued", path)
    return next(i for i in tracker._items if i.kind == "process" and i.song_path == path)


def _finished(tracker, kind="regen", status="complete", path=LIB_PATH):
    """A regen / process row that has finished with ``status``."""
    if kind == "regen":
        item, _ = _queue_regen(tracker, path)
    else:
        item = _announce_processing(tracker, path)
    item.processing_status = status
    return item


class TestRegenRows:
    def test_a_regen_row_is_hidden_from_guests(self):
        tracker = _make_tracker()
        _queue_regen(tracker)

        assert tracker.get_status(admin=False, user="Alice") == []

    def test_an_admin_sees_the_regen_row_with_its_kind_and_label(self):
        tracker = _make_tracker()
        item, _ = _queue_regen(tracker, label="Reprocess")
        tracker._processing_manager.pending_jobs = [LIB_PATH]

        [row] = tracker.get_status(admin=True, user="Alice")

        assert (row["kind"], row["label"], row["title"]) == ("regen", "Reprocess", "Library Song")
        assert row["song_path"] == LIB_PATH
        assert row["processing_status"] == "pending"
        assert row["actions"] == ["cancel", "song_info"]

    def test_queueing_a_regen_replaces_the_finished_rows_of_that_song(self):
        tracker = _make_tracker()
        _finished(tracker, "regen", "error")
        other = _finished(tracker, "regen", "complete", path="/songs/Other---xyz789.mp4")

        item, _ = _queue_regen(tracker)

        assert tracker._items == [other, item]

    def test_cancelling_a_pending_regen_row_never_deletes_the_song(self):
        tracker = _make_tracker()
        item, _ = _queue_regen(tracker)
        tracker._processing_manager.pending_jobs = [LIB_PATH]
        tracker.get_status(admin=True)  # derives "pending"

        assert tracker.cancel(item.id) is True

        tracker._processing_manager.cancel_pending.assert_called_once_with(LIB_PATH)
        tracker._song_manager.delete.assert_not_called()
        assert tracker._items == []

    def test_cancelling_an_active_regen_row_never_deletes_the_song(self):
        tracker = _make_tracker()
        item, _ = _queue_regen(tracker)
        tracker._processing_manager.get_active_job.return_value = LIB_PATH
        tracker.get_status(admin=True)  # derives "active"

        assert tracker.cancel(item.id) is True
        tracker._events.emit("processing_cancelled", LIB_PATH)  # the run wound down

        tracker._processing_manager.cancel_active.assert_called_once_with(LIB_PATH)
        tracker._song_manager.delete.assert_not_called()
        assert tracker._items == []

    def test_cancelling_a_pending_download_still_deletes_its_song(self):
        tracker = _make_tracker()
        item = PipelineItem(title="New", url="https://example.com", user="Alice")
        item.download_status = "complete"
        item.song_path = "/songs/New---aaa111.mp4"
        tracker._items.append(item)
        tracker._processing_manager.pending_jobs = [item.song_path]
        tracker.get_status(admin=True)

        assert tracker.cancel(item.id) is True

        tracker._song_manager.delete.assert_called_once_with("/songs/New---aaa111.mp4")

    def test_cancelling_an_active_download_still_deletes_its_song(self):
        tracker = _make_tracker()
        item = PipelineItem(title="New", url="https://example.com", user="Alice")
        item.download_status = "complete"
        item.song_path = "/songs/New---aaa111.mp4"
        tracker._items.append(item)
        tracker._processing_manager.get_active_job.return_value = item.song_path
        tracker.get_status(admin=True)
        tracker.cancel(item.id)

        tracker._events.emit("processing_cancelled", item.song_path)

        tracker._song_manager.delete.assert_called_once_with("/songs/New---aaa111.mp4")


class TestProcessRows:
    def test_a_song_with_no_row_gets_a_process_row(self):
        tracker = _make_tracker()

        item = _announce_processing(tracker)

        assert (item.label, item.title, item.download_status) == (
            "Process",
            "Library Song",
            "complete",
        )
        assert item.user == ""

    def test_a_download_with_a_live_row_adds_no_row(self):
        tracker = _make_tracker()
        item = PipelineItem(
            title="New", url="https://www.youtube.com/watch?v=aaa11111111", user="Alice"
        )
        item.song_path = "/songs/New---aaa11111111.mp4"
        item.download_status = "complete"
        tracker._items.append(item)

        tracker._events.emit("processing_queued", item.song_path)

        assert tracker._items == [item]

    def test_a_new_process_row_replaces_the_finished_rows_of_that_song(self):
        tracker = _make_tracker()
        _finished(tracker, "regen", "error")

        item = _announce_processing(tracker)

        assert tracker._items == [item]

    def test_the_download_row_is_found_when_the_tracker_hears_song_downloaded_first(self):
        # karaoke.py subscribes ProcessingManager.enqueue after the tracker so
        # the tracker's handler runs first and the item has its song path.
        events = EventSystem()
        pm = ProcessingManager(events=events, preferences=MagicMock(get_or_default=lambda k: ""))
        tracker = PipelineTracker(
            download_manager=MagicMock(active_url=None),
            processing_manager=pm,
            queue_manager=MagicMock(),
            song_manager=MagicMock(),
            events=events,
        )
        events.on("song_downloaded", pm.enqueue)
        events.emit(
            "download_queued",
            {
                "title": "New",
                "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "user": "Alice",
            },
        )

        events.emit("song_downloaded", "/songs/New---dQw4w9WgXcQ.mp4")

        [item] = tracker._items
        assert (item.kind, item.song_path) == ("download", "/songs/New---dQw4w9WgXcQ.mp4")


class TestRowsThatFinish:
    def test_events_update_the_first_unfinished_row_for_the_song(self):
        tracker = _make_tracker()
        old = _finished(tracker, "process", "complete")
        live = PipelineItem(title="Again", url="", user="")
        live.song_path = LIB_PATH
        tracker._items.append(live)

        tracker._events.emit("processing_error", {"song_path": LIB_PATH, "error": "boom"})

        assert (old.processing_status, old.error_message) == ("complete", None)
        assert (live.processing_status, live.error_message) == ("error", "boom")

    def test_complete_and_error_stamp_the_time_they_finished(self):
        tracker = _make_tracker()
        done = _announce_processing(tracker, "/songs/A---aaa111.mp4")
        failed = _announce_processing(tracker, "/songs/B---bbb222.mp4")
        assert done.finished_at is None

        tracker._events.emit(
            "processing_complete", {"song_path": done.song_path, "lyric_method": None}
        )
        tracker._events.emit("processing_error", {"song_path": failed.song_path, "error": "x"})

        assert done.finished_at is not None and failed.finished_at is not None
        rows = {r["id"]: r for r in tracker.get_status(admin=True)}
        assert 0 <= rows[done.id]["finished_ago_s"] < 5
        assert rows[failed.id]["finished_ago_s"] is not None

    def test_a_running_row_has_no_finished_time_and_carries_the_elapsed_time(self):
        tracker = _make_tracker()
        item, _ = _queue_regen(tracker)
        tracker._processing_manager.get_active_job.return_value = LIB_PATH
        tracker._processing_manager.get_active_elapsed_s.return_value = 12.5

        [row] = tracker.get_status(admin=True)

        assert row["finished_ago_s"] is None
        assert row["elapsed_s"] == 12.5

    def test_only_the_running_row_gets_the_elapsed_time(self):
        tracker = _make_tracker()
        _queue_regen(tracker, "/songs/A---aaa111.mp4")
        _queue_regen(tracker, "/songs/B---bbb222.mp4")
        tracker._processing_manager.get_active_job.return_value = "/songs/A---aaa111.mp4"
        tracker._processing_manager.pending_jobs = [
            "/songs/A---aaa111.mp4",
            "/songs/B---bbb222.mp4",
        ]
        tracker._processing_manager.get_active_elapsed_s.return_value = 3.0

        rows = {r["song_path"]: r for r in tracker.get_status(admin=True)}

        assert rows["/songs/A---aaa111.mp4"]["elapsed_s"] == 3.0
        assert rows["/songs/B---bbb222.mp4"]["elapsed_s"] is None

    @pytest.mark.parametrize(
        "event, data, status",
        [
            ("processing_error", {"song_path": LIB_PATH, "error": "boom"}, "error"),
            ("processing_complete", {"song_path": LIB_PATH, "lyric_method": None}, "complete"),
        ],
    )
    def test_a_finished_row_keeps_its_status_while_the_manager_cleans_up(self, event, data, status):
        # The manager reports how a job ended before it stops naming the job as
        # running; a read in between must not turn the row back into "active".
        tracker = _make_tracker()
        _queue_regen(tracker)
        tracker._events.emit(event, data)
        tracker._processing_manager.get_active_job.return_value = LIB_PATH
        tracker._processing_manager.pending_jobs = [LIB_PATH]

        [during] = tracker.get_status(admin=True)
        tracker._processing_manager.get_active_job.return_value = None
        tracker._processing_manager.pending_jobs = []
        [after] = tracker.get_status(admin=True)

        assert during["processing_status"] == status
        assert after["processing_status"] == status

    def test_a_cancel_while_the_manager_cleans_up_after_an_error_is_refused(self):
        tracker = _make_tracker()
        item, _ = _queue_regen(tracker)
        tracker._events.emit("processing_error", {"song_path": LIB_PATH, "error": "boom"})
        tracker._processing_manager.get_active_job.return_value = LIB_PATH
        tracker.get_status(admin=True)

        assert tracker.cancel(item.id) is False
        tracker._processing_manager.cancel_active.assert_not_called()
        tracker._processing_manager.get_active_job.return_value = None
        [row] = tracker.get_status(admin=True)
        assert row["processing_status"] == "error"
        assert "retry" in row["actions"]


class TestRowActions:
    @pytest.mark.parametrize("kind", ["regen", "process"])
    def test_remove_is_not_offered_for_a_row_that_is_not_a_download(self, kind):
        tracker = _make_tracker()
        item = _finished(tracker, kind, "complete")

        [row] = tracker.get_status(admin=True)

        assert "remove" not in row["actions"]
        assert "dismiss" in row["actions"]
        assert "enqueue" not in row["actions"]
        assert tracker.remove(item.id) is False
        assert tracker._items == [item]
        tracker._song_manager.delete.assert_not_called()

    def test_a_download_still_offers_remove(self):
        tracker = _make_tracker()
        item = PipelineItem(title="Done", url="", user="Alice")
        item.download_status = item.processing_status = "complete"
        item.song_path = "/songs/Done---ddd444.mp4"
        tracker._items.append(item)

        [row] = tracker.get_status(admin=True, user="Alice")

        assert "remove" in row["actions"] and "dismiss" in row["actions"]

    def test_a_download_that_failed_before_it_had_a_file_offers_no_remove(self):
        tracker = _make_tracker()
        _download_row(tracker, "Bad link", url="https://x/bad")
        tracker._events.emit("download_error", {"url": "https://x/bad", "error": "nope"})

        [row] = tracker.get_status(admin=True)

        assert "remove" not in row["actions"] and "dismiss" in row["actions"]

    def test_guests_are_offered_none_of_the_new_actions(self):
        tracker = _make_tracker()
        item = PipelineItem(title="Done", url="", user="Alice")
        item.download_status = "complete"
        item.processing_status = "error"
        item.song_path = "/songs/Done---ddd444.mp4"
        tracker._items.append(item)

        [row] = tracker.get_status(admin=False, user="Alice")

        assert "dismiss" not in row["actions"] and "retry" not in row["actions"]

    def test_a_process_row_is_hidden_from_guests(self):
        tracker = _make_tracker()
        _announce_processing(tracker)
        tracker._processing_manager.pending_jobs = [LIB_PATH]

        assert tracker.get_status(admin=False, user="") == []
        assert tracker.get_status(admin=False, user="Alice") == []

    def test_an_admin_is_offered_song_info_on_a_row_with_a_song_path_only(self):
        tracker = _make_tracker()
        in_library = _announce_processing(tracker)
        waiting = PipelineItem(title="Waiting", url="https://example.com/v", user="Alice")
        tracker._items.append(waiting)

        rows = {r["id"]: r for r in tracker.get_status(admin=True)}
        guest_rows = {r["id"]: r for r in tracker.get_status(admin=False, user="Alice")}

        assert "song_info" in rows[in_library.id]["actions"]
        assert "song_info" not in rows[waiting.id]["actions"]
        assert "song_info" not in guest_rows[waiting.id]["actions"]

    def test_retry_is_offered_only_for_a_failed_row_with_a_song_path(self):
        tracker = _make_tracker()
        failed = _finished(tracker, "process", "error", path="/songs/A---aaa111.mp4")
        ok = _finished(tracker, "process", "complete", path="/songs/B---bbb222.mp4")

        rows = {r["id"]: r for r in tracker.get_status(admin=True)}

        assert "retry" in rows[failed.id]["actions"]
        assert "retry" not in rows[ok.id]["actions"]


class TestDismiss:
    @pytest.mark.parametrize("kind", ["regen", "process"])
    @pytest.mark.parametrize("status", ["complete", "error"])
    def test_drops_a_finished_row_without_touching_files(self, kind, status):
        tracker = _make_tracker()
        item = _finished(tracker, kind, status)

        assert tracker.dismiss(item.id) is True

        assert tracker._items == []
        tracker._song_manager.delete.assert_not_called()

    def test_a_download_row_is_dropped_too_but_its_song_stays(self):
        tracker = _make_tracker()
        item = PipelineItem(title="Done", url="", user="Alice")
        item.download_status = item.processing_status = "complete"
        item.song_path = "/songs/Done---ddd444.mp4"
        tracker._items.append(item)

        assert tracker.dismiss(item.id) is True

        tracker._song_manager.delete.assert_not_called()

    def test_refuses_a_row_still_in_flight(self):
        tracker = _make_tracker()
        item, _ = _queue_regen(tracker)

        assert tracker.dismiss(item.id) is False
        assert tracker._items == [item]

    def test_unknown_id(self):
        assert _make_tracker().dismiss("nope") is False

    def test_notifies_a_change(self):
        tracker = _make_tracker()
        calls = []
        tracker._on_change = lambda: calls.append(1)
        item = _finished(tracker, "regen", "complete")
        calls.clear()

        tracker.dismiss(item.id)

        assert calls == [1]


class TestRetry:
    def test_a_failed_regen_queues_its_job_again(self):
        tracker = _make_tracker()
        item, job = _queue_regen(tracker)
        item.processing_status = "error"
        tracker._processing_manager.enqueue_regen.return_value = True

        assert tracker.retry(item.id) is True

        tracker._processing_manager.enqueue_regen.assert_called_once_with(job)
        tracker._processing_manager.enqueue.assert_not_called()
        tracker._song_manager.delete.assert_not_called()

    def test_a_retried_regen_comes_back_as_a_fresh_row(self):
        # With the real manager: enqueue_regen announces the job and the tracker
        # swaps the failed row for a new one.
        events = EventSystem()
        pm = ProcessingManager(events=events, preferences=MagicMock())
        tracker = PipelineTracker(
            download_manager=MagicMock(active_url=None),
            processing_manager=pm,
            queue_manager=MagicMock(),
            song_manager=MagicMock(),
            events=events,
        )
        regen = MagicMock()
        regen.song.song_path = LIB_PATH
        regen.label = "Repair"
        pm.enqueue_regen(regen)
        [failed] = tracker._items
        pm.pending_jobs.clear()
        pm._regen_jobs.clear()
        events.emit("processing_error", {"song_path": LIB_PATH, "error": "boom"})
        assert failed.processing_status == "error"

        assert tracker.retry(failed.id) is True

        [fresh] = tracker._items
        assert fresh is not failed
        assert (fresh.kind, fresh.processing_status, fresh.regen_job) == ("regen", "waiting", regen)

    def test_a_failed_process_row_goes_back_to_waiting_and_is_queued(self):
        tracker = _make_tracker()
        item = _finished(tracker, "process", "error")
        item.error_message = "boom"
        item.finished_at = 1.0

        assert tracker.retry(item.id) is True

        assert (item.processing_status, item.error_message, item.finished_at) == (
            "waiting",
            None,
            None,
        )
        tracker._processing_manager.enqueue.assert_called_once_with(LIB_PATH)
        tracker._processing_manager.enqueue_regen.assert_not_called()
        tracker._song_manager.delete.assert_not_called()

    def test_a_failed_download_goes_back_to_waiting_and_is_queued(self):
        tracker = _make_tracker()
        item = PipelineItem(title="New", url="https://example.com", user="Alice")
        item.download_status = "complete"
        item.processing_status = "error"
        item.error_message = "boom"
        item.song_path = "/songs/New---aaa111.mp4"
        tracker._items.append(item)

        assert tracker.retry(item.id) is True

        assert (item.kind, item.processing_status, item.error_message) == (
            "download",
            "waiting",
            None,
        )
        tracker._processing_manager.enqueue.assert_called_once_with("/songs/New---aaa111.mp4")

    def test_refuses_what_has_not_failed_or_has_no_song(self):
        tracker = _make_tracker()
        running, _ = _queue_regen(tracker)
        no_song = PipelineItem(title="x", url="https://example.com", user="Alice")
        no_song.processing_status = "error"
        tracker._items.append(no_song)

        assert tracker.retry(running.id) is False
        assert tracker.retry(no_song.id) is False
        assert tracker.retry("nope") is False
        tracker._processing_manager.enqueue.assert_not_called()
        tracker._processing_manager.enqueue_regen.assert_not_called()

    def test_a_regen_the_manager_refuses_reports_false(self):
        tracker = _make_tracker()
        item, _ = _queue_regen(tracker)
        item.processing_status = "error"
        tracker._processing_manager.enqueue_regen.return_value = False

        assert tracker.retry(item.id) is False


class TestAStatusReadBeforeTheQueue:
    """A status read between song_downloaded (or a retry) and processing_queued
    finds the song neither running nor waiting and calls its row complete."""

    URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    PATH = "/songs/Song---dQw4w9WgXcQ.mp4"

    def test_a_download_keeps_its_row(self):
        tracker = _make_tracker()
        events = tracker._events
        events.emit("download_queued", {"title": "Song", "video_url": self.URL, "user": "Alice"})
        events.emit("song_downloaded", self.PATH)
        tracker.get_status(user="Alice")
        tracker._processing_manager.pending_jobs.append(self.PATH)
        events.emit("processing_queued", self.PATH)
        [item] = tracker._items

        # In flight again before any read: a dismiss can't drop it.
        assert tracker.dismiss(item.id) is False
        [row] = tracker.get_status(user="Alice")

        assert (row["kind"], row["group"], row["processing_status"], row["mine"]) == (
            "download",
            "active",
            "pending",
            True,
        )
        assert [r["kind"] for r in tracker.get_status(admin=True)] == ["download"]

    def test_a_retried_download_keeps_its_row(self):
        tracker = _make_tracker()
        item = _download_row(tracker, "Song", url=self.URL, song_path=self.PATH)
        tracker._events.emit("processing_error", {"song_path": self.PATH, "error": "boom"})
        manager = tracker._processing_manager

        def enqueue(path):
            tracker.get_status(admin=True)
            manager.pending_jobs.append(path)
            tracker._events.emit("processing_queued", path)

        manager.enqueue.side_effect = enqueue

        assert tracker.retry(item.id) is True
        [row] = tracker.get_status(admin=True)

        assert (row["id"], row["user"], row["group"], row["processing_status"]) == (
            item.id,
            "Alice",
            "active",
            "pending",
        )


class TestClearFinished:
    def test_drops_every_completed_row_and_counts_them(self):
        tracker = _make_tracker()
        _finished(tracker, "regen", "complete", path="/songs/A---aaa111.mp4")
        _finished(tracker, "process", "complete", path="/songs/B---bbb222.mp4")
        done = PipelineItem(title="Done", url="", user="Alice")
        done.download_status = done.processing_status = "complete"
        done.song_path = "/songs/Done---ddd444.mp4"
        tracker._items.append(done)
        failed = _finished(tracker, "process", "error", path="/songs/C---ccc333.mp4")
        running, _ = _queue_regen(tracker, "/songs/D---ddd111.mp4")

        assert tracker.clear_finished() == 3

        assert tracker._items == [failed, running]
        tracker._song_manager.delete.assert_not_called()

    def test_nothing_to_clear(self):
        tracker = _make_tracker()
        calls = []
        tracker._on_change = lambda: calls.append(1)

        assert tracker.clear_finished() == 0
        assert calls == []


class TestTrackedPaths:
    def test_holds_the_song_of_every_row_finished_or_not(self):
        tracker = _make_tracker()
        _finished(tracker, "process", "complete", path="/songs/A---aaa111.mp4")
        _queue_regen(tracker, "/songs/D---ddd111.mp4")
        _download_row(tracker, "Not downloaded yet", url="https://x/1")

        assert tracker.tracked_paths() == {"/songs/A---aaa111.mp4", "/songs/D---ddd111.mp4"}


# ---------------------------------------------------------------------------
# Routes: retry / dismiss / clear_finished (admin only)
# ---------------------------------------------------------------------------


class TestNewAdminEndpoints:
    @pytest.mark.parametrize(
        "url",
        ["/processing/some-id/retry", "/processing/some-id/dismiss", "/processing/clear_finished"],
    )
    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=False)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_non_admin_gets_403(self, mock_get_instance, mock_is_admin, mock_gettext, client, url):
        mock_karaoke = MagicMock()
        mock_get_instance.return_value = mock_karaoke

        response = client.post(url)

        assert response.status_code == 403
        assert json.loads(response.data)["success"] is False
        mock_karaoke.pipeline_tracker.retry.assert_not_called()
        mock_karaoke.pipeline_tracker.dismiss.assert_not_called()
        mock_karaoke.pipeline_tracker.clear_finished.assert_not_called()

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_admin_can_retry(self, mock_get_instance, mock_is_admin, mock_gettext, client):
        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker.retry.return_value = True
        mock_get_instance.return_value = mock_karaoke

        response = client.post("/processing/abc/retry")

        assert json.loads(response.data) == {"success": True}
        mock_karaoke.pipeline_tracker.retry.assert_called_once_with("abc")

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_admin_can_dismiss(self, mock_get_instance, mock_is_admin, mock_gettext, client):
        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker.dismiss.return_value = False
        mock_get_instance.return_value = mock_karaoke

        response = client.post("/processing/abc/dismiss")

        assert json.loads(response.data) == {"success": False}
        mock_karaoke.pipeline_tracker.dismiss.assert_called_once_with("abc")

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_admin_can_clear_finished(self, mock_get_instance, mock_is_admin, mock_gettext, client):
        mock_karaoke = MagicMock()
        mock_karaoke.pipeline_tracker.clear_finished.return_value = 4
        mock_get_instance.return_value = mock_karaoke

        response = client.post("/processing/clear_finished")

        assert json.loads(response.data) == {"success": True, "count": 4}


# ---------------------------------------------------------------------------
# Display order, groups and positions
# ---------------------------------------------------------------------------


def _download_row(tracker, title, url="", user="Alice", song_path=None, status="waiting"):
    item = PipelineItem(title=title, url=url, user=user)
    item.song_path = song_path
    if song_path is not None:
        item.download_status = "complete"
    item.processing_status = status
    tracker._items.append(item)
    return item


class TestDisplayOrder:
    def test_active_rows_come_in_the_order_the_app_will_run_them(self):
        tracker = _make_tracker()
        running = _download_row(tracker, "Running", song_path="/songs/R---rrr.mp4")
        # Added in a different order from the way they run.
        regen, _ = _queue_regen(tracker, "/songs/G---ggg.mp4")
        process = _announce_processing(tracker, "/songs/P---ppp.mp4")
        waiting_dl = _download_row(tracker, "Waiting download", url="https://x/2")
        queued_dl = _download_row(tracker, "Queued download", song_path="/songs/Q---qqq.mp4")
        live_dl = _download_row(tracker, "Downloading", url="https://x/1")
        tracker._download_manager.active_url = "https://x/1"
        tracker._processing_manager.get_active_job.return_value = running.song_path
        tracker._processing_manager.pending_jobs = [
            running.song_path,
            regen.song_path,
            process.song_path,
            queued_dl.song_path,
        ]

        rows = tracker.get_status(admin=True, user="Alice")

        assert [r["id"] for r in rows] == [
            running.id,
            live_dl.id,
            waiting_dl.id,
            process.id,
            queued_dl.id,
            regen.id,
        ]
        assert {r["group"] for r in rows} == {"active"}
        assert [r["position"] for r in rows] == [None, 1, 2, 3, 4, 5]

    def test_groups_are_active_then_attention_then_finished_newest_first(self):
        tracker = _make_tracker()
        old_done = _finished(tracker, "regen", "complete", path="/songs/A---aaa.mp4")
        new_done = _finished(tracker, "process", "complete", path="/songs/B---bbb.mp4")
        old_failed = _finished(tracker, "regen", "error", path="/songs/C---ccc.mp4")
        new_failed = _finished(tracker, "process", "error", path="/songs/D---ddd.mp4")
        waiting = _download_row(tracker, "Waiting", url="https://x/1")
        for item, age in ((old_done, 50), (new_done, 5), (old_failed, 40), (new_failed, 4)):
            item.finished_at = 1000.0 - age

        rows = tracker.get_status(admin=True)

        assert [(r["id"], r["group"]) for r in rows] == [
            (waiting.id, "active"),
            (new_failed.id, "attention"),
            (old_failed.id, "attention"),
            (new_done.id, "finished"),
            (old_done.id, "finished"),
        ]
        assert [r["position"] for r in rows] == [1, None, None, None, None]

    def test_a_cancelling_row_is_the_running_one(self):
        tracker = _make_tracker()
        queued = _download_row(tracker, "Queued", song_path="/songs/Q---qqq.mp4")
        cancelling = _download_row(tracker, "Cancelling", song_path="/songs/C---ccc.mp4")
        cancelling.cancelling = True
        tracker._processing_manager.get_active_job.return_value = cancelling.song_path
        tracker._processing_manager.pending_jobs = [queued.song_path, cancelling.song_path]

        rows = tracker.get_status(admin=True)

        assert [r["id"] for r in rows] == [cancelling.id, queued.id]
        assert rows[0]["processing_status"] == "cancelling" and rows[0]["position"] is None
        assert rows[1]["position"] == 1

    def test_a_failed_download_goes_to_attention_with_the_time_it_failed(self):
        tracker = _make_tracker()
        item = _download_row(tracker, "Bad link", url="https://x/bad")

        tracker._events.emit("download_error", {"url": "https://x/bad", "error": "nope"})
        [row] = tracker.get_status(admin=True)

        assert (row["group"], row["processing_status"], row["error_message"]) == (
            "attention",
            "error",
            "nope",
        )
        assert row["finished_ago_s"] is not None
        assert "dismiss" in row["actions"]
        assert tracker.dismiss(item.id) is True

    def test_a_download_that_just_failed_can_be_removed_before_the_next_status_read(self):
        tracker = _make_tracker()
        item = _download_row(tracker, "Bad link", url="https://x/bad")
        tracker._events.emit("download_error", {"url": "https://x/bad", "error": "nope"})

        assert tracker.remove(item.id) is True
        assert tracker._items == []

    def test_every_row_says_whether_it_is_the_callers_own(self):
        tracker = _make_tracker()
        mine = _download_row(tracker, "Mine", url="https://x/1", user="Alice")
        theirs = _download_row(tracker, "Theirs", url="https://x/2", user="Bob")

        rows = {r["id"]: r for r in tracker.get_status(admin=False, user="Alice")}

        assert rows[mine.id]["mine"] is True
        assert rows[theirs.id]["mine"] is False


class TestPoorSongNumbers:
    @staticmethod
    def song_with_bundle(tmp_path, line_count, lines_with_words):
        video = tmp_path / "Song---abcdefghijk.mp4"
        video.write_bytes(b"")
        bundle = tmp_path / "alignment_debug" / f"{video.stem}.json"
        bundle.parent.mkdir()
        bundle.write_text(
            json.dumps(
                {
                    "schema_version": 11,
                    "output_summary": {
                        "line_count": line_count,
                        "lines_with_words": lines_with_words,
                    },
                }
            ),
            encoding="utf-8",
        )
        return str(video)

    def test_an_admin_sees_how_many_lines_a_poor_song_guessed(self, tmp_path):
        tracker = _make_tracker()
        path = self.song_with_bundle(tmp_path, line_count=20, lines_with_words=12)
        _announce_processing(tracker, path)

        tracker._events.emit("processing_complete", {"song_path": path, "lyric_method": None})
        [admin_row] = tracker.get_status(admin=True)

        assert (admin_row["guessed"], admin_row["line_count"]) == (8, 20)

    def test_a_guest_is_not_told(self, tmp_path):
        tracker = _make_tracker()
        path = self.song_with_bundle(tmp_path, line_count=20, lines_with_words=12)
        item = _download_row(tracker, "Song", url="https://x/1", song_path=path)

        tracker._events.emit("processing_complete", {"song_path": path, "lyric_method": None})
        [guest_row] = tracker.get_status(admin=False, user="Alice")

        assert item.guessed == 8
        assert (guest_row["guessed"], guest_row["line_count"]) == (None, None)

    def test_a_song_that_is_not_poor_carries_no_numbers(self, tmp_path):
        tracker = _make_tracker()
        path = self.song_with_bundle(tmp_path, line_count=20, lines_with_words=19)
        _announce_processing(tracker, path)

        tracker._events.emit("processing_complete", {"song_path": path, "lyric_method": None})
        [row] = tracker.get_status(admin=True)

        assert (row["guessed"], row["line_count"]) == (None, None)

    def test_a_bundle_that_cannot_be_read_does_not_fail_the_finished_job(self, tmp_path):
        tracker = _make_tracker()
        path = self.song_with_bundle(tmp_path, line_count=20, lines_with_words=12)
        bundle = tmp_path / "alignment_debug" / "Song---abcdefghijk.json"
        bundle.write_text('{"output_summary": ["not", "a", "mapping"]}', encoding="utf-8")
        _announce_processing(tracker, path)

        tracker._events.emit("processing_complete", {"song_path": path, "lyric_method": None})
        [row] = tracker.get_status(admin=True)

        assert row["processing_status"] == "complete"
        assert (row["guessed"], row["line_count"]) == (None, None)

    def test_a_bundle_with_a_count_that_is_not_a_number_does_not_fail_the_finished_job(
        self, tmp_path
    ):
        tracker = _make_tracker()
        path = self.song_with_bundle(tmp_path, line_count=20, lines_with_words="12")
        _announce_processing(tracker, path)

        tracker._events.emit("processing_complete", {"song_path": path, "lyric_method": None})
        [row] = tracker.get_status(admin=True)

        assert row["processing_status"] == "complete"
        assert (row["guessed"], row["line_count"]) == (None, None)

    def test_a_song_with_no_bundle_carries_no_numbers(self):
        tracker = _make_tracker()
        _announce_processing(tracker)

        tracker._events.emit("processing_complete", {"song_path": LIB_PATH, "lyric_method": None})
        [row] = tracker.get_status(admin=True)

        assert (row["guessed"], row["line_count"]) == (None, None)


# ---------------------------------------------------------------------------
# Routes: attention list and retrying a song with no row
# ---------------------------------------------------------------------------


@pytest.fixture
def library_env():
    """A real tracker and LibraryTools behind a mocked Karaoke, with a three-song library."""
    from pikaraoke.lib.library_tools import LibraryTools
    from pikaraoke.lib.song_list import SongList
    from pikaraoke.lib.song_manager import SongManager

    paths = [f"/songs/{name}---{name * 11}.mp4" for name in ("A", "B", "C")]
    failed, unfinished = paths[0], paths[1]
    library = SongList()
    library.update(paths)
    karaoke = MagicMock()
    karaoke.pipeline_tracker = _make_tracker()
    song_manager = MagicMock()
    song_manager.songs = library
    song_manager.filename_from_path = SongManager.filename_from_path
    song_manager.get_paths_by_pipeline_state.side_effect = lambda states: [
        path for path, state in ((failed, "failed"), (unfinished, "pending")) if state in states
    ]
    karaoke.song_manager = song_manager
    karaoke.processing_manager = MagicMock()
    karaoke.processing_manager.get_active_job.return_value = None
    karaoke.processing_manager.pending_jobs = []
    karaoke.library_tools = LibraryTools(karaoke.processing_manager, song_manager, "/songs")
    return karaoke, paths


class TestAttentionRoute:
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=False)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_guests_get_an_empty_list(self, mock_get_instance, mock_is_admin, client, library_env):
        mock_get_instance.return_value = library_env[0]

        response = client.get("/processing/attention")

        assert response.status_code == 200
        assert json.loads(response.data) == []

    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_a_failed_song_with_no_tracker_row_is_listed(
        self, mock_get_instance, mock_is_admin, client, library_env
    ):
        karaoke, paths = library_env
        mock_get_instance.return_value = karaoke

        rows = json.loads(client.get("/processing/attention").data)

        assert [(r["song_path"], r["state"]) for r in rows] == [
            (paths[0], "failed"),
            (paths[1], "unfinished"),
        ]
        assert rows[0]["actions"] == ["retry", "song_info", "delete"]

    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_a_song_the_tracker_already_shows_is_not_listed(
        self, mock_get_instance, mock_is_admin, client, library_env
    ):
        karaoke, paths = library_env
        mock_get_instance.return_value = karaoke
        _finished(karaoke.pipeline_tracker, "process", "error", path=paths[0])

        rows = json.loads(client.get("/processing/attention").data)

        assert [r["song_path"] for r in rows] == [paths[1]]


class TestRetrySongRoute:
    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=False)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_a_guest_gets_403(
        self, mock_get_instance, mock_is_admin, mock_gettext, client, library_env
    ):
        karaoke, paths = library_env
        mock_get_instance.return_value = karaoke

        response = client.post("/processing/song/retry", json={"song": paths[0]})

        assert response.status_code == 403
        karaoke.processing_manager.enqueue.assert_not_called()

    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_an_admin_queues_the_song_for_processing(
        self, mock_get_instance, mock_is_admin, mock_gettext, client, library_env
    ):
        karaoke, paths = library_env
        mock_get_instance.return_value = karaoke

        response = client.post("/processing/song/retry", json={"song": paths[0]})

        assert json.loads(response.data) == {"success": True}
        karaoke.processing_manager.enqueue.assert_called_once_with(paths[0])

    @pytest.mark.parametrize(
        "body",
        [
            {"song": "/songs/Elsewhere---ZZZZZZZZZZZ.mp4"},
            {"song": ["/songs/A---AAAAAAAAAAA.mp4"]},
            {"song": None},
            {},
            ["/songs/A---AAAAAAAAAAA.mp4"],
        ],
    )
    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_a_song_outside_the_library_is_refused(
        self, mock_get_instance, mock_is_admin, mock_gettext, client, library_env, body
    ):
        karaoke, _ = library_env
        mock_get_instance.return_value = karaoke

        response = client.post("/processing/song/retry", json=body)

        assert response.status_code == 400
        assert json.loads(response.data)["success"] is False
        karaoke.processing_manager.enqueue.assert_not_called()

    @pytest.mark.parametrize("where", ["running", "waiting"])
    @patch(f"{ROUTE_PREFIX}._", side_effect=lambda x: x)
    @patch(f"{ROUTE_PREFIX}.is_admin", return_value=True)
    @patch(f"{ROUTE_PREFIX}.get_karaoke_instance")
    def test_a_song_already_running_or_waiting_is_not_queued_twice(
        self, mock_get_instance, mock_is_admin, mock_gettext, client, library_env, where
    ):
        karaoke, paths = library_env
        mock_get_instance.return_value = karaoke
        if where == "running":
            karaoke.processing_manager.get_active_job.return_value = paths[0]
        else:
            karaoke.processing_manager.pending_jobs = [paths[0]]

        response = client.post("/processing/song/retry", json={"song": paths[0]})

        assert response.status_code == 400
        karaoke.processing_manager.enqueue.assert_not_called()
