import os
from typing import Optional, Tuple, List
import numpy as np
from rapidfuzz import fuzz
from .models import RunningRecordResult, AlignmentResult, ErrorType, AlignmentMetrics


class AlignmentEngine:
    def __init__(self, phonetic_threshold: float = 0.75, homophone_tolerance: bool = True):
        self.phonetic_threshold = phonetic_threshold
        self.homophone_tolerance = homophone_tolerance

    # Needleman-Wunsch scoring. A match must beat splitting a substitution into
    # a separate omission + insertion (MISMATCH > 2 * GAP), so real substitutions
    # stay paired while genuine gaps are recovered globally.
    _MATCH = 2
    _MISMATCH = -1
    _GAP = -1

    def align_texts(self, target_text: str, transcript_text: str) -> Tuple[List[str], List[str]]:
        """Align target vs transcript words with global (Needleman-Wunsch) alignment.

        Produces two equal-length lists where each position is a matched/substituted
        pair, an omission (target word / ""), or an insertion ("" / transcript word).
        Global cost minimisation avoids the greedy failure where a single omission
        whose neighbours recur later desyncs the two sequences.
        """
        target_words = [w.strip().lower() for w in target_text.split()]
        transcript_words = [w.strip().lower() for w in transcript_text.split()]
        n, m = len(target_words), len(transcript_words)

        def sub_score(t_word: str, tr_word: str) -> int:
            same = t_word == tr_word or self._is_homophone(t_word, tr_word)
            return self._MATCH if same else self._MISMATCH

        # Score matrix; first row/column are pure gaps.
        score = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            score[i][0] = i * self._GAP
        for j in range(1, m + 1):
            score[0][j] = j * self._GAP

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                diag = score[i - 1][j - 1] + sub_score(target_words[i - 1], transcript_words[j - 1])
                up = score[i - 1][j] + self._GAP       # target word consumed → omission
                left = score[i][j - 1] + self._GAP     # transcript word consumed → insertion
                score[i][j] = max(diag, up, left)

        # Backtrace from (n, m). Prefer diagonal (match/substitution) on ties.
        aligned_target: List[str] = []
        aligned_transcript: List[str] = []
        i, j = n, m
        while i > 0 or j > 0:
            if (
                i > 0 and j > 0
                and score[i][j] == score[i - 1][j - 1] + sub_score(target_words[i - 1], transcript_words[j - 1])
            ):
                aligned_target.append(target_words[i - 1])
                aligned_transcript.append(transcript_words[j - 1])
                i -= 1
                j -= 1
            elif i > 0 and score[i][j] == score[i - 1][j] + self._GAP:
                aligned_target.append(target_words[i - 1])
                aligned_transcript.append("")
                i -= 1
            else:
                aligned_target.append("")
                aligned_transcript.append(transcript_words[j - 1])
                j -= 1

        aligned_target.reverse()
        aligned_transcript.reverse()
        return aligned_target, aligned_transcript

    def _is_homophone(self, word1: str, word2: str) -> bool:
        """Check if words are likely homophones (phonetically similar)."""
        return fuzz.token_sort_ratio(word1, word2) > self.phonetic_threshold * 100

    def classify_error(
        self, 
        target_word: str, 
        transcript_word: str, 
        offset_seconds: float = 0.0
    ) -> ErrorType:
        """Classify the error type using rule-based heuristics."""
        # Child added a word that wasn't in the target text → insertion
        if target_word == "" and transcript_word != "":
            return ErrorType(
                error_type="insertion",
                confidence=0.95,
                reason=f"Extra word '{transcript_word}' not in target text",
                target_word=None
            )
            
        # Child skipped a word that should have been there → omission
        if target_word != "" and transcript_word == "":
            return ErrorType(
                error_type="omission",
                confidence=0.90,
                reason=f"Target word '{target_word}' missing from transcription",
                target_word=target_word
            )
            
        # Both empty → self-correction (word was attempted but corrected)
        if target_word == "" and transcript_word == "":
            return ErrorType(
                error_type="self_correction",
                confidence=0.85,
                reason=f"Self-correction detected at offset {offset_seconds:.2f}s",
                target_word=None
            )
            
        # Both present. Homophones are identical in speech and indistinguishable
        # to ASR, so they are not counted as errors. Defer to the same
        # _is_homophone check the aligner uses so the two stages agree.
        if self._is_homophone(target_word, transcript_word):
            return ErrorType(
                error_type="unknown",
                confidence=0.50,
                reason="Homophone — not counted as a reading error",
                target_word=target_word
            )

        # Both present → substitution check
        ratio = fuzz.ratio(target_word.lower(), transcript_word.lower())
        phonetic_ratio = fuzz.token_sort_ratio(target_word.lower(), transcript_word.lower())

        if ratio < 85 or phonetic_ratio < 70:
            return ErrorType(
                error_type="substitution",
                confidence=0.92,
                reason=f"Phonetic mismatch (ratio={ratio:.1f}%, token_sort={phonetic_ratio:.1f}%)",
                target_word=target_word
            )
            
        # Words match closely enough → no error
        return ErrorType(
            error_type="unknown",
            confidence=0.50,
            reason=f"Close match (ratio={ratio:.1f}%) — likely correct",
            target_word=target_word
        )

    def calculate_metrics(self, result: RunningRecordResult) -> AlignmentMetrics:
        """Calculate accuracy, WPM, and reading rate variance based on alignment."""
        segments = result.word_segments
        duration_s = result.metadata.get("duration_s", 0.0)
        
        # Always compute alignment — this is the source of truth for accuracy
        aligned_target, aligned_transcript = self.align_texts(
            result.target_text,
            result.transcript_text
        )
        
        # Running words = number of words in the target passage (Running Record
        # convention), independent of what was read.
        running_words = len(result.target_text.split())
        if running_words == 0:
            return AlignmentMetrics(
                accuracy=0.0,
                wpm=0.0,
                reading_rate_variance=0.0,
                total_words=0,
                error_count=0
            )

        # error_count and accuracy share one source of truth: the assembled
        # errors list. Accuracy = (running words - errors) / running words,
        # clamped at 0 (insertions can push errors above the passage length).
        error_count = len(self._detect_errors(aligned_target, aligned_transcript))
        accuracy = max(0.0, (running_words - error_count) / running_words)

        # WPM calculation — only if we have timing data
        wpm = (running_words * 60) / duration_s if duration_s > 0 else 0.0

        # Reading rate variance — needs word-level segments
        if segments and len(segments) > 1:
            timestamps = np.array([s.end_time for s in segments])
            reading_rate_variance = float(np.std(timestamps))
        else:
            reading_rate_variance = 0.0

        return AlignmentMetrics(
            accuracy=accuracy,
            wpm=wpm,
            reading_rate_variance=reading_rate_variance,
            total_words=running_words,
            error_count=error_count
        )

    def _detect_errors(self, aligned_target: List[str], aligned_transcript: List[str]) -> List[ErrorType]:
        """Turn an alignment into a list of errors, derived entirely from the alignment.

        Substitutions come straight from ``classify_error``. Omissions and insertions
        are held back: when the same word is both omitted (at one position) and
        inserted (at another), that is a genuine reordering — reported once as a
        ``word_order`` error rather than as a separate omission + insertion.
        """
        errors: List[ErrorType] = []
        omissions: List[Tuple[str, ErrorType]] = []    # (omitted word, error), in order
        insertions: List[Tuple[str, ErrorType]] = []   # (inserted word, error), in order

        for tgt_word, tr_word in zip(aligned_target, aligned_transcript):
            error = self.classify_error(tgt_word, tr_word)
            if error.error_type == "unknown":
                continue
            if error.error_type == "omission":
                omissions.append((tgt_word, error))
            elif error.error_type == "insertion":
                insertions.append((tr_word, error))
            else:
                errors.append(error)

        # Pair each omission with an insertion of the same word → reordering.
        remaining_insertions = list(insertions)
        for word, om in omissions:
            paired = next((pair for pair in remaining_insertions if pair[0] == word), None)
            if paired is not None:
                remaining_insertions.remove(paired)
                errors.append(ErrorType(
                    error_type="word_order",
                    confidence=0.85,
                    reason=f"Word '{word}' read out of order (transposed with a neighbouring word)",
                    target_word=word,
                ))
            else:
                errors.append(om)

        errors.extend(err for _, err in remaining_insertions)
        return errors

    def process_result(self, result: RunningRecordResult) -> AlignmentResult:
        """Process a complete transcription result and return structured alignment output."""
        # Align texts
        aligned_target, aligned_transcript = self.align_texts(
            result.target_text,
            result.transcript_text
        )
        
        errors = self._detect_errors(aligned_target, aligned_transcript)

        # Calculate metrics
        metrics = self.calculate_metrics(result)
        
        return AlignmentResult(
            target_text=result.target_text,
            transcript_text=result.transcript_text,
            word_segments=result.word_segments,
            errors=errors,
            metrics=metrics
        )
