"""Тесты для youtube_to_srt.py."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from youtube_to_srt import parse_srt, rebucket, format_srt


# --- parse_srt ---

def test_parse_srt_single_segment():
    srt = "1\n00:00:00,000 --> 00:00:05,000\nПривет мир\n"
    result = parse_srt(srt)
    assert len(result) == 1
    assert result[0]['index'] == 1
    assert result[0]['start_ms'] == 0
    assert result[0]['end_ms'] == 5000
    assert result[0]['text'] == 'Привет мир'


def test_parse_srt_multiple_segments():
    srt = (
        "1\n00:00:00,000 --> 00:00:05,000\nПервый\n\n"
        "2\n00:00:05,000 --> 00:00:10,500\nВторой\n"
    )
    result = parse_srt(srt)
    assert len(result) == 2
    assert result[1]['start_ms'] == 5000
    assert result[1]['end_ms'] == 10500


def test_parse_srt_multiline_text():
    srt = "1\n00:00:00,000 --> 00:00:03,000\nСтрока один\nСтрока два\n"
    result = parse_srt(srt)
    assert result[0]['text'] == 'Строка один Строка два'


def test_parse_srt_empty():
    assert parse_srt('') == []


def test_parse_srt_trailing_whitespace():
    srt = "1\n00:00:00,000 --> 00:00:05,000\nТекст\n\n\n"
    result = parse_srt(srt)
    assert len(result) == 1
    assert result[0]['text'] == 'Текст'


# --- rebucket ---

def _seg(start_ms, end_ms, text):
    return {'index': 0, 'start_ms': start_ms, 'end_ms': end_ms, 'text': text}


def test_rebucket_merges_into_30s_blocks():
    """Сегменты группируются в блоки по началу: floor(start_ms / 30s)."""
    segments = [
        _seg(0, 5000, 'один'),
        _seg(5000, 10000, 'два'),
        _seg(10000, 28000, 'три'),
        _seg(28000, 32000, 'четыре'),     # начинается до 30s — в первый блок
        _seg(32000, 50000, 'пять'),       # начинается после 30s — во второй
        _seg(50000, 58000, 'шесть'),
    ]
    result = rebucket(segments, block_seconds=30)
    assert len(result) == 2
    assert result[0]['start_ms'] == 0
    assert result[0]['end_ms'] == 32000   # реальный конец последнего сегмента блока
    assert result[0]['text'] == 'один два три четыре'
    assert result[1]['start_ms'] == 30000  # выровнен к границе блока
    assert result[1]['end_ms'] == 58000
    assert result[1]['text'] == 'пять шесть'


def test_rebucket_single_segment_under_block():
    segments = [_seg(0, 5000, 'короткий')]
    result = rebucket(segments, block_seconds=30)
    assert len(result) == 1
    assert result[0]['start_ms'] == 0
    assert result[0]['end_ms'] == 5000
    assert result[0]['text'] == 'короткий'


def test_rebucket_segment_longer_than_block():
    """Сегмент длиннее блока — оставить в своём блоке как есть."""
    segments = [_seg(0, 45000, 'длинный')]
    result = rebucket(segments, block_seconds=30)
    assert len(result) == 1
    assert result[0]['text'] == 'длинный'
    assert result[0]['end_ms'] == 45000


def test_rebucket_empty():
    assert rebucket([], block_seconds=30) == []


def test_rebucket_preserves_index_renumber():
    """Индексы перенумеровываются с 1."""
    segments = [
        _seg(0, 5000, 'a'),
        _seg(30000, 35000, 'b'),
        _seg(60000, 65000, 'c'),
    ]
    result = rebucket(segments, block_seconds=30)
    assert [s['index'] for s in result] == [1, 2, 3]
