# Whisper Worker Subprocess Plan — Issue Review

Review of `plans/whisper-worker-subprocess.md` against the current
codebase. Each finding is classified by severity: **high** (will cause
runtime failures or data loss if not addressed), **medium** (significant
design gap or inconsistency), **low** (minor, cosmetic, or future-proofing).

---

## 1. fork-after-CUDA is not mitigated in the plan or the codebase

**Severity: high**

The plan's risk table (line 666) correctly notes that `fork` after CUDA
init is "famously broken" and recommends forcing `spawn` via
`multiprocessing.get_context("spawn")`. However:

- The codebase never calls `set_start_method` or `get_context` anywhere.
  Linux defaults to `fork`.
- The existing `StemWorker` already uses `multiprocessing.Process` under
  `fork` — and it works only because the `import torch` happens **inside**
  `_worker_main`, after the fork. The parent process never initializes
  CUDA.
- The **whisper** worker currently runs in-process: `load_model()` calls
  `torch.cuda.is_available()` and `stable_whisper.load_model()` in the
  **parent** process. After the move, the first `StemWorker.start()` call
  (which happens before whisper's `start()`) will fork a child that
  inherits a **parent with an initialized CUDA context** — exactly the
  scenario the plan warns about.

The plan's `_worker_main` moves CUDA init into the child, which is correct
for the whisper child. But the parent will still have a CUDA context from
the stem worker's model (loaded inside the stem subprocess, but the
parent's `torch` import at module level in `whisper_worker.py` may
initialize the CUDA driver on some PyTorch builds). More critically, if
the stem worker subprocess is ever restarted (auto-restart on OOM), the
second `Process()` call forks a parent that may have had CUDA initialized
by any stray `torch.cuda` call.

**Recommendation:** The plan should mandate `multiprocessing.get_context("spawn")`
for the whisper worker's `Process` creation, and audit the stem worker for
the same issue. Alternatively, add an early `multiprocessing.set_start_method("spawn")`
call at application startup so both workers use `spawn` consistently.

---

## 2. `WorkerDiedError` is not defined or imported for the whisper worker

**Severity: high**

The plan's `start()` method raises `WorkerDiedError` if the subprocess
dies during model load (line 337-339). But `WorkerDiedError` is currently
defined only in `stem_worker.py` (line 64-65). The plan does not mention
moving, importing, or re-defining this exception for the whisper worker
module.

Options:
- Import it from `stem_worker` (creates a cross-dependency between worker
  modules).
- Define a duplicate in `whisper_worker.py`.
- Move it to a shared location (`_ipc.py` or `pipeline/exceptions.py`).

This also affects `_run_job` which needs to raise `WorkerDiedError` when
the subprocess dies mid-job (mirroring `StemWorker.separate()` line 197).

**Recommendation:** Define `WorkerDiedError` in the proposed `_ipc.py`
shared module, or in a new `pipeline/exceptions.py`, and import from there
in both worker modules.

---

## 3. WhisperResult passed between align and refine inside the subprocess

**Severity: medium**

The plan correctly moves `align`+`refine` and `transcribe`+`refine` into
the subprocess as atomic operations (`align_refine`, `transcribe_refine`).
This means the `WhisperResult` object never crosses the IPC boundary — it
lives entirely in the subprocess. Good.

However, the current `LyricAlignStage.run()` extracts `line_objects` from
the `WhisperResult` **twice** — once after the initial align/transcribe
(steps that the plan says move into the subprocess), and **again** after
refine (lines 118-122 in lyric_align.py):

```python
# Re-extract line_objects from the *refined* result
if lyrics_path is not None:
    words = self._extract_words(result)
    lines = [line.strip() for line in lyrics_text.split("\n") if line.strip()]
    line_objects = self._match_words_to_lines(words, lines)
else:
    line_objects = self._segments_to_line_objects(result)
```

The plan's target `LyricAlignStage.run()` (lines 372-406 of the plan)
correctly shows `line_objects` being returned directly from the worker
facade and then consumed by `_generate_ass`/`_generate_srt` — the
re-extraction after refine is no longer needed because it happens inside
the subprocess. This is correct.

**But there is a subtle semantic issue:** The current code re-extracts
`line_objects` from the refined `WhisperResult`, which may differ from the
pre-refine extraction because `refine()` can change word timestamps and
segment boundaries. The plan's `_do_align_refine` / `_do_transcribe_refine`
helpers perform this final extraction inside the subprocess, so the
semantics are preserved. **No bug here** — just worth confirming in code
review that the subprocess-side extraction uses the **refined** result, not
the pre-refine one.

---

## 4. Missing cancellation between align and refine inside the subprocess

**Severity: medium**

The plan's job loop (lines 208-239) catches `_CancelledInsideEncoder` from
the **inference** call but does not show how cancellation is handled
**between** the align and refine sub-operations within `_do_align_refine`.

The current in-process code calls `refine()` with the same `cancel_event`
as `align()` — there is no `cancel_event.clear()` between them. A cancel
signal that arrives after `align()` completes but before `refine()` starts
is caught by `refine()`'s encoder pre-hook.

In the subprocess, the cancel signal arrives via `cancel_recv` pipe. The
hook body (line 266-272) polls `cancel_recv.poll(0)` — if the cancel byte
was already consumed during `align()`, the hook will not fire during
`refine()`. But the plan's `_forward_cancel` thread sends **one byte**
on `cancel_send` (same as stem worker). After `align()` catches it and
drains the pipe, the byte is gone — `refine()` would run without
cancellation.

Wait — re-reading the flow: when cancel fires during `align()`, the
subprocess catches `_CancelledInsideEncoder` inside `_do_align_refine`,
sends `("cancelled",)`, and the job is done. The `refine()` call never
happens. That's correct.

The concern is: what if the user cancels **after** `align()` returns but
**before** `refine()` starts? In the current in-process design, the
`cancel_event` is still set (it's a `threading.Event` — latched), so
`refine()`'s hook sees it immediately and aborts. In the subprocess
design, the `cancel_recv` pipe was drained by the `align()` hook's poll,
so there's no lingering signal. The `_forward_cancel` thread sends one
byte and exits — it doesn't re-send.

**This is a real gap.** If the cancel event is set in the narrow window
between `align()` returning and `refine()` starting, the subprocess will
proceed with `refine()` despite the user's cancellation intent.

**Recommendation:** The `_do_align_refine` helper should check
`cancel_recv.poll(0)` **between** the `align()` and `refine()` calls,
and raise `_CancelledInsideEncoder` if a signal is present. Alternatively,
`_forward_cancel` could be modified to keep sending bytes periodically
(e.g., every 0.5s) while the event is set, not just once. The stem worker
doesn't have this problem because it has a single inference call per job.

---

## 5. `_forward_cancel` sends only one byte — no re-signal

**Severity: medium** (closely related to finding #4)

The stem worker's `_forward_cancel` sends a single byte and exits:

```python
def _forward_cancel(cancel_event, cancel_send):
    cancel_event.wait()
    try:
        cancel_send.send(1)
    except (OSError, BrokenPipeError):
        pass
```

This is sufficient for stem separation because each `separate()` call has
one continuous inference loop — the hook checks once per chunk, and once
the byte is consumed, the cancellation has been detected.

For whisper, the align+refine flow has **two** distinct inference phases
with a gap between them (see finding #4). A single-byte signal is
insufficient to cover both phases.

**Recommendation:** Either:
- (a) Have `_forward_cancel` send repeatedly while `event.is_set()`, with
  a small sleep between sends, so the pipe always has a pending byte for
  the next hook poll. This is the simplest fix.
- (b) Add an explicit `cancel_recv.poll(0)` check between align and
  refine inside `_do_align_refine` / `_do_transcribe_refine`.
- (c) Both — belt and suspenders.

---

## 6. `WhisperModelConfig` has a `compute_type` field not used by `load_model()`

**Severity: low**

`WhisperModelConfig.compute_type` (default `"float16"`) is defined in
`config.py` but the current `WhisperWorker.load_model()` never passes it
to `stable_whisper.load_model()`. The plan's `_worker_main` also does not
show `compute_type` being used.

If `compute_type` is intended for CTranslate2-based models (which accept
`compute_type` in `load_model()`), the subprocess should pass it through.
If it's vestigial, it should be removed from the config. Either way, the
plan should clarify this.

---

## 7. The plan's `LyricAlignStage.run()` loses the `lyrics_text` variable in transcription path

**Severity: low**

The plan's target `LyricAlignStage.run()` (lines 372-406) shows:

```python
if lyrics_path is not None:
    lyrics_text, lyrics_format = self._load_lyrics(lyrics_path)
    ...
    line_objects = _model_call(ctx, Phase.ALIGN, lambda: self._worker.align_refine(
        vocal_path=vocal_wav, lyrics_text=lyrics_text, ...
    ))
else:
    line_objects = _model_call(ctx, Phase.TRANSCRIBE, lambda: self._worker.transcribe_refine(
        vocal_path=vocal_wav, ...
    ))
```

The `lyrics_text` and `lyrics_format` variables are set in the alignment
branch. The current code also sets `ctx.artifacts["lyrics_text"]` and
`ctx.artifacts["lyrics_format"]` (line 76-77). The plan's version omits
this — it doesn't store these in artifacts. If any downstream consumer
reads `ctx.artifacts["lyrics_text"]`, this is a regression.

**Recommendation:** Verify that no downstream stage or artifact consumer
reads `lyrics_text` or `lyrics_format` from artifacts. If they do, keep
the artifact assignment.

---

## 8. StemWorker has no ready signal — the plan's justification is inconsistent

**Severity: low** (correctness of the plan, not a bug)

The plan says (line 189-193):

> StemWorker doesn't use a ready signal today — its first `separate()`
> call eats the load latency. We adopt a ready signal for whisper because
> the orchestrator's `start()` already blocks on `load_model()` today.

This is accurate — the orchestrator's `start()` currently calls
`self._whisper_worker.load_model()` which blocks. The ready signal
preserves this property.

However, this means `start()` now blocks for **both** workers' model
loads sequentially: stem worker model load (~7s) + ready wait, then
whisper worker model load (~10s) + ready wait. Total: ~17s. This is the
same as today (stem subprocess spawns + loads, then whisper loads
in-process), so no regression. But the plan should note that the two
loads could be parallelized in the future since they are now both
asynchronous subprocess startups.

---

## 9. `refine_steps` is typed as `str` but used as a string argument — potential type confusion

**Severity: low**

`WhisperModelConfig.refine_steps` is typed as `str` with default `"se"`.
In the current `refine()` method, it's passed as `steps=self._config.refine_steps`.
If stable-ts expects an `int` for `steps` (number of refinement passes),
this would be a type error. The plan does not address this — it passes
`config_dict` through to `_do_align_refine` which would use the same
string value.

This is a pre-existing issue, not introduced by the plan, but it could
surface during testing of the subprocess path.

---

## 10. Translation file cleanup scope is understated

**Severity: medium**

The plan mentions (line 448-449):

> Remove `refining lyrics` translation strings from any `.po` files.

There are **15** `.po` files in the project. Each one will need the
`refining lyrics` msgid/msgstr pair removed (or marked obsolete). This is
not just a cleanup — if the `.po` files reference a msgid that no longer
exists in the source templates, `babel` or `pybabel` may emit warnings
during compilation, and the `.mo` files will carry dead entries.

Additionally, the `case 'refine':` branch in `processing.html` (line 119)
uses `{% trans %}refining lyrics{% endtrans %}` — removing the case branch
is straightforward, but the corresponding msgid in each `.po` file must
also be handled.

**Recommendation:** After removing the `case 'refine'` branch from
`processing.html`, run `pybabel extract` + `pybabel update` to
automatically mark the orphaned msgid as obsolete in all `.po` files.
Do not manually edit 15 files.

---

## 11. `AlignmentCancelledError` exception class location after the move

**Severity: medium**

Currently `AlignmentCancelledError` is defined in `whisper_worker.py`
(line 38). After the move, the parent still needs this exception:
`_model_call` in `lyric_align.py` catches it and translates to
`PipelineCancelled`. The plan says the parent's `_run_job` raises
`AlignmentCancelledError` on `("cancelled",)` (line 358).

But after the move, `whisper_worker.py` becomes the **parent-side
facade** module. The subprocess-side code also has a concept of
cancellation (`_CancelledInsideEncoder`), but that stays inside the
subprocess. The plan should clarify:

- `AlignmentCancelledError` stays in `whisper_worker.py` (the parent-side
  module) and is raised by `_run_job` on receipt of `("cancelled",)`.
- `lyric_align.py` continues to import it from `whisper_worker`.
- `_CancelledInsideEncoder` stays as a module-level class inside
  `whisper_worker.py` (used only by `_worker_main` in the subprocess).

This is likely the intended design but is not stated explicitly, which
could cause confusion during implementation.

---

## 12. The `_route_to_pty` context manager is process-scoped in a subprocess

**Severity: medium**

The plan notes (line 559-563):

> The existing `_route_to_pty` context manager moves as-is into the
> subprocess module-level helpers; it is still useful for scoping
> CTranslate2 output around inference calls.

In the subprocess, `dup2(pty_fd, 1)` and `dup2(pty_fd, 2)` happen at
`_worker_main` entry (permanent redirection), AND `_route_to_pty` is
used as a context manager around inference calls (temporary redirection
with save/restore). Since the entry-level `dup2` already set fds 1 and 2
to the PTY, the `_route_to_pty` context manager would be a no-op in the
subprocess — it saves the current fd 1/2 (which are already the PTY),
redirects them to the PTY (no change), and restores them (no change).

If `_route_to_pty` was intended to scope **only** certain output to the
PTY while suppressing other output, the entry-level `dup2` defeats that
purpose — ALL stdout/stderr goes to the PTY regardless.

If `_route_to_pty`'s purpose is to ensure CTranslate2 output goes to the
PTY even when something else temporarily redirected fds (unlikely in a
single-threaded subprocess), it's a no-op but harmless.

**Recommendation:** Clarify whether `_route_to_pty` is still needed inside
the subprocess. If the entry-level `dup2` makes it redundant, removing it
simplifies the subprocess code. If it's needed for scoped output routing
(e.g., to suppress CTranslate2 output between calls), the entry-level
`dup2` should NOT happen, and `_route_to_pty` should be the only routing
mechanism.

---

## 13. No deadlock analysis for the ready-signal blocking pattern

**Severity: medium**

The plan's `start()` method blocks on `result_recv.poll(0.5)` in a loop
until `("ready",)` is received. If the subprocess takes > 60s to load
(the `WHISPER_LOAD_TIMEOUT_SEC`), it's killed.

But there is a subtle issue: `result_recv` is a `Pipe(duplex=False)`. If
the subprocess sends `("ready",)` and the parent is not yet polling, the
byte sits in the pipe buffer — no data loss. However, if the subprocess
sends `("error", msg)` instead of `("ready",)` and then immediately exits
(closing its end of the pipe), the parent's `poll` will see the data and
`recv` will get the error message. This is handled by the plan's
`raise RuntimeError(f"Unexpected boot message: {msg}")`.

**What about partial writes?** `multiprocessing.Pipe` uses pickle
serialization. A pickle write is atomic at the OS level for messages
under `PIPE_BUF` size (typically 4KB on Linux, 64KB on some systems).
The `("ready",)` tuple is tiny, so no concern. But if a future change
sends large payloads on the result pipe (e.g., a large `line_objects`
list for a 10-minute song with 5000+ words), the pickle could exceed
`PIPE_BUF` and a concurrent `poll` + `recv` could see partial data.

In practice, `Pipe` uses `Connection.send()` which does a full pickle +
write, and `Connection.recv()` blocks until the full message is
available. `poll()` returns True only when a complete message is
readable. So **no actual deadlock risk** from partial writes.

However, there is a **potential hang** if the subprocess is killed
(SIGKILL) between loading the model and sending `("ready",)`. In that
case, the pipe's write end is closed (OS reclaims the fd), the parent's
`poll` eventually returns True (EOF), and `recv` raises `EOFError`. The
plan's loop should catch `EOFError` and convert it to `WorkerDiedError`.

**Recommendation:** Add `except EOFError: raise WorkerDiedError(...)`
to the `start()` ready-wait loop, alongside the `is_alive()` check.

---

## 14. Auto-restart race: `_run_job` calls `self.start()` which blocks

**Severity: medium**

The plan says `_run_job` mirrors `StemWorker.separate()`:

> Auto-restart if `proc is not None and not proc.is_alive()`
> (preserves the OOM-recovery property landed in `8463af8`).

`StemWorker.separate()` calls `self.start()` on a dead process, which
creates fresh pipes and spawns a new subprocess. This is a non-blocking
call (no ready signal in stem worker).

The **whisper** `start()` blocks for up to 60s waiting for `("ready",)`.
If auto-restart is triggered during `align_refine`, the calling thread
blocks for ~10s while the whisper model reloads. This is acceptable
behavior (the plan acknowledges 5-30s model-load latency on restart).

But there's a concurrency concern: if the orchestrator's pipeline thread
is blocked in `start()` during auto-restart, and the user issues a
cancel, the cancel `threading.Event` is set. The `_forward_cancel` thread
would try to write to `cancel_send` — but `start()` just created new
pipes, and the cancel-forwarder from the **previous** job's pipe is
writing to the old (now-closed) pipe. The new job's `_forward_cancel`
thread is not started until `_run_job` sends the job tuple.

**This means a cancel signal during auto-restart is silently dropped.**
The user clicks cancel, but the pipeline thread is blocked in `start()`,
and no cancel-forwarder is active for the new subprocess.

**Recommendation:** Either:
- (a) After auto-restart `self.start()` completes in `_run_job`, check
  `cancel_event.is_set()` before sending the job tuple, and raise
  `AlignmentCancelledError` if already cancelled.
- (b) Register the cancel-forwarder before sending the job tuple (the
  plan already does this in step 4 of `_run_job`, but the check in (a)
  covers the restart window specifically).

---

## 15. `asdict(self._config)` may not produce JSON-serializable values

**Severity: low**

The plan uses `asdict(self._config)` to convert `WhisperModelConfig` to a
dict for passing to the subprocess (line 318). `WhisperModelConfig` is a
simple dataclass with `str`, `bool`, `int`, and `float` fields — all
pickle-serializable. `asdict()` returns a plain dict of these primitives,
which is also pickle-serializable. No issue here.

However, if `WhisperModelConfig` ever gains a `Path` field or a nested
non-trivially-picklable field, `asdict()` would silently pass it through
to `Process(args=...)`, which would fail at pickle time with an opaque
error. The plan's choice of `config_dict` is a good defensive measure,
but adding a comment in the dataclass would help future maintainers.

---

## 16. No test coverage for the current whisper worker or lyric_align stage

**Severity: medium** (testing gap, not a plan bug)

The codebase has zero test files for `whisper_worker` or `lyric_align`.
The plan proposes new tests (lines 614-633), but the migration order
(step 1: "Add new APIs alongside old") doesn't include adding tests for
the **current** behavior first. This means the migration has no
regression baseline.

**Recommendation:** Before step 1, add characterization tests for the
current in-process `WhisperWorker` (or at minimum for
`LyricAlignStage._extract_words`, `_match_words_to_lines`, and
`_segments_to_line_objects`). These tests can then be refactored to test
the subprocess boundary in later steps.

---

## 17. `is_segment_first` field semantics depend on regroup

**Severity: medium**

The `LineObject` / `Word` contract (lines 128-148) includes
`is_segment_first: bool` on each `Word`. This field is set by
`_extract_words` (current code) or the subprocess-side equivalent based
on `segment.words[i] == segment.words[0]`.

The `_generate_ass` method uses `is_segment_first` for the
`first_word_nudge_cs` clipping fix (lyric_align.py line 227-232). This
nudge pushes back the first word of a **segment** if it starts too soon
after the previous event.

When `regroup()` is applied (transcription mode), segment boundaries
change. The `is_segment_first` flags must be computed **after** regroup,
not before. The current code computes them inside `_segments_to_line_objects`,
which runs after regroup — correct. The plan's subprocess-side
`_do_transcribe_refine` must do the same: regroup → then extract words
with `is_segment_first` based on the post-regroup segments.

**Recommendation:** Add an explicit note in the plan that
`is_segment_first` must be computed from the post-regroup segment
structure, not from the original transcription segments.

---

## 18. GPU memory state logging on OOM assumes CUDA is still usable

**Severity: low**

The plan's OOM diagnostics (lines 523-531) call
`torch.cuda.memory_allocated()`, `torch.cuda.memory_reserved()`, and
`torch.cuda.max_memory_allocated()` after catching `OutOfMemoryError`.

On some CUDA driver versions and hardware, querying memory state after
OOM can itself fail (the CUDA context may be corrupted). The code wraps
this in a `try/except` in the plan's job loop (the error branch), but
the diagnostic logging code itself has no try/except.

**Recommendation:** Wrap the GPU memory logging in its own try/except so
a failed query doesn't prevent the `("error", ...)` message from being
sent on the result pipe.

---

## Summary

| # | Finding | Severity |
|---|---------|----------|
| 1 | fork-after-CUDA not mitigated; `spawn` not enforced | high |
| 2 | `WorkerDiedError` not available to whisper worker | high |
| 4 | Cancel signal lost between align and refine in subprocess | medium |
| 5 | `_forward_cancel` sends only one byte — insufficient for two-phase jobs | medium |
| 10 | Translation file cleanup scope understated (15 .po files) | medium |
| 11 | `AlignmentCancelledError` location not stated explicitly after move | medium |
| 12 | `_route_to_pty` is a no-op inside the subprocess | medium |
| 13 | Missing `EOFError` handling in `start()` ready-wait loop | medium |
| 14 | Cancel signal dropped during auto-restart blocking window | medium |
| 16 | No test baseline for current whisper/lyric_align behavior | medium |
| 17 | `is_segment_first` must be computed post-regroup | medium |
| 3 | Re-extraction of line_objects after refine (confirmed correct) | — |
| 6 | `compute_type` field not passed through to load_model | low |
| 7 | `lyrics_text`/`lyrics_format` artifacts not set in plan's stage code | low |
| 8 | Sequential model loads — no regression but parallelizable in future | low |
| 9 | `refine_steps` typed as `str` — pre-existing, not plan-introduced | low |
| 15 | `asdict()` fragile to future non-picklable fields | low |
| 18 | GPU memory logging on OOM assumes CUDA is still usable | low |
