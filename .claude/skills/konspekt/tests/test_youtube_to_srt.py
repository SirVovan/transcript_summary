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
