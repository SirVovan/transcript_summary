# Покрытие сегментов и чистка детекции в ветке «виджет с кадрами» — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить шумную позиционную детекцию/вставку кадров детерминированной привязкой кадр→сегмент по таймкоду, pHash-дедупом катов камеры, посегментными квотами и двухфазным отбором с гарантией ≥1 кадра на сегмент.

**Architecture:** Правится только opt-in ветка «виджет с кадрами». `frames_extract.py` получает независимый парсер границ сегментов из мастер-MD (`segment_bounds`), бакетирование таймкодов по сегментам с посегментными квотами и общим предохранителем, pHash-дедуп (average-hash на PIL, скользящее окно N=3), детерминированный двухфазный отбор (`select_frames`), обрезку по весу (`trim_to_weight`) и таблицу отчёта (`segment_report`) — все как чистые тестируемые функции. Рантайм-ветка (`layer2_widget.md`) вызывает их через две CLI-подкоманды: `extract` (кандидаты + contact-sheet + `candidates.json` с `segment_id`) и `select` (join триажа с `candidates.json` по `cand_id` → shortlist + отчёт). Из `frames_schema.json` убирается `segment_hint`.

**Tech Stack:** Python 3.12, ffmpeg 8.1, yt-dlp, Pillow (PIL), pytest. Никаких новых зависимостей.

## Global Constraints

- Скилл — под junction `~/.claude/skills/konspekt` → этот репозиторий; правки делать здесь.
- Windows / PowerShell основной, Bash доступен. Запуск питона скилла: `PYTHONUTF8=1 python ...`.
- Тесты скилла: `.claude/skills/konspekt/tests/`, запуск `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`.
- Скоуп — **только** ветка «виджет с кадрами»: `frames_extract.py`, `frames_schema.json`, `layer2_widget.md`, `tests/test_frames_extract.py`, плюс **контроль веса** в `widget_generator.py` / `md_parser.py` / `tests/test_widget_generator.py` (Task 4.4, включается опциональным флагом `--shortlist` — без него обычная сборка виджета, master-MD и preview **не трогаются**).
- Формат заголовка сегмента мастер-MD закреплён: `## Сегмент N | HH:MM:SS-HH:MM:SS | Тема`; дефис между таймкодами — класс `[–-]` (hyphen или en-dash), как в `md_parser.py:332`. Новый парсер `segment_bounds` **независим** от `md_parser.py` (тот хранит только укороченную строку для отображения, числовых секунд там нет).
- Пороги `scene-detect threshold` и `phash_threshold` — стартовые приближения, подбираются на E2E (не жёсткие числа спеки). В коде выставляются разумные дефолты.
- TDD: сначала падающий тест, потом минимальная реализация. Частые локальные коммиты. **Push и PR не делать — пользователь сам.**
- Не выводить содержимое PNG-кадров или полный `MASTER_..._с_кадрами.md` в чат (существующий запрет `layer2_widget.md`).

---

## Файловая структура

**Правится существующее:**
- `.claude/skills/konspekt/frames_extract.py` — новые функции `segment_bounds`, `assign_segment`, `bucket_timecodes`, `average_hash`/`hamming`/`phash_dedup`, `adaptive_cap`, `select_frames`, `trim_to_weight`, `segment_report`; переписан `build_candidates` (новая сигнатура: `master_md_text`, возврат `segment_id` + итоговый cap); CLI переведён на подкоманды `extract`/`select`.
- `.claude/skills/konspekt/frames_schema.json` — удаляется `segment_hint`.
- `.claude/skills/konspekt/md_parser.py` — `_render_image` помечает `<figure>` атрибутом `data-cand`, вес base64 выносится в переиспользуемый `_encode_frame_b64`; новый `frame_weights` (Task 4.4).
- `.claude/skills/konspekt/widget_generator.py` — чистый `control_weight` + опциональный флаг `--shortlist`: замер итогового HTML и обрезка по весу через `frames_extract.trim_to_weight` (Task 4.4).
- `.claude/skills/konspekt/tests/test_widget_generator.py` — тесты `control_weight` / `frame_weights` / `data-cand` (Task 4.4).
- `.claude/skills/konspekt/layer2_widget.md` — Шаг 1 (флаг `--master-md`, посегментные квоты, pHash), Шаг 2 (триаж скорит всех, не отбирает), новый под-шаг «Отбор» между 2 и 3, Шаг 3 (промпт без `segment_hint`), Шаг 4 (join по `cand_id`, снятие посегментного потолка, адаптивный потолок, исправить фразу «у сегментов нет таймкодов»), Шаг 5/6 (порядок разрешения конфликта веса, таблица по сегментам), таблица «Лимиты по умолчанию».
- `.claude/skills/konspekt/tests/test_frames_extract.py` — тесты новых функций; обновляется существующий `test_build_candidates_numbers_successful_frames_without_gaps` под новую сигнатуру.

---

# ФАЗА 1 — Границы сегментов и привязка таймкода

### Task 1.1: `segment_bounds` — независимый парсер границ + валидация

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces:
  - `class SegmentBoundsError(ValueError)` — ошибка входного контракта мастер-MD.
  - `_hms_to_sec(s: str) -> float` — `HH:MM:SS` или `MM:SS` → секунды.
  - `segment_bounds(master_md_text: str) -> list[dict]` — `[{'id': '01', 'start': float, 'end': float}, ...]` в порядке появления. Пустой результат / `start >= end` / пересечение (`next.start < cur.end`) → `SegmentBoundsError`.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
import pytest

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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k segment_bounds -v`
Ожидание: FAIL (`segment_bounds`/`SegmentBoundsError` не существуют).

- [ ] **Step 3: Реализовать**

В `frames_extract.py` (после `_srt_time_to_sec`):

```python
class SegmentBoundsError(ValueError):
    """Мастер-MD не удовлетворяет контракту границ сегментов."""

_SEG_HEADER = re.compile(
    r'##\s+Сегмент\s+\d+\s*\|\s*([\d:]+)\s*[–-]\s*([\d:]+)\s*\|')

def _hms_to_sec(s):
    sec = 0
    for p in s.strip().split(':'):
        sec = sec * 60 + int(p)
    return float(sec)

def segment_bounds(master_md_text):
    bounds = []
    for i, m in enumerate(_SEG_HEADER.finditer(master_md_text), 1):
        bounds.append({'id': f'{i:02d}',
                       'start': _hms_to_sec(m.group(1)),
                       'end': _hms_to_sec(m.group(2))})
    if not bounds:
        raise SegmentBoundsError(
            'в мастер-MD не найден ни один заголовок '
            '"## Сегмент N | HH:MM:SS-HH:MM:SS | ..." — границы сегментов обязательны')
    for b in bounds:
        if not b['start'] < b['end']:
            raise SegmentBoundsError(
                f"сегмент {b['id']}: пустой/обратный диапазон {b['start']}–{b['end']}")
    for cur, nxt in zip(bounds, bounds[1:]):
        if nxt['start'] < cur['end']:
            raise SegmentBoundsError(
                f"сегменты {cur['id']} и {nxt['id']} пересекаются")
    return bounds
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k segment_bounds -v`
Ожидание: 4 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): segment_bounds — независимый парсер границ сегментов + валидация"
```

### Task 1.2: `assign_segment` — привязка таймкода к сегменту

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Consumes: `segment_bounds()` из Task 1.1.
- Produces: `assign_segment(timecode: float, bounds: list[dict]) -> str` — id сегмента. Раньше начала первого → первый; `>=` конца последнего → последний; внутри диапазона → его id; в щели между сегментами → сегмент с ближайшей границей (start или end).

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
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
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k assign -v`
Ожидание: FAIL (`assign_segment` не существует).

- [ ] **Step 3: Реализовать**

```python
def assign_segment(timecode, bounds):
    first, last = bounds[0], bounds[-1]
    if timecode < first['start']:
        return first['id']
    if timecode >= last['end']:
        return last['id']
    for b in bounds:
        if b['start'] <= timecode < b['end']:
            return b['id']
    # в щели между сегментами — сегмент с ближайшей границей
    return min(bounds,
               key=lambda b: min(abs(timecode - b['start']),
                                 abs(timecode - b['end'])))['id']
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k assign -v`
Ожидание: 4 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): assign_segment — привязка таймкода к сегменту (щель/края)"
```

---

# ФАЗА 2 — pHash-дедуп катов камеры

### Task 2.1: `average_hash` + `hamming`

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces:
  - `average_hash(img) -> int` — 64-битный average-hash: PIL `convert('L').resize((8,8))`, бинаризация по среднему яркости. Принимает путь/`Path` или `PIL.Image`.
  - `hamming(a: int, b: int) -> int` — число различающихся бит.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить (использует _png из существующих тестов)
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
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k average_hash -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать**

```python
def average_hash(img):
    from PIL import Image
    im = img if isinstance(img, Image.Image) else Image.open(img)
    im = im.convert('L').resize((8, 8))
    px = list(im.getdata())
    avg = sum(px) / len(px)
    bits = 0
    for p in px:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return bits

def hamming(a, b):
    return bin(a ^ b).count('1')
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k average_hash -v`
Ожидание: 2 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): average_hash + hamming (average-hash на PIL)"
```

### Task 2.2: `phash_dedup` — скользящее окно N=3

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Consumes: `average_hash`, `hamming` из Task 2.1.
- Produces: `phash_dedup(frames: list[tuple], threshold: int = 6, window: int = 3) -> list[tuple]` — `frames` — список кортежей, где `[0]` = путь к PNG (порядок = временной, как из `bucket_timecodes`). Кадр гасится, если его hash в пределах `threshold` по Хэммингу к любому из **последних `window`** оставленных. Возвращает отфильтрованный список тех же кортежей.

> **Риск: окно скользит через границы бакетов.** `raw` в `build_candidates` отсортирован по таймкоду (`bucket_timecodes` делает `result.sort()`), поэтому окно N=3 сравнивает первый кадр нового сегмента с хвостом предыдущего. Если начало сегмента визуально похоже на конец прошлого (та же говорящая голова) — единственный кандидат сегмента может погаснуть **до** `select_frames`, и гарантия «≥1 кадр на сегмент» молча не сработает (в отчёте — легитимно выглядящий `0`, хотя кадр физически был). Принято как компромисс метода (спека фиксирует average-hash как грубую метрику), но **проверяется глазами на E2E** (Task 7.1 Step 4, критерий «б»). Если на реале это будет заметно — запасной вариант: гонять `phash_dedup` внутри каждого бакета отдельно, а не сквозным потоком (отложено, не в MVP).

- [ ] **Step 1: Написать падающий тест (в т.ч. цикл A→B→A окном N=3)**

```python
# tests/test_frames_extract.py — добавить
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
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k phash_dedup -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать**

```python
def phash_dedup(frames, threshold=6, window=3):
    kept = []
    kept_hashes = []
    for item in frames:
        h = average_hash(item[0])
        if any(hamming(h, kh) <= threshold for kh in kept_hashes[-window:]):
            continue
        kept.append(item)
        kept_hashes.append(h)
    return kept
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k phash_dedup -v`
Ожидание: 3 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): phash_dedup со скользящим окном N=3 (ловит циклические каты)"
```

---

# ФАЗА 3 — Посегментные квоты в конвейере

### Task 3.1: `bucket_timecodes` — квоты по сегментам + fallback-пересчёт

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Consumes: `assign_segment`, `dedup_by_gap` (существует).
- Produces: `bucket_timecodes(scene_tcs, cue_tcs, bounds, min_gap=3.0, per_segment_cap=10, global_cap=150) -> tuple[list[tuple[float,str]], int]` — объединяет scene+cue (уникальные), бакетирует по сегментам, применяет `dedup_by_gap` **внутри каждого бакета** с текущим cap; если суммарно > `global_cap`, уменьшает единый cap для всех бакетов (по 1), пока не впишется или cap не дойдёт до 1. Возвращает `(отсортированный по таймкоду список (tc, segment_id), итоговый_cap)`.

> **Терминология.** Спека (компонент 3) говорит «пропорционально всем бакетам». Здесь это реализовано как **единый нисходящий cap для всех бакетов сразу** (все ужимаются одновременно), а не пропорционально размеру каждого бакета: при cap=k бакеты крупнее k режутся до k, а мелкие (размер < k) не трогаются, пока cap не опустится ниже их размера. Это соответствует смыслу «ужимать все одновременно» и проще; отличие от буквального «пропорционально размеру» проявилось бы только при сильном перекосе размеров бакетов и признано приемлемым.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
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
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k bucket_timecodes -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать**

```python
def bucket_timecodes(scene_tcs, cue_tcs, bounds,
                     min_gap=3.0, per_segment_cap=10, global_cap=150):
    buckets = {b['id']: [] for b in bounds}
    for t in sorted(set(scene_tcs) | set(cue_tcs)):
        buckets[assign_segment(t, bounds)].append(t)
    cap = per_segment_cap
    while True:
        result = []
        for sid, tcs in buckets.items():
            for t in dedup_by_gap(tcs, min_gap=min_gap, cap=cap):
                result.append((t, sid))
        if len(result) <= global_cap or cap <= 1:
            break
        cap -= 1
    result.sort()
    return result, cap
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k bucket_timecodes -v`
Ожидание: 2 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): bucket_timecodes — посегментные квоты + fallback-пересчёт cap"
```

### Task 3.2: Переписать `build_candidates` + `--master-md` + `segment_id` в манифесте

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py` — `build_candidates`, `main`/CLI (`extract`-ветка)
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py` — обновить существующий тест

**Interfaces:**
- Consumes: `segment_bounds`, `bucket_timecodes`, `phash_dedup`, `scene_timecodes`, `cue_timecodes`, `extract_frame`.
- Produces: `build_candidates(video, srt_text, master_md_text, work_dir, threshold=0.2, min_gap=3.0, per_segment_cap=10, global_cap=150, phash_threshold=6) -> tuple[list[tuple[Path,float,str]], int]` — список `(файл, таймкод, segment_id)` после извлечения и pHash-дедупа + итоговый cap бакета. **Бакетирование — по исходному таймкоду события**, извлечение — со сдвигом `shift` внутри `extract_frame` (сдвиг к смыслу события отношения не имеет). `cand_id` может быть непрерывной после pHash — это ок.

- [ ] **Step 1: Обновить существующий тест под новую сигнатуру + добавить тест `segment_id`**

Заменить `test_build_candidates_numbers_successful_frames_without_gaps` на версию с `master_md_text` и заглушкой pHash (сплошные PNG иначе схлопнутся в один):

```python
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
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k build_candidates -v`
Ожидание: FAIL (старая сигнатура/возврат).

- [ ] **Step 3: Переписать `build_candidates`**

```python
def build_candidates(video, srt_text, master_md_text, work_dir,
                     threshold=0.2, min_gap=3.0, per_segment_cap=10,
                     global_cap=150, phash_threshold=6):
    work = Path(work_dir); work.mkdir(parents=True, exist_ok=True)
    bounds = segment_bounds(master_md_text)
    tagged, final_cap = bucket_timecodes(
        scene_timecodes(video, threshold), cue_timecodes(srt_text), bounds,
        min_gap=min_gap, per_segment_cap=per_segment_cap, global_cap=global_cap)
    raw = []
    success_idx = 0
    for tc, sid in tagged:
        tmp = work / f'_tmp_{success_idx + 1:04d}.png'
        try:
            extract_frame(video, tc, tmp)
        except subprocess.CalledProcessError:
            if tmp.exists():
                tmp.unlink()
            continue
        if tmp.exists():
            success_idx += 1
            f = work / f'cand_{success_idx:04d}.png'
            tmp.replace(f)
            raw.append((f, tc, sid))
    return phash_dedup(raw, threshold=phash_threshold), final_cap
```

- [ ] **Step 4: Обновить CLI (`extract`): флаг `--master-md`, `segment_id` в манифесте**

В `main()` заменить плоский разбор аргументов на подкоманду `extract` (подкоманда `select` добавляется в Task 4.3; здесь пока только `extract`):

```python
def _cmd_extract(args):
    work_dir = Path(args.work_dir)
    video = download_video(args.url, work_dir) if args.url else Path(args.video)
    srt_text = Path(args.srt).read_text(encoding='utf-8')
    master_md_text = Path(args.master_md).read_text(encoding='utf-8')
    cands, final_cap = build_candidates(video, srt_text, master_md_text, work_dir,
                                        threshold=args.threshold)
    sheet_path = contact_sheet([f for f, _, _ in cands], work_dir / 'contact_sheet.png')
    manifest_path = work_dir / 'candidates.json'
    manifest_path.write_text(
        json.dumps([{'cand_id': _cand_num(f), 'timecode': t, 'segment_id': sid}
                    for f, t, sid in cands], ensure_ascii=False, indent=2),
        encoding='utf-8')
    print(f'Кандидатов найдено: {len(cands)} (cap на бакет: {final_cap})')
    print(f'Contact-sheet: {sheet_path}')
    print(f'Манифест: {manifest_path}')

def main():
    parser = argparse.ArgumentParser(description='Кадры-кандидаты для виджета /konspekt.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    ex = sub.add_parser('extract', help='кандидаты + contact-sheet + candidates.json')
    src = ex.add_mutually_exclusive_group(required=True)
    src.add_argument('--url', help='YouTube URL')
    src.add_argument('--video', help='путь к локальному видео')
    ex.add_argument('--srt', required=True, help='путь к .srt транскрипту')
    ex.add_argument('--master-md', required=True, help='путь к мастер-MD (границы сегментов)')
    ex.add_argument('--work-dir', required=True, help='папка для кадров и простыни')
    ex.add_argument('--threshold', type=float, default=0.2, help='порог scene-detect')
    ex.set_defaults(func=_cmd_extract)

    args = parser.parse_args()
    args.func(args)
```

> `--dry-run` **удалён**, а не оставлен «для совместимости»: после разбиения на `extract`/`select` подкоманда `extract` и так завершается на простыне+манифесте (триаж/отбор — отдельные шаги ветки), поэтому флаг был бы no-op — `_cmd_extract` его не читал. Оставлять неработающий флаг = вводить в заблуждение. Упоминание `--dry-run` вычищается и из `layer2_widget.md` (Task 6.1 Step 1).

- [ ] **Step 5: Прогнать весь набор — зелёные**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное (старые тесты cue/showinfo/dedup/contact_sheet/codex не затронуты).

- [ ] **Step 6: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): build_candidates на посегментных квотах + pHash + --master-md + segment_id в манифесте"
```

---

# ФАЗА 4 — Отбор с гарантией покрытия и лимиты

### Task 4.1: `adaptive_cap` + `select_frames` (двухфазный отбор)

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces:
  - `adaptive_cap(n_segments: int) -> int` = `max(12, n_segments + 10)`.
  - `select_frames(triage: list[dict], candidates: list[dict], cap: int) -> list[dict]` — join триажа (`{cand_id, type, confidence}`) с `candidates` (`{cand_id, segment_id, ...}`) по `cand_id`. **Обязательная фаза:** для каждого сегмента с ≥1 non-drop кандидатом — кандидат с максимальным `confidence` (`phase='mandatory'`). **Фаза бюджета:** остаток `cap` заполняется по убыванию `confidence` по всему виджету (`phase='budget'`). Возвращает список `{cand_id, segment_id, type, confidence, phase}`. Кандидаты `type == drop` и без пары в `candidates` игнорируются.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
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
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k "adaptive_cap or select_frames" -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать**

```python
def adaptive_cap(n_segments):
    return max(12, n_segments + 10)

def select_frames(triage, candidates, cap):
    seg_by_cand = {c['cand_id']: c['segment_id'] for c in candidates}
    scored = [
        {'cand_id': tr['cand_id'], 'segment_id': seg_by_cand[tr['cand_id']],
         'type': tr['type'], 'confidence': tr['confidence']}
        for tr in triage
        if tr['type'] != 'drop' and tr['cand_id'] in seg_by_cand
    ]
    # Обязательная фаза: лучший non-drop на каждый сегмент
    best = {}
    for s in scored:
        sid = s['segment_id']
        if sid not in best or s['confidence'] > best[sid]['confidence']:
            best[sid] = s
    selected = [dict(s, phase='mandatory') for s in best.values()]
    chosen = {s['cand_id'] for s in selected}
    # Фаза бюджета: остаток по убыванию confidence по всему виджету
    budget = cap - len(selected)
    rest = sorted((s for s in scored if s['cand_id'] not in chosen),
                  key=lambda s: s['confidence'], reverse=True)
    selected.extend(dict(s, phase='budget') for s in rest[:max(0, budget)])
    return selected
```

> **Инвариант cap.** `select_frames` **не** обрезает обязательную фазу до `cap` — она полагается на то, что вызывающий передаёт `cap ≥ числа сегментов с non-drop`. Это гарантирует `adaptive_cap = max(12, сегментов+10)`: обязательных ≤ сегментов, значит `budget = cap − len(mandatory) ≥ 10 > 0` всегда, и `max(0, budget)` — защита от отрицательного бюджета — на штатном пути не срабатывает (мёртвая, но безвредная). Если функцию когда-нибудь вызовут с `cap < числа сегментов` (не текущий пайплайн), она вернёт > cap кадров — обрезка веса до лимита остаётся за `trim_to_weight` (Task 4.2).

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k "adaptive_cap or select_frames" -v`
Ожидание: 5 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): adaptive_cap + select_frames (обязательная фаза + бюджет)"
```

### Task 4.2: `trim_to_weight` — порядок обрезки при превышении 8 МБ

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces: `trim_to_weight(selection: list[dict], size_by_cand: dict[int,int], limit_bytes: int) -> tuple[list[dict], list[str]]` — если суммарный вес отобранных > `limit_bytes`, сначала убирает кадры `phase='budget'` по **возрастанию** `confidence`; если всё ещё превышает — убирает `phase='mandatory'` по возрастанию `confidence`, собирая `segment_id` лишившихся гарантированного кадра. Возвращает `(оставшиеся, список_потерявших_сегментов)`.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
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
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k trim_to_weight -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать**

```python
def trim_to_weight(selection, size_by_cand, limit_bytes):
    kept = list(selection)

    def total():
        return sum(size_by_cand.get(s['cand_id'], 0) for s in kept)

    for s in sorted((s for s in kept if s['phase'] == 'budget'),
                    key=lambda s: s['confidence']):
        if total() <= limit_bytes:
            break
        kept.remove(s)
    lost = []
    if total() > limit_bytes:
        for s in sorted((s for s in kept if s['phase'] == 'mandatory'),
                        key=lambda s: s['confidence']):
            if total() <= limit_bytes:
                break
            kept.remove(s)
            lost.append(s['segment_id'])
    return kept, lost
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k trim_to_weight -v`
Ожидание: 3 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): trim_to_weight — бюджет по возрастанию conf, затем деградация обязательных"
```

### Task 4.3: `segment_report` + подкоманда `select`

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py` — `segment_report`, `_cmd_select`, регистрация подкоманды
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Consumes: `segment_bounds`, `adaptive_cap`, `select_frames`.
- Produces:
  - `segment_report(bounds, candidates, triage, selection) -> list[dict]` — по каждому сегменту `{'segment_id', 'candidates', 'triage_pass', 'inserted'}` (кандидатов после дедупа / прошло триаж / вставлено).
  - CLI `select --candidates <candidates.json> --triage <triage.json> --master-md <путь> --out <shortlist.json>` — join, отбор, запись shortlist, печать таблицы по сегментам.

- [ ] **Step 1: Написать падающий тест `segment_report`**

```python
# tests/test_frames_extract.py — добавить
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
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k segment_report -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать `segment_report`, `_cmd_select`, зарегистрировать подкоманду**

```python
def segment_report(bounds, candidates, triage, selection):
    triage_by = {t['cand_id']: t for t in triage}
    rows = []
    for b in bounds:
        sid = b['id']
        cand_ids = [c['cand_id'] for c in candidates if c['segment_id'] == sid]
        passed = sum(1 for cid in cand_ids
                     if triage_by.get(cid, {}).get('type', 'drop') != 'drop')
        inserted = sum(1 for s in selection if s['segment_id'] == sid)
        rows.append({'segment_id': sid, 'candidates': len(cand_ids),
                     'triage_pass': passed, 'inserted': inserted})
    return rows

def _cmd_select(args):
    cands = json.loads(Path(args.candidates).read_text(encoding='utf-8'))
    triage = json.loads(Path(args.triage).read_text(encoding='utf-8'))
    if isinstance(triage, dict) and 'frames' in triage:
        triage = triage['frames']
    bounds = segment_bounds(Path(args.master_md).read_text(encoding='utf-8'))
    cap = adaptive_cap(len(bounds))
    selection = select_frames(triage, cands, cap)
    Path(args.out).write_text(
        json.dumps(selection, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Отобрано кадров: {len(selection)} (адаптивный потолок {cap})')
    print('Сегмент | Кандидатов | Прошло триаж | Вставлено')
    for r in segment_report(bounds, cands, triage, selection):
        print(f"{r['segment_id']:>7} | {r['candidates']:>10} | "
              f"{r['triage_pass']:>12} | {r['inserted']:>9}")
```

В `main()` добавить регистрацию подкоманды `select` рядом с `extract`:

```python
    sl = sub.add_parser('select', help='join триажа с candidates.json -> shortlist')
    sl.add_argument('--candidates', required=True, help='candidates.json из extract')
    sl.add_argument('--triage', required=True, help='JSON триажа (Шаг 2)')
    sl.add_argument('--master-md', required=True, help='мастер-MD (число сегментов)')
    sl.add_argument('--out', required=True, help='куда записать shortlist.json')
    sl.set_defaults(func=_cmd_select)
```

- [ ] **Step 4: Запустить `segment_report` + весь набор — зелёные**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное.

- [ ] **Step 5: Smoke подкоманды `select` (ручная, на временных JSON)**

```bash
PYTHONUTF8=1 python .claude/skills/konspekt/frames_extract.py select \
  --candidates "<...>/candidates.json" --triage "<...>/triage.json" \
  --master-md "<...>/MASTER_X.md" --out "<...>/shortlist.json"
```
Ожидание: печать таблицы по сегментам, создан `shortlist.json`.

- [ ] **Step 6: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): segment_report + CLI select (join по cand_id, таблица по сегментам)"
```

### Task 4.4: Замкнуть петлю веса ≤8 МБ (замер итогового HTML → `trim_to_weight` → ребилд)

**Мотивация (находка ревью).** До этой задачи `trim_to_weight` (Task 4.2) — функция **без триггера**: рендер картинок (`md_parser._render_image`) жмёт каждую по отдельности (ресайз до `IMG_MAX_WIDTH=1280`, JPEG q82), но **суммарного измерения веса итогового HTML и цикла обрезки нет нигде** — `widget_generator` просто пишет файл. При адаптивном потолке `max(12, сегментов+10)` = 15-25 картинок это реальный риск перевеса (спека, компонент 6). Задача замыкает петлю **build → вес → обрезка → ребилд**: `data-cand` на `<figure>` даёт адрес для хирургического удаления, `control_weight` меряет итог и режет проигравших через `trim_to_weight`. Обычная сборка (без `--shortlist`) не затрагивается.

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py` — `_encode_frame_b64` (выделить из `_render_image`), `data-cand` на `<figure>`, `frame_weights`.
- Modify: `.claude/skills/konspekt/widget_generator.py` — `control_weight`, флаг `--shortlist`, `WEIGHT_LIMIT`.
- Test: `.claude/skills/konspekt/tests/test_widget_generator.py`

**Interfaces:**
- `md_parser._encode_frame_b64(path) -> tuple[str, str]` — `(mime, b64)`; та же логика сжатия, что была в `_render_image` (рефактор без смены поведения).
- `md_parser._render_image(...)` — теперь эмитит `<figure class="frame" data-cand="NN">…` (`NN` — число из имени `cand_NN.png`; если в `src` нет числа — атрибут не добавляется). Прочий вывод неизменен (существующие тесты `test_render_image_embeds_base64` и др. продолжают проходить).
- `md_parser.frame_weights(md_text, base_dir) -> dict[int, int]` — по строкам `![](src)` вернуть `{cand_id: len(b64)}` тем же кодированием.
- `widget_generator.control_weight(html, weights, selection, limit_bytes) -> tuple[str, list[str]]` — если `len(html.encode('utf-8')) > limit_bytes`: считает overhead (`total − сумма весов картинок`), фильтрует `selection` до картиночных кандидатов (`cand_id in weights`), зовёт `trim_to_weight(img_sel, weights, limit − overhead)`, вырезает `<figure … data-cand="N">…</figure>` проигравших. Возвращает `(html, lost_segment_ids)`. Текстовые кадры (не в `weights`) в обрезку веса не попадают. JS не трогается (удаляются только `<figure>`), инвариант `✅ JS syntax OK` сохраняется.
- `widget_generator` CLI: опциональный `--shortlist <shortlist.json>` — при наличии и перевесе применить `control_weight`; при `lost` — предупреждение в stderr. Без флага — поведение как сейчас.

> **Приближение и YAGNI.** overhead (CSS/JS/текст) считается как «итог минус вес картинок» — байты base64-строки ≈ utf-8 байты, точности для порога 8 МБ достаточно (лимит с запасом). «Сначала сильнее сжать, потом резать» (спека, компонент 6, п.1) в MVP реализовано фиксированным сжатием 1280/q82 + обрезкой; **динамическое** пере-сжатие (снижать качество/ширину перед выбрасыванием) отложено как улучшение.

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_widget_generator.py — добавить
import widget_generator
from md_parser import frame_weights, _render_image
from PIL import Image

def _figure(cand, nbytes):
    # фейковая figure заданного «веса»: балласт в base64-поле + метка data-cand
    return (f'<figure class="frame" data-cand="{cand}">'
            f'<img src="data:image/jpeg;base64,{"A" * nbytes}"></figure>')

def test_control_weight_noop_under_limit():
    html = '<x>' + _figure(1, 10) + '</x>'
    sel = [{'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'}]
    out, lost = widget_generator.control_weight(html, {1: 10}, sel, limit_bytes=10_000)
    assert out == html and lost == []

def test_control_weight_drops_budget_figure_first():
    html = '<x>' + _figure(1, 100) + _figure(2, 100) + '</x>'
    weights = {1: 100, 2: 100}
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 2, 'segment_id': '01', 'confidence': 0.2, 'phase': 'budget'},
    ]
    limit = len(html.encode('utf-8')) - 100        # надо срезать ~один кадр
    out, lost = widget_generator.control_weight(html, weights, sel, limit_bytes=limit)
    assert 'data-cand="2"' not in out and 'data-cand="1"' in out
    assert lost == []                              # обязательный не тронут

def test_control_weight_degrades_mandatory_reports_segment():
    html = '<x>' + _figure(1, 100) + _figure(2, 100) + '</x>'
    weights = {1: 100, 2: 100}
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 2, 'segment_id': '02', 'confidence': 0.1, 'phase': 'mandatory'},
    ]
    limit = len(html.encode('utf-8')) - 100        # места только на один кадр
    out, lost = widget_generator.control_weight(html, weights, sel, limit_bytes=limit)
    assert 'data-cand="2"' not in out and 'data-cand="1"' in out
    assert lost == ['02']

def test_frame_weights_and_data_cand(tmp_path):
    Image.new('RGB', (120, 80), (10, 20, 30)).save(tmp_path / 'cand_07.png')
    Image.new('RGB', (120, 80), (90, 90, 90)).save(tmp_path / 'cand_12.png')
    md = "![Слайд 7](cand_07.png)\n\n![Схема 12](cand_12.png)\n"
    w = frame_weights(md, tmp_path)
    assert set(w) == {7, 12} and all(v > 0 for v in w.values())
    assert 'data-cand="7"' in _render_image('Слайд', 'cand_07.png', tmp_path)
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_widget_generator.py" -k "control_weight or frame_weights" -v`
Ожидание: FAIL (`control_weight`/`frame_weights`/`data-cand` не существуют).

- [ ] **Step 3: Реализовать**

В `md_parser.py` — выделить кодирование и добавить `data-cand` + `frame_weights` (рефактор `_render_image` без смены прочего вывода):

```python
def _frame_cand_num(src):
    m = re.search(r'(\d+)', Path(src).stem)
    return int(m.group(1)) if m else None

def _encode_frame_b64(path):
    from PIL import Image
    img = Image.open(path); img.load()
    if img.width > IMG_MAX_WIDTH:
        h = round(img.height * IMG_MAX_WIDTH / img.width)
        img = img.resize((IMG_MAX_WIDTH, h))
    buf = io.BytesIO()
    if img.mode in ('RGBA', 'LA', 'P'):
        img.convert('RGBA').save(buf, format='PNG', optimize=True); mime = 'image/png'
    else:
        img.convert('RGB').save(buf, format='JPEG', quality=82, optimize=True); mime = 'image/jpeg'
    return mime, base64.b64encode(buf.getvalue()).decode('ascii')

def _render_image(alt, src, base_dir):
    """`![alt](src)` -> <figure> c base64 data-URI. Мягкая деградация -> ''."""
    try:
        mime, b64 = _encode_frame_b64(Path(base_dir) / src)
    except Exception as e:
        print(f"[frames] пропуск картинки {src!r}: {e}", file=sys.stderr)
        return ''
    cap = html.escape(alt, quote=True)
    cand = _frame_cand_num(src)
    attr = f' data-cand="{cand}"' if cand is not None else ''
    return (f'<figure class="frame"{attr}><img alt="{cap}" '
            f'src="data:{mime};base64,{b64}"><figcaption>{cap}</figcaption></figure>')

def frame_weights(md_text, base_dir):
    weights = {}
    for m in re.finditer(r'^!\[(.*?)\]\((.+?)\)$', md_text, flags=re.MULTILINE):
        cand = _frame_cand_num(m.group(2))
        if cand is None:
            continue
        try:
            _, b64 = _encode_frame_b64(Path(base_dir) / m.group(2))
        except Exception:
            continue
        weights[cand] = len(b64)
    return weights
```

В `widget_generator.py` — `control_weight`, `WEIGHT_LIMIT`, флаг `--shortlist`:

```python
WEIGHT_LIMIT = 8 * 1024 * 1024

def control_weight(html_str, weights, selection, limit_bytes):
    total = len(html_str.encode('utf-8'))
    if total <= limit_bytes:
        return html_str, []
    import re
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from frames_extract import trim_to_weight
    overhead = total - sum(weights.values())
    img_sel = [s for s in selection if s['cand_id'] in weights]
    kept, lost = trim_to_weight(img_sel, weights, max(0, limit_bytes - overhead))
    keep_ids = {s['cand_id'] for s in kept}
    for s in img_sel:
        if s['cand_id'] not in keep_ids:
            html_str = re.sub(
                r'<figure class="frame" data-cand="%d">.*?</figure>' % s['cand_id'],
                '', html_str, flags=re.DOTALL)
    return html_str, lost
```

В `main()` — распарсить опциональный `--shortlist` (до позиционного `input_path`) и после `build_html` применить контроль веса только для `.md` с переданным shortlist:

```python
    html = build_html(data)
    if shortlist_path and ext == '.md':
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from md_parser import frame_weights
        md_text = open(input_path, encoding='utf-8').read()
        weights = frame_weights(md_text, out_dir)
        selection = json.load(open(shortlist_path, encoding='utf-8'))
        html, lost = control_weight(html, weights, selection, WEIGHT_LIMIT)
        if lost:
            print('⚠ вес >8 МБ: сегменты без гарантированного кадра: '
                  + ', '.join(lost), file=sys.stderr)
```

- [ ] **Step 4: Запустить тесты + весь набор — зелёные**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное (в т.ч. существующие тесты картинок в `test_widget_generator.py` — вывод `_render_image` изменился только добавлением `data-cand`).

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/md_parser.py .claude/skills/konspekt/widget_generator.py .claude/skills/konspekt/tests/test_widget_generator.py
git commit -m "feat(konspekt): контроль веса ≤8 МБ — замер HTML + trim_to_weight + ребилд по --shortlist"
```

---

# ФАЗА 5 — Схема без `segment_hint`

### Task 5.1: Убрать `segment_hint` из `frames_schema.json`

**Files:**
- Modify: `.claude/skills/konspekt/frames_schema.json`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces: контракт vision-JSON без `segment_hint`; ключ кадра — `cand_id`, принадлежность сегменту восстанавливается join'ом по `cand_id` (Task 4.3), а не угадыванием.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
import json as _json

def test_schema_has_no_segment_hint():
    schema_path = Path(__file__).resolve().parents[1] / 'frames_schema.json'
    schema = _json.loads(schema_path.read_text(encoding='utf-8'))
    props = schema['properties']['frames']['items']['properties']
    required = schema['properties']['frames']['items']['required']
    assert 'segment_hint' not in props
    assert 'segment_hint' not in required
    assert 'cand_id' in props and 'cand_id' in required
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k segment_hint -v`
Ожидание: FAIL (`segment_hint` пока в схеме).

- [ ] **Step 3: Убрать `segment_hint` из схемы**

В `frames_schema.json` удалить строку свойства `"segment_hint": {"type": ["string", "null"]}` и убрать `"segment_hint"` из массива `required`. Итог:

```json
{
  "type": "object",
  "properties": {
    "frames": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "cand_id": {"type": "integer"},
          "timecode": {"type": ["number", "null"]},
          "type": {"type": "string", "enum": ["prompt", "slide-text", "illustration", "drop"]},
          "text": {"type": ["string", "null"]},
          "caption": {"type": ["string", "null"]},
          "confidence": {"type": "number"}
        },
        "required": ["cand_id", "timecode", "type", "text", "caption", "confidence"],
        "additionalProperties": false
      }
    }
  },
  "required": ["frames"],
  "additionalProperties": false
}
```

- [ ] **Step 4: Запустить тест + весь набор — зелёные**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_schema.json .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): убрать segment_hint из frames_schema — сегмент через join по cand_id"
```

---

# ФАЗА 6 — Документация ветки

### Task 6.1: Переписать ветку кадров в `layer2_widget.md`

**Files:**
- Modify: `.claude/skills/konspekt/layer2_widget.md`

> Правки текстовые, отдельного теста нет — проверка через grep-ассерты в Step 8. Каждый под-шаг ниже — отдельная точечная правка того же файла; коммит один в конце.

- [ ] **Step 1: Шаг 1 — флаг `--master-md`, подкоманда `extract`, посегментные квоты, pHash**

В блоке команды Шага 1 (`layer2_widget.md:174-178`) добавить подкоманду `extract` и обязательный `--master-md`:

```
PYTHONUTF8=1 python "$HOME/.claude/skills/konspekt/frames_extract.py" extract \
  --url "<youtube-url>" --srt "<рабочая-папка>/SRC_....srt" \
  --master-md "<рабочая-папка>/MASTER_[Название].md" \
  --work-dir "<рабочая-папка>/frames_work" [--threshold 0.2]
```

Убрать `--dry-run` из команды и из описания флагов (`:180`) — флаг удалён (см. Task 3.2 Step 4): `extract` и так останавливается на простыне+манифесте.

В описании «Под капотом» (`:182`) заменить логику дедупа/cap: `dedup_by_gap` теперь применяется **внутри каждого сегментного бакета** (`bucket_timecodes` через `segment_bounds`), с общим предохранителем ~150 (пропорциональный пересчёт cap); после извлечения работает `phash_dedup` (average-hash, скользящее окно N=3) — гасит повторные каты камеры. Порог scene-detect по умолчанию понижен (0.2, подбирается на E2E — pHash гасит возросший шум).

В описании `candidates.json` (`:184`) заменить `{cand_id, timecode}` на `{cand_id, timecode, segment_id}`. Обновить примечание про min-gap/cap (`:186`): посегментный cap стартует с 10, общий предохранитель 150.

- [ ] **Step 2: Шаг 2 — триаж скорит всех, отбор не его ответственность**

В Шаге 2 (`:188-200`) убрать формулировку «отобрать shortlist 5–15 кандидатов». Зафиксировать: триаж **оценивает каждого** кандидата (`{cand_id, type, confidence}`), включая заведомо шумные, **не режет сам**. Формулировка Codex-промпта уже соответствует («для КАЖДОГО кандидата поле type... confidence») — оставить. Убрать финальную фразу «Из ответа оставляем кандидатов с `type != drop`» (отбор ушёл в отдельный под-шаг).

- [ ] **Step 3: Новый под-шаг «Отбор shortlist (детерминированный, главный поток)» между Шагом 2 и Шагом 3**

Вставить раздел: результат триажа (JSON по `cand_id`) сохранить в `frames_work/triage.json`, затем вызвать детерминированный отбор:

```
PYTHONUTF8=1 python "$HOME/.claude/skills/konspekt/frames_extract.py" select \
  --candidates "<рабочая-папка>/frames_work/candidates.json" \
  --triage "<рабочая-папка>/frames_work/triage.json" \
  --master-md "<рабочая-папка>/MASTER_[Название].md" \
  --out "<рабочая-папка>/frames_work/shortlist.json"
```

Описать двухфазную логику (`select_frames`): **обязательная фаза** — лучший non-drop кадр на каждый сегмент (гарантия ≥1); **фаза бюджета** — остаток адаптивного потолка `max(12, сегментов+10)` по убыванию `confidence` по всему виджету. Сегмент без non-drop кандидатов законно остаётся без кадра. `shortlist.json` → вход Шага 3.

- [ ] **Step 4: Шаг 3 — промпт без `segment_hint`, разбирать только shortlist**

В Шаге 3 (`:202-216`) в Codex-промпте (`:210`) убрать `segment_hint` из требуемых полей — оставить `type`, дословный `text`, `caption`, `confidence`. В перечне полей фолбэк-контракта (`:216`) тоже убрать `segment_hint`. Уточнить: full-res разбирает только кандидатов из `shortlist.json`.

- [ ] **Step 5: Шаг 4 — join по `cand_id`, снятие посегментного потолка, исправить фразу про таймкоды**

В Шаге 4 (`:218-229`):
- заменить «привязка кадр→сегмент — по `segment_hint` и смыслу (у сегментов мастер-MD нет собственных таймкодов, машинной синхронизации нет)» на: **принадлежность сегменту берётся из `shortlist.json`/`candidates.json` по `cand_id`** (детерминированный join, посчитан на этапе `extract` по таймкоду события — у сегментов мастер-MD **есть** таймкоды в шапке);
- убрать упоминание входного поля `segment_hint` в перечне JSON-результата (`:220`);
- заменить строку лимитов (`:229`) «≤12 картинок на виджет, ≤2 на сегмент»: посегментного потолка **нет**, общий потолок адаптивный `max(12, сегментов+10)`, отбор регулируется двухфазной логикой.

- [ ] **Step 6: Шаг 5/6 — контроль веса (автоматический) + таблица по сегментам**

В Шаге 5 (`:233-239`) в команду сборки добавить `--shortlist "<рабочая-папка>/frames_work/shortlist.json"` — это включает контроль веса в `widget_generator` (Task 4.4):

```
PYTHONUTF8=1 python "$HOME/.claude/skills/konspekt/widget_generator.py" \
  "<рабочая-папка>/MASTER_[Название]_с_кадрами.md" \
  --shortlist "<рабочая-папка>/frames_work/shortlist.json"
```

Описать процедуру разрешения «покрытие vs вес ≤8 МБ», которую `control_weight` выполняет **автоматически**: (1) картинки уже сжаты при рендере (ресайз 1280 / JPEG q82); (2) если итоговый HTML всё равно >8 МБ — убираются `<figure>` фазы бюджета по возрастанию `confidence` (`trim_to_weight`); (3) в крайнем случае — деградация обязательных с предупреждением в stderr, какие сегменты лишились гарантированного кадра (эти `segment_id` идут в отчёт Шага 6). Тихого падения нет — при перевесе печатается явное предупреждение. Динамическое пере-сжатие (снижать качество перед выбрасыванием) — отложенное улучшение.

В Шаге 6 (`:241-243`) дополнить отчёт таблицей по сегментам (её печатает подкоманда `select`):

```
Сегмент | Кандидатов (после дедупа) | Прошло триаж | Вставлено
01      | 4                          | 2            | 1
02      | 0                          | 0            | 0
```

Общие числа (найдено / shortlist / текстом / картинкой / отброшено) — оставить.

- [ ] **Step 7: Таблица «Лимиты по умолчанию»**

Обновить таблицу (`:256-265`):
- Порог scene-detection: `0.2 (стартовый, подбирается на E2E)`;
- Кандидатов на отсмотр (cap): `посегментные квоты (старт ≤10/сегмент) + предохранитель ~150`;
- Картинок на сегмент: `без потолка (двухфазный отбор)`;
- Картинок на виджет: `max(12, сегментов+10)`;
- добавить строку `Порог pHash-дедупа | 6 бит по Хэммингу (стартовый, подбирается на E2E)`.

- [ ] **Step 8: Проверить, что устаревших формулировок не осталось**

Run: `rg -n "segment_hint|у сегментов.*нет.*таймкод|≤2 на сегмент|≤12 картинок|shortlist 5–15|dry-run" .claude/skills/konspekt/layer2_widget.md`
Ожидание: пусто (все вхождения переписаны).

- [ ] **Step 9: Коммит**

```bash
git add .claude/skills/konspekt/layer2_widget.md
git commit -m "docs(konspekt): ветка кадров — квоты/pHash/двухфазный отбор/адаптивный потолок/таблица по сегментам"
```

---

# ФАЗА 7 — E2E (ручной прогон)

### Task 7.1: Прогон на реальном уроке с несколькими сегментами

**Files:** —

- [ ] **Step 1: Выбрать урок**

Серия из K_T_P с `MASTER_*.md` (несколько сегментов, разное визуальное наполнение) и YouTube-URL/локальным видео.

- [ ] **Step 2: `extract` + проверка манифеста**

Прогнать `frames_extract.py extract --url/--video ... --srt ... --master-md ... --work-dir ...`. Проверить `candidates.json` (у каждого кандидата есть `segment_id`), число кандидатов в разумных пределах, отсутствие явных дублей одного ракурса на contact-sheet.

- [ ] **Step 3: Триаж → `select` → полный прогон ветки**

Триаж (Codex/Sonnet) → `triage.json` → `frames_extract.py select ...` → `shortlist.json` + таблица по сегментам → Шаг 3 (full-res) → вписать кадры в `MASTER_[Название]_с_кадрами.md` → собрать `WIDGET_[Название]_с_кадрами.html`.

- [ ] **Step 4: Проверка глазами (критерии спеки)**

(а) нет дублей одного ракурса; (б) хотя бы один слайд на сегмент, где он был отснят; (в) богатый сегмент получает больше одного кадра без искусственного обрезания; (г) таблица по сегментам совпадает с тем, что видно в виджете; вес HTML ≤8 МБ; `✅ JS syntax OK`.

- [ ] **Step 5: Подстроить пороги и зафиксировать наблюдения**

По итогам подправить `--threshold` (scene-detect) и `phash_threshold` (дефолт в коде). Наблюдения — в `backlog.md`. Артефакты прогона (видео, `frames_work`, копию MD, виджет) не коммитить — это продукты в K_T_P.

---

## Self-Review (заполнено при написании плана)

**Покрытие спеки (7 компонентов + обработка ошибок + тесты):**
1. `segment_bounds` (независимый парсер, валидация монотонности/непересечения/непустоты) → Task 1.1; привязка (края/щель, по исходному таймкоду) → Task 1.2 + `build_candidates` Task 3.2.
2. `phash_dedup` (average-hash PIL, окно N=3, цикл A→B→A) → Task 2.1–2.2.
3. Посегментные квоты + fallback-пересчёт при >150 → Task 3.1; интеграция в `build_candidates` → Task 3.2.
4. Явный порядок «триаж (скорит всех) → детерминированный двухфазный отбор → full-res только shortlist» → Task 4.1 (`select_frames`) + документация Task 6.1 (Шаги 2/новый/3).
5. Удаление `segment_hint` + join по `cand_id` → Task 5.1 (схема) + Task 4.3 (`select_frames`/`select`) + Task 6.1 (Шаги 3/4).
6. Адаптивный потолок `max(12, сегментов+10)` + порядок разрешения конфликта веса → Task 4.1 (`adaptive_cap`), Task 4.2 (`trim_to_weight` как чистая политика) + **Task 4.4 (замкнутая петля веса: замер итогового HTML в `control_weight` → `trim_to_weight` → вырезание `<figure>` → предупреждение)**, Task 6.1 (Шаг 5/6, флаг `--shortlist`).
7. Отчёт-таблица по сегментам → Task 4.3 (`segment_report`, печать в `select`) + Task 6.1 (Шаг 6).
8. Исправить фразу «у сегментов нет таймкодов» → Task 6.1 Step 5.
- Обработка ошибок: нет `--master-md`/сегментов → `SegmentBoundsError` (Task 1.1, `build_candidates` через `segment_bounds`); немонотонность/пересечение → та же ошибка; пустой бакет → ноль в отчёте (`segment_report`); превышение веса итогового HTML → `control_weight` режет бюджет, затем обязательные, `lost` → предупреждение в stderr + отчёт (Task 4.4, Task 6.1 Шаг 6).
- Тесты спеки: `segment_bounds` (1.1), бакетирование по исходному таймкоду (3.2), `phash_dedup` три кейса (2.2), посегментные квоты + fallback 150 (3.1), двухфазный отбор + join (4.1/4.3), вес — бюджет раньше обязательных (4.2), контроль веса итогового HTML + `data-cand`/`frame_weights` (4.4), схема без `segment_hint` (5.1), E2E (7.1).

**Плейсхолдеры:** код приведён для всех тестируемых задач; текстовые правки `layer2_widget.md` — с точными якорями строк и grep-проверкой (Task 6.1 Step 8).

**Согласованность типов/имён (сквозная):**
- `segment_bounds(str) -> list[{'id','start','end'}]`; `assign_segment(float, bounds) -> str`.
- `bucket_timecodes(...) -> (list[(float,str)], int)`; `phash_dedup(list[tuple]) -> list[tuple]` (первый элемент кортежа — путь).
- `build_candidates(...) -> (list[(Path,float,str)], int)`; манифест — `{cand_id, timecode, segment_id}`.
- `adaptive_cap(int) -> int`; `select_frames(triage, candidates, cap) -> list[{cand_id, segment_id, type, confidence, phase}]`; `phase ∈ {'mandatory','budget'}` — единое написание в `select_frames`/`trim_to_weight`/`segment_report`.
- `trim_to_weight(selection, size_by_cand, limit) -> (list, list[str])`; `segment_report(bounds, candidates, triage, selection) -> list[{segment_id, candidates, triage_pass, inserted}]`.
- `frame_weights(md_text, base_dir) -> dict[cand_id, int]`; `control_weight(html, weights, selection, limit) -> (html, list[segment_id])` — `selection` = `shortlist.json` (та же форма, что отдаёт `select_frames`: `{cand_id, segment_id, confidence, phase}`); ключ join с картинками — `cand_id` (число из `cand_NN.png` = `data-cand`).
- Ключ join везде — `cand_id`; `segment_id` — строка `'01'`, `'02'`, … (совпадает с `id` из `segment_bounds`).
