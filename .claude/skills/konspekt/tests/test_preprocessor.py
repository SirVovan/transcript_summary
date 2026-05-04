import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from preprocessor import estimate_tokens, parse_transcript_lines, time_to_seconds


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_estimate_tokens_proportional():
    t1 = estimate_tokens("а" * 100)
    t2 = estimate_tokens("а" * 200)
    assert t2 == t1 * 2


def test_parse_hhmmss():
    lines = parse_transcript_lines("[00:01:30] Привет мир\n[00:02:00] Второй")
    assert len(lines) == 2
    assert lines[0]['seconds'] == 90
    assert lines[0]['text'] == 'Привет мир'
    assert lines[1]['seconds'] == 120


def test_parse_mmss():
    lines = parse_transcript_lines("[01:30] Текст")
    assert lines[0]['seconds'] == 90


def test_parse_no_timestamp_appends_to_prev():
    lines = parse_transcript_lines("[00:01:00] Начало\nпродолжение")
    assert len(lines) == 1
    assert 'продолжение' in lines[0]['text']


def test_time_to_seconds_mmss():
    assert time_to_seconds("01:30") == 90


def test_time_to_seconds_hhmmss():
    assert time_to_seconds("01:02:03") == 3723


def test_split_creates_two_chunks(tmp_path):
    content = '\n'.join(f"[00:{i:02d}:00] {'слово ' * 30}" for i in range(60))
    transcript = tmp_path / "test.txt"
    transcript.write_text(content, encoding='utf-8')

    from preprocessor import split
    chunks = split(str(transcript), ["00:30:00"])
    assert len(chunks) == 2
    for c in chunks:
        assert os.path.exists(c)


def test_split_overlap_present(tmp_path):
    content = '\n'.join(f"[00:{i:02d}:00] {'слово ' * 50}" for i in range(60))
    transcript = tmp_path / "test.txt"
    transcript.write_text(content, encoding='utf-8')

    from preprocessor import split
    chunks = split(str(transcript), ["00:30:00"])

    text2 = open(chunks[1], encoding='utf-8').read()
    # chunk2 должен начинаться раньше 00:30:00 из-за перекрытия
    assert any(f"00:{m:02d}:" in text2 for m in range(27, 30))
