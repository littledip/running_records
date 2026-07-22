# Technical Concerns Register

A living list of known technical concerns and deferred work for `running_records`, kept for recap/review. These are **not decisions** (those go in `docs/adr/`) — they are open items to evaluate later.

Last updated: 2026-06-19

---

## Deferred: transformers / Whisper console noise & fixes

During real transcription runs, [`src/pipeline.py`](../src/pipeline.py) emits a lot of `[transformers]` output. Investigated and **deferred** — none of it affects correctness; runs transcribe fine. Three separable pieces of work:

1. **Pass `language="en"` + `task="transcribe"`** to the pipeline (`pipeline.py:28-34`). *Highest value — a real improvement, not just silencing.* Removes the biggest warnings, skips the language-detection pass (slightly faster), and forces deterministically-English transcription (correct for a reading-assessment tool; avoids mis-detect on a mumbled read).
2. **Lower transformers log verbosity** (`transformers.logging.set_verbosity_error()`). Optional, cosmetic. Silences the remaining deprecation warnings and the repeated `ModuleNotFoundError: No module named 'torchvision'` tracebacks (transformers 5.x lazily probes optional vision components we don't use — benign). Blunt: also hides all *future* transformers warnings, so keep it as a separate layer from #1.
3. **Fix the MPS device selection** at `pipeline.py:31`: `device=0 if self.device == "mps" else -1`. In transformers `device=0` means **CUDA:0**, not MPS — so on Apple Silicon the model is **not** using the GPU (likely CPU fallback). To actually use MPS, pass `device="mps"`. A latent performance bug, orthogonal to the log noise.

> Note: these are unrelated to the current `refactor/ux-polish` branch theme — when picked up, they belong on a fresh branch off `main`.

---

## In progress: alignment engine is greedy, not global (correctness bug)

**Most consequential correctness issue found so far.** [`src/alignment.py`](../src/alignment.py) `align_texts()` is a greedy one-pass heuristic, not a real sequence alignment. A single mid-sentence omission whose neighbouring words recur later in the text desyncs the target/transcript pointers and cannot recover.

Reproducer: target `"The rain in Spain stays mainly in the plain."` vs transcript `"The rain in Spain stays in the plain."`. The only true omission is `mainly`, but the engine:
- **never reports `mainly`** (it drops out of the alignment entirely), and
- **double-counts `in`, `the`, `plain.`** — each emitted once as a false insertion/match and again as a false omission.

Because accuracy %, error count, and the WPM basis all derive from this alignment, the metrics are also wrong in these cases — not just the error list.

**Fix (DONE — Option A):** replaced the greedy pass with global **Needleman–Wunsch** alignment in `align_texts()`, using the fuzzy/phonetic ratio as match-vs-substitute cost so homophone tolerance is preserved. Driven by TDD (4 new tests in `tests/test_alignment.py`: mid-sentence omission, multiple omissions, insertion, substitution-stays-paired). On the reproducer, `mainly` is now the only omission (accuracy 8/9); false omissions of `in`/`the`/`plain.` are gone. Full suite green.

## DONE: word-order pass now derived from the alignment

Was: the word-order second pass compared each shared word's **raw index** in target vs transcript, so any omission/insertion shifted following words' indices by one and those correctly-read words got flagged as `word_order` errors (e.g. `in`, `the`, `plain.` after `mainly` was omitted).

**Fixed (Option A, TDD):** the two-pass logic in `process_result` was replaced by a single `_detect_errors()` method that derives all errors from the alignment. A `word_order` error is now only reported when the **same word is both omitted and inserted** in the alignment (a genuine move); a uniform positional shift after a gap is no longer flagged. Genuine transpositions (e.g. `the cat` → `cat the`) are still caught. Tests: `test_omission_shift_does_not_create_word_order_errors`, `test_genuine_transposition_flagged_as_word_order`.

## DONE: `error_count` reconciled with the errors list (#3)

`calculate_metrics` used to count `error_count` independently (non-matching alignment cells), which diverged from `_detect_errors` (a transposition is two cells but one `word_order` error → `error_count=2` vs `len(errors)=1`). Fixed: `error_count` is now `len(self._detect_errors(...))`, so the headline metric and the detailed list share one source of truth. Test: `test_error_count_matches_errors_list_for_transposition`.

## DONE: accuracy derived from the miscue count (Running Record convention)

`accuracy` used to be `correct_words / total_words` over **alignment cells** with raw string-equality, so it disagreed with `error_count` (transposition read 0.5 with 1 error; homophone read 0.778 with 1 error).

**Fixed:** `calculate_metrics` now uses the Running Record formula — **`accuracy = (running_words - error_count) / running_words`**, clamped at 0. `running_words` is the target passage length (`len(target_text.split())`); `error_count` is the same `_detect_errors` list. `total_words` reported is now running words (not alignment cells), and WPM is over running words. Accuracy and the Detailed Errors list can no longer diverge. Homophone read is now 88.9% (8/9); transposition is 66.7% (2/3). Tests: `test_accuracy_derived_from_error_count_homophone`, `test_accuracy_consistent_with_errors_transposition`, `test_total_words_is_passage_length_not_alignment_cells`, `test_accuracy_clamped_at_zero_with_excess_insertions`.

## DONE: homophones no longer count as errors (#2)

Decided (assessment-design call): true homophones (e.g. `plain`/`plane`) are indistinguishable to ASR and must not count as reading errors. `classify_error` now defers to the same `_is_homophone` check the aligner uses (before the substitution check), so the two stages agree and homophones return no error. Tests: `test_homophone_is_not_a_substitution`, `test_homophone_produces_no_error_in_pipeline`.

---

## Broader architectural concerns to evaluate

Higher-level concerns about the ASR/deployment approach. Candidates for review; not yet validated or scheduled.

1. **Dependency footprint.** `torch` + `transformers` + `whisper-medium` is a large install and a heavy model to load. May be a concern for deployment size, cold-start time, and hosting cost.

2. **Local-only inference.** Recording (`sounddevice`) and ASR both run on the machine hosting Streamlit. This does not scale to real multi-user or cloud deployment, where audio capture and model inference would need to be decoupled from a single host.

3. **Model choice / accuracy.** Whether `whisper-medium` is the right size for the accuracy/speed/cost trade-off, or whether to swap the backend (e.g. `faster-whisper`, a hosted/API-based ASR, or a smaller/larger Whisper variant). Tied to concerns #1 and #2.
