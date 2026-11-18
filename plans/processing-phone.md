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
"Processing: a failed job opened", "Processing: Library tools" and "Reference palette". Its
rows, Now card and step strip are still draft 1 (below, not ruled); only its colours and chips
are settled. For those it wins over this branch's mockup; this file wins over both.

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

## Drafted, not yet ruled

Draft 1 shows these; Ken has not accepted or rejected them.

- Rows in the shared Queue/Browse style: song name 17 px bold on top, "artist · details" 13 px
  grey under it, a 60 px state slot on the left, a 40 px chevron button on the right, alternate
  rows shaded.
- The slot carries the state. Solid means tappable: green Queue on finished songs (queues
  straight from the row; today Add to queue sits inside the opened row), amber Pick on songs
  waiting for lyrics. Dashed means a state: grey with the place in line (waiting, downloading),
  red "failed", amber "unfinished", red "cancelling".
- Under All, the list is grouped Attention, Active, Finished with a small heading each ("Active ·
  5 more songs": the running job is in the Now card). Another chip shows just its group.
- The running job is Queue v2's Now card plus a four-step strip (Download, Audio, Vocals, Lyrics)
  and a large line saying what it is doing and for how long.
- Rows open from the chevron. The error shows in a dark box; buttons Retry (blue; grey since
  L10), Song info, Dismiss, Delete song (red outline). Cancel confirms in place (Cancel job /
  Keep it).
- Jobs / Library tools becomes Browse v2's By artist / By song toggle.
- Library tools: each list is a row with its count in the slot (red dashed Looks poor, amber
  dashed Behind); explanations move into (i) tips; Regenerate rows each with a Preview button.
- Guest: Queue v2's guest look. Own songs tinted green, red delete button on own songs still
  getting ready (asks first), green Queue on ready ones. Dropped by L14.

## Open questions (on the mockup's yellow note)

1. Group order under All: Attention first (what the host must act on) or Active first (today's
   order)? Drawn Attention first.
2. Under All, keep the small group headings, or one flat list like today?
3. Do guests still see other people's failed songs, or only their own? Moot since L14: guests
   get no Processing view.
4. Is the four-step strip right? It groups the real phases (download, extract, loudnorm,
   stem_separation, transcode, align, transcribe) into four.

## Unchecked assumptions in the mockup

- A failed download shows as Failed for the host; `statusOf()` in `processing.html` only checks
  `processing_status === 'error'`.
- Guests get a cancel button on every own song still getting ready, including the running one.
  Moot since L14.

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
