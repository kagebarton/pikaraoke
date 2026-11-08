# Cutting songs out of films and TV shows

`scripts/split_songs.py` cuts a film's or TV episode's songs into one clip and
one clip-timed SRT each, ready for the library's SRT cue-align path. This doc
covers which songs to cut, where each clip starts and ends, how the script
measures that, and how to get the clips into the library. The numbers the
script was tuned with are constants at the top of the script, each with its
reason.

Done so far: The Last Five Years (2014), KPop Demon Hunters (2025), Rent
(2005), Flight of the Conchords (2007). The first three used an older
keyframe-copy method. FOTC was the first show cut with this script.

## The rules

These are Ken's choices. When a rule doesn't cover something, ask him.

**Which songs:**

- Only near-full songs. Compare the length of the singing in the film with
  the soundtrack track (Wikipedia lists lengths), and skip snippets.
- Never a song under 2 minutes. Never a repeat: no reprises, and no finale
  built from earlier songs.
- Not a song with a lot of dialogue over it, a lead-in full of dialogue, or a
  mostly spoken number.
- When the list is a judgment call, ask before cutting. Let Ken check one song
  before running them all.

**Where a clip starts and ends**, highest priority first. Each rule gives way
only to the ones above it:

1. **Whole music.** Start before the song's music starts and end after it
   fades: these are whole songs for karaoke. Count credits music after an
   episode's last song as part of the song.
2. **Nobody talking at the cut.** No edge lands in the middle of a line.
3. **On a camera cut.** Open on a fresh shot and end on the last frame of one,
   with no sliver of another shot.
4. **Padding.** Aim to start 5 s before the first sung line and end 5 s after
   the last, but never run into the next spoken line.

The exception: if the nearest clean camera cut is more than 15 s past the
nearest pause, use the pause and start or end partway through the shot
(`MAX_CUT_DETOUR`). Otherwise a far-off cut drags in a whole scene of dialogue.

**Rules for particular cases:**

- Keep a setup scene when Ken asks for one (`start_by`; FOTC: Foux du Fafa,
  Hurt Feelings).
- Join a song that an episode splits in two into one clip (FOTC: Robots).
- `plan` reports every outer edge that missed a camera cut, and how many
  dialogue lines the lead and tail hold. Pass both on to Ken.

**Output:**

- Files are named `<Film> (<year>) - <Song>.mp4` and `.srt`, and are written
  next to the config.
- 720p H.264 like the rest of the library, x264 CRF 26 with stereo AAC 192k.
  Ken traded some quality for size: CRF 20 was about twice the size.
- A new cut replaces any earlier version of the same clip; don't keep both. An
  uploader's YouTube copy of the same scene is deleted once the clip is in the
  library. Delete it through `SongManager.delete`, never `rm`, so its other
  files go too.

**Subtitles:**

- Prefer plain English over SDH when the lyric text is the same: the pipeline
  strips SDH's tags anyway.
- Use SDH to *find* songs. `♪` marks sung lines, and tags such as
  `["<Song>" playing]` and `[song ends]` name and bound them.
- "Forced" tracks are useless. Release-group ad cues sit at the very start.
- With no SDH, map the songs from the lyrics and the soundtrack's track list.
- Grep the SRT for mojibake (non-ASCII like `и` for `è`) and OCR slips (`lf`
  for `If`, words run together). Cut from a fixed copy (`subtitles = ...` in
  the config).
- The clip SRT drops mixed-case speaker labels (`Both:`). The app strips only
  labels typed in capitals, so it would sing a mixed-case one.
- Captions typed in capitals get sentence case, with the config's `names` put
  back. The app's own recasing would lowercase the names.
- Dialogue inside a song stays.

## Workflow

1. **Find the songs.** Dump the subtitles with
   `ffmpeg -i <video> -map 0:s:0 -f srt subs.srt`. Read them for `♪` and song
   tags, then make the song list and check it against the rules above.
2. **Note the first and last sung cue numbers** for each song, and for each
   half of a split song.
3. **Find the music's edges.** Usually you only need the end: where the fade
   finishes is `music_to`. Set `music_from` when SDH has no music tag before
   the first sung line, or when its tag is wrong. Print the level per second
   with the command in [Reading the music's edges](#reading-the-musics-edges)
   and read where it rises or falls.
4. **Write the config** next to the source (format below). Each choice that
   needed a judgment gets a comment explaining it.
5. **Run `plan`:**
   `python scripts/split_songs.py <show.toml> plan`. Read every `NOT ON A CUT` and every lead or tail with lines in it.
6. **Cut one song**, let Ken check it, then cut the rest:
   `python scripts/split_songs.py <show.toml> cut "<part of title>"`.
   `srt` rewrites only the SRTs.
7. **Run the checks** below, then **ingest**.

A stereo source's voice track comes from the app's vocal model on the GPU. The
running app's workers hold up to 4.5 GB, so separating with the app up runs
out of memory. Stop the app first. A source with a 5.1 track uses its centre
channel instead and needs no GPU. Everything measured is cached in
`split_cache/` next to the config, under the source file's name, so rerunning
`plan` is fast. Delete that folder when you're done.

## Config format

```toml
# python scripts/split_songs.py <this file> plan|cut|srt [song]
prefix = "Flight of the Conchords (2007) - "   # clip names: <prefix><title>.mp4/.srt
source = "Season */*{episode}*.mkv"            # glob from this file's folder
# subtitles = "fixed/{episode}.srt"            # optional; default: the source's first subtitle stream
labels = ["both", "bret", "jemaine", "girls", "all"]  # speaker labels to strip, any case
names = ["Bret", "Jemaine", "Carol Brown", "New Zealand"]  # restored when recasing all-caps captions

[[songs]]
episode = "S01E01"          # fills {episode}; leave it out for a film
title = "The Most Beautiful Girl (In the Room)"
parts = [{ first = 51, last = 116, music_to = 395.5 }]

# A song split by the episode, joined into one clip.
[[songs]]
episode = "S01E01"
title = "Robots"
parts = [
    { first = 326, last = 353, music_to = 968.5 },
    { first = 573, last = 589, music_from = 1618.0, music_to = 1700.5 },
]

# Keeps a setup scene: start at or before 92 s.
[[songs]]
episode = "S01E08"
title = "Foux du Fafa"
parts = [{ first = 34, last = 95, start_by = 92.0, music_to = 260.5 }]
```

Each part takes these fields:

- `first`, `last`: the first and last sung cue numbers in the source SRT.
- `music_from`: where the music starts. Optional.
- `music_to`: where the music's fade ends. Optional.
- `start_by`: a time the clip must start at or before, to keep a setup scene.
  Optional.

All times are seconds in the source. FOTC's full config is
`split_songs.toml` in its download folder.

## How the script measures each rule

**Camera cuts:** ffmpeg's `scdet` filter at a score of 10, run on a 320 px
copy. FOTC's hard cuts scored 15-19. It runs on each search window and prints
times from the window's start, which the script adds back. Absolute times
(`-copyts`) come out rounded to 10 ms past 1000 s, and an end on one rounded up
keeps the next shot's first frame (FOTC's Bowie). They would also be off by the
container's start time where that isn't 0. x265 sources put their keyframes on
these cuts.

**Nobody talking:** a moment is clean if no spoken caption is up, or if the
voice track is quiet for 0.15 s on each side.

- **Why not the captions alone:** FOTC's captions run back to back, and its
  editors cut between words inside them. Almost every camera cut lands inside
  a caption, yet 9 of the 13 tested were real pauses.
- **Voice track:** for 5.1, the centre channel. For stereo, the app's vocal
  model (`PipelineConfig.separator_model_name`) separates it.
- **Quiet:** a 50 ms frame counts as quiet below the higher of two thresholds,
  computed over the search window:
  - 30% of the way up from the floor (5th percentile) to speech (95th). This
    is for a centre channel, which never falls silent: its room tone sits
    about 18 dB under speech.
  - 25 dB under speech. This is for a separated voice. Its floor is digital
    silence, but at a party it still carries crowd murmur, which the first
    threshold alone would read as talking.

**The edge search**, for each end of a part:

- **Start:** the latest allowed start is the earliest of the first sung line,
  the music start and `start_by`. The target is 5 s before the first line, or
  that latest start if it's earlier.
- **End:** the earliest allowed end is `music_to`, or the last line's end. The
  target is 5 s past the last line, capped at the next spoken line, but never
  before that earliest end.
- **Search:** clean camera cuts are looked for up to 60 s beyond those limits.
  Each candidate is clean or not by the test above. The pick is the one nearest
  the target, on the padding side when there is one: earlier for a start, later
  for an end, and earlier for an end the next spoken line caps.
- **Fallback:** if no clean cut lies within 15 s of the nearest clean moment,
  on either side of it, the edge goes on that moment instead.

**Music start without `music_from`:** an SDH music tag (music, guitar,
strumming, piano...) between the last spoken line and the first sung one,
minus 1 s. Failing that, the first sung line. FOTC's tags matched the audio.

**Joined parts:** the join is a cut anyway, so the inner edges skip the
camera-cut rule and pad only 0.5 s.

**Markup:** `<i>`, `<font>` and `{\an8}` are dropped as the subtitles are
read, so a tag in italics is still a bare tag, and recasing and labels see only
the words.

**Recasing:** captions are treated as typed in capitals by the app's own test
(`srt_cues.is_all_caps`). Recasing then:

- lowercases everything and capitalizes the cue start, each sentence start, a
  new speaker's dash, and a quote opened after a comma.
- skips over `( tags )` and leaves them lowercase.
- capitalizes `I`, then puts back `names`.

**Which cues land in a clip SRT:** a spoken cue counts if its midpoint is
inside the clip, a tag if any of it is. Both are clipped to the clip's edges.

### Reading the music's edges

This prints the level for each second, starting from `-ss`. Add the start time
to get times in the source. For stereo it measures the difference between the
two channels, where centred dialogue cancels out. FOTC's ambience sat around
-40 dB to -55 dB and its music at -25 dB to -35 dB.

```bash
ffmpeg -hide_banner -ss 388 -t 30 -i <video> -map 0:a:0 \
  -af "pan=mono|c0=0.5*c0-0.5*c1,asetnsamples=n=48000,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level" \
  -f null - 2>&1 | grep -oE 'pts_time:\S+|RMS_level=\S+' | paste - -
```

For 5.1, use `pan=mono|c0=0.5*FL+0.5*FR` instead: the dialogue is in the
centre channel, so the front left and right carry the music. `n=48000` is one
second at 48 kHz. Use the source's own rate if it differs.

### Encode pitfalls already hit

- **Copied audio starts early.** With an exact `-ss`, copied audio starts at
  the keyframe before it, 2-9 s ahead of the video. The script encodes all
  audio.
- **ffconcat's `inpoint` only lands on keyframes.** That's fine for stream
  copy but not for exact cuts. The script seeks each part on the input
  (`-ss`/`-t` before `-i`, which is exact when re-encoding) and joins the parts
  with the `concat` filter.
- **Mkv chapters become a text track in the mp4** (`-map_chapters -1`).
- **Size:** at CRF 20 FOTC came out at 2-7 Mbps. That came from detail and
  motion, not grain: denoising saved only about 5%. CRF 26 is about 45% of
  CRF 20, and x265 at CRF 24 about 50%.

## Checks before handing over

- `ffprobe` each clip: 720p h264, 2-channel AAC, video and audio both
  starting within about 20 ms, and no data track.
- **Sync:** cross-correlate each clip's audio against the source at the
  planned span. FOTC was within 20 ms everywhere, and within 60 ms at the
  Robots join.
- Each SRT parses the way the app reads it (run from the repo root; it prints
  each file's line count):
  `python -c "import sys; from pikaraoke.lib.srt_cues import cue_spans_from_srt as c; [print(len(c(open(f).read())[0]), f) for f in sys.argv[1:]]" <folder>/*.srt`.
- Grep the SRTs for non-ASCII. In FOTC the only hits were the French in Foux
  du Fafa.

## Ingest

1. Copy the mp4s to the library folder (`~/pikaraoke-songs/`) and the SRTs to
   its `subtitles/` folder. Don't add a `.srt.generated` marker: without one,
   the SRT counts as the uploader's and gets cue align.
2. If a song is already in the library, move its `vocal/`, `nonvocal/`,
   `karaoke/` and `alignment_debug/` files aside first. Otherwise the run
   reuses the old stems and skips the song.
3. With the app stopped, run
   `python -u scripts/regen_alignment_bundles.py --song "<full file name>" ... --yes`.
   - Pass whole file names (each pattern must match exactly one song). Never
     pass `--reset`.
   - Press Enter at the search prompt, and `s` (use the local SRT) at "choose".
   - Keep `-u`: block-buffered output hides the per-song lines.
4. Never commit the clips, SRTs or configs: they are copyrighted material.
