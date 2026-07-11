# Смысловая плотность кадров в виджете /konspekt — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Привязать отбор кадров к смыслу конспекта — гарантированные маркер-кадры «заскриньте», посегментное суждение оркестратора о плотности, распознавание промптов с экрана в `.pr-block`, WebP-контроль веса.

**Architecture:** Правится только opt-in ветка «виджет с кадрами». Детерминированное ядро (`frames_extract.py`, `md_parser.py`) получает: узкий маркер-греп с гарантированной нарезкой вне дедупа/капа + окно серии; приоритет `marker > mandatory > budget` в обрезке веса; WebP-кодек; хелперы нарезки транскрипта и группировки сегментов в ≤3 пачки — всё как чистые тестируемые функции. Суждение (разметка плотности Ярусом 1, отбор и распознавание Ярусом 2) живёт в `layer2_widget.md` как guidance, проверяется на E2E.

**Tech Stack:** Python 3.12, ffmpeg, yt-dlp, Pillow (PIL, WebP-кодек в комплекте), pytest. Никаких новых зависимостей.

## Global Constraints

- Скилл — под junction `~/.claude/skills/konspekt` → этот репозиторий; правки делать здесь.
- Windows / PowerShell основной, Bash доступен. Запуск питона скилла: `PYTHONUTF8=1 python ...`.
- Тесты: `.claude/skills/konspekt/tests/`, запуск `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`.
- Скоуп — **только** ветка «виджет с кадрами»: `frames_extract.py`, `md_parser.py` (функции кадров), `frames_schema.json`, `layer2_widget.md`, соответствующие тесты. Обычная сборка виджета, master-MD, preview **не трогаются**.
- Формат заголовка сегмента мастер-MD: `## Сегмент N | HH:MM:SS-HH:MM:SS | Тема`; дефис — класс `[–-]` (как в `frames_extract.py:22`).
- **Охват маркеров — узкий** (решение пользователя): триггеры `скринь`, `зафиксируй`, `сохрани этот` — отдельная категория, НЕ смешивать со старым `CUE_MARKERS` (тот остаётся мягким).
- **8 МБ — жёсткий предел** (решение пользователя): приоритет обрезки `marker > mandatory > budget`; при деградации маркеров — громкое предупреждение в stderr.
- Пороги (`marker_window_sec=100`, `marker_window_frames=5`, `phash_threshold=6`, scene-detect `0.2`) — стартовые, подбираются на E2E.
- TDD: сначала падающий тест, потом минимальная реализация. Частые локальные коммиты. **Push и PR не делать — пользователь сам.**
- Не выводить содержимое PNG-кадров или полный `MASTER_..._с_кадрами.md` в чат (запрет `layer2_widget.md`).
- Спека-источник: `docs/superpowers/specs/2026-07-11-konspekt-frames-semantic-density-design.md`.

---

## Файловая структура

**Правится существующее:**
- `.claude/skills/konspekt/frames_extract.py` — новые: `MARKER_TRIGGERS`, `marker_timecodes`, `expand_marker_window`, `segment_transcript`, `batch_segments`; переписан `build_candidates` (маркеры вне дедупа/капа, тег `marker`+`phrase`); `trim_to_weight` (категория `marker`); `select_frames` (phase `marker`); `segment_report` (+`block_type`); `_cmd_extract` (манифест с `marker`/`phrase`, посегментные простыни); `_cmd_select` (+`--segment-plan`).
- `.claude/skills/konspekt/md_parser.py` — `_encode_frame_b64` на WebP.
- `.claude/skills/konspekt/layer2_widget.md` — Шаги 1–6, таблицы, формат `segment_plan.json`.
- `.claude/skills/konspekt/tests/test_frames_extract.py`, `tests/test_widget_generator.py` — тесты.

---

# ФАЗА 1 — Маркеры: гарантия, окно, флаг

### Task 1.1: `marker_timecodes` — узкий греп с фразой спикера

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces:
  - `MARKER_TRIGGERS = ['скринь', 'зафиксируй', 'сохрани этот']` — узкий список (отдельно от `CUE_MARKERS`).
  - `marker_timecodes(srt_text: str) -> list[dict]` — `[{'timecode': float, 'phrase': str}]` по SRT-блокам, где текст содержит любой триггер. `phrase` — исходный текст реплики (без нижнего регистра, обрезанный). Сортировка по `timecode`, дубли таймкодов схлопнуты (первый `phrase`).

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
_SRT_MARKERS = (
    "1\n00:00:10,000 --> 00:00:12,000\nЗаскриньте этот слайд, пожалуйста\n\n"
    "2\n00:00:20,000 --> 00:00:22,000\nПросто рассказываю без маркера\n\n"
    "3\n00:00:30,000 --> 00:00:32,000\nЗафиксируйте формулу\n"
)

def test_marker_timecodes_narrow_list():
    res = frames_extract.marker_timecodes(_SRT_MARKERS)
    assert [r['timecode'] for r in res] == [10.0, 30.0]
    assert 'аскриньте' in res[0]['phrase']

def test_marker_timecodes_ignores_broad_cues():
    # «смотрите/на экране» — старые CUE_MARKERS, но НЕ маркеры-гарантия
    srt = "1\n00:00:05,000 --> 00:00:07,000\nСмотрите на экране\n"
    assert frames_extract.marker_timecodes(srt) == []
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k marker_timecodes -v`
Ожидание: FAIL (`marker_timecodes` не существует).

- [ ] **Step 3: Реализовать** (после `cue_timecodes`)

```python
MARKER_TRIGGERS = ['скринь', 'зафиксируй', 'сохрани этот']

def marker_timecodes(srt_text):
    out = {}
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    for b in blocks:
        lines = b.splitlines()
        tc_line = next((l for l in lines if '-->' in l), None)
        if not tc_line:
            continue
        raw = ' '.join(l for l in lines
                       if '-->' not in l and not l.strip().isdigit()).strip()
        if any(mk in raw.lower() for mk in MARKER_TRIGGERS):
            t = _srt_time_to_sec(tc_line.split('-->')[0].strip())
            out.setdefault(t, raw)
    return [{'timecode': t, 'phrase': out[t]} for t in sorted(out)]
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k marker_timecodes -v`
Ожидание: 2 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): marker_timecodes — узкий греп маркеров заскриньте с фразой спикера"
```

### Task 1.2: `expand_marker_window` — якорь + серия слайдов по окну

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces: `expand_marker_window(anchor: float, scene_tcs: list[float], window_end: float, window_frames: int = 5) -> list[float]` — `[anchor]` плюс scene-таймкоды строго в `(anchor, window_end]`; итог отсортирован, уникален, ограничен `window_frames` (якорь всегда включён; при избытке — равномерная выборка из остатка).

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
def test_expand_marker_window_series():
    scenes = [12.0, 25.0, 40.0, 55.0, 70.0, 130.0]   # 130 вне окна
    res = frames_extract.expand_marker_window(10.0, scenes, window_end=110.0,
                                              window_frames=5)
    assert res[0] == 10.0
    assert 130.0 not in res
    assert res == sorted(set(res)) and len(res) <= 5

def test_expand_marker_window_caps():
    scenes = [float(x) for x in range(11, 60)]       # много кадров
    res = frames_extract.expand_marker_window(10.0, scenes, window_end=100.0,
                                              window_frames=3)
    assert len(res) == 3 and res[0] == 10.0

def test_expand_marker_window_anchor_only():
    assert frames_extract.expand_marker_window(10.0, [200.0], window_end=100.0) == [10.0]
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k expand_marker_window -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать** (после `marker_timecodes`)

```python
def expand_marker_window(anchor, scene_tcs, window_end, window_frames=5):
    inside = sorted(t for t in set(scene_tcs) if anchor < t <= window_end)
    extra = window_frames - 1
    if len(inside) > extra > 0:
        step = (len(inside) - 1) / (extra - 1) if extra > 1 else len(inside)
        inside = [inside[round(i * step)] for i in range(extra)] if extra > 1 else [inside[-1]]
    elif extra <= 0:
        inside = []
    return sorted(set([anchor, *inside]))
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k expand_marker_window -v`
Ожидание: 3 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): expand_marker_window — якорь + серия слайдов по окну маркера"
```

### Task 1.3: `build_candidates` — маркеры вне дедупа/капа + тег в манифесте

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py` — `build_candidates`, `_cmd_extract`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py` — обновить существующий тест

**Interfaces:**
- Consumes: `marker_timecodes`, `expand_marker_window`, `bucket_timecodes`, `scene_timecodes`, `cue_timecodes`, `phash_dedup`, `extract_frame`, `segment_bounds`, `assign_segment`.
- Produces: `build_candidates(video, srt_text, master_md_text, work_dir, threshold=0.2, min_gap=3.0, per_segment_cap=10, global_cap=150, phash_threshold=6, marker_window_sec=100.0, marker_window_frames=5) -> tuple[list[tuple[Path,float,str,bool,str]], int]` — список `(файл, таймкод, segment_id, marker_bool, phrase)` + итоговый cap. Маркер-таймкоды **не проходят** `dedup_by_gap`/global-cap и **не проходят** `phash_dedup`; scene+cue — как раньше.

- [ ] **Step 1: Адаптировать старый тест под 5-кортеж + добавить тест гарантии маркера**

**Не удалять** покрытие ветки ошибки `extract_frame` — адаптировать существующий `test_build_candidates_numbers_successful_frames_without_gaps` под новую 5-элементную арность (fake принимает `shift`):

```python
def test_build_candidates_numbers_successful_frames_without_gaps(tmp_path, monkeypatch):
    calls = []
    md = ("## Сегмент 1 | 00:00:00-00:01:00 | A\n\n"
          "## Сегмент 2 | 00:01:00-00:02:00 | B\n")
    monkeypatch.setattr(frames_extract, 'scene_timecodes', lambda v, threshold: [1.0, 2.0, 65.0])
    monkeypatch.setattr(frames_extract, 'cue_timecodes', lambda s: [])
    monkeypatch.setattr(frames_extract, 'phash_dedup', lambda frames, **k: frames)

    def fake_extract_frame(video, t, out, shift=0.7):
        calls.append(t)
        if len(calls) == 2:                         # 2-й кадр падает
            raise frames_extract.subprocess.CalledProcessError(1, ['ffmpeg'])
        _png(out)
    monkeypatch.setattr(frames_extract, 'extract_frame', fake_extract_frame)

    frames, cap = frames_extract.build_candidates('video.mp4', '', md, tmp_path, min_gap=0.0)
    assert [f.name for f, *_ in frames] == ['cand_0001.png', 'cand_0002.png']
    assert [t for _, t, *_ in frames] == [1.0, 65.0]
    assert [sid for _, _, sid, *_ in frames] == ['01', '02']   # нумерация без дыр после сбоя
```

И добавить рядом тест гарантии маркера:

```python
def test_build_candidates_marker_survives_dedup(tmp_path, monkeypatch):
    md = ("## Сегмент 1 | 00:00:00-00:01:00 | A\n\n"
          "## Сегмент 2 | 00:01:00-00:02:00 | B\n")
    srt = "1\n00:00:30,000 --> 00:00:31,000\nЗаскриньте это\n"
    # scene-кадр в 0.5с рядом с маркером 30с — маркер не должен быть поглощён
    monkeypatch.setattr(frames_extract, 'scene_timecodes', lambda v, threshold: [0.5])
    monkeypatch.setattr(frames_extract, 'phash_dedup', lambda frames, **k: frames)

    def fake_extract_frame(video, t, out, shift=0.7):
        _png(out)
    monkeypatch.setattr(frames_extract, 'extract_frame', fake_extract_frame)

    frames, cap = frames_extract.build_candidates('v.mp4', srt, md, tmp_path, min_gap=0.0)
    markers = [(t, sid, ph) for _, t, sid, mk, ph in frames if mk]
    assert any(abs(t - 30.0) < 1e-6 and sid == '01' for t, sid, ph in markers)
    assert any('аскриньте' in ph for _, _, ph in markers)
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k build_candidates -v`
Ожидание: FAIL (старая сигнатура/арность).

- [ ] **Step 3: Переписать `build_candidates`**

```python
def build_candidates(video, srt_text, master_md_text, work_dir,
                     threshold=0.2, min_gap=3.0, per_segment_cap=10,
                     global_cap=150, phash_threshold=6,
                     marker_window_sec=100.0, marker_window_frames=5):
    work = Path(work_dir); work.mkdir(parents=True, exist_ok=True)
    bounds = segment_bounds(master_md_text)
    scenes = scene_timecodes(video, threshold)
    # обычные (scene+cue) — через дедуп/кап
    tagged, final_cap = bucket_timecodes(
        scenes, cue_timecodes(srt_text), bounds,
        min_gap=min_gap, per_segment_cap=per_segment_cap, global_cap=global_cap)
    normal = [(t, sid, False, '') for t, sid in tagged]
    # маркеры — вне дедупа/капа, с окном серии
    markers = marker_timecodes(srt_text)
    anchors = [m['timecode'] for m in markers]
    marker_items = []
    seen_marker_tc = set()   # дедуп на стыке окон соседних маркеров (finding 6)
    for i, m in enumerate(markers):
        nxt = anchors[i + 1] if i + 1 < len(anchors) else float('inf')
        end = min(m['timecode'] + marker_window_sec, nxt)
        for t in expand_marker_window(m['timecode'], scenes, end, marker_window_frames):
            if t in seen_marker_tc:
                continue
            seen_marker_tc.add(t)
            marker_items.append((t, assign_segment(t, bounds), True, m['phrase']))
    raw_normal, raw_marker = [], []
    success_idx = 0
    for t, sid, is_marker, phrase in normal + marker_items:
        success_idx += 1
        tmp = work / f'_tmp_{success_idx:04d}.png'
        try:
            extract_frame(video, t, tmp)
        except subprocess.CalledProcessError:
            if tmp.exists():
                tmp.unlink()
            success_idx -= 1
            continue
        if not tmp.exists():
            success_idx -= 1
            continue
        f = work / f'cand_{success_idx:04d}.png'
        tmp.replace(f)
        (raw_marker if is_marker else raw_normal).append((f, t, sid, is_marker, phrase))
    kept = phash_dedup(raw_normal, threshold=phash_threshold) + raw_marker
    kept.sort(key=lambda x: x[1])
    return kept, final_cap
```

- [ ] **Step 4: Обновить `_cmd_extract` — манифест с `marker`/`phrase` + посегментные простыни**

```python
def _cmd_extract(args):
    work_dir = Path(args.work_dir)
    video = download_video(args.url, work_dir) if args.url else Path(args.video)
    srt_text = Path(args.srt).read_text(encoding='utf-8')
    master_md_text = Path(args.master_md).read_text(encoding='utf-8')
    cands, final_cap = build_candidates(video, srt_text, master_md_text, work_dir,
                                        threshold=args.threshold)
    sheet_path = contact_sheet([f for f, *_ in cands], work_dir / 'contact_sheet.png')
    # посегментные простыни для субагентов Яруса 2
    by_seg = {}
    for f, t, sid, mk, ph in cands:
        by_seg.setdefault(sid, []).append(f)
    for sid, files in by_seg.items():
        contact_sheet(files, work_dir / f'contact_sheet_seg{sid}.png')
    manifest_path = work_dir / 'candidates.json'
    manifest_path.write_text(
        json.dumps([{'cand_id': _cand_num(f), 'timecode': t, 'segment_id': sid,
                     'marker': mk, 'phrase': ph}
                    for f, t, sid, mk, ph in cands], ensure_ascii=False, indent=2),
        encoding='utf-8')
    print(f'Кандидатов найдено: {len(cands)} (cap на бакет: {final_cap})')
    print(f'Contact-sheet: {sheet_path} (+ посегментные contact_sheet_seg*.png)')
    print(f'Манифест: {manifest_path}')
```

- [ ] **Step 5: Прогнать весь набор — зелёные**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное (обновить/поправить прочие тесты `build_candidates`, если ловят старую арность).

- [ ] **Step 6: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): build_candidates — маркеры вне дедупа/капа + флаг marker/phrase + посегментные простыни"
```

---

# ФАЗА 2 — Вес: приоритет маркеров + WebP

### Task 2.1: `trim_to_weight` — категория `marker` (приоритет marker > mandatory > budget)

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces: `trim_to_weight(selection, size_by_cand, limit_bytes) -> tuple[list[dict], list[str]]` — порядок выбрасывания: `budget` → `mandatory` → `marker` (каждая группа по возрастанию `confidence`). `lost` собирает `segment_id` выброшенных из `mandatory` **и** `marker`.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
def test_trim_drops_marker_last():
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.2, 'phase': 'marker'},
        {'cand_id': 2, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 3, 'segment_id': '01', 'confidence': 0.9, 'phase': 'budget'},
    ]
    size = {1: 6, 2: 6, 3: 6}
    kept, lost = frames_extract.trim_to_weight(sel, size, limit_bytes=8)
    # выбиты budget(3) и mandatory(2); marker(1) выжил, хоть и conf ниже
    assert {s['cand_id'] for s in kept} == {1}
    assert lost == ['01']   # потерян mandatory сегмента 01

def test_trim_degrades_marker_only_when_forced():
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.1, 'phase': 'marker'},
        {'cand_id': 2, 'segment_id': '02', 'confidence': 0.9, 'phase': 'marker'},
    ]
    size = {1: 6, 2: 6}
    kept, lost = frames_extract.trim_to_weight(sel, size, limit_bytes=8)
    assert {s['cand_id'] for s in kept} == {2}   # оставлен более уверенный маркер
    assert lost == ['01']
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k "trim_drops_marker or trim_degrades_marker" -v`
Ожидание: FAIL.

- [ ] **Step 3: Переписать `trim_to_weight`**

```python
def trim_to_weight(selection, size_by_cand, limit_bytes):
    kept = list(selection)

    def total():
        return sum(size_by_cand.get(s['cand_id'], 0) for s in kept)

    lost = []
    for phase in ('budget', 'mandatory', 'marker'):
        for s in sorted((s for s in kept if s['phase'] == phase),
                        key=lambda s: s['confidence']):
            if total() <= limit_bytes:
                break
            kept.remove(s)
            if phase in ('mandatory', 'marker'):
                lost.append(s['segment_id'])
    return kept, lost
```

- [ ] **Step 4: Запустить — прогнать существующие `trim_to_weight` тоже**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k trim -v`
Ожидание: все `trim`-тесты зелёные (старые про budget/mandatory сохраняют поведение).

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): trim_to_weight — приоритет marker > mandatory > budget"
```

### Task 2.2: `_encode_frame_b64` → WebP

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py:532-543`
- Test: `.claude/skills/konspekt/tests/test_widget_generator.py`

**Interfaces:**
- Produces: `md_parser._encode_frame_b64(path) -> tuple[str, str]` — RGB-кадр кодируется в **WebP** (`format='WEBP'`, `quality=82`, `method=6`), `mime='image/webp'`. Альфа/палитра → тоже WebP (без потери прозрачности). `frame_weights` считает тем же кодированием (без изменений — вызывает `_encode_frame_b64`).

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_widget_generator.py — добавить (base64 -> байты, сигнатура RIFF/WEBP)
import base64
from md_parser import _encode_frame_b64

def test_encode_frame_webp(tmp_path):
    from PIL import Image
    p = tmp_path / "cand_0001.png"
    Image.new("RGB", (100, 60), (120, 30, 30)).save(p)
    mime, b64 = _encode_frame_b64(p)
    assert mime == "image/webp"
    raw = base64.b64decode(b64)
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_widget_generator.py" -k encode_frame_webp -v`
Ожидание: FAIL (сейчас `image/jpeg`).

- [ ] **Step 3: Реализовать** — заменить тело кодирования в `_encode_frame_b64`

```python
def _encode_frame_b64(path):
    from PIL import Image
    img = Image.open(path); img.load()
    if img.width > IMG_MAX_WIDTH:
        h = round(img.height * IMG_MAX_WIDTH / img.width)
        img = img.resize((IMG_MAX_WIDTH, h))
    buf = io.BytesIO()
    mode = 'RGBA' if img.mode in ('RGBA', 'LA', 'P') else 'RGB'
    img.convert(mode).save(buf, format='WEBP', quality=82, method=6)
    return 'image/webp', base64.b64encode(buf.getvalue()).decode('ascii')
```

- [ ] **Step 4: Запустить — зелёные + существующие тесты рендера картинок**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_widget_generator.py" -q`
Ожидание: новый зелёный. **Два теста гарантированно упадут** (вызывают `_encode_frame_b64` и ассертят JPEG) — поправить их на `data:image/webp`: `test_render_image_embeds_base64` (`:165`) и `test_build_html_with_frame` (`:213`). Тесты с *хардкоженной* строкой `data:image/jpeg` в фикстуре (напр. `:224`, вход для контроля веса) — не трогать, они не зовут кодек.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/md_parser.py .claude/skills/konspekt/tests/test_widget_generator.py
git commit -m "feat(konspekt): _encode_frame_b64 на WebP (~30% веса даром)"
```

---

# ФАЗА 3 — Посегментные входы + отбор с учётом маркеров

### Task 3.1: `segment_transcript` — срез транскрипта по сегменту

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Consumes: `segment_bounds`, `_srt_time_to_sec`.
- Produces: `segment_transcript(srt_text: str, bounds: list[dict]) -> dict[str, str]` — `{segment_id: 'склеенный текст реплик сегмента'}`. Реплика относится к сегменту, если её start-таймкод в `[start, end)` (по `assign_segment`).

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
def test_segment_transcript_splits_by_bounds():
    bounds = [{'id': '01', 'start': 0.0, 'end': 60.0},
              {'id': '02', 'start': 60.0, 'end': 120.0}]
    srt = ("1\n00:00:10,000 --> 00:00:12,000\nПервый сегмент\n\n"
           "2\n00:01:10,000 --> 00:01:12,000\nВторой сегмент\n")
    res = frames_extract.segment_transcript(srt, bounds)
    assert 'Первый' in res['01'] and 'Второй' not in res['01']
    assert 'Второй' in res['02']
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k segment_transcript -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать**

```python
def segment_transcript(srt_text, bounds):
    out = {b['id']: [] for b in bounds}
    for b in re.split(r'\n\s*\n', srt_text.strip()):
        lines = b.splitlines()
        tc_line = next((l for l in lines if '-->' in l), None)
        if not tc_line:
            continue
        t = _srt_time_to_sec(tc_line.split('-->')[0].strip())
        text = ' '.join(l for l in lines
                        if '-->' not in l and not l.strip().isdigit()).strip()
        if text:
            out[assign_segment(t, bounds)].append(text)
    return {sid: ' '.join(parts) for sid, parts in out.items()}
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k segment_transcript -v`
Ожидание: 1 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): segment_transcript — срез транскрипта по сегменту (вход Яруса 2)"
```

### Task 3.2: `batch_segments` — группировка в ≤3 смежные пачки

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces: `batch_segments(segment_ids: list[str], max_batches: int = 3) -> list[list[str]]` — сохраняет порядок (смежность), делит на не более `max_batches` почти равных подряд-групп. При `len <= max_batches` — по одному id в группе.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
def test_batch_segments_contiguous_le3():
    assert frames_extract.batch_segments(['01', '02', '03']) == [['01'], ['02'], ['03']]
    r = frames_extract.batch_segments(['01', '02', '03', '04', '05', '06', '07'])
    assert len(r) == 3
    assert [x for grp in r for x in grp] == ['01','02','03','04','05','06','07']  # порядок цел
    assert all(grp == sorted(grp) for grp in r)                                    # смежность

def test_batch_segments_single():
    assert frames_extract.batch_segments(['01']) == [['01']]
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k batch_segments -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать**

```python
def batch_segments(segment_ids, max_batches=3):
    n = len(segment_ids)
    if n == 0:
        return []
    k = min(max_batches, n)
    size = (n + k - 1) // k
    return [segment_ids[i:i + size] for i in range(0, n, size)]
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k batch_segments -v`
Ожидание: 2 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): batch_segments — ≤3 смежные пачки сегментов для субагентов"
```

### Task 3.3: `select_frames` — маркер как высшая фаза + `_cmd_select` с `--segment-plan`

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py` — `select_frames`, `segment_report`, `_cmd_select`, регистрация флага
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces:
  - `select_frames(triage, candidates, cap)` — если у кандидата `marker == True`, он **всегда** отбирается с `phase='marker'` (вне cap, независимо от типа триажа, кроме явного `drop`); остальные — как прежде (`mandatory`/`budget`).
  - `segment_report(bounds, candidates, triage, selection, block_by_seg=None)` — строки получают ключ `block_type` (из `block_by_seg`, дефолт `''`).
  - CLI `select` — новый опциональный `--segment-plan <segment_plan.json>`; `block_type` в печатной таблице.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
def test_select_frames_marker_always_in():
    cands = [
        {'cand_id': 1, 'segment_id': '01', 'marker': True},
        {'cand_id': 2, 'segment_id': '01', 'marker': False},
    ]
    triage = [
        {'cand_id': 1, 'type': 'slide-text', 'confidence': 0.05},   # низкая, но маркер
        {'cand_id': 2, 'type': 'illustration', 'confidence': 0.9},
    ]
    sel = frames_extract.select_frames(triage, cands, cap=12)
    by = {s['cand_id']: s['phase'] for s in sel}
    assert by[1] == 'marker'          # маркер отобран как высшая фаза
    assert 2 in by

def test_select_frames_marker_survives_drop():
    # Триаж ошибочно пометил маркер-кадр drop — он всё равно обязан выжить.
    cands = [{'cand_id': 1, 'segment_id': '01', 'marker': True}]
    triage = [{'cand_id': 1, 'type': 'drop', 'confidence': 0.0}]
    sel = frames_extract.select_frames(triage, cands, cap=12)
    assert [s['phase'] for s in sel] == ['marker']

def test_segment_report_block_type():
    bounds = [{'id': '01', 'start': 0.0, 'end': 100.0}]
    cands = [{'cand_id': 1, 'segment_id': '01', 'marker': False}]
    triage = [{'cand_id': 1, 'type': 'slide-text', 'confidence': 0.9}]
    selection = [{'cand_id': 1, 'segment_id': '01', 'phase': 'mandatory'}]
    rows = frames_extract.segment_report(bounds, cands, triage, selection,
                                         block_by_seg={'01': 'контентный'})
    assert rows[0]['block_type'] == 'контентный'
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k "marker_always_in or block_type" -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать** — обновить `select_frames` и `segment_report`

```python
def select_frames(triage, candidates, cap):
    by_cand = {c['cand_id']: c for c in candidates}
    tri_by = {tr['cand_id']: tr for tr in triage}
    # Маркеры — высшая фаза, вне cap И вне drop-фильтра триажа (гарантия «всегда»).
    # Идём по candidates, а не по triage: маркер выживает, даже если триаж
    # ошибочно пометил его drop или вовсе не оценил.
    selected = []
    for c in candidates:
        if c.get('marker'):
            tr = tri_by.get(c['cand_id'], {})
            selected.append({'cand_id': c['cand_id'], 'segment_id': c['segment_id'],
                             'type': tr.get('type', 'illustration'),
                             'confidence': tr.get('confidence', 0.0), 'phase': 'marker'})
    chosen = {s['cand_id'] for s in selected}
    # non-marker: drop-фильтр применяется только здесь
    scored = [
        {'cand_id': tr['cand_id'], 'segment_id': by_cand[tr['cand_id']]['segment_id'],
         'type': tr['type'], 'confidence': tr['confidence']}
        for tr in triage
        if tr['type'] != 'drop' and tr['cand_id'] in by_cand
        and tr['cand_id'] not in chosen
    ]
    # Обязательная фаза: лучший non-drop на каждый сегмент без маркера
    best = {}
    for s in scored:
        sid = s['segment_id']
        if sid not in best or s['confidence'] > best[sid]['confidence']:
            best[sid] = s
    selected += [dict(s, phase='mandatory') for s in best.values()]
    chosen |= {s['cand_id'] for s in selected}
    # Фаза бюджета: остаток по убыванию confidence
    budget = cap - len(selected)
    rest = sorted((s for s in scored if s['cand_id'] not in chosen),
                  key=lambda s: s['confidence'], reverse=True)
    selected += [dict(s, phase='budget') for s in rest[:max(0, budget)]]
    return selected

def segment_report(bounds, candidates, triage, selection, block_by_seg=None):
    block_by_seg = block_by_seg or {}
    triage_by = {t['cand_id']: t for t in triage}
    rows = []
    for b in bounds:
        sid = b['id']
        cand_ids = [c['cand_id'] for c in candidates if c['segment_id'] == sid]
        passed = sum(1 for cid in cand_ids
                     if triage_by.get(cid, {}).get('type', 'drop') != 'drop')
        inserted = sum(1 for s in selection if s['segment_id'] == sid)
        rows.append({'segment_id': sid, 'block_type': block_by_seg.get(sid, ''),
                     'candidates': len(cand_ids), 'triage_pass': passed,
                     'inserted': inserted})
    return rows
```

- [ ] **Step 4: Обновить `_cmd_select` — читать `--segment-plan`, печатать `block_type`**

```python
def _cmd_select(args):
    cands = json.loads(Path(args.candidates).read_text(encoding='utf-8'))
    triage = json.loads(Path(args.triage).read_text(encoding='utf-8'))
    if isinstance(triage, dict) and 'frames' in triage:
        triage = triage['frames']
    bounds = segment_bounds(Path(args.master_md).read_text(encoding='utf-8'))
    block_by_seg = {}
    if getattr(args, 'segment_plan', None):
        plan = json.loads(Path(args.segment_plan).read_text(encoding='utf-8'))
        block_by_seg = {p['segment_id']: p.get('block_type', '') for p in plan}
    cap = adaptive_cap(len(bounds))
    selection = select_frames(triage, cands, cap)
    Path(args.out).write_text(
        json.dumps(selection, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Отобрано кадров: {len(selection)} (страховочный потолок {cap})')
    print('Сегмент | Тип блока | Кандидатов | Прошло триаж | Вставлено')
    for r in segment_report(bounds, cands, triage, selection, block_by_seg):
        print(f"{r['segment_id']:>7} | {r['block_type']:>9} | {r['candidates']:>10} | "
              f"{r['triage_pass']:>12} | {r['inserted']:>9}")
```

И зарегистрировать флаг в `main()` рядом с прочими `select`-аргументами:

```python
    sl.add_argument('--segment-plan', help='segment_plan.json (тип блока для отчёта)')
```

- [ ] **Step 5: Прогнать весь набор — зелёные**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное. **Явно поправить `test_segment_report_counts` (`tests/test_frames_extract.py:360-373`)**: новый `segment_report` всегда добавляет ключ `block_type`, поэтому строгое сравнение `rows == [...]` упадёт — дописать `'block_type': ''` в оба ожидаемых словаря. Прочие `select_frames`-тесты со старыми фикстурами без ключа `marker` проходят (в `candidates` `.get('marker')` вернёт None → non-marker путь).

- [ ] **Step 6: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): select_frames маркер-фаза + segment_report block_type + select --segment-plan"
```

---

# ФАЗА 4 — Документация ветки

> **Примечание (по ревью Sonnet, finding 3).** Правка `frames_schema.json` из первоначального плана **удалена** — поля `block_type`/`marker` в триаж-схеме были бы мёртвыми: `block_type` для отчёта берётся из `segment_plan.json` (пишет Ярус 1), `marker` — из `candidates.json` (Python-сторона, `select_frames`). Контракт триаж-JSON (`type/text/caption/confidence/cand_id`) не меняется. По правилу «ничего умозрительного» схему не трогаем.

### Task 4.1: `layer2_widget.md` — Шаги 1–6, таблицы, `segment_plan.json` (суждение)

**Files:**
- Modify: `.claude/skills/konspekt/layer2_widget.md`

**Interfaces:** документная правка (без юнит-тестов). Источник точных формулировок — спека `docs/superpowers/specs/2026-07-11-konspekt-frames-semantic-density-design.md`, разделы «Маркеры…», «Промпты…», «Формат виджета и контроль веса», «Оркестрация: три яруса», «Изменения по шагам ветки». Переносить смысл, не копировать дословно спеку целиком.

- [ ] **Step 1: Шаг 1 — маркеры-гарантия**

В разделе «Шаг 1» описать: узкий маркер-греп (`скринь/зафиксируй/сохрани этот`) с **гарантированной** нарезкой вне дедупа/капа + окно серии (`marker_window_sec=100`, `marker_window_frames=5`); флаг `marker`+`phrase` в `candidates.json`; посегментные `contact_sheet_seg<NN>.png`. Явно отделить от старых `CUE_MARKERS` (мягкие). Убрать формулировку, будто маркер уже гарантирован.

- [ ] **Step 2: Шаг 2 — триаж с выжимкой конспекта**

Дописать: в тот же codex/субагент-вызов подкладывается выжимка ключевых мыслей конспекта по сегментам; триаж помечает «пустой/декоративный» и «бьётся ли с мыслью конспекта». Без нового прохода.

- [ ] **Step 3: Шаг 2.5 — три яруса + формат `segment_plan.json`**

Заменить нынешний одноуровневый отбор на три яруса (таблица ниже). Добавить формат `segment_plan.json`:

```json
[{ "segment_id": "02", "block_type": "маркетинговый",
   "density": "точечно", "budget_hint": 2,
   "rationale": "продающий блок: только ключевые слайды оффера" }]
```

Ярус 1 (Opus, текст) пишет `segment_plan.json`; Ярус 2 (≤3 субагента Codex→Sonnet, пачки `batch_segments`) получает срез `candidates.json` + `contact_sheet_seg*.png` + `segment_transcript` + список промптов сегментов → per-cand решения. Жёсткие правила: маркер обязателен; промпт → `.pr-block`. `select`/`adaptive_cap` — мягкая страховка покрытия, жёсткий предел — вес.

- [ ] **Step 4: Шаг 3 — промпт с экрана дословно**

Дописать: у промпт-кадров цель — распознать дословно со структурой (переносы/нумерация); сомнение → картинка + «проверить». Выполняют субагенты Яруса 2.

- [ ] **Step 5: Шаг 4/5/6 — вставка, вес, отчёт**

Шаг 4: промпты → `.pr-block` распознанным текстом; смысловые/маркер-слайды → картинкой с подписью-таймкодом; демо → 1–2; пустые не вставляются. Шаг 5: WebP; `trim_to_weight` приоритет `marker > mandatory > budget`; 8 МБ жёсткий, деградация маркеров — громкое предупреждение. Шаг 6: в таблицу отчёта добавить колонку «Тип блока».

- [ ] **Step 6: Таблицы «Оркестрация и модели» и «Лимиты по умолчанию»**

Обновить таблицу оркестрации на три яруса (Opus управляет; ≤3 субагента Codex→Sonnet). В «Лимитах»: строку «Картинок на виджет» пометить как **мягкий ориентир** `max(12, сегментов+10)`, жёсткий предел — вес ≤8 МБ; добавить строки «Маркер-окно» (100 с / ≤5 кадров) и «Кодек кадров» (WebP q82).

- [ ] **Step 7: Ревью связности + коммит**

Перечитать `layer2_widget.md` целиком: нет ли осиротевших упоминаний «равномерный потолок»/«JPEG»/«маркер не гарантирован». Затем:

```bash
git add .claude/skills/konspekt/layer2_widget.md
git commit -m "docs(konspekt): ветка кадров — маркеры-гарантия, 3 яруса, промпты с экрана, WebP, отчёт по типам блоков"
```

---

# ФАЗА 5 — E2E на реальном практикуме

### Task 5.1: Прогон и проверка критериев успеха

**Files:** нет правок кода — приёмочная проверка. Артефакты — на F: (продукт, не в репо).

**Данные:** видео `D:\Users\Вова\Downloads\Ледовских. Практикум - Агент для контента_Д1.mp4` (ч1 = 0–01:20:30); мастер `F:\...\Практикум - Агент для контента\MASTER_..._Д1_ч1.md`; `frames_work/` существует.

- [ ] **Step 1: `extract` на локальном видео**

```bash
PYTHONUTF8=1 python .claude/skills/konspekt/frames_extract.py extract \
  --video "D:/Users/Вова/Downloads/Ледовских. Практикум - Агент для контента_Д1.mp4" \
  --srt "F:/Наш Архив/ИИ/Ледовских/Интенсивы/Практикум - Агент для контента/SRC_transcript_Ледовских_Практикум_Агент_для_контента_Д1.srt" \
  --master-md "F:/Наш Архив/ИИ/Ледовских/Интенсивы/Практикум - Агент для контента/MASTER_Ледовских_Практикум_Агент_для_контента_Д1_ч1.md" \
  --work-dir "F:/Наш Архив/ИИ/Ледовских/Интенсивы/Практикум - Агент для контента/frames_work"
```
Проверить: в `candidates.json` есть записи с `marker:true` и `phrase`, среди них таймкоды у 00:20 (350=100 000) и 00:23 (5 ошибок); созданы `contact_sheet_seg*.png`.

- [ ] **Step 2: Прогнать ветку по `layer2_widget.md`** (Ярус 1 → триаж → Ярус 2 → сборка). Соблюсти запрет: не выводить PNG/полный `_с_кадрами.md` в чат.

- [ ] **Step 3: Проверить объективные критерии успеха**

- все 3 промпта/скрипта → `.pr-block` дословно со структурой;
- «заскриньте»-слайды на месте: «350 = 100 000 ₽», «5 ошибок» (серия), «ШАГ 1. Настройте свою ленту»;
- отчёт Шага 6 показывает тип блока по сегментам;
- итоговый HTML ≤8 МБ; кадры WebP (`data:image/webp` в HTML); `✅ JS syntax OK`.

- [ ] **Step 4: Проверить оценочные (на глаз)**: пустых фотогеничных слайдов нет; в демо-фрагментах ≤1–2 кадра.

- [ ] **Step 5: Зафиксировать результат** — если расхождения, завести список правок порогов (`marker_window_*`, scene-detect, `phash_threshold`) и guidance Ярусов; при успехе — отметить план выполненным. E2E-артефакты на F: не коммитить (продукт).

---

## Порядок исполнения

Фазы строго по порядку (1 → 5): маркеры (ядро) → вес → посегментные входы/отбор → схема+документация → E2E. Внутри фазы — задачи по номерам. Каждая Python-задача самодостаточна и заканчивается зелёными тестами + коммитом.
