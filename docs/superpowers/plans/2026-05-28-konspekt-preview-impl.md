# /konspekt-preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать скилл `/konspekt-preview` — один проход агента, который читает транскрипт (локальный или скачанный с YouTube) и пишет связный нарративный обзор ~800–950 слов с рекомендацией по глубине обработки.

**Architecture:** Markdown-driven скилл (SKILL.md как промпт-инструкция для агента) + Python-помощник для YouTube (`yt-dlp` + переразбивка SRT в 30-секундные блоки). Без субагентов, без хуков, без чанкования.

**Tech Stack:** Markdown (SKILL.md), Python 3 + `yt-dlp` CLI, pytest для юнит-тестов.

**Спецификация:** [docs/superpowers/specs/2026-05-28-konspekt-preview-design.md](../specs/2026-05-28-konspekt-preview-design.md)

---

## File Structure

**Создаются:**

- `.claude/skills/konspekt-preview/SKILL.md` (~250 строк) — промпт-инструкция: когда вызывается, как обрабатывать входы, шаблон обзора, правила сохранения, граничные случаи.
- `.claude/skills/konspekt-preview/youtube_to_srt.py` (~120 строк) — модуль с функциями `parse_srt`, `rebucket`, `format_srt`, `download_subtitles`, `main`. CLI-точка входа.
- `.claude/skills/konspekt-preview/tests/test_youtube_to_srt.py` (~80 строк) — юнит-тесты на парсинг и переразбивку.
- `.claude/skills/konspekt-preview/tests/__init__.py` (пустой) — чтобы pytest подхватил пакет.

**Модифицируются:**

- `CLAUDE.md` — добавить одну строку про новый скилл и убрать TODO про карту смыслов в .md (если он уже неактуален; проверить по факту).

---

## Task 1: Структура скилла и минимальный SKILL.md

**Files:**
- Create: `.claude/skills/konspekt-preview/SKILL.md`

- [ ] **Step 1: Создать директорию и минимальный SKILL.md с frontmatter**

Создать файл `.claude/skills/konspekt-preview/SKILL.md` с содержимым:

```markdown
---
name: konspekt-preview
description: Предварительная оценка видео — связный нарративный обзор ~800–950 слов по сырому транскрипту (локальный файл или YouTube-ссылка). Без сопроводилок и серийного контекста. Дешёвое «первое касание» перед решением запускать /konspekt.
---

# Скилл: /konspekt-preview

Один проход Claude: транскрипт → связный обзор ~800–950 слов.

## Файлы скилла

- `SKILL.md` — этот файл (методология + формат + шаблон).
- `youtube_to_srt.py` — скачивание субтитров с YouTube и переразбивка в 30-секундные блоки.
- `tests/test_youtube_to_srt.py` — юнит-тесты.

## Когда вызывается

- `/konspekt-preview <путь к транскрипту>` — локальный `.srt`/`.vtt`/`.txt`/`.md`.
- `/konspekt-preview <YouTube-ссылка>` — `https://www.youtube.com/watch?v=...` или `https://youtu.be/...`.
- `/konspekt-preview` без аргумента — спросить путь или ссылку.

---
```

- [ ] **Step 2: Проверить, что директория создана**

Run: `ls .claude/skills/konspekt-preview/`
Expected: видеть `SKILL.md`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt-preview/SKILL.md
git commit -m "feat(preview): создать каркас скилла /konspekt-preview"
```

---

## Task 2: SKILL.md — ШАГ 0. Получение транскрипта

**Files:**
- Modify: `.claude/skills/konspekt-preview/SKILL.md`

- [ ] **Step 1: Добавить раздел про входы и YouTube**

Дописать в `SKILL.md` после раздела «Когда вызывается»:

````markdown
## ШАГ 0. Получение транскрипта

### 0.1. Локальный файл

Поддерживаемые форматы: `.srt`, `.vtt`, `.txt`, `.md`.

- Прочитать файл целиком через Read.
- Если файл не существует — сообщить пользователю и остановиться.
- Если файл `>` 30 000 токенов (≈ 2 часов лекции) — попросить разрезать на источнике, оценить по частям.

### 0.2. YouTube-ссылка

Если аргумент — URL вида `https://www.youtube.com/watch?v=...` или `https://youtu.be/...`:

1. Запустить `youtube_to_srt.py` через Bash:

   ```bash
   python .claude/skills/konspekt-preview/youtube_to_srt.py "<URL>" transcripts/
   ```

2. Скрипт пытается скачать **ручные субтитры** на оригинальном языке. Если их нет — берёт **авто-генерированные**. Если нет ни ручных, ни авто — выходит с кодом 2 и сообщением: «У этого видео нет субтитров».
3. Результат — путь к файлу `transcripts/SRC_transcript_<title>.srt` с 30-секундными блоками.
4. Если такой файл уже есть — скрипт допишет суффикс `_v2`, `_v3` и т.д. (никогда не перезаписывает молча).

**Если скрипт вернул код 2 (нет субтитров)** — сообщить пользователю:

> У этого видео нет субтитров. Транскрибируй отдельно (Whisper или сервис) и подавай `.srt` напрямую.

И остановиться.

**Если скачано успешно** — далее работать со скачанным файлом как с обычным локальным транскриптом.

### 0.3. Язык вывода

Обзор всегда пишется **по-русски**, независимо от языка транскрипта. Если оригинал на английском или другом языке — переводить смысл естественно при написании обзора, не дословно.

---
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/konspekt-preview/SKILL.md
git commit -m "feat(preview): SKILL.md — ШАГ 0 (получение транскрипта, YouTube)"
```

---

## Task 3: SKILL.md — ШАГ 1. Чтение и оценка

**Files:**
- Modify: `.claude/skills/konspekt-preview/SKILL.md`

- [ ] **Step 1: Дописать ШАГ 1**

Дописать в `SKILL.md` после ШАГ 0:

````markdown
## ШАГ 1. Чтение и оценка

1. **Прочитать транскрипт целиком.**
2. **Определить длительность.**
   - Для `.srt`/`.vtt` — из **последнего таймстампа в файле**, не из упоминаний времени в речи. Спикер может говорить «у нас час впереди», а реально записано 35 минут — брать таймстамп.
   - Для `.txt`/`.md` без таймингов — оценка по объёму (примерно).
3. **Определить имя спикера.** Из транскрипта (если представляется) или из имени файла.
4. **Зафиксировать тип видео** одной фразой (лекция, разбор, разговор, демо, интервью, стрим, Q&A).
5. **Определить, есть ли единая нить** (методология / арка / разрозненные темы). Это влияет на структуру раздела «О чём по сути».
6. **Найти «жемчужины»** — короткие сильные моменты вне ядра (история, инсайт, мотивирующая иллюстрация). Они идут в раздел «Как раскрыто» или в «Где смотреть» как точечная отметка.
7. **Определить «стартовый шум»** — если первые минуты заняты приветствиями, проблемами связи, организационкой — отметить минуту, до которой можно мотать.

Это внутренняя подготовка. В файл она не выводится — только используется при написании обзора в ШАГ 2.

---
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/konspekt-preview/SKILL.md
git commit -m "feat(preview): SKILL.md — ШАГ 1 (чтение и оценка)"
```

---

## Task 4: SKILL.md — ШАГ 2. Формат и шаблон обзора

**Files:**
- Modify: `.claude/skills/konspekt-preview/SKILL.md`

- [ ] **Step 1: Дописать принципы формы**

Дописать в `SKILL.md` после ШАГ 1:

````markdown
## ШАГ 2. Написание обзора

### 2.1. Принципы формы

- **Связный нарративный рассказ**, не маркерные блоки. Раздел течёт абзацами, списки — только в трёх специальных местах (см. 2.2).
- **Объём ~800–950 слов.** Читается за ~5 минут. Меньше — теряется содержательность; больше — обзор перестаёт быть «первым касанием».
- **Голос спокойного знающего коллеги.** Без академического дистанцирования, без рекламной интонации, без панибратства. Близко к голосу мастер-MD `/konspekt`.
- **Простой язык.** Без «риторической дуги», «фундамента, который держит», «глубинного зачем». Тест: прочитать вслух — звучит как нормальная речь?
- **Жирное** — сжатые формулировки ключевых мыслей абзацев. По тем же правилам, что в `/konspekt`. Тест: прочитать только жирное сверху вниз — складывается ли канва смыслов?
- **Тон описательный, не оценочный.** Не «отличное видео», а «методология стройная, артефактов много». Не «слабая часть», а «много общих слов, конкретики мало».
- **Без ASCII-схем, Mermaid, Unicode-полосок, шапок-карточек в `code-fence`.** Эти приёмы проверены в пилотировании — утяжеляют восприятие, ломают поток.

### 2.2. Структура (шаблон)

Семь разделов в строгом порядке:

````markdown
# [Короткий заголовок видео]

*[Подзаголовок-курсивом — одна фраза про суть.]*

**Длительность:** [HH:MM] (полезного потока ~[HH:MM]) · **Спикер:** [имя] · **Формат:** [короткое описание]

---

## Что это

[1–2 абзаца. Физика видео: формат, темп, кто говорит, как устроен экран,
видимые проблемы (плохой звук, не открылась презентация, и т.п.).
Если есть «стартовый шум» — упомянуть с минутой, до которой можно мотать.]

> **Имей в виду:** [одно предложение про главное предупреждение для зрителя,
> если есть. Если нет — блок опускается полностью.]

---

## О чём по сути

[2–4 абзаца. Сквозная тема, риторическая позиция автора, главная мысль одной
фразой. Если у автора есть отчётливая методология — она перечисляется
маркированным списком из 3–5 пунктов внутри этого раздела (список даёт
«остров» для глаза, не ломая поток).]

---

## Как раскрыто

[2–3 абзаца. Глубина, плотность, конкретика — словами, не баллами. Где ядро,
где Q&A, есть ли «жемчужины» в неожиданных местах. Дословные шаблоны
(промпты, фразы) — курсивом в кавычках, если они короткие; жирное на ключевых
формулировках. Список из 2–4 опор внутри раздела допустим.]

---

## На вынос

[1 строка-зацепка + маркированный список из 4–6 конкретных артефактов,
которые можно взять и применить. Каждый пункт — с жирным заголовком и
коротким пояснением: `- **Артефакт:** что это и где применить`.]

---

## Кому зайдёт

[1–2 абзаца простой прозой. Один абзац про целевую аудиторию,
один — про кому будет мало нового. Без таблиц.]

---

## Где смотреть

| Минуты | Что | Решение |
| --- | --- | --- |
| 00:00 – HH:MM | [описание участка] | смотреть / по интересу / проматывать / пропускать |

[Таблица 3–5 строк. Колонка «Решение» — из ограниченного словаря выше.
Если транскрипт без таймингов — раздел заменяется на абзац словами
(«первая треть — то-то; ядро в середине; концовка — Q&A»).]

---

## Рекомендация

> **Смотреть [полностью / выборочно / пропустить].** [Конкретика по участкам.]
>
> **Глубина обработки:** [полный мастер-MD через `/konspekt` /
> краткое саммари / не нужно]. [Если нужны сопроводилки для `/konspekt` —
> явно сказать, что приложить.]
````

### 2.3. Что НЕ должно быть в обзоре

- Метрики, баллы, проценты.
- ASCII-арт, Mermaid-диаграммы, Unicode-полоски, шапки-карточки в `code-fence`.
- Длинные цитаты из транскрипта (> 1 строки).
- Имена участников чата / Q&A — описывать без имён («один из участников спрашивает», «в чате уточняют»).
- Личные впечатления агента («мне понравилось», «я считаю»).
- Оценочные эпитеты («отличное», «гениальное», «слабое»).
- Автоматический вызов `/konspekt` — даже если рекомендация «делать полный мастер-MD». Решение запуска — за пользователем.

### 2.4. Раздел «Где смотреть» — отдельно

Это **единственный табличный элемент** в обзоре. Проверено в пилотировании: таблица в этом месте работает как компактная навигационная карта, не утяжеляет восприятие. Колонки фиксированные: `Минуты | Что | Решение`. Значения «Решение» — только из словаря: `смотреть`, `по интересу`, `проматывать`, `пропускать`.

---
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/konspekt-preview/SKILL.md
git commit -m "feat(preview): SKILL.md — ШАГ 2 (формат, шаблон, что не должно быть)"
```

---

## Task 5: SKILL.md — ШАГ 3, граничные случаи, дисциплина

**Files:**
- Modify: `.claude/skills/konspekt-preview/SKILL.md`

- [ ] **Step 1: Дописать оставшиеся разделы**

Дописать в `SKILL.md` после ШАГ 2:

````markdown
## ШАГ 3. Сохранение

**Автоматически, без вопроса.**

### Куда

- Если транскрипт лежит в **рабочей папке урока** (например, `F:/.../М3-Д4.../SRC_*.srt`) — обзор сохранять **рядом** как `OUT_<название>_обзор.md`. Симметрично с тем, как `/konspekt` сохраняет `OUT_<название>_мастер.md`.
- Если транскрипт лежит в `transcripts/` проекта — обзор сохранять туда же как `<название>_обзор.md`.
- Для YouTube-входа транскрипт изначально лежит в `transcripts/`, поэтому обзор тоже идёт туда.

### Имя файла обзора

- Базируется на имени транскрипта: убрать префиксы `SRC_transcript_`, `SRC_Тайминг_`, расширение, добавить `_обзор.md`.
- Если транскрипт уже не имеет узнаваемого префикса — просто заменить расширение на `_обзор.md`.

### Отчёт в чате

После сохранения:

```text
Обзор готов: [путь]/[название]_обзор.md
```

Никаких дополнительных строк. Если в обзоре сделали оговорки про неполноту материала (нет слайдов, плохое распознавание) — это уже внутри файла.

---

## Граничные случаи

- **Транскрипт > 30 000 токенов** → попросить разрезать на источнике, обработать по частям.
- **Нет таймстампов** (`.txt`/`.md`) → раздел «Где смотреть» становится словесным абзацем; длительность оценить по объёму.
- **Очень короткий транскрипт** (< 5 минут полезного потока) → обзор сжать до 300–500 слов, разделы «Что это» и «О чём по сути» можно слить.
- **Несколько спикеров** → описать кратко («двое ведут разговор», «панельная дискуссия из четырёх»); имена не персонифицировать, если это не критично для смысла.
- **Транскрипт явно мусорный** (битый, не транскрипт, машинный перевод низкого качества) — коротко сообщить о проблеме и спросить пользователя, продолжать ли. Не писать обзор поверх мусора.
- **YouTube-видео без субтитров** → отказать с инструкцией (см. 0.2).
- **YouTube-видео > 2 часов** → транскрипт скачается, но потом попросить разрезать.

---

## Стыковка с другими скиллами

- **`/konspekt`** — независимый. `/konspekt-preview` в разделе «Рекомендация» **явно указывает**, нужен ли последующий `/konspekt`, но автоматически не запускает. Пользователь вызывает отдельно.
- **`/digest`** — другая задача (оценка через wiki). Оба скилла могут вызываться на одном источнике в любом порядке.

---

## Дисциплина

- **Не использовать `TodoWrite`** — пайплайн линейный, прогресс виден из текста сообщений.
- **Не запускать субагентов и deferred tools.**
- **Не читать** `profile_*.md`, серийный контекст, сопроводилки, `tov_<серия>.md`, wiki. Это намеренная дешевизна первого касания.
- **Не предлагать улучшения транскрипта** (groom, чистку шумов распознавания) — у обзора своя задача.
- **Не вызывать `/konspekt` автоматически.**
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/konspekt-preview/SKILL.md
git commit -m "feat(preview): SKILL.md — ШАГ 3, граничные случаи, стыковка, дисциплина"
```

---

## Task 6: Python — тесты на `parse_srt`

**Files:**
- Create: `.claude/skills/konspekt-preview/tests/__init__.py`
- Create: `.claude/skills/konspekt-preview/tests/test_youtube_to_srt.py`

- [ ] **Step 1: Создать пустой `__init__.py`**

```bash
mkdir -p .claude/skills/konspekt-preview/tests
echo. > .claude/skills/konspekt-preview/tests/__init__.py
```

(PowerShell: `New-Item -ItemType Directory -Force .claude/skills/konspekt-preview/tests; New-Item -ItemType File .claude/skills/konspekt-preview/tests/__init__.py`)

- [ ] **Step 2: Написать тесты на `parse_srt`**

Создать `.claude/skills/konspekt-preview/tests/test_youtube_to_srt.py`:

```python
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
```

- [ ] **Step 3: Запустить тесты — должны упасть (нет реализации)**

Run:

```bash
cd .claude/skills/konspekt-preview && python -m pytest tests/ -v
```

Expected: `ImportError` или `ModuleNotFoundError` на `from youtube_to_srt import ...`.

---

## Task 7: Python — реализация `parse_srt` + `format_srt`

**Files:**
- Create: `.claude/skills/konspekt-preview/youtube_to_srt.py`

- [ ] **Step 1: Создать модуль с `parse_srt` и `format_srt`**

Создать `.claude/skills/konspekt-preview/youtube_to_srt.py`:

```python
"""Скачивание субтитров с YouTube и переразбивка SRT на 30-секундные блоки.

CLI: python youtube_to_srt.py <youtube_url> <output_dir>
"""

import re
import subprocess
import sys
from pathlib import Path

BLOCK_SECONDS = 30
TIMESTAMP_RE = re.compile(
    r'(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})\s*-->\s*'
    r'(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})'
)


def _ts_to_ms(h: str, m: str, s: str, ms: str) -> int:
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)


def _ms_to_ts(ms: int) -> str:
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(content: str) -> list[dict]:
    """Парсит SRT-строку в список сегментов.

    Каждый сегмент: {'index': int, 'start_ms': int, 'end_ms': int, 'text': str}.
    """
    segments = []
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        # lines[0] — индекс (может быть отсутствует или нечисловой — терпим)
        try:
            index = int(lines[0])
            ts_line = lines[1]
            text_lines = lines[2:]
        except ValueError:
            index = len(segments) + 1
            ts_line = lines[0]
            text_lines = lines[1:]
        m = TIMESTAMP_RE.search(ts_line)
        if not m:
            continue
        start_ms = _ts_to_ms(*m.group(1, 2, 3, 4))
        end_ms = _ts_to_ms(*m.group(5, 6, 7, 8))
        text = ' '.join(line.strip() for line in text_lines if line.strip())
        segments.append({
            'index': index,
            'start_ms': start_ms,
            'end_ms': end_ms,
            'text': text,
        })
    return segments


def format_srt(segments: list[dict]) -> str:
    """Сериализует список сегментов обратно в SRT."""
    parts = []
    for i, seg in enumerate(segments, 1):
        parts.append(
            f"{i}\n"
            f"{_ms_to_ts(seg['start_ms'])} --> {_ms_to_ts(seg['end_ms'])}\n"
            f"{seg['text']}\n"
        )
    return '\n'.join(parts)
```

- [ ] **Step 2: Запустить тесты на `parse_srt`**

Run:

```bash
cd .claude/skills/konspekt-preview && python -m pytest tests/test_youtube_to_srt.py -v -k parse_srt
```

Expected: 5 PASS, 0 FAIL. (`rebucket` ещё не реализован — пока не вызывается.)

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt-preview/youtube_to_srt.py .claude/skills/konspekt-preview/tests/
git commit -m "feat(preview): parse_srt + format_srt с юнит-тестами"
```

---

## Task 8: Python — тесты на `rebucket`

**Files:**
- Modify: `.claude/skills/konspekt-preview/tests/test_youtube_to_srt.py`

- [ ] **Step 1: Дописать тесты на `rebucket`**

Дописать в конец `tests/test_youtube_to_srt.py`:

```python


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
    assert result[0]['end_ms'] == 5000  # end_ms не растягиваем за пределы реального конца
    assert result[0]['text'] == 'короткий'


def test_rebucket_segment_longer_than_block():
    """Сегмент длиннее блока (например, музыкальная пауза) — оставить как есть, в своём блоке."""
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
```

- [ ] **Step 2: Запустить тесты — должны упасть на `rebucket`**

Run:

```bash
cd .claude/skills/konspekt-preview && python -m pytest tests/test_youtube_to_srt.py -v -k rebucket
```

Expected: `ImportError` на `from youtube_to_srt import ... rebucket ...` (rebucket ещё не определён).

---

## Task 9: Python — реализация `rebucket`

**Files:**
- Modify: `.claude/skills/konspekt-preview/youtube_to_srt.py`

- [ ] **Step 1: Дописать `rebucket` в `youtube_to_srt.py`**

Дописать в `youtube_to_srt.py` после `format_srt`:

```python


def rebucket(segments: list[dict], block_seconds: int = BLOCK_SECONDS) -> list[dict]:
    """Склеивает короткие сегменты в блоки по N секунд.

    Правила:
    - Каждый блок длится максимум N секунд, начинается на границе N (0, N, 2N, ...).
    - Сегменты, начавшиеся в пределах блока, добавляются в него — даже если перетекают
      за границу.
    - Сегмент длиннее N секунд оставляется в своём блоке как есть.
    - Индексы перенумеровываются с 1.
    """
    if not segments:
        return []

    block_ms = block_seconds * 1000
    blocks: list[dict] = []
    current: dict | None = None
    current_boundary = 0

    for seg in segments:
        seg_boundary = (seg['start_ms'] // block_ms) * block_ms
        if current is None or seg_boundary != current_boundary:
            if current is not None:
                blocks.append(current)
            current_boundary = seg_boundary
            current = {
                'index': 0,
                'start_ms': seg_boundary,
                'end_ms': seg['end_ms'],
                'text': seg['text'],
            }
        else:
            current['end_ms'] = seg['end_ms']
            current['text'] = (current['text'] + ' ' + seg['text']).strip()

    if current is not None:
        blocks.append(current)

    for i, b in enumerate(blocks, 1):
        b['index'] = i

    return blocks
```

- [ ] **Step 2: Запустить тесты — все должны пройти**

Run:

```bash
cd .claude/skills/konspekt-preview && python -m pytest tests/test_youtube_to_srt.py -v
```

Expected: все ~10 тестов PASS.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt-preview/youtube_to_srt.py .claude/skills/konspekt-preview/tests/test_youtube_to_srt.py
git commit -m "feat(preview): rebucket для переразбивки SRT в 30-сек блоки"
```

---

## Task 10: Python — `download_subtitles` и CLI

**Files:**
- Modify: `.claude/skills/konspekt-preview/youtube_to_srt.py`

- [ ] **Step 1: Дописать `download_subtitles` и `main`**

Дописать в `youtube_to_srt.py` после `rebucket`:

```python


def _slugify(title: str) -> str:
    """Превращает заголовок YouTube в безопасное имя файла."""
    slug = re.sub(r'[^\w\s\-]', '', title, flags=re.UNICODE)
    slug = re.sub(r'\s+', '_', slug.strip())
    return slug[:80] or 'youtube_video'


def _get_video_title(url: str) -> str:
    """Получает заголовок видео через yt-dlp."""
    result = subprocess.run(
        ['yt-dlp', '--get-title', '--no-warnings', url],
        capture_output=True, text=True, encoding='utf-8',
    )
    if result.returncode != 0:
        raise RuntimeError(f'yt-dlp --get-title failed: {result.stderr}')
    return result.stdout.strip()


def download_subtitles(url: str, output_dir: Path) -> Path:
    """Скачивает субтитры с YouTube и возвращает путь к SRT-файлу.

    Сначала пробует ручные на оригинальном языке, потом авто. Если нет ни тех,
    ни других — вызывает SystemExit с кодом 2.
    """
    title = _get_video_title(url)
    slug = _slugify(title)
    output_dir.mkdir(parents=True, exist_ok=True)

    tmp_template = str(output_dir / f'_tmp_{slug}.%(ext)s')

    # 1. Сначала ручные субтитры на оригинальном языке.
    result = subprocess.run(
        ['yt-dlp', '--write-subs', '--sub-langs', 'orig',
         '--sub-format', 'srt', '--skip-download', '--no-warnings',
         '-o', tmp_template, url],
        capture_output=True, text=True, encoding='utf-8',
    )
    srt_files = list(output_dir.glob(f'_tmp_{slug}*.srt'))

    # 2. Если не нашли — пробуем авто-генерированные.
    if not srt_files:
        result = subprocess.run(
            ['yt-dlp', '--write-auto-subs', '--sub-langs', 'orig',
             '--sub-format', 'srt', '--skip-download', '--no-warnings',
             '-o', tmp_template, url],
            capture_output=True, text=True, encoding='utf-8',
        )
        srt_files = list(output_dir.glob(f'_tmp_{slug}*.srt'))

    if not srt_files:
        print('ERROR: У этого видео нет субтитров (ни ручных, ни авто).',
              file=sys.stderr)
        sys.exit(2)

    tmp_srt = srt_files[0]

    # Переразбиваем в 30-секундные блоки.
    content = tmp_srt.read_text(encoding='utf-8')
    segments = parse_srt(content)
    rebucketed = rebucket(segments)
    rebucketed_srt = format_srt(rebucketed)

    # Финальное имя с префиксом SRC_transcript_, с защитой от перезаписи.
    base_name = f'SRC_transcript_{slug}'
    final_path = output_dir / f'{base_name}.srt'
    suffix_n = 2
    while final_path.exists():
        final_path = output_dir / f'{base_name}_v{suffix_n}.srt'
        suffix_n += 1

    final_path.write_text(rebucketed_srt, encoding='utf-8')

    # Удалить временный файл.
    tmp_srt.unlink()

    return final_path


def main():
    if len(sys.argv) != 3:
        print('Usage: youtube_to_srt.py <youtube_url> <output_dir>',
              file=sys.stderr)
        sys.exit(1)
    url, output_dir = sys.argv[1], Path(sys.argv[2])
    final_path = download_subtitles(url, output_dir)
    print(str(final_path))


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Прогнать существующие тесты — ничего не сломалось**

Run:

```bash
cd .claude/skills/konspekt-preview && python -m pytest tests/test_youtube_to_srt.py -v
```

Expected: все ~10 тестов PASS.

- [ ] **Step 3: Smoke-тест CLI справки**

Run:

```bash
python .claude/skills/konspekt-preview/youtube_to_srt.py
```

Expected: на stderr `Usage: youtube_to_srt.py <youtube_url> <output_dir>`, exit code 1.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/konspekt-preview/youtube_to_srt.py
git commit -m "feat(preview): download_subtitles + CLI для youtube_to_srt"
```

---

## Task 11: End-to-end проверка на локальном SRT

**Files:**
- Read: `F:/Наш Архив/ИИ/Ледовских/Вайбкодинг/Модуль 3. Спринт по заработку/М3-Д4. Быстрые каналы заработка-2/SRC_Тайминг_Вайбкодинг  М3 Д4  Быстрые каналы заработка_RU.srt`

- [ ] **Step 1: Запустить скилл вручную (новая сессия / Skill tool)**

Из новой сессии:

```
/konspekt-preview F:/Наш Архив/ИИ/Ледовских/Вайбкодинг/Модуль 3. Спринт по заработку/М3-Д4. Быстрые каналы заработка-2/SRC_Тайминг_Вайбкодинг  М3 Д4  Быстрые каналы заработка_RU.srt
```

- [ ] **Step 2: Сверить результат с эталонным «вторым пилотом»**

Эталон — обзор М3-Д4 из брейнстормиинговой сессии 2026-05-28 (см. историю чата той сессии или этот план):
- Длительность: 35 минут (полезного потока ~25)
- Заголовок про «первые клиенты на вайб-кодинг через знакомых»
- 7 разделов в правильном порядке
- Таблица «Где смотреть» 4 строки
- Рекомендация: смотреть выборочно, полный мастер-MD

Проверить:
- Файл сохранён в `F:/.../М3-Д4.../OUT_*_обзор.md` (рядом с транскриптом, не в `transcripts/` проекта).
- Длительность взята из последнего таймстампа SRT (`00:34:47`), не из речи спикера.
- Объём 800–950 слов.
- Нет ASCII-схем, нет жирных шапок-карточек.

- [ ] **Step 3: Если есть расхождения с эталоном — править SKILL.md**

Если, например, скилл выдал отчёт другого формата — найти место в `SKILL.md`, где правило сформулировано неточно, и поправить. Запустить заново. Цикл до сходимости с эталоном.

- [ ] **Step 4: Commit правок (если были)**

```bash
git add .claude/skills/konspekt-preview/SKILL.md
git commit -m "fix(preview): уточнить SKILL.md после end-to-end теста"
```

(Если правок не было — пропустить.)

---

## Task 12: End-to-end проверка на YouTube-ссылке

**Files:** —

- [ ] **Step 1: Выбрать тестовое YouTube-видео**

Условия:
- На русском или английском (для проверки перевода).
- 10–30 минут (не слишком короткое, не слишком длинное).
- Есть субтитры (ручные или авто).
- Желательно не из курса Ледовских (чтобы избежать дублирования с локальными транскриптами).

Например: любая случайная техническая лекция с конференции YouTube.

- [ ] **Step 2: Запустить скилл с YouTube-ссылкой**

```
/konspekt-preview https://www.youtube.com/watch?v=<id>
```

- [ ] **Step 3: Проверить артефакты**

- В `transcripts/` появился файл `SRC_transcript_<slug>.srt` с 30-секундными блоками.
- В `transcripts/` появился файл `<slug>_обзор.md` рядом.
- Обзор соответствует формату.

- [ ] **Step 4: Проверить кейс «нет субтитров»**

Найти YouTube-видео без субтитров (или с заблокированными — короткие shorts иногда без них). Запустить.

Expected: сообщение от скилла «У этого видео нет субтитров. Транскрибируй отдельно...» и остановка. Никакого мусорного обзора не сгенерировано.

- [ ] **Step 5: Если есть проблемы — править**

Например: yt-dlp не находит языки → уточнить аргумент `--sub-langs`. Скрипт падает на UTF-8 → добавить кодировку. SKILL.md не упоминает edge case → дописать.

- [ ] **Step 6: Commit правок (если были)**

```bash
git add .claude/skills/konspekt-preview/
git commit -m "fix(preview): уточнения после YouTube end-to-end теста"
```

(Если правок не было — пропустить.)

---

## Task 13: Документация проекта

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Добавить упоминание скилла в CLAUDE.md**

Открыть `CLAUDE.md` (корень проекта) и добавить раздел или строку:

```markdown
## Доступные скиллы

- `/konspekt` — полный мастер-MD из транскрипта (см. `.claude/skills/konspekt/`).
- `/konspekt-preview` — предварительная оценка видео (связный обзор ~800–950 слов; см. `.claude/skills/konspekt-preview/`).
```

Если такого раздела ещё нет — добавить его после блока «Как работать». Если уже есть — дописать строку про `/konspekt-preview`.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: упомянуть скилл /konspekt-preview в CLAUDE.md"
```

---

## Task 14: Финальная проверка и обновление хранилища

**Files:** —

- [ ] **Step 1: Прогнать всё ещё раз кратко**

- Все тесты проходят: `cd .claude/skills/konspekt-preview && python -m pytest tests/ -v`
- Структура файлов соответствует разделу «File Structure» этого плана.
- Спека и план закоммичены.

- [ ] **Step 2: Сказать пользователю «обнови хранилище»**

Сообщить, что скилл готов, попросить пользователя сказать «обнови хранилище» — тогда обновится `D:/Users/Вова/Desktop/Work/VibeCoding/vibecoding vault/projects/konspekt-project.md` (запись про новый скилл).

---

## Notes for the implementer

- **Кодировки.** Все Python-вызовы `subprocess.run` с `encoding='utf-8'` — на Windows иначе ломается кириллица в заголовках YouTube. Если всё равно ломается — попробовать `errors='replace'`.
- **`--sub-langs orig`.** Это значение yt-dlp для оригинального языка видео. Если на конкретном видео не сработает — fallback на конкретные коды (`ru`, `en`) или `--sub-langs '.*'` с последующим выбором первого `.srt`.
- **PowerShell на Windows.** Для запуска тестов из PowerShell использовать `cd .claude/skills/konspekt-preview ; python -m pytest tests/ -v` (точка с запятой вместо `&&`, который в PowerShell 5.1 не работает).
- **`mkdir -p` в Bash vs `New-Item -Force` в PowerShell.** В шагах используется bash-форма; на Windows может потребоваться PowerShell-вариант (см. Task 6).
- **При первом запуске скилла** проверять, что Claude Code прочитал именно новый `SKILL.md`, а не закешировал старый. При сомнении — перезапустить сессию.
- **При расхождении обзора с эталоном** — не «починить вручную в файле», а **найти и поправить правило в SKILL.md**, после чего перегенерировать. Иначе следующий запуск выдаст ту же ошибку.
