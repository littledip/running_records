import pytest

from src.karaoke import build_target_word_timings
from src.models import WordSegment


def _segments(words_with_times):
    return [
        WordSegment(word=w, start_time=s, end_time=e, confidence=0.95)
        for w, s, e in words_with_times
    ]


def test_all_words_matched_returns_timing_for_each():
    target = "the cat sat"
    transcript = "the cat sat"
    segments = _segments([("the", 0.0, 0.3), ("cat", 0.4, 0.7), ("sat", 0.8, 1.1)])

    timings = build_target_word_timings(target, transcript, segments)

    assert timings == [(0.0, 0.3), (0.4, 0.7), (0.8, 1.1)]


def test_omission_produces_none_at_that_position():
    target = "the quick brown fox"
    transcript = "the fox"
    segments = _segments([("the", 0.0, 0.3), ("fox", 0.4, 0.7)])

    timings = build_target_word_timings(target, transcript, segments)

    assert timings == [(0.0, 0.3), None, None, (0.4, 0.7)]


def test_insertion_does_not_consume_a_target_position():
    target = "the cat sat"
    transcript = "the big cat sat"
    segments = _segments(
        [("the", 0.0, 0.3), ("big", 0.4, 0.6), ("cat", 0.7, 1.0), ("sat", 1.1, 1.4)]
    )

    timings = build_target_word_timings(target, transcript, segments)

    assert len(timings) == len(target.split())
    assert timings == [(0.0, 0.3), (0.7, 1.0), (1.1, 1.4)]


def test_substitution_still_gets_transcript_timing():
    target = "the cat sat"
    transcript = "the bat sat"
    segments = _segments([("the", 0.0, 0.3), ("bat", 0.4, 0.7), ("sat", 0.8, 1.1)])

    timings = build_target_word_timings(target, transcript, segments)

    assert timings == [(0.0, 0.3), (0.4, 0.7), (0.8, 1.1)]


def test_empty_target_text_returns_empty_list():
    assert build_target_word_timings("", "the cat sat", _segments([("the", 0.0, 0.3)])) == []


def test_empty_word_segments_returns_all_none():
    timings = build_target_word_timings("the cat sat", "the cat sat", [])
    assert timings == [None, None, None]


@pytest.mark.parametrize(
    "target,transcript,segments",
    [
        ("the cat sat", "the cat sat", [("the", 0, 0.3), ("cat", 0.4, 0.7), ("sat", 0.8, 1.1)]),
        ("the quick brown fox", "the fox", [("the", 0, 0.3), ("fox", 0.4, 0.7)]),
        ("the cat sat", "the big cat sat", [("the", 0, 0.3), ("big", 0.4, 0.6), ("cat", 0.7, 1.0), ("sat", 1.1, 1.4)]),
    ],
)
def test_result_length_matches_target_word_count(target, transcript, segments):
    timings = build_target_word_timings(target, transcript, _segments(segments))
    assert len(timings) == len(target.split())
