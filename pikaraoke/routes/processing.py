"""Processing pipeline monitoring routes."""

from __future__ import annotations

import json
import logging

import flask_babel
from flask import jsonify, render_template, request
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, is_admin

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
        admin=is_admin(),
    )


@processing_bp.route("/processing/status")
def processing_status():
    """Get the status of all pipeline items."""
    k = get_karaoke_instance()
    items = k.pipeline_tracker.get_status()
    return json.dumps(items)


@processing_bp.route("/processing/user/cancel", methods=["POST"])
def user_cancel_item():
    """Let a user cancel their own pipeline item."""
    k = get_karaoke_instance()
    item_id = request.form.get("id", "")
    user = request.cookies.get("user", "")
    if not user:
        logging.warning("User cancel rejected: no user cookie (item_id=%s)", item_id)
        return jsonify({"success": False, "error": _("Not owner")}), 403
    owner = k.pipeline_tracker.get_item_user(item_id)
    if owner is None or owner != user:
        logging.warning(
            "User cancel rejected: cookie user %r != owner %r (item_id=%s)",
            user,
            owner,
            item_id,
        )
        return jsonify({"success": False, "error": _("Not owner")}), 403
    logging.info("User cancel request: item_id=%s user=%s", item_id, user)
    success = k.pipeline_tracker.cancel(item_id)
    return jsonify({"success": success})


@processing_bp.route("/processing/<item_id>/cancel", methods=["POST"])
def cancel_item(item_id):
    """Cancel an in-progress download or processing job (admin only)."""
    if not is_admin():
        logging.warning("Admin cancel rejected: not admin (item_id=%s)", item_id)
        return jsonify({"success": False, "error": _("Admin only")}), 403
    logging.info("Admin cancel request: item_id=%s", item_id)
    k = get_karaoke_instance()
    success = k.pipeline_tracker.cancel(item_id)
    return jsonify({"success": success})


@processing_bp.route("/processing/<item_id>/enqueue", methods=["POST"])
def enqueue_item(item_id):
    """Queue a completed song for playback."""
    k = get_karaoke_instance()
    success = k.pipeline_tracker.enqueue(item_id)
    return json.dumps({"success": success})


@processing_bp.route("/processing/<item_id>/remove", methods=["POST"])
def remove_item(item_id):
    """Remove a completed or errored item from the tracker (admin only)."""
    if not is_admin():
        return jsonify({"success": False, "error": _("Admin only")}), 403
    k = get_karaoke_instance()
    success = k.pipeline_tracker.remove(item_id)
    return jsonify({"success": success})
