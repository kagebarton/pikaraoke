"""Processing pipeline monitoring routes."""

from __future__ import annotations

import json

import flask_babel
from flask import render_template
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance

_ = flask_babel.gettext

processing_bp = Blueprint("processing", __name__)


@processing_bp.route("/processing")
def processing():
    """Processing pipeline monitoring page."""
    k = get_karaoke_instance()
    return render_template(
        "processing.html",
        site_title=getattr(k, "preferences", None)
        and k.preferences.get("site_name")
        or "PiKaraoke",
        title="Processing",
    )


@processing_bp.route("/processing/status")
def processing_status():
    """Get the status of all pipeline items."""
    k = get_karaoke_instance()
    items = k.pipeline_tracker.get_status()
    return json.dumps(items)


@processing_bp.route("/processing/<item_id>/cancel", methods=["POST"])
def cancel_item(item_id):
    """Cancel an in-progress download or processing job."""
    k = get_karaoke_instance()
    success = k.pipeline_tracker.cancel(item_id)
    return json.dumps({"success": success})


@processing_bp.route("/processing/<item_id>/enqueue", methods=["POST"])
def enqueue_item(item_id):
    """Queue a completed song for playback."""
    k = get_karaoke_instance()
    success = k.pipeline_tracker.enqueue(item_id)
    return json.dumps({"success": success})


@processing_bp.route("/processing/<item_id>/remove", methods=["POST"])
def remove_item(item_id):
    """Remove a completed or errored item from the tracker."""
    k = get_karaoke_instance()
    success = k.pipeline_tracker.remove(item_id)
    return json.dumps({"success": success})
