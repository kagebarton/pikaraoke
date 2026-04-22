# Processing UI Port — Plan Review Findings

Reviewer: Kilo (z-ai/glm-5.1)
Date: 2026-04-22
Target plan: [`processing-ui-port.md`](processing-ui-port.md)

---

## Critical Issues

### C1. Red checkmark on completed download during cancellation is misleading

The mockup's `stateIcon(status, isCancellingContext)` applies `icon-state-cancelling` (red/danger color) to the `complete` checkmark when `isCancellingContext` is true. This happens when a user cancels during separation: the download already completed successfully, so the download column shows `stateIcon("complete", true)` → a red checkmark.

A red checkmark is semantically wrong — the download succeeded. The cancelling spinner on the separation column already communicates the cancellation state. Showing the download checkmark in red misleads the user into thinking the download failed.

**Fix**: Drop `isCancellingContext` from the `complete` branch. Always render the grey check for `complete`, regardless of cancellation state. The cancelling spinner on the other column carries the signal.

```js
// Before (mockup)
else if (status === 'complete')
  inner = '<i class="icon icon-ok ' + (isCancellingContext ? 'icon-state-cancelling' : 'icon-state-ok') + '"></i>';

// After
else if (status === 'complete')
  inner = '<i class="icon icon-ok icon-state-ok"></i>';
```

This also simplifies the `stateIcon` signature — remove the `isCancellingContext` parameter entirely, and remove the `isCancellingContext` computation from `renderRow`.

---

## Moderate Issues

### M1. `{% trans %}` cannot wrap JS runtime string literals

Plan step 3 says: *"Wrap `progressLabel()` output strings in `{% trans %}` (downloading / separating / cancelling)."* And step 7 says: *"Use `{% trans %}` for the prompt strings."*

Jinja's `{% trans %}` is a **template-time** directive — it executes during HTML rendering on the server. It cannot wrap JavaScript runtime string literals. `progressLabel()` is a JS function that returns strings like `'downloading'` at runtime in the browser — `{% trans %}` has no way to reach into it.

The same problem applies to confirmation prompts like `"Are you sure you want to cancel "{title}"?"` — the title is a JS runtime variable, not a Jinja template variable.

**Fix**: Inject translated strings into JS at template-render time, matching the existing `window.i18n` pattern in [`base.html:22-27`](../pikaraoke/templates/base.html#L22-L27) and the `.replace()` interpolation pattern in [`spa-navigation.js:138-140`](../pikaraoke/static/spa-navigation.js#L138-L140):

```html
<script>
var i18n = {
  downloading: "{% trans %}downloading{% endtrans %}",
  separating: "{% trans %}separating{% endtrans %}",
  cancelling: "{% trans %}cancelling{% endtrans %}",
  confirmCancel: "{{ _('Are you sure you want to cancel \"SONG_TITLE\"?') }}",
  confirmRemove: "{{ _('Are you sure you want to remove \"SONG_TITLE\"?') }}"
};
</script>
```

Then in JS:

```js
function progressLabel(item) {
  if (item.download_status === 'cancelling' || item.processing_status === 'cancelling')
    return i18n.cancelling;
  if (item.download_status === 'active')
    return i18n.downloading;
  if (item.processing_status === 'active')
    return i18n.separating;
  return '';
}

// In the cancel handler:
var msg = i18n.confirmCancel.replace('SONG_TITLE', title);
if (!window.confirm(msg)) return;
```

### M2. `outerHTML` comparison for keyed row updates is fragile

Plan step 4 proposes:

```js
if ($existing.prop('outerHTML') !== nextHtml) {
  $existing.replaceWith(nextHtml);
}
```

This has two problems:

1. **Browser-normalized HTML**: `prop('outerHTML')` returns the browser's DOM serialization, which may differ from the generated string in attribute order, self-closing tag style, whitespace, and entity encoding. Chrome and Firefox serialize attributes in different orders. Two strings that produce identical DOM can have different `outerHTML`.
2. **Entity encoding**: If `item.id` contains characters that get entity-encoded differently by the browser vs. the template string, the comparison fails every poll and the row is replaced on every cycle — defeating the spinner-preservation goal entirely.

**Fix**: Compare only the data that matters (the status fields) via data attributes, and only re-render when status actually changes:

```js
var $existing = $body.find('tr[data-id="' + item.id + '"]');
var prevKey = $existing.attr('data-dl-status') + '|' + $existing.attr('data-proc-status')
             + '|' + $existing.attr('data-song-path');
var currKey = item.download_status + '|' + item.processing_status
             + '|' + (item.song_path || '');

if ($existing.length === 0) {
  $body.append(nextHtml);
} else if (prevKey !== currKey) {
  $existing.replaceWith(nextHtml);
}
```

Add `data-dl-status`, `data-proc-status`, and `data-song-path` attributes to the `<tr>` in `renderRow()`. This is robust, fast, and avoids DOM serialization entirely.

### M3. Optimistic-UI fade on `cancelItem` creates a visual glitch

Plan step 5 says to call `fadeAndRemove($row)` on success of all three actions, then `fetchStatus()`. For `cancelItem` during separation (the only case that sets `cancelling = True`), the backend returns `{success: true}` but the item **remains** in the tracker with `cancelling = True` until the separation worker finishes (pipeline_tracker.py:161-168). The sequence:

1. User clicks cancel → confirm → `cancelItem()` fires
2. Backend returns `{success: true}` → `fadeAndRemove($row)` → row fades out
3. `fetchStatus()` fires → backend still has the item with `processing_status: "cancelling"` → keyed-update logic **re-appends** the row with the cancelling spinner

The row disappears then immediately reappears. This is worse than no fade at all.

**Fix**: Only apply `fadeAndRemove` for `enqueueItem` and `removeItem` (where the item is immediately removed from the tracker). For `cancelItem`, skip the fade and just call `fetchStatus()` — the poll will update the row to show the cancelling state. Or, more granularly: fade only when `download_status` is `"active"` or `"pending"` (where `cancel()` immediately removes the item from the tracker per pipeline_tracker.py:149-156), but not when `processing_status` is `"active"` (where `cancel()` sets `cancelling = True` and keeps the item).

```js
$(document).on('click', '.pipeline-cancel-btn', function(e) {
  e.preventDefault();
  var id = $(this).data('id');
  var $row = $('tr[data-id="' + id + '"]');
  var title = $row.find('.is-truncated').text();
  var msg = i18n.confirmCancel.replace('SONG_TITLE', title);
  if (!window.confirm(msg)) return;

  cancelItem(id, function(success) {
    if (!success) return;
    // Only fade if the item is immediately removed (download cancel).
    // If separation was active, the item stays in cancelling state —
    // the next poll will update the row.
    var procStatus = $row.attr('data-proc-status');
    if (procStatus !== 'active') {
      fadeAndRemove($row);
    }
    fetchStatus();
  });
});
```

### M4. `--bulma-grey` / `--bulma-danger` CSS custom properties are undefined

The mockup's `:root` block references CSS variables like `var(--bulma-grey)` and `var(--bulma-danger)`. The project uses Bulma 0.9.x (loaded as `bulma.min.css` + `bulma-dark.css`), which **does not** define `--bulma-*` custom properties — those are a Bulma 1.0 feature. These references will resolve to nothing (empty/initial value), causing all spinner borders, icon colors, and text colors to fall back to defaults or appear broken.

**Fix**: Define these variables explicitly in the `:root` block with values that match the project's Bulma theme:

```css
:root {
  --bulma-grey: #b5b5b5;
  --bulma-danger: #f14668;
  --bulma-success: #48c774;
  /* ...etc for any other --bulma-* vars used */
}
```

Or, alternatively, replace all `var(--bulma-*)` references with the hardcoded color values directly. The hardcoded approach is simpler but less maintainable if the project ever upgrades to Bulma 1.0.

---

## Minor Issues

### m1. `error_message` only rendered for `download_status === 'error'` — misses processing errors

Both the current file and the mockup only show `error_message` when `download_status === 'error'`:

```js
if (item.error_message && item.download_status === 'error') {
```

But the backend can set `processing_status = "error"` independently (e.g. separation failure), and `error_message` is serialized in `_item_to_dict()` regardless of which stage failed. If a separation error occurs, `download_status` is `"complete"` and `processing_status` is `"error"`, but the error message won't render.

**Fix**: Also render `error_message` when `processing_status === 'error'`:

```js
if (item.error_message && (item.download_status === 'error' || item.processing_status === 'error')) {
```

### m2. Unused `escape()` function in the current file should be dropped

The current `processing.html` has `function escape(str) { return encodeURIComponent(str); }` which is never called. The rewrite should simply drop it rather than port it.

### m3. `waiting` status should be documented as explicitly handled in `cancelCell()` — not just `stateIcon()`

The plan's step 3 only mentions handling `waiting` in `stateIcon()`. It doesn't mention `cancelCell()`. In practice, `cancelCell()` works correctly by accident: it checks `download_status` first (`active` or `pending`), and `waiting` only appears on `processing_status` while the download is still in progress. But this is a fragile implicit dependency — if someone later refactors `cancelCell()` to check `processing_status` first, the `waiting` state would silently break.

**Fix**: Add an explicit `waiting` branch or comment in `cancelCell()`, and document in the plan that `waiting` on `processing_status` is expected alongside `download_status: "pending" | "active"`.

### m4. Zebra stripe flash on row removal (pre-existing)

When a row is faded out and removed, the remaining rows shift their `:nth-child` parity, causing a brief visual flash as stripes invert. This is a pre-existing issue (base.html line 173-175 defines global `tr:nth-child(even)` striping), not introduced by the plan. The `fadeAndRemove()` animation makes it more noticeable though. No action required, but worth noting.

---

## Summary

| ID | Severity | Issue | Recommended fix |
|----|----------|-------|-----------------|
| C1 | Critical | Red checkmark on completed download during cancellation | Drop `isCancellingContext` from `complete` branch in `stateIcon()` |
| M1 | Moderate | `{% trans %}` can't wrap JS runtime strings | Use `window.i18n` injection + `.replace()` for interpolation |
| M2 | Moderate | `outerHTML` comparison is fragile across browsers | Compare data-attribute keys instead of serialized HTML |
| M3 | Moderate | Optimistic fade on cancel re-shows the cancelled row | Only fade for enqueue/remove; skip fade for separation-cancel |
| M4 | Moderate | `--bulma-*` CSS vars undefined in Bulma 0.9.x | Define explicitly in `:root` or use hardcoded values |
| m1 | Minor | `error_message` not shown for processing errors | Also render when `processing_status === 'error'` |
| m2 | Minor | Unused `escape()` function | Drop in rewrite |
| m3 | Minor | `waiting` not explicitly handled in `cancelCell()` | Add explicit branch or comment |
| m4 | Minor | Zebra stripe flash on row removal | Pre-existing; no action needed |
