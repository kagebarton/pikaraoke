"""Unit tests for pikaraoke/lib/library_status.py -- status, overview counts, history.

Bundles are written to ``tmp_path``; nothing here touches the network.
"""

import json
from pathlib import Path

from pikaraoke.lib import library_status, lrclib
from pikaraoke.lib.alignment_capture import SCHEMA_VERSION

VID = "dQw4w9WgXcQ"


def make_video(folder: Path, stem: str = f"Song---{VID}") -> Path:
    video = folder / f"{stem}.mp4"
    video.write_bytes(b"")
    return video


def write_bundle(root: Path, stem: str, **fields) -> None:
    bundle = {"schema_version": SCHEMA_VERSION, "captured_at": "2026-10-01T00:00:00Z"}
    bundle.update(fields)
    path = root / "alignment_debug" / f"{stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle), encoding="utf-8")


def summary(line_count: int, lines_timed: int) -> dict:
    return {"output_summary": {"line_count": line_count, "lines_with_words": lines_timed}}


class TestCategory:
    def test_current_bundle(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem)
        status = library_status.song_status(video)
        assert status.category == "current"
        assert status.youtube_id == VID

    def test_older_schema_is_behind(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, schema_version=SCHEMA_VERSION - 1)
        assert library_status.song_status(video).category == "behind"

    def test_bundle_without_a_version_is_behind(self, tmp_path):
        video = make_video(tmp_path)
        path = tmp_path / "alignment_debug" / f"{video.stem}.json"
        path.parent.mkdir()
        path.write_text("{}", encoding="utf-8")
        assert library_status.song_status(video).category == "behind"

    def test_karaoke_file_without_a_bundle_is_no_lyrics(self, tmp_path):
        video = make_video(tmp_path)
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{video.stem}.ass").write_text("", encoding="utf-8")
        assert library_status.song_status(video).category == "no_lyrics"

    def test_nothing_made_yet_is_not_processed(self, tmp_path):
        video = make_video(tmp_path)
        status = library_status.song_status(video)
        assert status.category == "not_processed"
        assert status.lrclib_state == "n/a"
        assert status.guessed is None
        assert not status.poor

    def test_unreadable_bundle_counts_as_no_bundle(self, tmp_path):
        video = make_video(tmp_path)
        path = tmp_path / "alignment_debug" / f"{video.stem}.json"
        path.parent.mkdir()
        path.write_text("{not json", encoding="utf-8")
        assert library_status.song_status(video).category == "not_processed"


class TestPoor:
    def test_exactly_the_threshold_is_poor(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, **summary(line_count=20, lines_timed=17))
        status = library_status.song_status(video)
        assert status.guessed == 3
        assert status.poor

    def test_just_under_the_threshold_is_not_poor(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, **summary(line_count=21, lines_timed=18))
        status = library_status.song_status(video)
        assert status.guessed == 3
        assert not status.poor

    def test_fully_timed_is_not_poor(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, **summary(line_count=10, lines_timed=10))
        assert not library_status.song_status(video).poor

    def test_a_summary_missing_the_timed_count_is_not_poor(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, output_summary={"line_count": 10})
        status = library_status.song_status(video)
        assert status.guessed is None
        assert not status.poor

    def test_a_bundle_with_no_lines_is_not_poor(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, **summary(line_count=0, lines_timed=0))
        assert not library_status.song_status(video).poor


class TestTimedBy:
    def test_joint_song_reports_who_won_each_line(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(
            tmp_path,
            video.stem,
            pipeline_decisions={"method_used": "joint"},
            joint_stats={"align_won": 30, "transcribe_won": 5, "ytasr_won": 2},
        )
        status = library_status.song_status(video)
        assert status.method == "joint"
        assert status.timed_by == {"aligner": 30, "transcription": 5, "captions": 2}

    def test_lines_the_evidence_veto_dropped_are_not_the_aligners(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(
            tmp_path,
            video.stem,
            pipeline_decisions={"method_used": "joint"},
            joint_stats={
                "align_won": 22,
                "transcribe_won": 0,
                "ytasr_won": 0,
                "evidence_veto": {"n_vetoed": 4},
            },
            **summary(line_count=42, lines_timed=18),
        )
        assert library_status.song_status(video).timed_by["aligner"] == 18

    def test_the_veto_cannot_take_the_aligner_below_zero(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(
            tmp_path,
            video.stem,
            pipeline_decisions={"method_used": "joint"},
            joint_stats={"align_won": 1, "evidence_veto": {"n_vetoed": 3}},
        )
        assert library_status.song_status(video).timed_by["aligner"] == 0

    def test_cue_align_song_has_no_split(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, pipeline_decisions={"method_used": "cue_align"})
        status = library_status.song_status(video)
        assert status.method == "cue_align"
        assert status.timed_by is None


class TestLrclibState:
    def genius_bundle(self, tmp_path, *, lrclib_meta=None, fill=None) -> Path:
        video = make_video(tmp_path)
        lyrics = {"origin": "genius", "genius": {"id": 7, "title": "T", "artist": "A"}}
        if lrclib_meta is not None:
            lyrics["lrclib"] = lrclib_meta
        write_bundle(tmp_path, video.stem, lyrics=lyrics, joint_stats={"lrclib_fill": fill or {}})
        return video

    def test_used_when_the_fill_was_eligible(self, tmp_path):
        video = self.genius_bundle(
            tmp_path,
            lrclib_meta={"lrc_file": "x.lrc", "trackName": "T", "id": 5},
            fill={"eligible": True, "filled_lids": [3, 4]},
        )
        status = library_status.song_status(video)
        assert status.lrclib_state == "used"
        assert status.lrclib_filled == 2
        assert status.lrclib_reason is None
        assert status.lrclib["trackName"] == "T"

    def test_rejected_carries_the_reason(self, tmp_path):
        video = self.genius_bundle(
            tmp_path,
            lrclib_meta={"lrc_file": "x.lrc", "id": 5},
            fill={"eligible": False, "reason": "duration_mismatch"},
        )
        status = library_status.song_status(video)
        assert status.lrclib_state == "rejected"
        assert status.lrclib_reason == "duration_mismatch"
        assert status.lrclib_filled == 0

    def test_none_when_there_was_no_match(self, tmp_path):
        video = self.genius_bundle(tmp_path)
        assert library_status.song_status(video).lrclib_state == "none"

    def test_skipped_when_the_disk_holds_a_skip_marker(self, tmp_path):
        video = self.genius_bundle(tmp_path, lrclib_meta={"lrc_file": "x.lrc"})
        lrclib.write_skip_marker(tmp_path / "lyrics" / f"{video.stem}.lrc")
        assert library_status.song_status(video).lrclib_state == "skipped"

    def test_a_real_lrc_on_disk_is_not_a_skip(self, tmp_path):
        video = self.genius_bundle(tmp_path, lrclib_meta={"lrc_file": "x.lrc", "id": 5})
        lrc = tmp_path / "lyrics" / f"{video.stem}.lrc"
        lrc.parent.mkdir()
        lrc.write_text("[00:01.00]hello\n", encoding="utf-8")
        assert library_status.song_status(video).lrclib_state == "rejected"

    def test_an_lrc_that_is_not_utf8_reads_like_any_other_lrc(self, tmp_path):
        video = self.genius_bundle(tmp_path, lrclib_meta={"lrc_file": "x.lrc", "id": 5})
        lrc = tmp_path / "lyrics" / f"{video.stem}.lrc"
        lrc.parent.mkdir()
        lrc.write_bytes("[ti:Caf\xe9]\n[00:01.00]hello\n".encode("cp1252"))

        assert library_status.song_status(video).lrclib_state == "rejected"

    def test_a_marker_reference_is_not_a_match(self, tmp_path):
        # The pipeline records a skip marker as {"lrc_file": ...} with no id.
        video = self.genius_bundle(tmp_path, lrclib_meta={"lrc_file": "lyrics/x.lrc"})

        status = library_status.song_status(video)

        assert status.lrclib is None
        assert status.lrclib_state == "none"  # not "rejected": nothing was rejected

    def test_a_marker_reference_with_the_marker_on_disk_is_skipped_with_no_match(self, tmp_path):
        video = self.genius_bundle(tmp_path, lrclib_meta={"lrc_file": "lyrics/x.lrc"})
        lrclib.write_skip_marker(tmp_path / "lyrics" / f"{video.stem}.lrc")

        status = library_status.song_status(video)

        assert status.lrclib is None
        assert status.lrclib_state == "skipped"

    def test_not_applicable_to_a_caption_song(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, lyrics={"origin": "srt"})
        assert library_status.song_status(video).lrclib_state == "n/a"

    def test_not_applicable_to_a_movie_subtitles_song_whatever_is_on_disk(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, lyrics={"origin": "movie_srt", "lrclib": {"id": 5}})
        lrclib.write_skip_marker(tmp_path / "lyrics" / f"{video.stem}.lrc")

        assert library_status.song_status(video).lrclib_state == "n/a"

    def custom_bundle(self, tmp_path, *, lrclib_meta=None, fill=None) -> Path:
        video = make_video(tmp_path)
        lyrics = {"origin": "custom", "lines": ["one", "two"]}
        if lrclib_meta is not None:
            lyrics["lrclib"] = lrclib_meta
        write_bundle(tmp_path, video.stem, lyrics=lyrics, joint_stats={"lrclib_fill": fill or {}})
        return video

    def test_a_custom_song_has_the_same_states_as_a_genius_one(self, tmp_path):
        for name in ("used", "rejected", "none"):
            (tmp_path / name).mkdir()
        used = self.custom_bundle(
            tmp_path / "used",
            lrclib_meta={"lrc_file": "x.lrc", "id": 5},
            fill={"eligible": True, "filled_lids": [3]},
        )
        rejected = self.custom_bundle(
            tmp_path / "rejected",
            lrclib_meta={"lrc_file": "x.lrc", "id": 5},
            fill={"eligible": False, "reason": "no_mapping"},
        )
        none = self.custom_bundle(tmp_path / "none")

        states = [library_status.song_status(v) for v in (used, rejected, none)]

        assert [s.origin for s in states] == ["custom"] * 3
        assert [s.lrclib_state for s in states] == ["used", "rejected", "none"]
        assert (states[0].lrclib_filled, states[1].lrclib_reason) == (1, "no_mapping")

    def test_a_custom_song_can_have_its_lrclib_match_skipped(self, tmp_path):
        video = self.custom_bundle(tmp_path, lrclib_meta={"lrc_file": "x.lrc"})
        lrclib.write_skip_marker(tmp_path / "lyrics" / f"{video.stem}.lrc")

        assert library_status.song_status(video).lrclib_state == "skipped"


class TestCustomSheet:
    """The sheet on disk, not the bundle's origin, says a song's pick is custom."""

    def test_only_a_sheet_on_disk_counts(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, lyrics={"origin": "custom", "lines": ["one"]})
        assert library_status.song_status(video).sheet_kind is None

        sheet = tmp_path / "lyrics" / f"{video.stem}.custom.txt"
        sheet.parent.mkdir()
        sheet.write_text("one\n", encoding="utf-8")
        status = library_status.song_status(video)
        assert (status.origin, status.sheet_kind) == ("custom", "custom")

    def test_a_sheet_counts_with_no_bundle_too(self, tmp_path):
        video = make_video(tmp_path)
        (tmp_path / "lyrics").mkdir()
        (tmp_path / "lyrics" / f"{video.stem}.custom.txt").write_text("one\n", encoding="utf-8")

        assert library_status.song_status(video).sheet_kind == "custom"

    def test_a_movie_subtitles_sheet_counts_too(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, lyrics={"origin": "movie_srt", "lines": ["one"]})
        assert library_status.song_status(video).sheet_kind is None

        (tmp_path / "lyrics").mkdir()
        (tmp_path / "lyrics" / f"{video.stem}.custom.srt").write_text("x\n", encoding="utf-8")
        status = library_status.song_status(video)

        assert (status.origin, status.sheet_kind) == ("movie_srt", "movie")

    def test_a_movie_subtitles_sheet_counts_with_no_bundle_too(self, tmp_path):
        video = make_video(tmp_path)
        (tmp_path / "lyrics").mkdir()
        (tmp_path / "lyrics" / f"{video.stem}.custom.srt").write_text("x\n", encoding="utf-8")

        status = library_status.song_status(video)

        assert status.sheet_kind == "movie"

    def test_a_movie_bundle_with_no_sheet_on_disk_has_no_kind(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, lyrics={"origin": "movie_srt", "lines": ["one"]})

        assert library_status.song_status(video).sheet_kind is None

    def test_the_sheet_the_next_run_uses_names_the_kind_when_both_are_on_disk(self, tmp_path):
        """A failed put-back can leave both kinds; the typed one comes first, as the plan does."""
        video = make_video(tmp_path)
        (tmp_path / "lyrics").mkdir()
        for suffix in (".custom.txt", ".custom.srt"):
            (tmp_path / "lyrics" / f"{video.stem}{suffix}").write_text("x\n", encoding="utf-8")

        status = library_status.song_status(video)

        assert status.sheet_kind == "custom"


class TestLrcOnDisk:
    """A usable LRC is read from disk: the bundle of a song from before schema 9 never recorded it."""

    def lrc(self, tmp_path, video) -> Path:
        path = tmp_path / "lyrics" / f"{video.stem}.lrc"
        path.parent.mkdir(exist_ok=True)
        return path

    def test_no_file_is_not_usable(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem)

        assert library_status.song_status(video).lrc_on_disk is False

    def test_a_skip_marker_is_not_usable(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem)
        lrclib.write_skip_marker(self.lrc(tmp_path, video))

        assert library_status.song_status(video).lrc_on_disk is False

    def test_an_lrc_that_cannot_be_read_is_not_usable(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem)
        self.lrc(tmp_path, video).write_bytes("[00:01.00]caf\xe9\n".encode("latin-1"))

        assert library_status.song_status(video).lrc_on_disk is False

    def test_a_real_lrc_is_usable_whatever_the_bundle_recorded(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, schema_version=8, lyrics={"origin": "genius"})
        self.lrc(tmp_path, video).write_text("[00:01.00]one\n", encoding="utf-8")

        status = library_status.song_status(video)

        assert status.lrc_on_disk is True
        assert status.lrclib_state == "none"  # the bundle says no match; the disk says otherwise

    def test_a_real_lrc_is_usable_with_no_bundle_too(self, tmp_path):
        video = make_video(tmp_path)
        self.lrc(tmp_path, video).write_text("[00:01.00]one\n", encoding="utf-8")

        assert library_status.song_status(video).lrc_on_disk is True


class TestSourceLists:
    """The by-source lists go by what the last run used, so a song may be on several."""

    def lists_of(self, video: Path) -> set[str]:
        status = library_status.song_status(video)
        return {name for name, in_list in library_status.SONG_LISTS.items() if in_list(status)}

    def song(self, tmp_path, origin: str, method: str, *, lrc: bool | str = False) -> Path:
        """A processed song; ``lrc`` puts a real LRC (True) or a skip marker ("skip") beside it."""
        video = make_video(tmp_path)
        write_bundle(
            tmp_path,
            video.stem,
            lyrics={"origin": origin},
            pipeline_decisions={"method_used": method},
        )
        path = tmp_path / "lyrics" / f"{video.stem}.lrc"
        if lrc == "skip":
            lrclib.write_skip_marker(path)
        elif lrc:
            path.parent.mkdir(exist_ok=True)
            path.write_text("[00:01.00]one\n", encoding="utf-8")
        return video

    def test_a_caption_song(self, tmp_path):
        assert self.lists_of(self.song(tmp_path, "srt", "cue_align")) == {"caption", "all"}

    def test_a_movie_subtitles_song(self, tmp_path):
        assert self.lists_of(self.song(tmp_path, "movie_srt", "cue_align")) == {"movie", "all"}

    def test_an_lrclib_timed_song(self, tmp_path):
        assert self.lists_of(self.song(tmp_path, "lrclib_srt", "cue_align")) == {"lrc", "all"}

    def test_a_genius_song_with_an_lrc_has_a_timed_source(self, tmp_path):
        video = self.song(tmp_path, "genius", "joint", lrc=True)

        assert self.lists_of(video) == {"genius", "all"}

    def test_a_custom_song_with_only_a_skip_marker_has_no_timed_source(self, tmp_path):
        video = self.song(tmp_path, "custom", "joint", lrc="skip")

        assert self.lists_of(video) == {"custom", "no_timed_source", "all"}

    def test_a_genius_song_with_no_lrc_has_no_timed_source(self, tmp_path):
        video = self.song(tmp_path, "genius", "joint")

        assert self.lists_of(video) == {"genius", "no_timed_source", "all"}

    def test_only_a_joint_song_can_lack_a_timed_source(self, tmp_path):
        """A song already on the cue route needs no LRC, so it is not asking for one."""
        video = self.song(tmp_path, "genius", "cue_align")

        assert "no_timed_source" not in self.lists_of(video)

    def test_a_song_with_no_bundle_is_on_no_source_list(self, tmp_path):
        assert self.lists_of(make_video(tmp_path)) == {"all"}

    def test_a_transcribed_song_is_on_no_source_list(self, tmp_path):
        video = make_video(tmp_path)
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{video.stem}.ass").write_text("", encoding="utf-8")

        assert self.lists_of(video) == {"no_lyrics", "all"}


class TestLrclibTimedMatch:
    """A cue-route bundle records no LRCLIB match, so an LRCLIB-timed song's is read off its .lrc."""

    RECORD = {
        "id": 11,
        "trackName": "Invented Song",
        "artistName": "Invented Artist",
        "duration": 200.0,
    }

    def song(self, tmp_path, origin: str) -> Path:
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, lyrics={"origin": origin})
        path = tmp_path / "lyrics" / f"{video.stem}.lrc"
        path.parent.mkdir(exist_ok=True)
        lrclib.write_lrc(path, {**self.RECORD, "syncedLyrics": "[00:01.00]one\n"})
        return video

    def test_the_match_is_the_lrcs_header(self, tmp_path):
        status = library_status.song_status(self.song(tmp_path, "lrclib_srt"))

        assert status.lrclib == {
            "id": 11,
            "trackName": "Invented Song",
            "artistName": "Invented Artist",
            "duration": 200.0,
        }
        assert status.lrclib_state == "n/a"  # the fill is a joint-route matter

    def test_a_song_timed_another_way_records_only_what_its_bundle_says(self, tmp_path):
        assert library_status.song_status(self.song(tmp_path, "genius")).lrclib is None

    def test_an_lrc_that_cannot_be_read_is_no_match(self, tmp_path):
        video = self.song(tmp_path, "lrclib_srt")
        lrclib.lrc_path(video).write_bytes("caf\xe9".encode("latin-1"))

        assert library_status.song_status(video).lrclib is None

    def test_a_skip_marker_is_no_match(self, tmp_path):
        video = self.song(tmp_path, "lrclib_srt")
        lrclib.write_skip_marker(lrclib.lrc_path(video))

        assert library_status.song_status(video).lrclib is None

    def test_an_lrclib_sheet_is_the_sheet_kind_and_needs_no_bundle(self, tmp_path):
        video = make_video(tmp_path)
        sheet = tmp_path / "lyrics" / f"{video.stem}.lrclib.srt"
        sheet.parent.mkdir()
        sheet.write_text("1\n00:00:01,000 --> 00:00:02,000\none\n", encoding="utf-8")

        assert library_status.song_status(video).sheet_kind == "lrclib"


class TestAsrAndDuration:
    def test_ytasr_and_duration_come_from_the_bundle(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(
            tmp_path,
            video.stem,
            media_duration_s=212.5,
            lyrics={"origin": "srt", "ytasr": {"asr_file": "x.json3", "n_words": 9}},
        )
        status = library_status.song_status(video)
        assert status.ytasr_used
        assert status.media_duration_s == 212.5

    def test_no_ytasr_block_means_unused(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, lyrics={"origin": "srt"})
        assert not library_status.song_status(video).ytasr_used


class TestLengthGap:
    def test_a_longer_match_is_positive_and_a_shorter_one_negative(self):
        assert library_status.length_gap_s(354.0, 257.23) == 97
        assert library_status.length_gap_s(227, 257.23) == -30

    def test_a_missing_or_non_numeric_length_has_no_gap(self):
        assert library_status.length_gap_s(None, 257.23) is None
        assert library_status.length_gap_s(354.0, None) is None
        assert library_status.length_gap_s("354", 257.23) is None


class TestOverview:
    def test_counts_cover_the_whole_folder(self, tmp_path):
        current = make_video(tmp_path, f"A---{VID}")
        write_bundle(tmp_path, current.stem, **summary(line_count=10, lines_timed=10))
        poor = make_video(tmp_path, "B---abcdefghijk")
        write_bundle(tmp_path, poor.stem, **summary(line_count=10, lines_timed=5))
        behind = make_video(tmp_path, "C---bbbbbbbbbbb")
        write_bundle(tmp_path, behind.stem, schema_version=SCHEMA_VERSION - 1)
        no_lyrics = make_video(tmp_path, "D---ccccccccccc")
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{no_lyrics.stem}.ass").write_text("", encoding="utf-8")
        make_video(tmp_path, "E---ddddddddddd")

        statuses = library_status.library_statuses(tmp_path)

        assert [s.path.name for s in statuses] == sorted(s.path.name for s in statuses)
        assert library_status.overview_counts(statuses) == {
            "behind": 1,
            "poor": 1,
            "no_lyrics": 1,
            "caption": 0,
            "movie": 0,
            "lrc": 0,
            "genius": 0,
            "custom": 0,
            "no_timed_source": 0,
            "all": 5,
        }

    def test_counts_by_lyric_source(self, tmp_path):
        for stem, origin, method in (
            ("A---aaaaaaaaaaa", "srt", "cue_align"),
            ("B---bbbbbbbbbbb", "srt", "cue_align"),
            ("C---ccccccccccc", "movie_srt", "cue_align"),
            ("D---ddddddddddd", "genius", "joint"),
            ("E---eeeeeeeeeee", "custom", "joint"),
            ("F---fffffffffff", "lrclib_srt", "cue_align"),
        ):
            video = make_video(tmp_path, stem)
            write_bundle(
                tmp_path,
                video.stem,
                lyrics={"origin": origin},
                pipeline_decisions={"method_used": method},
            )

        counts = library_status.overview_counts(library_status.library_statuses(tmp_path))

        assert counts == {
            "behind": 0,
            "poor": 0,
            "no_lyrics": 0,
            "caption": 2,
            "movie": 1,
            "lrc": 1,
            "genius": 1,
            "custom": 1,
            "no_timed_source": 2,  # neither joint song has an LRC beside it
            "all": 6,
        }

    def test_empty_folder(self, tmp_path):
        assert library_status.overview_counts(
            library_status.library_statuses(tmp_path)
        ) == dict.fromkeys(library_status.SONG_LISTS, 0)


class TestHistory:
    def test_current_bundle_alone(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(
            tmp_path,
            video.stem,
            captured_at="2026-10-03T00:00:00Z",
            lyrics={"genius": {"id": 7}, "lrclib": {"id": 9}},
            **summary(line_count=10, lines_timed=8),
        )
        [entry] = library_status.song_history(video)
        assert entry.backup is None
        assert entry.captured_at == "2026-10-03T00:00:00Z"
        assert entry.origin is None  # this bundle names none
        assert entry.genius == {"id": 7}
        assert entry.lrclib == {"id": 9}
        assert (entry.line_count, entry.lines_timed) == (10, 8)

    def test_each_version_carries_the_origin_of_its_lyrics(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(
            tmp_path, video.stem, captured_at="2026-10-03T00:00:00Z", lyrics={"origin": "custom"}
        )
        write_bundle(
            tmp_path / "regen_backups" / "20261001T000000Z",
            video.stem,
            captured_at="2026-09-01T00:00:00Z",
            lyrics={"origin": "srt"},
        )

        assert [e.origin for e in library_status.song_history(video)] == ["custom", "srt"]

    def test_a_marker_reference_is_not_listed_as_a_match(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(
            tmp_path,
            video.stem,
            captured_at="2026-10-03T00:00:00Z",
            lyrics={"genius": {"id": 7}, "lrclib": {"lrc_file": "lyrics/x.lrc"}},
        )

        [entry] = library_status.song_history(video)

        assert entry.lrclib is None

    def test_newest_first_with_the_current_bundle_on_top(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, captured_at="2026-10-03T00:00:00Z")
        write_bundle(
            tmp_path / "regen_backups" / "20261001T000000Z",
            video.stem,
            captured_at="2026-09-01T00:00:00Z",
        )
        write_bundle(
            tmp_path / "regen_backups" / "20261002T000000Z",
            video.stem,
            captured_at="2026-09-20T00:00:00Z",
        )

        entries = library_status.song_history(video)

        assert [e.captured_at for e in entries] == [
            "2026-10-03T00:00:00Z",
            "2026-09-20T00:00:00Z",
            "2026-09-01T00:00:00Z",
        ]
        assert [e.backup for e in entries] == [
            None,
            "20261002T000000Z",
            "20261001T000000Z",
        ]

    def test_a_version_copied_into_two_backups_is_listed_once_under_the_newer(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, captured_at="2026-10-03T00:00:00Z")
        for name in ("20261001T000000Z", "20261002T000000Z"):
            write_bundle(
                tmp_path / "regen_backups" / name, video.stem, captured_at="2026-09-01T00:00:00Z"
            )

        entries = library_status.song_history(video)

        assert [e.captured_at for e in entries] == ["2026-10-03T00:00:00Z", "2026-09-01T00:00:00Z"]
        assert entries[1].backup == "20261002T000000Z"

    def test_the_current_bundle_unchanged_since_a_backup_is_listed_once(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, captured_at="2026-10-03T00:00:00Z")
        write_bundle(
            tmp_path / "regen_backups" / "20261002T000000Z",
            video.stem,
            captured_at="2026-10-03T00:00:00Z",
        )

        [entry] = library_status.song_history(video)

        assert entry.backup is None

    def test_backups_without_this_song_or_a_timestamp_are_skipped(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, captured_at="2026-10-03T00:00:00Z")
        write_bundle(tmp_path / "regen_backups" / "20261001T000000Z", "Other---aaaaaaaaaaa")
        old = tmp_path / "regen_backups" / "20261002T000000Z" / "alignment_debug"
        old.mkdir(parents=True)
        (old / f"{video.stem}.json").write_text('{"schema_version": 5}', encoding="utf-8")

        entries = library_status.song_history(video)

        assert [e.backup for e in entries] == [None]

    def test_no_bundle_anywhere_gives_no_history(self, tmp_path):
        assert library_status.song_history(make_video(tmp_path)) == []
