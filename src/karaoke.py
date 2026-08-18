"""Map target-passage words to transcript timing for synced playback highlighting.

Reuses AlignmentEngine.align_texts rather than reimplementing alignment. No
Streamlit imports — this stays part of the UI-agnostic core.
"""
from typing import List, Optional, Tuple

from .alignment import AlignmentEngine
from .models import WordSegment


def build_target_word_timings(
    target_text: str,
    transcript_text: str,
    word_segments: List[WordSegment],
    engine: Optional[AlignmentEngine] = None,
) -> List[Optional[Tuple[float, float]]]:
    """Return one entry per `target_text.split()` word: (start_time, end_time)
    if the audio actually said something there (match or substitution), else
    None (omission — no timing, should never be highlighted).
    """
    target_words = target_text.split()
    if not target_words:
        return []
    if not word_segments:
        return [None] * len(target_words)

    engine = engine or AlignmentEngine()
    aligned_target, aligned_transcript = engine.align_texts(target_text, transcript_text)

    timings: List[Optional[Tuple[float, float]]] = []
    transcript_idx = 0
    for t, tr in zip(aligned_target, aligned_transcript):
        if t != "" and tr != "":
            seg = word_segments[transcript_idx]
            timings.append((seg.start_time, seg.end_time))
            transcript_idx += 1
        elif t != "" and tr == "":
            timings.append(None)
        elif t == "" and tr != "":
            transcript_idx += 1

    return timings
