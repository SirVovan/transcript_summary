"""Тесты для cookies_spec.py."""

import os
import sys

import pytest

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


def test_build_candidates_numbers_successful_frames_without_gaps(tmp_path, monkeypatch):
    calls = []
    md = ("## Сегмент 1 | 00:00:00-00:01:00 | A\n\n"
          "## Сегмент 2 | 00:01:00-00:02:00 | B\n")
    monkeypatch.setattr(frames_extract, 'scene_timecodes', lambda v, threshold: [1.0, 2.0, 65.0])
    monkeypatch.setattr(frames_extract, 'cue_timecodes', lambda s: [])
    monkeypatch.setattr(frames_extract, 'phash_dedup', lambda frames, **k: frames)

    def fake_extract_frame(video, t, out):
        calls.append(t)
        if len(calls) == 2:
            raise frames_extract.subprocess.CalledProcessError(1, ['ffmpeg'])
        _png(out)

    monkeypatch.setattr(frames_extract, 'extract_frame', fake_extract_frame)

    frames, cap = frames_extract.build_candidates('video.mp4', '', md, tmp_path, min_gap=0.0)

    assert [f.name for f, _, _ in frames] == ['cand_0001.png', 'cand_0002.png']
    assert [t for _, t, _ in frames] == [1.0, 65.0]
    assert [sid for _, _, sid in frames] == ['01', '02']    # привязка к сегментам


# Phase 1 Task 1.1: segment_bounds tests
_MD_TWO_SEG = (
    "# Название\n\n---\n\n"
    "## Сегмент 1 | 00:00:00-00:01:30 | Первый\n\n**Тип:** идея\n\n"
    "## Сегмент 2 | 00:01:30–00:03:00 | Второй\n\n**Тип:** идея\n"  # en-dash во втором
)


def test_segment_bounds_parses_ranges():
    b = frames_extract.segment_bounds(_MD_TWO_SEG)
    assert b == [
        {'id': '01', 'start': 0.0, 'end': 90.0},
        {'id': '02', 'start': 90.0, 'end': 180.0},
    ]


def test_segment_bounds_empty_raises():
    with pytest.raises(frames_extract.SegmentBoundsError):
        frames_extract.segment_bounds("# Название\n\nтекст без сегментов\n")


def test_segment_bounds_overlap_raises():
    md = (
        "## Сегмент 1 | 00:00:00-00:02:00 | A\n\n"
        "## Сегмент 2 | 00:01:00-00:03:00 | B\n"
    )
    with pytest.raises(frames_extract.SegmentBoundsError):
        frames_extract.segment_bounds(md)


def test_segment_bounds_reversed_range_raises():
    md = "## Сегмент 1 | 00:02:00-00:01:00 | A\n"
    with pytest.raises(frames_extract.SegmentBoundsError):
        frames_extract.segment_bounds(md)


# Phase 1 Task 1.2: assign_segment tests
_BOUNDS = [
    {'id': '01', 'start': 0.0, 'end': 90.0},
    {'id': '02', 'start': 100.0, 'end': 180.0},   # щель 90..100
]


def test_assign_before_first():
    assert frames_extract.assign_segment(-5.0, _BOUNDS) == '01'


def test_assign_after_last():
    assert frames_extract.assign_segment(999.0, _BOUNDS) == '02'


def test_assign_inside():
    assert frames_extract.assign_segment(50.0, _BOUNDS) == '01'
    assert frames_extract.assign_segment(150.0, _BOUNDS) == '02'


def test_assign_gap_nearest_boundary():
    assert frames_extract.assign_segment(92.0, _BOUNDS) == '01'   # ближе к end 90
    assert frames_extract.assign_segment(98.0, _BOUNDS) == '02'   # ближе к start 100


# Task 2.6: codex_available tests
def test_codex_available_true(monkeypatch):
    class R: returncode = 0
    monkeypatch.setattr(frames_extract.subprocess, 'run', lambda *a, **k: R())
    assert frames_extract.codex_available() is True


def test_codex_available_false(monkeypatch):
    def boom(*a, **k): raise FileNotFoundError()
    monkeypatch.setattr(frames_extract.subprocess, 'run', boom)
    assert frames_extract.codex_available() is False


def test_average_hash_identical(tmp_path):
    a = tmp_path / "a.png"; b = tmp_path / "b.png"
    _png(a, color=(30, 30, 30)); _png(b, color=(30, 30, 30))
    assert frames_extract.hamming(frames_extract.average_hash(a),
                                  frames_extract.average_hash(b)) == 0


def test_average_hash_differs_for_gradient(tmp_path):
    from PIL import Image
    a = tmp_path / "a.png"; b = tmp_path / "b.png"
    Image.new("RGB", (64, 64), (0, 0, 0)).save(a)
    grad = Image.new("L", (64, 64))
    grad.putdata([(x * 4) % 256 for x in range(64) for _ in range(64)])
    grad.convert("RGB").save(b)
    assert frames_extract.hamming(frames_extract.average_hash(a),
                                  frames_extract.average_hash(b)) > 0


# Task 2.2: phash_dedup tests
def _solid(path, color):
    from PIL import Image
    Image.new("RGB", (64, 64), color).save(path)

def test_phash_dedup_collapses_identical(tmp_path):
    a = tmp_path / "cand_0001.png"; b = tmp_path / "cand_0002.png"
    _solid(a, (20, 20, 20)); _solid(b, (20, 20, 20))
    res = frames_extract.phash_dedup([(a, 1.0, '01'), (b, 2.0, '01')], threshold=6)
    assert [f.name for f, _, _ in res] == ["cand_0001.png"]

def test_phash_dedup_keeps_distinct(tmp_path):
    from PIL import Image
    a = tmp_path / "cand_0001.png"; b = tmp_path / "cand_0002.png"
    Image.new("RGB", (64, 64), (0, 0, 0)).save(a)
    grad = Image.new("L", (64, 64))
    grad.putdata([(x * 4) % 256 for x in range(64) for _ in range(64)])
    grad.convert("RGB").save(b)
    res = frames_extract.phash_dedup([(a, 1.0, '01'), (b, 2.0, '01')], threshold=6)
    assert len(res) == 2

def _pattern(path, fn):
    # ВАЖНО: average-hash различает кадры по пространственной структуре, а НЕ по
    # однотонной яркости. У сплошной заливки все пиксели равны среднему → маска из
    # 64 единиц, ОДИНАКОВАЯ для любого цвета (см. average_hash: `p >= avg`). Поэтому
    # фикстуры цикла строим паттернами: A и D идентичны, B и C отличаются от A и друг
    # от друга. Solid-заливки здесь дали бы hamming=0 попарно и тест бы не проверял окно.
    from PIL import Image
    img = Image.new("L", (64, 64))
    img.putdata([255 if fn(x, y) else 0 for y in range(64) for x in range(64)])
    img.convert("RGB").save(path)

def test_phash_dedup_cycle_abca_window3(tmp_path):
    # A B C A: последний A совпадает с кадром 3 позиции назад -> окно N=3 его гасит.
    patterns = [
        lambda x, y: x < 32,   # A: лево/право
        lambda x, y: y < 32,   # B: верх/низ      (hamming к A = 32)
        lambda x, y: x >= 32,  # C: инверсия A    (hamming к A = 64)
        lambda x, y: x < 32,   # D == A           (hamming к A = 0)
    ]
    paths = []
    for i, fn in enumerate(patterns, 1):
        p = tmp_path / f"cand_{i:04d}.png"
        _pattern(p, fn)
        paths.append((p, float(i), '01'))
    res = frames_extract.phash_dedup(paths, threshold=6, window=3)
    assert [f.name for f, _, _ in res] == ["cand_0001.png", "cand_0002.png", "cand_0003.png"]


# Task 3.1: bucket_timecodes tests
def test_bucket_timecodes_isolates_noisy_segment():
    bounds = [
        {'id': '01', 'start': 0.0, 'end': 100.0},
        {'id': '02', 'start': 100.0, 'end': 200.0},
    ]
    scene = [float(i) for i in range(0, 100, 4)]   # шумный сегмент 01
    cue = [150.0]                                   # один кадр в сегменте 02
    res, cap = frames_extract.bucket_timecodes(scene, cue, bounds,
                                               min_gap=0.0, per_segment_cap=10)
    seg02 = [tc for tc, sid in res if sid == '02']
    assert seg02 == [150.0]                         # тихий сегмент не потерян
    assert all(0.0 <= tc < 100.0 for tc, sid in res if sid == '01')
    assert res == sorted(res)                       # общий порядок по таймкоду

def test_bucket_timecodes_global_fallback_reduces_cap():
    bounds = [{'id': f'{i:02d}', 'start': i * 100.0, 'end': i * 100.0 + 100.0}
              for i in range(1, 11)]                # 10 сегментов
    scene = [i * 100.0 + j for i in range(1, 11) for j in range(0, 50, 2)]
    res, cap = frames_extract.bucket_timecodes(scene, [], bounds,
                                               min_gap=0.0, per_segment_cap=10,
                                               global_cap=30)
    assert len(res) <= 30
    assert cap < 10                                 # cap ужат для всех бакетов


# Task 4.1: adaptive_cap + select_frames tests
def test_adaptive_cap():
    assert frames_extract.adaptive_cap(3) == 13
    assert frames_extract.adaptive_cap(1) == 12      # пол 12

def test_select_frames_guarantees_low_conf_segment():
    cands = [
        {'cand_id': 1, 'segment_id': '01'},
        {'cand_id': 2, 'segment_id': '02'},
    ]
    triage = [
        {'cand_id': 1, 'type': 'illustration', 'confidence': 0.9},
        {'cand_id': 2, 'type': 'slide-text', 'confidence': 0.1},   # единственный в 02
    ]
    sel = frames_extract.select_frames(triage, cands, cap=12)
    ids = {s['cand_id'] for s in sel}
    assert ids == {1, 2}                             # тихий сегмент 02 гарантирован
    assert all(s['phase'] == 'mandatory' for s in sel)

def test_select_frames_budget_allows_multiple_per_segment():
    cands = [{'cand_id': i, 'segment_id': '01'} for i in range(1, 6)]
    triage = [{'cand_id': i, 'type': 'slide-text', 'confidence': i / 10} for i in range(1, 6)]
    sel = frames_extract.select_frames(triage, cands, cap=12)
    assert len(sel) == 5                             # богатый сегмент берёт больше 1
    assert sum(1 for s in sel if s['phase'] == 'mandatory') == 1

def test_select_frames_budget_respects_cap():
    cands = [{'cand_id': i, 'segment_id': '01'} for i in range(1, 21)]
    triage = [{'cand_id': i, 'type': 'slide-text', 'confidence': i / 100} for i in range(1, 21)]
    sel = frames_extract.select_frames(triage, cands, cap=12)
    assert len(sel) == 12

def test_select_frames_drops_and_unknown_ignored():
    cands = [{'cand_id': 1, 'segment_id': '01'}]     # cand_id 2 нет в манифесте
    triage = [
        {'cand_id': 1, 'type': 'drop', 'confidence': 0.9},
        {'cand_id': 2, 'type': 'slide-text', 'confidence': 0.9},
    ]
    assert frames_extract.select_frames(triage, cands, cap=12) == []


# Task 4.2: trim_to_weight tests
def test_trim_to_weight_drops_budget_first():
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 2, 'segment_id': '01', 'confidence': 0.8, 'phase': 'budget'},
        {'cand_id': 3, 'segment_id': '01', 'confidence': 0.2, 'phase': 'budget'},
    ]
    size = {1: 4, 2: 4, 3: 4}
    kept, lost = frames_extract.trim_to_weight(sel, size, limit_bytes=8)
    assert {s['cand_id'] for s in kept} == {1, 2}    # выбит бюджетный с меньшим conf (3)
    assert lost == []                                # обязательный не тронут

def test_trim_to_weight_degrades_mandatory_last():
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 2, 'segment_id': '02', 'confidence': 0.1, 'phase': 'mandatory'},
    ]
    size = {1: 6, 2: 6}
    kept, lost = frames_extract.trim_to_weight(sel, size, limit_bytes=8)
    assert {s['cand_id'] for s in kept} == {1}       # оставлен более уверенный
    assert lost == ['02']

def test_trim_to_weight_noop_when_fits():
    sel = [{'cand_id': 1, 'segment_id': '01', 'confidence': 0.5, 'phase': 'mandatory'}]
    kept, lost = frames_extract.trim_to_weight(sel, {1: 3}, limit_bytes=8)
    assert kept == sel and lost == []


# Task 4.3: segment_report tests
def test_segment_report_counts():
    bounds = [{'id': '01', 'start': 0.0, 'end': 100.0},
              {'id': '02', 'start': 100.0, 'end': 200.0}]
    cands = [{'cand_id': 1, 'segment_id': '01'}, {'cand_id': 2, 'segment_id': '01'},
             {'cand_id': 3, 'segment_id': '02'}]
    triage = [{'cand_id': 1, 'type': 'slide-text', 'confidence': 0.9},
              {'cand_id': 2, 'type': 'drop', 'confidence': 0.1},
              {'cand_id': 3, 'type': 'drop', 'confidence': 0.2}]
    selection = [{'cand_id': 1, 'segment_id': '01', 'phase': 'mandatory'}]
    rows = frames_extract.segment_report(bounds, cands, triage, selection)
    assert rows == [
        {'segment_id': '01', 'candidates': 2, 'triage_pass': 1, 'inserted': 1},
        {'segment_id': '02', 'candidates': 1, 'triage_pass': 0, 'inserted': 0},
    ]
