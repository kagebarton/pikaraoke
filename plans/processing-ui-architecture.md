Model: Claude Opus 4.7

# Processing UI: bug findings, fixes applied, and architectural suggestions

## Context

After implementing `plans/user-processing-controls.md` (commits `12e4747`,
`1f59d00`, `6c42e21`), several intermittent bugs surfaced on the processing
page:

1. Cancel actions sometimes did not fade — the row would either disappear
   instantly or stick around without animation.
2. Cancels during stem separation disappeared immediately rather than
   showing a "cancelling" state until separation completed.
3. Various scenarios where users or admins had no cancel option for songs
   that were clearly in progress.

This document records the root-cause analysis, the patches applied to
[processing.html](pikaraoke/templates/processing.html), and a longer-term
architectural direction that would eliminate the class of bug rather than
papering over individual instances.

## Root causes

### Bug A — `cancelCell()` branch order (deterministic, hits during separation)

Location: [processing.html:88-116](pikaraoke/templates/processing.html#L88-L116)

The plan reordered the original branches: **remove first, cancel second**,
but kept the broad `||` condition on the remove branch. That broad condition
was originally safe because it ran *second* as a fallthrough. Run first, it
hijacks rows where one status is terminal but the other is still in flight:

| download_status | processing_status | new code rendered | should be |
|-----------------|-------------------|-------------------|-----------|
| complete        | pending           | remove (admin) / nothing (user) | **cancel** |
| complete        | active            | remove (admin) / nothing (user) | **cancel** |

Consequences (this single bug explains all three reported symptoms):

- **Non-admin owners lose the cancel button** the moment download finishes
  and the song enters the processing queue. Their row is theirs, but no
  button shows.
- **Admins see the wrong button** — `Remove` (trash icon) instead of
  `Cancel` — during separation.
- If the admin clicks that misleading remove button mid-separation,
  [`pipeline_tracker.remove()`](pikaraoke/lib/pipeline_tracker.py#L220-L230)
  yanks the item out of `_items` and deletes the song file *without*
  calling `cancel_active()`. The orchestrator keeps separating in the
  background, the file vanishes mid-stream, and the row disappears
  instantly — explaining "cancels during separation disappearing
  immediately".

### Bug B — race between cancel-AJAX and the 1s poll (intermittent, all roles)

Location: [processing.html:269-300](pikaraoke/templates/processing.html#L269-L300)

The fade only ran inside the cancel `done()` callback. While the AJAX was
in flight, the 1s poll could fire, fetch a payload that no longer contained
the item (the server had already removed it), and `renderItems()` would
remove the row directly because it had no `is-fading` class yet. When
`done()` finally fired, `$row` was detached and `fadeAndRemove` was a
no-op.

This is what made the bug intermittent — it depended on whether the cancel
AJAX returned before or after the next poll cycle.

### Bug C — admin cancel during separation: no fade when orchestrator finishes

The cancel-during-active-processing flow correctly leaves the row in
`cancelling` state. When `_on_processing_cancelled` finally fires
server-side and the item is removed from `_items`, the next poll has no
record of it and `renderItems()` removes the row instantly. There was no
mechanism to fade an item that the *server* removed asynchronously —
`fadeAndRemove` was only ever called from click handlers.

## Fixes applied

All three fixes are in [processing.html](pikaraoke/templates/processing.html):

1. **`cancelCell` ordering restored** to cancel-branch-first,
   remove-branch-fallthrough. Ownership/admin gating is layered on top of
   each branch.
2. **Click handler marks the row `is-fading` immediately** for the
   non-active cases. The existing poll-side guards
   (`!hasClass('is-fading')` checks in `renderItems`) then keep the row
   alive until `done()` runs the actual `fadeOut`. `fail()` removes the
   class so a failed cancel doesn't leave the row stuck.
3. **`renderItems` fades disappearing rows that were in `cancelling`
   state** instead of removing them instantly, giving admin/user
   cancel-during-separation the same fade UX as a synchronous cancel.

All 14 backend tests in `tests/unit/test_processing_routes.py` still
pass; the bugs were JS-side only.

## Why these are patches, not a real fix

Each bug traces to the same architectural seam: **the client re-derives
state and authorization that the server already knows, and a 1s poll
races with user-initiated actions**. The `is-fading` class is being used
as a poll-blocker lock, the cancel-vs-remove distinction is reconstructed
client-side from `download_status × processing_status × isAdmin ×
isOwner` (10+ cell states × 4 actor types), and the polling cadence
creates timing-dependent UX.

## Suggested architectural improvements

These would collapse the class of bug rather than fix individual
instances. Listed in priority order.

### 1. Server returns the allowed actions per item

Instead of the client computing "which button to show," include the
allowed actions directly in the status payload:

```python
# in PipelineTracker._item_to_dict, with request context (user cookie + admin) available
"actions": ["cancel"]    # or ["enqueue", "remove"], or [], etc.
```

The template becomes a trivial map of `action → button`. Auth lives in
one place (the server). New states or new roles don't require ordering
puzzles. This is the single highest-leverage change — it's what would
have prevented Bug A entirely.

### 2. Push updates over the existing Socket.IO instead of polling

`window.socket` is already wired in [base.html](pikaraoke/templates/base.html).
Add `pipeline_updated` (or per-item: `item_changed`, `item_removed`)
emissions inside the same tracker methods that already mutate `_items`.
The client subscribes and re-renders on each push.

Benefits:
- No race between cancel-AJAX and the next poll → no need for the
  `is-fading` poll-lock hack.
- Updates are instant, not 1s-laggy.
- The async cancel-during-separation flow stops being special: when the
  orchestrator emits `processing_cancelled`, the tracker pushes
  `item_removed`, and the client just fades. No
  `data-proc-status === 'cancelling'` heuristic needed.

A small periodic "full snapshot" push (every 5–10s) covers reconnect /
missed-event drift without the 1s action-race window.

### 3. Make `remove()` imply `cancel()` when the item isn't terminal

[`pipeline_tracker.remove()`](pikaraoke/lib/pipeline_tracker.py#L220-L230)
will silently orphan a separation if called on an active item. The
UI fix (1) prevents the button from being exposed in that state, but the
server should be safe regardless of UI bugs.

Either route `remove()` through `cancel()` first when the state isn't
terminal, or collapse both into a single server-side `dismiss(item_id)`
that does the right thing. Smaller change than (1) or (2), worth doing
regardless.

## Tradeoffs

(1) and (2) are real refactors — probably ~half a day each, plus tests.
They eliminate a class of bug rather than patching individual ones, but
the current poll-based code does *work* now after the patches.

(3) is small and contained.

## Relationship to `processing-pipeline-port.md`

The processing-pipeline port is orthogonal — it touches
`pikaraoke/pipeline/`, `processing_manager.py`, and the DB layer. Its
plan explicitly says the routes / tracker / template don't change. None
of the files in this document overlap with the port plan.

The new pipeline does have **5 stages instead of 3**, and the slowest
(`lyric_align`) is even more cancel-prone than current stem separation.
That makes the architectural fix more valuable after the port, not less.

Recommended ordering: **port first, architecture after**. The port has
enough novelty (new deps, DB migration, model files moved, lazy Whisper
load) that mixing UI/auth refactors into the same PR would balloon the
review surface and make any regression harder to bisect. The current
`is-fading` patches will hold up through the port — the tracker
contract doesn't change.

After the port, the architecture pass also gets the natural opportunity
to surface per-stage progress in the tracker payload (e.g., `stage:
"lyric_align"`), which the current 3-bucket processing_status can't
express cleanly.

## Out of scope for this document

- Implementation of the suggested architecture (separate plan).
- Per-stage progress reporting in the tracker payload.
- Editing pipeline item metadata (title, URL) after submission.
- Reassigning ownership mid-pipeline.
