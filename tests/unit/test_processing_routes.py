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
from pikaraoke.routes.processing import processing_bp

ROUTE_PREFIX = "pikaraoke.routes.processing"


def _make_tracker():
    """Create a real PipelineTracker with mocked managers and an event system."""
    events = EventSystem()
    mock_dm = MagicMock()
    mock_dm.active_download = None
    mock_pm = MagicMock()
    mock_pm.get_active_job.return_value = None
    mock_pm.pending_jobs = []
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

        tracker._on_download_queued({
            "title": "Test Song",
            "video_url": "https://example.com",
            "user": "Alice",
        })

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

        tracker._on_processing_complete("/songs/test.mp4")

        assert len(calls) == 1

    def test_on_change_not_called_when_none(self):
        """No crash when on_change is None (default)."""
        tracker = _make_tracker()
        # Should not raise
        tracker._on_download_queued({
            "title": "Test Song",
            "video_url": "https://example.com",
            "user": "Alice",
        })

    def test_on_change_exception_does_not_crash(self):
        """A failing on_change callback is caught and logged."""
        calls = []
        tracker = _make_tracker()
        tracker._on_change = lambda: 1 / 0  # Will raise ZeroDivisionError

        # Should not raise — the exception is caught
        tracker._on_download_queued({
            "title": "Test Song",
            "video_url": "https://example.com",
            "user": "Alice",
        })

        # The item should still be added despite the callback failure
        assert len(tracker._items) == 1
