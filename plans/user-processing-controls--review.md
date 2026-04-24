# Review: User Processing Controls Plan

## Summary

The plan at `plans/user-processing-controls.md` adds user-ownership gating to the processing pipeline's cancel/remove actions, mirroring the pattern established in `plans/user-queue-controls.md`. Overall the plan is well-structured, accurate in its line-number references, and consistent with the existing codebase. The findings below are organized by severity.

---

## Critical Issues

### 1. User-supplied `user` field is trusted without server-side verification — spoofing vulnerability

The proposed `/processing/user/cancel` endpoint reads `user` from `request.form.get("user", "")` and compares it directly against `item.user`:

```python
user = request.form.get("user", "")
owner = k.pipeline_tracker.get_item_user(item_id)
if owner is None or owner != user:
    return json.dumps({"success": False, "error": "Not owner"}), 403
```

Any HTTP client can POST arbitrary `user` values. An attacker who knows (or guesses) another user's cookie name can cancel that user's pipeline items by simply setting `user=<victim_name>` in the form body. The server never cross-checks the POSTed `user` against the actual `"user"` cookie on the request.

The sibling queue plan (`user-queue-controls.md`) has the **same vulnerability** — it also reads `user` from form data and trusts it. This is acknowledged in both plans as acceptable for a home karaoke system ("User identity = cookie string. Anyone setting the same cookie value can act as that user"). However, the plan could at least read the user from the cookie server-side (via `request.cookies.get("user")`) rather than accepting a free-form POST field. This would eliminate the most trivial spoofing vector (curl with a crafted form body) without adding any session/auth layer.

**Recommendation**: Replace `user = request.form.get("user", "")` with `user = request.cookies.get("user", "")` on the server side. The JS side would still send `user: currentUser` for clarity, but the server would ignore it and read the cookie instead. This matches how `is_admin()` already works — it reads the `"admin"` cookie server-side, it doesn't accept a posted value.

### 2. Missing `Content-Type: application/json` on error responses

All the proposed 403 responses return `json.dumps(...)` without setting `Content-Type`. Flask defaults to `text/html` for tuple returns. This means the response body is valid JSON but the browser/jQuery will parse it as HTML:

```python
return json.dumps({"success": False, "error": "Admin only"}), 403
```

The existing endpoints also have this issue (they all return `json.dumps(...)` without a content type), so the plan is merely propagating a pre-existing pattern. But since new endpoints are being added, this is a good opportunity to fix it.

**Recommendation**: Use `flask.jsonify()` instead of `json.dumps()`, which sets the correct `Content-Type: application/json` header. Or at minimum, return a `Response` with `mimetype="application/json"`. This applies to both new and existing endpoints.

---

## Moderate Issues

### 3. `cancelCell()` logic is incomplete in the plan — pseudocode doesn't show the full button rendering

The plan shows:

```javascript
function cancelCell(item) {
  if (item.processing_status === 'cancelling') return '';
  var isOwner = currentUser && item.user === currentUser;

  // Remove button: admin only
  if (item.processing_status === 'complete' || item.processing_status === 'error') {
    if (!isAdmin) return '';
    // ... render remove button unchanged
  }

  // Cancel button: owner or admin only
  if (!isAdmin && !isOwner) return '';
  // ... rest of existing cancel-button rendering unchanged
}
```

The `// ... render remove button unchanged` and `// ... rest of existing cancel-button rendering unchanged` placeholders are ambiguous. The remove button currently fires when **either** `download_status` or `processing_status` is complete/error. The plan only checks `processing_status`, but the existing code checks both:

```javascript
if (item.download_status === 'complete' || item.download_status === 'error' ||
    item.processing_status === 'complete' || item.processing_status === 'error') {
```

A download-error item where `processing_status === 'waiting'` would be missed by the plan's simplified check. The plan's pseudocode needs to use the same compound condition, or the implementer will silently lose the remove button for download-only errors.

**Recommendation**: The plan should show the full condition from the existing code:

```javascript
if (item.download_status === 'complete' || item.download_status === 'error' ||
    item.processing_status === 'complete' || item.processing_status === 'error') {
    if (!isAdmin) return '';
    // remove button
}
```

### 4. Remove button click handler is not gated server-side for the admin-only case

The plan says: "`removeItem()` is unchanged — it already calls the admin-only `/processing/<id>/remove` endpoint. Since non-admins never see the remove button, no branching is needed here."

This relies on UI-only gating (hiding the button). If a non-admin user crafts a POST to `/processing/<id>/remove`, the proposed `is_admin()` check on the endpoint itself will block them, so the server-side gate is actually present. However, the plan doesn't explicitly mention this server-side gate in the context of the remove handler — it only discusses the cancel handler branching. This could cause confusion during implementation.

**Recommendation**: Add an explicit note in the "Remove" section: "The existing remove endpoint gets `is_admin()` gating in step 2, so server-side protection is already covered even if the UI is bypassed."

### 5. No error handling in the JS cancel click handler for 403 responses

The proposed cancel click handler branches on `isAdmin` to call different endpoints, but the `.done()` callback doesn't handle failures:

```javascript
$.ajax(ajaxOpts).done(function() {
    if (procStatus !== 'active') {
        fadeAndRemove($row);
    }
    fetchStatus();
});
```

If the user-cancel endpoint returns 403 (e.g., the item was reassigned or the cookie changed), jQuery's `.done()` won't fire — it goes to `.fail()`. There's no `.fail()` handler, so the user sees no feedback. The existing cancel handler has the same gap (no `.fail()`), but the new endpoint introduces a plausible 403 scenario.

**Recommendation**: Add a `.fail()` handler that at minimum calls `fetchStatus()` to refresh the table (showing the item is still there) and optionally shows an alert.

### 6. `isAdmin` template variable inconsistency across templates

The plan proposes:

```javascript
var isAdmin = {{ admin | tojson }};
```

But `queue.html` (line 6) uses:

```javascript
var isAdmin = JSON.parse('{{ admin | tojson }}');
```

And `home.html` (line 48) uses:

```javascript
var isAdmin = {{ admin | tojson }};
```

The plan's approach matches `home.html` and is correct — Jinja's `|tojson` filter for a boolean produces `true`/`false`, which is valid JS. `JSON.parse()` wrapping is redundant but harmless. However, the inconsistency across templates is worth noting.

**Recommendation**: Not a blocker for this plan, but the project should standardize on one approach. `{{ admin | tojson }}` without `JSON.parse()` is simpler and sufficient.

---

## Minor Issues

### 7. Route ordering: `/processing/user/cancel` may conflict with `/processing/<item_id>/cancel`

Flask resolves routes in registration order. If `/processing/<item_id>/cancel` (with a dynamic `item_id`) is registered before `/processing/user/cancel`, then a POST to `/processing/user/cancel` would match the first route with `item_id = "user"` — the literal string `"user"` would be captured as the item_id. This would return 403 from the admin gate (non-admins) or attempt to cancel an item with id `"user"` (admins), neither of which is the intended behavior.

Looking at the plan, the new route is added "at the bottom of the file", which means it's registered **after** the existing routes. Flask's URL matching for `Blueprint` routes follows registration order, so `item_id = "user"` would match first.

**Recommendation**: The new `/processing/user/cancel` route must be registered **before** the `/processing/<item_id>/cancel` route, or the URL pattern should be changed to avoid the ambiguity (e.g., `/processing/cancel/self` or `/processing/self/cancel`). The plan should note this ordering requirement explicitly.

### 8. The plan says "No new modal" but doesn't address the UX gap for non-admins

Currently, clicking cancel or remove shows a `window.confirm()` dialog. After the change, non-admins won't see the remove button at all (which is fine), and the cancel button is only shown for owned items. But there's no visual indication of *why* an action is missing — the cancel column just appears empty for non-owned rows.

The queue plan addresses this by rendering an empty `<td>` for non-owned rows (explicit empty cell). The processing plan should specify the same: the `<td class="col-icon-cancel">` should always be rendered (even if empty) to keep column alignment, just as `cancelCell()` returns `''` today for non-actionable states.

**Recommendation**: This is already the behavior of `cancelCell()` returning `''`, so no code change is needed. But the plan should note this explicitly for the implementer, similar to the queue plan's explicit empty-cell mention.

### 9. `get_item_user()` return type may cause silent auth bypass

The proposed `get_item_user()` returns `str | None` — `None` if the item isn't found. The endpoint then checks:

```python
if owner is None or owner != user:
    return json.dumps({"success": False, "error": "Not owner"}), 403
```

If `owner is None` (item doesn't exist), the user gets a 403 "Not owner" instead of a 404 "Not found". This leaks no information about item existence (good for security), but it's a misleading error message. More importantly, it means a user can't distinguish "I typed the wrong item ID" from "I don't own this item."

**Recommendation**: Minor — acceptable for a home karaoke system. If desired, return 404 when `owner is None` and 403 only when `owner != user`.

### 10. No i18n for error messages

The plan's server-side error messages (`"Admin only"`, `"Not owner"`) are hardcoded English strings. The project uses `flask_babel` for internationalization (the `_()` function is already imported in `processing.py` as `_= flask_babel.gettext`). The queue plan's error messages also aren't wrapped in `_()`.

**Recommendation**: Wrap error strings in `_()` for consistency with the rest of the codebase:

```python
return json.dumps({"success": False, "error": _("Admin only")}), 403
return json.dumps({"success": False, "error": _("Not owner")}), 403
```

### 11. No `get_site_name` import — plan uses inline pattern

The plan's proposed `processing()` route keeps the existing inline site-title logic:

```python
site_title=getattr(k, "preferences", None) and k.preferences.get("site_name") or "PiKaraoke",
```

Other routes (`queue.py` line 59-65) use `get_site_name()` from `current_app`. The plan doesn't refactor this to match, which is fine (out of scope), but worth noting the inconsistency.

---

## Plan Accuracy (Line Numbers & Code References)

| Plan Reference | Actual | Verdict |
|---|---|---|
| `PipelineItem.__init__` has `user` at line 42 | `self.user: str = user` at line 42 | ✅ Exact match |
| `_item_to_dict` emits `user` at line 294 | `"user": item.user` at line 294 | ✅ Exact match |
| `_find_item` is private, takes `item_id` | `_find_item(self, item_id: str)` at line 276 | ✅ Exact match |
| `self._lock` is threading lock | `self._lock = threading.Lock()` at line 73 | ✅ Exact match |
| No `get_item_user` method exists | Confirmed absent | ✅ Confirmed |
| `request` not imported in processing.py | Confirmed — only `render_template` | ✅ Confirmed |
| `is_admin` not imported | Confirmed — only `get_karaoke_instance` | ✅ Confirmed |
| `json` already imported | `import json` at line 5 | ✅ Confirmed |
| Line 22-28 for `processing()` route | `render_template` spans lines 22-28 | ✅ Accurate |
| Line 39-60 for cancel/remove | Cancel at 39, remove ends at 60 | ✅ Accurate |
| Line 41 for `'use strict'` insertion | IIFE at 39, `'use strict'` at 40, line 41 = `var pollInterval` | ✅ Accurate |
| Line 85 for `cancelCell()` | `function cancelCell(item) {` at line 85 | ✅ Exact match |
| Lines 256-276 for cancel click handler | Handler spans lines 256-276 | ✅ Exact match |
| No auth checks on existing endpoints | Confirmed — zero auth | ✅ Confirmed |
| `getUserCookie()` available from `base.html` | Lines 99-101 in base.html | ✅ Confirmed |
| No `test_processing_routes.py` exists | Confirmed — no test file found | ✅ Confirmed |

All line-number references in the plan are accurate against the current codebase.

---

## Design Consistency with Sibling Plan (`user-queue-controls.md`)

| Aspect | Queue Plan | Processing Plan | Consistent? |
|---|---|---|---|
| User identity model | Cookie string | Cookie string | ✅ |
| Admin gate pattern | `is_admin()` on existing endpoints | `is_admin()` on existing endpoints | ✅ |
| New user endpoints | `/queue/user/delete`, `/queue/user/pause` | `/processing/user/cancel` | ✅ |
| Input validation | Marshmallow `Schema` + `@bp.arguments()` | Raw `request.form.get()` | ⚠️ Different (acknowledged) |
| 403 response format | `json.dumps({"success": False, "error": "Not owner"}), 403` | Same | ✅ |
| `isAdmin` template var | `JSON.parse('{{ admin | tojson }}')` | `{{ admin | tojson }}` | ⚠️ Minor style diff |
| `currentUser` JS var | `getUserCookie()` with `typeof` guard | Same | ✅ |
| Ownership check location | `_verify_ownership()` helper in routes | `get_item_user()` on tracker | ✅ Appropriate (tracker's `_find_item` is private) |

The processing plan explicitly acknowledges the input-validation difference and justifies it by the existing processing route style. This is a reasonable trade-off.

---

## Recommendations Summary

1. **Critical**: Read `user` from `request.cookies.get("user")` server-side instead of `request.form.get("user")` to prevent trivial spoofing.
2. **Critical**: Use `flask.jsonify()` or set `Content-Type: application/json` on all JSON responses (existing pattern issue, but new endpoints should fix it).
3. **Moderate**: Show the full compound condition in `cancelCell()` pseudocode (don't simplify to `processing_status` only).
4. **Moderate**: Add a `.fail()` handler to the cancel AJAX call for 403 feedback.
5. **Moderate**: Register `/processing/user/cancel` **before** `/processing/<item_id>/cancel` to avoid Flask route shadowing.
6. **Minor**: Wrap error strings in `_()` for i18n consistency.
7. **Minor**: Return 404 for nonexistent items vs 403 for wrong owner (optional).
