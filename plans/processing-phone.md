# Processing page for phones

Model: Claude Opus 5.5 (decisions). Executor not yet named.

Branch `processing_phone` off `dev` at `764df44`, worktree `.claude/worktrees/processing_phone`.
Sibling of `browse_phone` and `queue_phone` (`plans/browse-phone.md`, `plans/queue-phone.md` on
those branches). Queue lands first and creates the shared row style; Processing reuses it
(`queue-phone.md`, decision 1).

Mockup (private to Ken): https://claude.ai/artifact/Mn2PoVbRJd5BKmPSXBZx11. Top row "Today" is the
page as built on `dev` (`templates/processing.html`); bottom row "After" is draft 1, each screen
under its Today twin (admin Jobs, admin with a row opened, admin Library tools, guest). Where this
file and the mockup differ, this file wins.

## Decided (Ken, 2026-11-17)

1. **The filter chips stay**: All, Active, Attention, Finished, each with its count, as today.
   Draft 1 had replaced them with section headings; Ken restored them.
2. **Chips are drawn as the Browse v2 letter pills**: 44 px tall, fully rounded, grey, the picked
   one blue (`#375a7f`). Sized to fit one row on a phone (14 px bold, 8 px side padding, 4 px gaps,
   each chip stretching to share the row), but **allowed to wrap** to a second row rather than
   squeeze or clip.

## Phone pages: one look (Ken, 2026-11-18)

From the style review across the seven phone-page branches (`plans/open-issues.md` on `dev`,
"Phone pages: one look"; numbers are that list's, prefixed L). Visual reference: the canvas
https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL (private to Ken), boards "Processing: Jobs",
"Processing: a failed job opened", "Processing: Library tools" and "Reference palette". Since
2026-11-26 its three Processing boards are draft 2: they draw the 2026-11-26 rulings below, and
whatever is still under "Drafted, not yet ruled". It wins over this branch's mockup; this file
wins over both.

- **L10. Buttons are neutral grey.** Retry, Preview and Check playlist are a row's main action:
  filled grey with a `#5e6d6f` border and bold white text (L4), the fill `#434d4e` (L15). Song
  info and Repair are a grey outline. Red outline stays for delete. Info blue `#3298dc` stays
  only for the running job's spinner and step bar.
- **L14. Processing is the admin's only.** Its nav icon is hidden from guests (the page still
  opens by its address), and nothing a guest sees links here. This branch's guest view is
  dropped. A guest's own failed song shows on Queue instead, as a red "failed" row with Dismiss.
  The failed row and the nav change are both `queue_phone`'s.
- L1 (one green, one amber), L15 and L16 (disabled: no fill, a faded border, a `#8c9b9d` label,
  no opacity fade; the canvas draws a disabled Check playlist so) land in `bulma-dark.css` on
  `singer_defaults`, its Phase 5. This branch takes them from `dev` once that lands.

## Decided (Ken, 2026-11-26)

These answer the draft 1 open questions (group order, headings, the step strip) and rule on its
rows. Canvas boards "Processing: Jobs" and "Processing: a failed job opened" draw them.

3. **Order under All: Attention, then Active, then Finished.** The running job's Now card sits
   above the list, under the pinned area.
4. **One flat list, no group headings.** The chips do the sorting.
5. **Pinned while the page scrolls: the Jobs / Library tools toggle and the filter chips**, as
   Browse pins its toggle and letter row (`.bp-pin` in `files.html`: sticky, top 0). The
   "Processing" heading scrolls away. On Library tools only the toggle is pinned. The running
   job's card is not pinned (too tall on a phone), nor is "Clear N finished" (it already ends the
   list, under the finished rows it clears).
6. **The running job shows three steps: Download, Vocals, Lyrics.** Vocals covers extract,
   loudnorm, stem_separation and transcode. Lyrics covers align, transcribe and dereverb. In one
   Windows run (`D:\Shared\whisper_regen\win\w0_run.log`) extract took about 2 s, loudnorm 14 s,
   stem separation 68 s and transcode 21 s, so steps of their own would only flicker. The large
   line still names the exact phase. A regen that skips download and separation shows those
   two steps already ticked. `dereverb` has no label in `T.phases` today (it falls back to
   "processing"): give it one.
7. **No Queue button on finished rows, and no Add to queue in the opened row.** Today Add to
   queue is offered on every finished download (`pipeline_tracker.py`, `actions.append("enqueue")`),
   even when the song already holds its queue slot from the download dialog, so a tap queues it
   twice. Songs downloaded without queueing are queued from Browse or Search. The enqueue
   action, its route and their tests go.
8. **A narrow strip replaces the 60 px slot on every row**, active ones and the Now card included.
   This is Processing's exception to the shared rule that every page uses a 60 px slot, solid for
   a tap and dashed for a state (`plans/queue-phone.md` S1-S4, on tag `archive/queue_phone`).
   Processing is admin-only, so the shared look matters less here, and the strip gives the song
   name the width. The strip is 6 px wide, full row height. Its colours: red failed or
   cancelling, amber needs a pick or unfinished, grey downloading or waiting, green done, info
   blue the running job. A colour on every row, not only on rows that need the host (ratified
   2026-11-26). The state is always in words on the row too, so colour is never the only sign.
9. **Pick lyrics moves into the opened row.** Rows open from a tap anywhere on them, as well as
   from the chevron (which still expands the row, per S1-S4).
10. **Three lines per row, grouped by what each line answers:**
    - the song, 17 px bold;
    - the artist, who or what started it (a guest's name, playlist, update, regenerate), and
      when: 13 px grey;
    - what happened, then what to do: 15 px. Bold red or amber when the row needs the host
      ("Processing failed: retry or delete", "Download failed: retry or delete", "No usable
      caption: pick lyrics", "Didn't finish: reprocess or delete"), plain light grey otherwise
      ("Downloading", "2nd in line", "Cancelling", "Done · Genius"). A finished row's lyric source
      sits here, with any guessed-lines warning in amber beside it.
    The action words are text, not buttons: they name what the opened row offers. The failure
    line says only "Download failed" or "Processing failed": the row has nothing shorter than
    the raw `error_message`, which shows in full when the row opens. "No usable caption" is
    always true of a pick row (`_on_needs_pick`). Draft 1's "caption too sparse" is not something
    the server reports, and is dropped.
11. **Sizes:** the action line at 15 px (above), the step names under the bar at 13 px, the
    opened row's error text at 13 px. The song name and the artist line keep the shared 17 / 13 px.

Checked: a failed download shows as Failed. `_on_download_error` sets `processing_status` to
`error` as well as `download_status`, and `statusOf()` reads that.

## Drafted, not yet ruled

Draft 2 still shows these from draft 1; Ken has not accepted or rejected them.

- The Now card: the song in Queue v2's card with its strip, a spinner beside a large line saying
  what it is doing and for how long, and the step bar under it.
- The opened row: the error in a dark box; buttons Retry (grey since L10), Song info, Dismiss,
  Delete song (red outline). Cancel confirms in place (Cancel job / Keep it).
- Jobs / Library tools becomes Browse v2's By artist / By song toggle.
- Library tools: each list is a row with its count in a slot (red dashed Looks poor, amber dashed
  Behind); explanations move into (i) tips; Regenerate rows each with a Preview button. The
  count slots stay there, not strips: there the number is the information.

## For the spec

- The branch is still on `dev` at `764df44`. `queue_phone` (the shared row style), `browse_phone`
  and the theme (L1, L15, L16) have all landed on `dev` since: rebase before the spec is written.
- `processing.py` stops passing `admin=` to its page render, with `test_processing_page.py`'s
  `get()` registering `admin_bp` and patching `admin.is_admin` (`plans/open-issues.md` on `dev`,
  "Two routes still pass `admin=`...").
- The unruled open issue "A Processing job row never says 'edited'" touches the same line 3. Ask
  Ken whether to fold it in.

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
