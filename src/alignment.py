import os
from typing import Optional, Tuple, List
import numpy as np
from rapidfuzz import fuzz, process
from .models import RunningRecordResult, AlignmentResult, ErrorType, AlignmentMetrics


class AlignmentEngine:
    def __init__(self, phonetic_threshold: float = 0.75, homophone_tolerance: bool = True):
        self.phonetic_threshold = phonetic_threshold
        self.homophone_tolerance = homophone_tolerance

    def align_texts(self, target_text: str, transcript_text: str) -> Tuple[List[str], List[str]]:
        """Align target vs transcript words using fuzzy matching.
        
        Handles length mismatches (insertions/omissions) by extending the shorter list with empty markers.
        """
        target_words = [w.strip().lower() for w in target_text.split()]
        transcript_words = [w.strip().lower() for w in transcript_text.split()]

        aligned_target = []
        aligned_transcript = []

        i, j = 0, 0
        while i < len(target_words) or j < len(transcript_words):
            if i >= len(target_words):
                # Transcript has extra words (insertions)
                aligned_target.append("")
                aligned_transcript.append(transcript_words[j])
                j += 1
            elif j >= len(transcript_words):
                # Target has words not in transcript (omissions)
                aligned_target.append(target_words[i])
                aligned_transcript.append("")
                i += 1
            else:
                t_word = target_words[i]
                tr_word = transcript_words[j]

                if self._is_homophone(tr_word, t_word):
                    aligned_target.append(t_word)
                    aligned_transcript.append(tr_word)
                    i += 1
                    j += 1
                else:
                    # Check if transcript word matches any nearby target word (insertion case)
                    best_match = process.extractOne(
                        tr_word, 
                        target_words[i:i+3],  # Look ahead up to 3 words
                        scorer=fuzz.ratio
                    )
                    
                    if best_match and fuzz.ratio(best_match[0], tr_word) >= self.phonetic_threshold * 100:
                        # Transcript word is an insertion (extra word not in target)
                        aligned_target.append("")
                        aligned_transcript.append(tr_word)
                        j += 1
                    else:
                        # Normal comparison
                        if t_word == tr_word:
                            aligned_target.append(t_word)
                            aligned_transcript.append(tr_word)
                        else:
                            # Substitution or mismatch
                            matched = process.extractOne(tr_word, target_words, scorer=fuzz.ratio)
                            if matched and fuzz.ratio(matched[0], tr_word) >= self.phonetic_threshold * 100:
                                aligned_target.append(matched[0])
                                aligned_transcript.append(tr_word)
                            else:
                                aligned_target.append(t_word)
                                aligned_transcript.append(tr_word)
                        i += 1
                        j += 1

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
                reason=f"Target word '{target_word}' missing from transcription at offset {offset_seconds:.2f}s",
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
        
        total_words = len(aligned_target)
        if total_words == 0:
            return AlignmentMetrics(
                accuracy=0.0,
                wpm=0.0,
                reading_rate_variance=0.0,
                total_words=0,
                error_count=0
            )
        
        # Count words where transcript matches target exactly
        correct_words = sum(
            1 for t, tr in zip(aligned_target, aligned_transcript)
            if t.lower() == tr.lower()
        )
        accuracy = correct_words / total_words
        
        # WPM calculation — only if we have timing data
        wpm = (total_words * 60) / duration_s if duration_s > 0 else 0.0
        
        # Reading rate variance — needs word-level segments
        if segments and len(segments) > 1:
            timestamps = np.array([s.end_time for s in segments])
            reading_rate_variance = float(np.std(timestamps))
        else:
            reading_rate_variance = 0.0
        
        error_count = total_words - correct_words
        
        return AlignmentMetrics(
            accuracy=accuracy,
            wpm=wpm,
            reading_rate_variance=reading_rate_variance,
            total_words=total_words,
            error_count=error_count
        )

    def process_result(self, result: RunningRecordResult) -> AlignmentResult:
        """Process a complete transcription result and return structured alignment output."""
        # Align texts
        aligned_target, aligned_transcript = self.align_texts(
            result.target_text,
            result.transcript_text
        )
        
        # First pass: classify errors (substitution, omission, insertion)
        errors = []
        for i, (tgt_word, tr_word) in enumerate(zip(aligned_target, aligned_transcript)):
            error = self.classify_error(tgt_word, tr_word, result.metadata.get("duration_s", 0.0))
            if error.error_type != "unknown":  # <-- FIX: filter out non-errors
                errors.append(error)
        
        # Second pass: detect word_order errors
        # Find words that appear in both target and transcript but at different positions
        target_words = [w.strip().lower() for w in result.target_text.split()]
        transcript_words = [w.strip().lower() for w in result.transcript_text.split()]
        
        # Build position maps (word -> list of positions)
        target_positions = {}
        for i, word in enumerate(target_words):
            if word not in target_positions:
                target_positions[word] = []
            target_positions[word].append(i)
            
        transcript_positions = {}
        for i, word in enumerate(transcript_words):
            if word not in transcript_positions:
                transcript_positions[word] = []
            transcript_positions[word].append(i)
        
        # Find words present in both but misaligned
        for word in set(target_words) & set(transcript_words):
            target_pos = target_positions[word]
            transcript_pos = transcript_positions[word]
            
            # Check if any occurrence is at a different position
            for tp, trp in zip(target_pos, transcript_pos):
                if abs(tp - trp) > 0:  # Different positions -> word_order error
                    errors.append(ErrorType(
                        error_type="word_order",
                        confidence=0.85,
                        reason=f"Word '{word}' appears at position {tp} in target but {trp} in transcript",
                        target_word=word
                    ))
        
        # Calculate metrics
        metrics = self.calculate_metrics(result)
        
        return AlignmentResult(
            target_text=result.target_text,
            transcript_text=result.transcript_text,
            word_segments=result.word_segments,
            errors=errors,
            metrics=metrics
        )
