"""Tests for the windowed re-align second pass (lib/windowed_realign.py)."""

from pikaraoke.lib.windowed_realign import (
    analyze_pass1,
    build_spans,
    interior_range,
    merge_spans,
    replay_span,
    span_align_lines,
    span_needs_realign,
)


def _word(text: str, start: float, end: float) -> dict:
    return {"word": text, "start": start, "end": end}


def _obj(lid: int, start: float | None, end: float | None, source: str = "align") -> dict:
    words = [] if start is None else [_word(f"w{lid}", start, end)]
    return {
        "line_id": lid,
        "text": f"line {lid}",
        "words": words,
        "start": start,
        "end": end,
        "source": source,
    }


def _stats(sources: list[str]) -> dict:
    return {"selected_source": list(sources)}


class TestAnalyzePass1:
    MARGIN = dict(margin_s=0.3, max_edit_ratio=0.75)

    def _transcribe_echo(self) -> list[dict]:
        # Echoes line 0's four tokens inside its placed window.
        return [
            _word("glowing", 10.2, 10.5),
            _word("river", 10.6, 10.9),
            _word("twilight", 11.0, 11.4),
            _word("ember", 11.5, 11.9),
        ]

    def test_corroborated_unique_long_line_is_anchor(self):
        align_lines = ["glowing river twilight ember", "second line", "", "mystery"]
        objs = [
            _obj(0, 10.0, 12.0),
            _obj(1, 20.0, 21.0),
            _obj(2, None, None, "absent"),
            _obj(3, 30.0, 30.5),
        ]
        anchors, suspects = analyze_pass1(
            align_lines,
            objs,
            _stats(["align", "align", "absent", "transcribe"]),
            self._transcribe_echo(),
            **self.MARGIN,
        )
        assert anchors == [{"lid": 0, "start": 10.0, "end": 12.0}]

    def test_uncorroborated_and_unplaced_lines_are_suspect(self):
        align_lines = ["glowing river twilight ember", "second line", "", "mystery"]
        objs = [
            _obj(0, 10.0, 12.0),
            _obj(1, 20.0, 21.0),
            _obj(2, None, None, "absent"),
            _obj(3, 30.0, 30.5),
        ]
        _, suspects = analyze_pass1(
            align_lines,
            objs,
            _stats(["align", "align", "absent", "transcribe"]),
            self._transcribe_echo(),
            **self.MARGIN,
        )
        # L1/L3 placed but with zero transcribe echo; L2 has no tokens
        # at all (display-only) so it carries no evidence either way.
        assert suspects == {1, 3}

    def test_interp_source_is_suspect_even_with_timing(self):
        align_lines = ["glowing river twilight ember"]
        objs = [_obj(0, 10.0, 12.0, source="interp")]
        anchors, suspects = analyze_pass1(
            align_lines, objs, _stats(["interp"]), self._transcribe_echo(), **self.MARGIN
        )
        assert anchors == []
        assert suspects == {0}

    def test_ytasr_sourced_line_can_anchor(self):
        # ytasr is a full peer source alongside align/transcribe — a
        # corroborated, unique, long-enough ytasr placement anchors a span
        # exactly like an align/transcribe one would.
        align_lines = ["glowing river twilight ember", "second line", "", "mystery"]
        objs = [
            _obj(0, 10.0, 12.0, source="ytasr"),
            _obj(1, 20.0, 21.0),
            _obj(2, None, None, "absent"),
            _obj(3, 30.0, 30.5),
        ]
        anchors, suspects = analyze_pass1(
            align_lines,
            objs,
            _stats(["ytasr", "align", "absent", "transcribe"]),
            self._transcribe_echo(),
            **self.MARGIN,
        )
        assert anchors == [{"lid": 0, "start": 10.0, "end": 12.0}]
        assert 0 not in suspects

    def test_repeated_line_text_never_anchors(self):
        align_lines = ["glowing river twilight ember", "glowing river twilight ember"]
        objs = [_obj(0, 10.0, 12.0), _obj(1, 50.0, 52.0)]
        anchors, _ = analyze_pass1(
            align_lines, objs, _stats(["align", "align"]), self._transcribe_echo(), **self.MARGIN
        )
        assert anchors == []

    def test_short_line_never_anchors_but_is_not_suspect_when_corroborated(self):
        align_lines = ["glowing river twilight"]
        objs = [_obj(0, 10.0, 11.4)]
        anchors, suspects = analyze_pass1(
            align_lines, objs, _stats(["align"]), self._transcribe_echo(), **self.MARGIN
        )
        assert anchors == []
        assert suspects == set()


class TestBuildSpans:
    def test_no_anchors_yields_single_full_song_span(self):
        spans = build_spans([], n_lines=5, duration=100.0)
        assert spans == [
            {"lid_lo": 0, "lid_hi": 4, "anchor_lo": None, "anchor_hi": None, "t0": 0.0, "t1": 100.0}
        ]

    def test_middle_anchor_splits_into_two_padded_spans(self):
        anchors = [{"lid": 2, "start": 40.0, "end": 44.0}]
        spans = build_spans(anchors, n_lines=6, duration=100.0, pad_s=0.5)
        assert spans == [
            {"lid_lo": 0, "lid_hi": 2, "anchor_lo": None, "anchor_hi": 2, "t0": 0.0, "t1": 44.5},
            {"lid_lo": 2, "lid_hi": 5, "anchor_lo": 2, "anchor_hi": None, "t0": 39.5, "t1": 100.0},
        ]

    def test_adjacent_anchors_produce_no_span(self):
        anchors = [
            {"lid": 0, "start": 10.0, "end": 12.0},
            {"lid": 1, "start": 14.0, "end": 16.0},
        ]
        spans = build_spans(anchors, n_lines=2, duration=50.0)
        assert spans == []

    def test_padding_clamped_to_song_bounds(self):
        anchors = [{"lid": 2, "start": 0.2, "end": 99.9}]
        spans = build_spans(anchors, n_lines=6, duration=100.0, pad_s=1.0)
        assert spans[0]["t0"] == 0.0
        assert spans[1]["t1"] == 100.0


class TestInteriorRange:
    def test_virtual_edges_keep_full_line_range(self):
        span = {"lid_lo": 0, "lid_hi": 4, "anchor_lo": None, "anchor_hi": None}
        assert interior_range(span) == (0, 4)

    def test_real_anchors_are_excluded(self):
        span = {"lid_lo": 2, "lid_hi": 7, "anchor_lo": 2, "anchor_hi": 7}
        assert interior_range(span) == (3, 6)


class TestSpanNeedsRealign:
    SPAN = {"lid_lo": 2, "lid_hi": 7, "anchor_lo": 2, "anchor_hi": 7}

    def test_suspect_in_interior_triggers(self):
        assert span_needs_realign(self.SPAN, {5})

    def test_suspect_only_at_edge_anchor_does_not_trigger(self):
        assert not span_needs_realign(self.SPAN, {2, 7})


class TestSpanAlignLines:
    def test_slices_lines_inclusive(self):
        span = {"lid_lo": 1, "lid_hi": 2}
        assert span_align_lines(span, ["a", "b", "c", "d"]) == ["b", "c"]

    def test_tokenless_span_returns_none(self):
        span = {"lid_lo": 0, "lid_hi": 1}
        assert span_align_lines(span, ["", ""]) is None


class TestReplaySpan:
    SPAN = {"lid_lo": 2, "lid_hi": 3, "anchor_lo": None, "anchor_hi": None, "t0": 9.0, "t1": 20.0}
    LINES = ["a", "b", "Hello world", "Second line"]

    def _span_words(self) -> list[dict]:
        return [
            _word("hello", 11.0, 11.4),
            _word("world", 11.5, 11.9),
            _word("second", 15.0, 15.4),
            _word("line", 15.5, 15.9),
        ]

    def test_places_lines_with_absolute_ids_and_times(self):
        result = replay_span(
            self.SPAN,
            self._span_words(),
            [dict(w) for w in self._span_words()],
            self.LINES,
            self.LINES,
            alpha=2.0,
            margin_s=0.3,
            max_edit_ratio=0.75,
        )
        assert result is not None
        placed, sources = result
        assert set(placed) == {2, 3}
        assert placed[2]["start"] == 11.0
        assert placed[2]["line_id"] == 2
        assert sources[3] in ("align", "transcribe")

    def test_empty_span_words_returns_none(self):
        result = replay_span(
            self.SPAN, [], [], self.LINES, self.LINES, alpha=2.0, margin_s=0.3, max_edit_ratio=0.75
        )
        assert result is None


class TestMergeSpans:
    ALIGN_WORDS = [_word("x", 0.0, 50.0)]
    SPAN = {"lid_lo": 0, "lid_hi": 4, "anchor_lo": 0, "anchor_hi": 4, "t0": 0.0, "t1": 45.0}

    def _pass1(self) -> list[dict]:
        return [
            _obj(0, 1.0, 2.0),
            _obj(1, 10.0, 11.0),
            _obj(2, None, None, source="interp"),
            _obj(3, 30.0, 31.0),
            _obj(4, 40.0, 41.0),
        ]

    def _result(self, lid2_source: str = "transcribe") -> tuple[dict[int, dict], dict[int, str]]:
        # Replay moved L1, newly placed L2, left L3 unplaced; it also
        # claims the edge anchors with shifted times, which the merge
        # must ignore (only interior lines may change).
        placed2 = {0: _obj(0, 5.0, 6.0), 1: _obj(1, 12.0, 13.0), 2: _obj(2, 20.0, 21.0)}
        sources2 = {0: "align", 1: "align", 2: lid2_source, 3: "absent", 4: "absent"}
        return placed2, sources2

    def test_careful_merge_replaces_places_and_drops(self):
        merged = merge_spans(self._pass1(), [self.SPAN], [self._result()], 5, self.ALIGN_WORDS)
        by_id = {o["line_id"]: o for o in merged}
        assert len(merged) == 5
        assert by_id[0]["start"] == 1.0  # edge anchor untouched
        assert by_id[1]["start"] == 12.0  # pass-1 placement replaced
        assert by_id[2]["start"] == 20.0  # newly placed, transcribe-corroborated
        assert by_id[3]["words"] == [] and by_id[3]["source"] == "interp"  # un-placed
        assert by_id[4]["start"] == 40.0

    def test_new_placement_without_transcribe_source_is_rejected(self):
        merged = merge_spans(
            self._pass1(), [self.SPAN], [self._result(lid2_source="align")], 5, self.ALIGN_WORDS
        )
        by_id = {o["line_id"]: o for o in merged}
        assert by_id[2]["words"] == []
        assert by_id[2]["source"] == "interp"

    def test_none_result_keeps_pass1_for_the_span(self):
        merged = merge_spans(self._pass1(), [self.SPAN], [None], 5, self.ALIGN_WORDS)
        by_id = {o["line_id"]: o for o in merged}
        assert [by_id[lid]["start"] for lid in (0, 1, 3, 4)] == [1.0, 10.0, 30.0, 40.0]

    def test_unplaced_lines_reinterpolate_between_merged_neighbours(self):
        merged = merge_spans(self._pass1(), [self.SPAN], [self._result()], 5, self.ALIGN_WORDS)
        by_id = {o["line_id"]: o for o in merged}
        # L3 was un-placed; its interp window brackets the merged L2/L4.
        assert by_id[3]["start"] == 21.0
        assert by_id[3]["end"] == 40.0

    def test_replacement_intruding_into_edge_anchor_keeps_pass1(self):
        # The replay nested L1 inside the kept lo-anchor's window
        # (anchor L0 ends at 2.0): distrust it, keep pass-1's 10.0.
        placed2 = {1: _obj(1, 1.2, 1.8)}
        sources2 = {1: "align"}
        merged = merge_spans(self._pass1(), [self.SPAN], [(placed2, sources2)], 5, self.ALIGN_WORDS)
        by_id = {o["line_id"]: o for o in merged}
        assert by_id[1]["start"] == 10.0

    def test_new_placement_intruding_into_edge_anchor_is_rejected(self):
        # L2 (unplaced in pass-1) claims audio inside the hi-anchor's
        # window (anchor L4 starts at 40.0): rejected despite the
        # transcribe source.
        placed2 = {2: _obj(2, 40.2, 41.0)}
        sources2 = {2: "transcribe"}
        merged = merge_spans(self._pass1(), [self.SPAN], [(placed2, sources2)], 5, self.ALIGN_WORDS)
        by_id = {o["line_id"]: o for o in merged}
        assert by_id[2]["words"] == []
        assert by_id[2]["source"] == "interp"

    def test_small_edge_overlap_within_tolerance_is_accepted(self):
        # Backing-vocal style overlap: L1 starts 0.3s before the
        # lo-anchor ends — inside MERGE_EDGE_TOL_S, accepted.
        placed2 = {1: _obj(1, 1.7, 9.0)}
        sources2 = {1: "align"}
        merged = merge_spans(self._pass1(), [self.SPAN], [(placed2, sources2)], 5, self.ALIGN_WORDS)
        by_id = {o["line_id"]: o for o in merged}
        assert by_id[1]["start"] == 1.7
