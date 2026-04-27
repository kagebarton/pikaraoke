# Processing UI Port (mockup v2 → live page)

Model: Claude Opus 4.7

## Overview

Port [processing_mockup_v2.html](../processing_mockup_v2.html) into [pikaraoke/templates/processing.html](../pikaraoke/templates/processing.html). The new UI:

- Switches from a 2-column table to a 5-column layout (title, download icon, separation icon, queue action, cancel/remove action).
- Replaces the pulse-color animation with a CSS-generated rotating spinner for `active` and `cancelling` states.
- Replaces the inline download percentage with a small text label ("downloading" / "separating" / "cancelling").
- Adopts a mostly-grey icon palette; only the cancelling spinner and action buttons (queue = success/green, cancel/remove = danger/red) carry color. Queue stays green to match the existing project convention for "add to queue" actions ([files.html:130](../pikaraoke/templates/files.html#L130), [queue.html:503-504](../pikaraoke/templates/queue.html#L503-L504)) — the mockup's primary/blue is overridden here.
- Adds a `window.confirm()` dialog before cancel and remove, matching the pattern in [spa-navigation.js:147-155](../pikaraoke/static/spa-navigation.js#L147-L155).

Backend contract is unchanged. `PipelineTracker.get_status()` already returns every field the new UI needs; `download_progress` just stops being rendered.

## Files to change

- [pikaraoke/templates/processing.html](../pikaraoke/templates/processing.html) — full rewrite of markup, styles, and render JS.

No Python/backend edits. No new static assets (fontello already has every icon the mockup uses: `icon-down-big`, `icon-music`, `icon-clock`, `icon-ok`, `icon-cancel-circled-1`, `icon-list-add`, `icon-trash-empty`).

## Plan

### 1. Replace the table markup

Swap the 2-column `<table>` for the 5-column version from [processing_mockup_v2.html:214-230](../processing_mockup_v2.html#L214-L230). Keep Jinja wrappers:

- `{% extends 'base.html' %}`, `{% block header %}`, `{% block content %}`, `{% block scripts %}`.
- `{% trans %}` around every user-facing string (Title, Download, Separation, pending, active, complete, cancelling, error, "No songs in the processing pipeline.").
- Drop the static/dynamic section headers and the simulator controls — those are mockup-only scaffolding.

### 2. Port the styles

Move the mockup's `<style>` block into the existing `{% block scripts %}` `<style>` section (current file already keeps styles there). Bring over:

- The `:root` CSS variable block (icon sizes, colors, spinner config).
- `.col-icon-*` fixed-width columns.
- `.state-box` flex wrapper + `.spinner-css` / `.spinner-css.cancelling` rotating spinner with the `@keyframes spin` rule.
- `.title-row` flexbox + `.progress-label` / `.progress-label.cancelling`.
- Fontello-inside-state-box sizing rules.
- Icon color classes (`.icon-state-ok`, `.icon-action-queue`, etc.).

**Define the `--bulma-*` vars explicitly.** The mockup references `var(--bulma-grey)`, `var(--bulma-danger)`, `var(--bulma-success)`, etc. Bulma 1.0 defines these as CSS custom properties, but this project uses Bulma 0.9.x (`bulma.min.css` + `bulma-dark.css`), which does not. Without an explicit definition, these resolve to nothing and colors break. Add concrete values to `:root` matching the project theme:

```css
:root {
    --bulma-grey: #b5b5b5;
    --bulma-grey-dark: #4a4a4a;
    --bulma-danger: #f14668;
    --bulma-success: #48c774;
    /* ...plus any other --bulma-* vars the mockup uses */
}
```

Audit the mockup's `:root` for every `--bulma-*` reference and give each a hardcoded value.

Drop from the mockup:

- `tr:nth-child(even)` rule — `is-striped` on the `<table>` already handles this.
- `.section-header` and `.controls` rules — scaffolding.
- `html[data-theme="dark"]` on the `<html>` tag — base.html handles theming.

Delete the old `.step-pending` / `.step-active` / `.step-complete` / `.step-error` / `.step-cancelling` rules and the `pulse-teal` / `pulse-amber` keyframes — unused after the swap.

### 3. Rewrite the render JS

Replace the current `renderRow` / `stepClass` / `actionButton` trio with the mockup's `renderRow` / `stateIcon` / `queueCell` / `cancelCell` / `progressLabel`. Adjustments while porting:

- Keep `fetchStatus()` / `pollInterval` / `pollTimer` / socket listeners from the current file — those talk to the real backend.
- Route action clicks through the existing `cancelItem` / `enqueueItem` / `removeItem` AJAX helpers (they already use `url_for`). Drop `addDynamicItem`, `startDownloadSimulation`, `startProcessingSimulation`, and all `#btn-*` handlers (simulator-only). Keep a trimmed `removeRow($row)` helper that runs `fadeOut()` on success — see the optimistic-UI note below.
- Drop the unused `escape()` helper (`function escape(str) { return encodeURIComponent(str); }` at [processing.html:46-48](../pikaraoke/templates/processing.html#L46-L48)) — it is never called. Keep `escapeHtml()`.
- Wrap `cancelItem` / `removeItem` calls in `window.confirm()` (the mockup pattern at [processing_mockup_v2.html:609-633](../processing_mockup_v2.html#L609-L633)). Use `{% trans %}` for the prompt strings — see step 7 for the interpolation pattern.
- Wrap `progressLabel()` output strings in `{% trans %}` (downloading / separating / cancelling). `{% trans %}` works inside `<script>` blocks because Jinja processes the template server-side before the browser ever sees it — the existing template already uses this pattern at [processing.html:127,131,136](../pikaraoke/templates/processing.html#L127).
- `stateIcon()` handles `pending | active | complete | error | cancelling`. The tracker can also emit `waiting` (see [pipeline_tracker.py:118](../pikaraoke/lib/pipeline_tracker.py#L118)) — treat it as `pending` (clock icon) so it falls through cleanly. Add `if (status === 'waiting') return '<span class="state-box"><i class="icon icon-clock"></i></span>';` or collapse `waiting` into the `pending` branch.
- `cancelCell()` also needs to tolerate `waiting`. In practice it works because `cancelCell()` checks `download_status` first (`active`/`pending`), and `waiting` only appears on `processing_status` while download is still in flight — but add an explicit comment noting the implicit dependency so a later refactor doesn't silently break it.
- Keep the `item.error_message` rendering under the title (mockup already does this at [processing_mockup_v2.html:420-423](../processing_mockup_v2.html#L420-L423)). **Also render it when `processing_status === 'error'`** — the current file only checks `download_status === 'error'`, so separation failures (where `download_status === 'complete'` but `processing_status === 'error'`) silently drop the error message. Use: `if (item.error_message && (item.download_status === 'error' || item.processing_status === 'error'))`.

### 4. Keyed row updates (avoid spinner jitter)

`renderItems()` currently replaces the entire `#pipeline-body` innerHTML every poll. With a CSS-animated spinner that re-starts on DOM replacement, this causes visible jitter every second. Swap the strategy to compare status via data attributes on the `<tr>`:

```js
function renderItems(items) {
    var seen = {};
    var $body = $('#pipeline-body');
    items.forEach(function(item) {
        seen[item.id] = true;
        var $existing = $body.find('tr[data-id="' + item.id + '"]');
        var currKey = item.download_status + '|' + item.processing_status
                    + '|' + (item.song_path || '') + '|' + (item.error_message || '');
        if ($existing.length === 0) {
            $body.append(renderRow(item));
        } else if ($existing.attr('data-state-key') !== currKey) {
            $existing.replaceWith(renderRow(item));
        }
    });
    // Remove rows whose items are gone from the payload.
    $body.find('tr').each(function() {
        var id = $(this).attr('data-id');
        if (id && !seen[id]) $(this).remove();
    });

    if (items.length === 0) { /* show empty / hide table */ }
    else { /* hide empty / show table */ }
}
```

`renderRow()` must set `data-state-key` on the `<tr>` with the same concatenation so the comparison is apples-to-apples. Comparing data attributes (not `outerHTML`) avoids browser serialization differences (attribute ordering, entity encoding) that would cause every poll to look "changed" and defeat the spinner-preservation goal. Include any field that changes the rendered row in the key — currently: `download_status`, `processing_status`, `song_path`, `error_message`. `download_progress` is no longer rendered, so it's deliberately excluded.

### 5. Optimistic-UI fade on action clicks

The server drives real removal via the next poll, but waiting up to 1s to see the row disappear feels sluggish. On success of `enqueueItem` / `removeItem`, fade the row locally:

```js
function fadeAndRemove($row) {
    $row.fadeOut(1000, function() { $(this).remove(); });
}

// inside enqueueItem / removeItem .done() handlers:
fadeAndRemove($row);
fetchStatus();
```

**Do not blanket-fade on `cancelItem`.** The tracker's `cancel()` has two paths (see [pipeline_tracker.py:133-176](../pikaraoke/lib/pipeline_tracker.py#L133-L176)):

- **Download active/pending** → item is immediately removed from the tracker. Fade is safe.
- **Separation active** → item stays in the tracker with `cancelling = True`, waiting for the worker to finish. A blanket fade here would hide the row, then the next poll would re-render it with the cancelling spinner — creating a "disappear-then-reappear" glitch worse than no fade at all.

Branch the fade on the row's pre-click processing state:

```js
$(document).on('click', '.pipeline-cancel-btn', function(e) {
    e.preventDefault();
    var id = $(this).data('id');
    var $row = $('tr[data-id="' + id + '"]');
    var title = $row.find('.is-truncated').text();
    var msg = "{% trans %}Are you sure you want to cancel \"SONG_TITLE\"?{% endtrans %}".replace('SONG_TITLE', title);
    if (!window.confirm(msg)) return;

    var procStatus = $row.attr('data-proc-status');
    $.ajax({
        url: '{{ url_for("processing.cancel_item", item_id="ITEM_ID") }}'.replace('ITEM_ID', id),
        type: 'POST'
    }).done(function() {
        // Only fade when the tracker removed the item synchronously.
        // When separation is active, cancelling is async — let the poll
        // update the row to show the cancelling spinner instead.
        if (procStatus !== 'active') {
            fadeAndRemove($row);
        }
        fetchStatus();
    });
});
```

Add `data-proc-status` to the `<tr>` in `renderRow()` so this check has something to read.

### 6. Accessibility: aria-labels on icon-only buttons

Cancel/remove/queue buttons render as bare icons. Add `aria-label` alongside the existing `title` attribute so screen readers announce the action. Use the same translated string (via `{% trans %}`) as `title`.

### 7. Confirmation prompts

Model after [spa-navigation.js:147-155](../pikaraoke/static/spa-navigation.js#L147-L155): use `window.confirm()`, `{% trans %}` the prompt string, and only fire the AJAX call on confirm. Two prompts needed:

- Cancel: `Are you sure you want to cancel "{title}"?`
- Remove: `Are you sure you want to remove "{title}"?`

**Interpolation pattern.** `{% trans %}` runs at template-render time and cannot see the JS runtime `title` variable. Use a placeholder token inside the translated string, then `.replace()` at click time:

```js
var title = $row.find('.is-truncated').text();
var msg = "{% trans %}Are you sure you want to cancel \"SONG_TITLE\"?{% endtrans %}".replace('SONG_TITLE', title);
if (!window.confirm(msg)) return;
```

Translators see `SONG_TITLE` as a literal placeholder in the string and are expected to preserve it. This keeps the string under `{% trans %}` for i18n tooling while allowing runtime interpolation.

### 8. Remove the download progress percentage

The current file renders `Math.round(item.download_progress) + '%'` next to the download icon ([processing.html:82-84](../pikaraoke/templates/processing.html#L82-L84)). The new UI replaces this with the `progressLabel()` text ("downloading"). Drop the percentage entirely; `download_progress` stays on the backend payload but goes unused on the frontend.

## Out of scope

- The A1 stage-based pipeline refactor (tracked separately in [pipeline-robustness-fixes.md](pipeline-robustness-fixes.md)).
- The B1–B6 / R1–R5 fixes. B5 (errored-download icon) overlaps with this UI but is better handled backend-side after the port lands — the current port just has to not regress the existing behavior.
- Socket-driven refresh (A3). Keep 1s polling.

## Test plan

- [ ] Visit `/processing` with an empty pipeline → "No songs in the processing pipeline." message shows, table hidden.
- [ ] Start a download → row appears, download icon shows spinner, "downloading" label visible, separation icon shows clock, cancel icon (red X) shows in the cancel column.
- [ ] Click cancel during download → confirm dialog appears; after OK, row transitions to cancelling spinner (red), then disappears on next poll.
- [ ] Let a download finish → download icon becomes grey check, separation icon shows spinner with "separating" label.
- [ ] Click cancel during separation → confirm dialog; row shows cancelling spinner (red) on separation column, then disappears after backend completes the in-flight separation.
- [ ] Let full pipeline finish → both icons grey check, queue (+) button appears in queue column, remove (trash) in cancel column.
- [ ] Click queue → item is enqueued and row disappears on next poll (no confirmation).
- [ ] Click remove on a completed item → confirm dialog; row disappears.
- [ ] Trigger a download error (e.g. private/removed video) → download icon shows grey X, error message under the title, remove (trash) button in cancel column.
- [ ] Zebra striping renders (Bulma `is-striped`).
- [ ] Light/dark theme both look correct — icon greys and the spinner border remain visible on both backgrounds.
- [ ] i18n: switch to a non-English locale and confirm Title / Download / Separation / legend / labels / confirm prompts all translate.
- [ ] Spinner does not visibly jitter/restart on each 1s poll (keyed row updates preserve unchanged rows).
- [ ] Cancelling, queueing, or removing a row fades it out over 1s (optimistic UI) rather than waiting for the next poll.
- [ ] Screen reader announces "Cancel" / "Queue" / "Remove" on the icon buttons (aria-label present).
