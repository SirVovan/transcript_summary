"""Тесты для cookies_spec.py."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import cookies_spec
import frames_extract


def test_cookies_args_empty_when_no_browser():
    assert cookies_spec.cookies_from_browser_args('') == []


def test_cookies_args_has_flag():
    args = cookies_spec.cookies_from_browser_args('firefox')
    assert args[0] == '--cookies-from-browser'
    assert 'firefox' in args[1]


# Task 2.2: cue_timecodes tests
SRT = """1
00:00:05,000 --> 00:00:08,000
Смотрите на слайде важный момент

2
00:00:10,000 --> 00:00:12,000
просто болтовня без маркеров

3
00:01:00,000 --> 00:01:03,000
Скопируйте этот промпт себе
"""


def test_cue_timecodes_finds_markers():
    tc = frames_extract.cue_timecodes(SRT)
    assert 5.0 in tc
    assert 60.0 in tc
    assert 10.0 not in tc


# Task 2.3: parse_showinfo_pts tests
SHOWINFO = (
    "[Parsed_showinfo_1 @ 0x..] n:0 pts:123 pts_time:12.5 pos:...\n"
    "[Parsed_showinfo_1 @ 0x..] n:1 pts:456 pts_time:47.0 pos:...\n"
)


def test_parse_showinfo_pts():
    assert frames_extract.parse_showinfo_pts(SHOWINFO) == [12.5, 47.0]


# Task 2.4: dedup_by_gap tests
def test_dedup_by_gap_min_gap():
    assert frames_extract.dedup_by_gap([0.0, 1.0, 2.5, 5.0], min_gap=3.0) == [0.0, 5.0]


def test_dedup_by_gap_cap():
    res = frames_extract.dedup_by_gap([float(i) for i in range(0, 200, 1)], min_gap=0.0, cap=10)
    assert len(res) <= 10
