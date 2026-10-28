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
        assert library_status.song_status(video).custom_sheet is False

        sheet = tmp_path / "lyrics" / f"{video.stem}.custom.txt"
        sheet.parent.mkdir()
        sheet.write_text("one\n", encoding="utf-8")
        status = library_status.song_status(video)
        assert (status.origin, status.custom_sheet) == ("custom", True)

    def test_a_sheet_counts_with_no_bundle_too(self, tmp_path):
        video = make_video(tmp_path)
        (tmp_path / "lyrics").mkdir()
        (tmp_path / "lyrics" / f"{video.stem}.custom.txt").write_text("one\n", encoding="utf-8")

        assert library_status.song_status(video).custom_sheet is True


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
            "all": 5,
        }

    def test_empty_folder(self, tmp_path):
        assert library_status.overview_counts(library_status.library_statuses(tmp_path)) == {
            "behind": 0,
            "poor": 0,
            "no_lyrics": 0,
            "all": 0,
        }


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
            tmp_path / "regen_backup_20261001T000000Z",
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
            tmp_path / "regen_backup_20261001T000000Z",
            video.stem,
            captured_at="2026-09-01T00:00:00Z",
        )
        write_bundle(
            tmp_path / "regen_backup_20261002T000000Z",
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
            "regen_backup_20261002T000000Z",
            "regen_backup_20261001T000000Z",
        ]

    def test_a_version_copied_into_two_backups_is_listed_once_under_the_newer(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, captured_at="2026-10-03T00:00:00Z")
        for name in ("regen_backup_20261001T000000Z", "regen_backup_20261002T000000Z"):
            write_bundle(tmp_path / name, video.stem, captured_at="2026-09-01T00:00:00Z")

        entries = library_status.song_history(video)

        assert [e.captured_at for e in entries] == ["2026-10-03T00:00:00Z", "2026-09-01T00:00:00Z"]
        assert entries[1].backup == "regen_backup_20261002T000000Z"

    def test_the_current_bundle_unchanged_since_a_backup_is_listed_once(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, captured_at="2026-10-03T00:00:00Z")
        write_bundle(
            tmp_path / "regen_backup_20261002T000000Z",
            video.stem,
            captured_at="2026-10-03T00:00:00Z",
        )

        [entry] = library_status.song_history(video)

        assert entry.backup is None

    def test_backups_without_this_song_or_a_timestamp_are_skipped(self, tmp_path):
        video = make_video(tmp_path)
        write_bundle(tmp_path, video.stem, captured_at="2026-10-03T00:00:00Z")
        write_bundle(tmp_path / "regen_backup_20261001T000000Z", "Other---aaaaaaaaaaa")
        old = tmp_path / "regen_backup_20261002T000000Z" / "alignment_debug"
        old.mkdir(parents=True)
        (old / f"{video.stem}.json").write_text('{"schema_version": 5}', encoding="utf-8")

        entries = library_status.song_history(video)

        assert [e.backup for e in entries] == [None]

    def test_no_bundle_anywhere_gives_no_history(self, tmp_path):
        assert library_status.song_history(make_video(tmp_path)) == []
