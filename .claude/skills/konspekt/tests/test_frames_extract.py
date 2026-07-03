"""Тесты для cookies_spec.py."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import cookies_spec
import frames_extract

from pathlib import Path
from PIL import Image


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
    assert res[0] == 0.0
    assert res[-1] == 199.0


def test_dedup_by_gap_cap_zero():
    assert frames_extract.dedup_by_gap([1.0, 2.0], min_gap=0.0, cap=0) == []


def test_dedup_by_gap_returns_shorter_list_unchanged():
    assert frames_extract.dedup_by_gap([1.0, 2.0, 3.0], min_gap=0.0, cap=10) == [1.0, 2.0, 3.0]


# Task 2.5: _cand_num / contact_sheet tests
def _png(path, size=(160, 90), color=(20, 40, 60)):
    Image.new("RGB", size, color).save(path)


def test_cand_num_from_name():
    assert frames_extract._cand_num(Path("cand_0007.png")) == 7


def test_contact_sheet_builds(tmp_path):
    frames = []
    for i in (1, 2, 3):
        p = tmp_path / f"cand_{i:04d}.png"
        _png(p); frames.append(p)
    out = tmp_path / "contact_sheet.png"
    res = frames_extract.contact_sheet(frames, out, cols=2, thumb_w=100)
    assert res.exists()
    im = Image.open(res)
    assert im.width == 2 * 100          # cols * thumb_w


# Task 2.6: codex_available tests
def test_codex_available_true(monkeypatch):
    class R: returncode = 0
    monkeypatch.setattr(frames_extract.subprocess, 'run', lambda *a, **k: R())
    assert frames_extract.codex_available() is True


def test_codex_available_false(monkeypatch):
    def boom(*a, **k): raise FileNotFoundError()
    monkeypatch.setattr(frames_extract.subprocess, 'run', boom)
    assert frames_extract.codex_available() is False
