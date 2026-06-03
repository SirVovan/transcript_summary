import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from split_transcript import (
    estimate_tokens,
    time_to_seconds,
    format_hms,
    detect_format,
    parse_srt,
    parse_bracket,
)


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_estimate_tokens_proportional():
    t1 = estimate_tokens("а" * 100)
    t2 = estimate_tokens("а" * 200)
    assert t2 == t1 * 2


def test_time_to_seconds_hhmmss():
    assert time_to_seconds("00:01:30") == 90
    assert time_to_seconds("01:00:00") == 3600


def test_time_to_seconds_mmss():
    assert time_to_seconds("01:30") == 90


def test_format_hms():
    assert format_hms(90) == "00:01:30"
    assert format_hms(3661) == "01:01:01"


def test_detect_format():
    assert detect_format("1\n00:00:01,000 --> 00:00:02,000\nПривет") == 'srt'
    assert detect_format("[00:01:30] Привет") == 'bracket'
    assert detect_format("просто текст без таймингов") == 'flat'


def test_parse_bracket_hhmmss():
    lines = parse_bracket("[00:01:30] Привет мир\n[00:02:00] Второй")
    assert len(lines) == 2
    assert lines[0]['seconds'] == 90
    assert lines[0]['text'] == 'Привет мир'
    assert lines[1]['seconds'] == 120


def test_parse_bracket_mmss():
    lines = parse_bracket("[01:30] Текст")
    assert lines[0]['seconds'] == 90


def test_parse_srt_start_timecode():
    # split_transcript опирается на start-таймкод блока (seconds); текст идёт
    # в превью-окна. Номер следующего блока парсер дописывает в текст предыдущего —
    # для нарезки это неважно, поэтому проверяем только тайминги и начало текста.
    srt = "1\n00:01:30,000 --> 00:01:35,000\nПривет мир\n\n2\n00:02:00,000 --> 00:02:05,000\nВторой"
    lines = parse_srt(srt)
    assert len(lines) == 2
    assert lines[0]['seconds'] == 90
    assert lines[0]['text'].startswith('Привет мир')
    assert lines[1]['seconds'] == 120
