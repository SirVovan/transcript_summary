# /konspekt preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать режим `preview` внутри существующего скилла `/konspekt` — один проход агента, который читает транскрипт (локальный или скачанный с YouTube) и пишет связный нарративный обзор ~800–950 слов с рекомендацией по глубине обработки.

**Architecture:** Режим внутри общей структуры `/konspekt`, по аналогии с режимом «виджет». Самодостаточный `preview.md` рядом с `SKILL.md` (изоляция правил мастер-MD). Общая утилита `youtube_to_srt.py` в корне скилла. Минимальные правки в существующий `SKILL.md`.

**Tech Stack:** Markdown (preview.md как промпт-инструкция), Python 3 + `yt-dlp` CLI, pytest. Реализация Python-кода — через **`codex exec`** как сабагента из Bash; SKILL.md/preview.md и end-to-end — Claude.

**Спецификация:** [docs/superpowers/specs/2026-05-28-konspekt-preview-design.md](../specs/2026-05-28-konspekt-preview-design.md)

**Опорная заметка про codex:** `D:/Users/Вова/Desktop/Work/VibeCoding/vibecoding vault/knowledge/codex-as-subagent.md` — точные флаги `codex exec`, замеры, подводные камни.

---

## File Structure

**Создаются:**

- `.claude/skills/konspekt/preview.md` (~250 строк) — самодостаточная методология режима: вводный блок «забудь правила мастер-MD», обработка входов, шаблон обзора, правила сохранения, граничные случаи, дисциплина.
- `.claude/skills/konspekt/youtube_to_srt.py` (~120 строк) — `parse_srt`, `rebucket`, `format_srt`, `download_subtitles`, `main`.
- `.claude/skills/konspekt/tests/test_youtube_to_srt.py` (~80 строк) — юнит-тесты.

**Модифицируются:**

- `.claude/skills/konspekt/SKILL.md` — две короткие правки (строка в «Команды пользователя» + диспетчерский блок в конце).
- `CLAUDE.md` (корень проекта) — упомянуть новый режим `preview` одной строкой.

**Не трогаются:**

- `profile_*.md`, `layer2_widget.md`, `layer3_recon.md`, `md_parser.py`, `widget_generator.py`, `validate_widget.py`, существующие тесты в `tests/` — работа режимов `master` и `widget` остаётся без изменений.

---

## Task 1: SKILL.md — добавить точки входа для режима `preview`

**Files:**
- Modify: `.claude/skills/konspekt/SKILL.md`

- [ ] **Step 1: Добавить строку в раздел «Команды пользователя»**

Найти в `SKILL.md` блок:

```markdown
## Команды пользователя

- `/konspekt` + транскрипт → мастер-MD.
- `/konspekt — сделай виджет из <файл>` → виджет: Слой 2 + Слой 3 одним процессом (см. `layer2_widget.md`, затем `layer3_recon.md`).
```

Дописать третью строку:

```markdown
- `/konspekt preview <путь или YouTube-URL>` → предварительный обзор видео (см. `preview.md`).
```

- [ ] **Step 2: Добавить диспетчерский блок в конец SKILL.md**

Найти в самом конце `SKILL.md` блок «Виджет (Слой 2 + Слой 3)». **После него** добавить:

````markdown
---

## Режим `preview`

Когда пользователь пишет `/konspekt preview <путь или YouTube-URL>` — это **отдельный режим**, не часть пайплайна мастер-MD.

**Алгоритм:**

1. Прочитать `preview.md`.
2. Дальше действовать **только по `preview.md`**, игнорируя всё остальное в этом SKILL.md (правила сегментации, шаблон сегмента, ToV, три уровня И/М/Д, самопроверку — это правила режима `master`, к обзору они не применяются).

`preview.md` самодостаточный — содержит весь шаблон обзора, дисциплину, граничные случаи, инструкцию по работе с YouTube.

**Связь с режимом `master`:** односторонняя через **рекомендацию** в финальном разделе обзора. Автоматический переход в `master` не делается — пользователь вызывает `/konspekt <путь>` отдельной командой.
````

- [ ] **Step 3: Проверить, что текущие правила скилла не нарушены**

Run: `git diff .claude/skills/konspekt/SKILL.md`

Expected: только добавления (одна строка в «Команды» + новый раздел в конце). Никаких изменений в существующих разделах про сегментацию, шаблон, голос.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/konspekt/SKILL.md
git commit -m "feat(preview): зарегистрировать режим preview в SKILL.md /konspekt"
```

---

## Task 2: preview.md — каркас, изоляция от мастер-MD, входы

**Files:**
- Create: `.claude/skills/konspekt/preview.md`

- [ ] **Step 1: Создать `preview.md` с шапкой, изоляцией и ШАГ 0**

Создать `.claude/skills/konspekt/preview.md`:

````markdown
# Режим `/konspekt preview` — предварительная оценка видео

## ВАЖНО: изоляция от правил мастер-MD

Этот файл — **самодостаточная инструкция режима `preview`**. Когда работаешь в этом режиме, **забудь всё, что написано в `SKILL.md` про сегментацию, шаблон сегмента, голос ToV, три уровня (И)/(М)/(Д), самопроверку, профили (`profile_*.md`), серийный контекст**. К обзору эти правила не применяются — это другой жанр.

Применяй только то, что написано **здесь**, в `preview.md`.

---

## Когда вызывается

- `/konspekt preview <путь к транскрипту>` — локальный `.srt`/`.vtt`/`.txt`/`.md`.
- `/konspekt preview <YouTube-URL>` — `https://www.youtube.com/watch?v=...` или `https://youtu.be/...`.
- `/konspekt preview` без аргумента — спросить путь или ссылку.

---

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
   python .claude/skills/konspekt/youtube_to_srt.py "<URL>" transcripts/
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
git add .claude/skills/konspekt/preview.md
git commit -m "feat(preview): preview.md — каркас, изоляция, ШАГ 0 (входы, YouTube)"
```

---

## Task 3: preview.md — ШАГ 1. Чтение и оценка

**Files:**
- Modify: `.claude/skills/konspekt/preview.md`

- [ ] **Step 1: Дописать ШАГ 1**

Дописать в `preview.md` после ШАГ 0:

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
git add .claude/skills/konspekt/preview.md
git commit -m "feat(preview): preview.md — ШАГ 1 (чтение и оценка)"
```

---

## Task 4: preview.md — ШАГ 2. Формат и шаблон обзора

**Files:**
- Modify: `.claude/skills/konspekt/preview.md`

- [ ] **Step 1: Дописать принципы формы и шаблон**

Дописать в `preview.md` после ШАГ 1:

````markdown
## ШАГ 2. Написание обзора

### 2.1. Принципы формы

- **Связный нарративный рассказ**, не маркерные блоки. Раздел течёт абзацами, списки — только в трёх специальных местах (см. 2.2).
- **Объём ~800–950 слов.** Читается за ~5 минут. Меньше — теряется содержательность; больше — обзор перестаёт быть «первым касанием».
- **Голос спокойного знающего коллеги.** Без академического дистанцирования, без рекламной интонации, без панибратства. Близко по тону к мастер-MD из режима `master`, но без его структурных элементов.
- **Простой язык.** Без «риторической дуги», «фундамента, который держит», «глубинного зачем». Тест: прочитать вслух — звучит как нормальная речь?
- **Жирное** — сжатые формулировки ключевых мыслей абзацев. Тест: прочитать только жирное сверху вниз — складывается ли канва смыслов?
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
маркированным списком из 3–5 пунктов внутри этого раздела.]

---

## Как раскрыто

[2–3 абзаца. Глубина, плотность, конкретика — словами, не баллами. Где ядро,
где Q&A, есть ли «жемчужины» в неожиданных местах. Дословные шаблоны
(промпты, фразы) — курсивом в кавычках, если они короткие; жирное на ключевых
формулировках. Список из 2–4 опор внутри раздела допустим.]

---

## На вынос

[1 строка-зацепка + маркированный список из 4–6 конкретных артефактов,
которые можно взять и применить: `- **Артефакт:** что это и где применить`.]

---

## Кому зайдёт

[1–2 абзаца простой прозой. Один абзац про целевую аудиторию,
один — про кому будет мало нового. Без таблиц.]

---

## Где смотреть

| Минуты | Что | Решение |
| --- | --- | --- |
| 00:00 – HH:MM | [описание участка] | смотреть / по интересу / проматывать / пропускать |

[Таблица 3–5 строк. Колонка «Решение» — только из словаря выше.
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
- **Элементы шаблона мастер-MD** (`## Сегмент N`, `### Карта`, `### Текст`, `**Ключевая мысль:**`, `> **Принцип:**`, `> **Методология:**` и т.п.) — это другой жанр, в обзоре их быть не должно.
- Автоматический переход в режим `master` — даже если рекомендация «делать полный мастер-MD». Решение запуска — за пользователем.

### 2.4. Раздел «Где смотреть» — отдельно

Это **единственный табличный элемент** в обзоре. Проверено в пилотировании: таблица в этом месте работает как компактная навигационная карта, не утяжеляет восприятие. Колонки фиксированные: `Минуты | Что | Решение`. Значения «Решение» — только из словаря: `смотреть`, `по интересу`, `проматывать`, `пропускать`.

---
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/konspekt/preview.md
git commit -m "feat(preview): preview.md — ШАГ 2 (формат, шаблон, что не должно быть)"
```

---

## Task 5: preview.md — ШАГ 3, граничные случаи, дисциплина

**Files:**
- Modify: `.claude/skills/konspekt/preview.md`

- [ ] **Step 1: Дописать оставшиеся разделы**

Дописать в `preview.md` после ШАГ 2:

````markdown
## ШАГ 3. Сохранение

**Автоматически, без вопроса.**

### Куда

- Если транскрипт лежит в **рабочей папке урока** (например, `F:/.../М3-Д4.../SRC_*.srt`) — обзор сохранять **рядом** как `OUT_<название>_обзор.md`. Симметрично с тем, как режим `master` сохраняет `OUT_<название>_мастер.md`.
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
- **Несколько спикеров** → описать кратко («двое ведут разговор», «панельная дискуссия из четырёх»); имена не персонифицировать.
- **Транскрипт явно мусорный** (битый, не транскрипт, машинный перевод низкого качества) — коротко сообщить о проблеме и спросить пользователя, продолжать ли. Не писать обзор поверх мусора.
- **YouTube-видео без субтитров** → отказать с инструкцией (см. ШАГ 0.2).
- **YouTube-видео > 2 часов** → транскрипт скачается, но потом попросить разрезать.

---

## Дисциплина (важно — не зависит от чтения SKILL.md)

- **Не использовать `TodoWrite`** — пайплайн линейный, прогресс виден из текста сообщений.
- **Не запускать субагентов и deferred tools.**
- **Не читать** `profile_*.md`, серийный контекст (`*_мастер.md`), сопроводилки (`.pptx`, презентации, скрины), `tov_<серия>.md`, wiki. Это намеренная дешевизна первого касания.
- **Не предлагать улучшения транскрипта** (`/groom`, чистка шумов распознавания) — у обзора своя задача.
- **Не применять правила мастер-MD** из `SKILL.md`: ни сегментации, ни шаблона сегмента, ни голоса ToV-через-сегменты, ни самопроверки. Обзор — другой жанр.
- **Не вызывать режим `master` автоматически.**
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/konspekt/preview.md
git commit -m "feat(preview): preview.md — ШАГ 3, граничные случаи, дисциплина"
```

---

## Task 6: Python — тесты на `parse_srt` (Claude пишет тесты)

**Files:**
- Create: `.claude/skills/konspekt/tests/test_youtube_to_srt.py`

- [ ] **Step 1: Написать тесты на `parse_srt`**

(Файл `tests/__init__.py` уже существует в проекте — не создавать заново.)

Создать `.claude/skills/konspekt/tests/test_youtube_to_srt.py`:

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

- [ ] **Step 2: Запустить тесты — должны упасть (нет реализации)**

Run:

```bash
cd .claude/skills/konspekt && python -m pytest tests/test_youtube_to_srt.py -v
```

Expected: `ImportError` или `ModuleNotFoundError` на `from youtube_to_srt import ...`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/tests/test_youtube_to_srt.py
git commit -m "test(preview): тесты parse_srt для youtube_to_srt"
```

---

## Task 7: Python — реализация `parse_srt` + `format_srt` через `codex exec`

**Files:**
- Create: `.claude/skills/konspekt/youtube_to_srt.py`

**Подход:** делегировать написание кода codex'у с готовыми тестами как контрактом. Claude формулирует промпт + ревьюит результат.

- [ ] **Step 1: Подготовить промпт для codex**

Создать временный файл `_codex_prompt_parse_srt.txt`:

```text
Создай Python-файл .claude/skills/konspekt/youtube_to_srt.py со следующим содержимым в начале:

1. Docstring модуля:
   "Скачивание субтитров с YouTube и переразбивка SRT на 30-секундные блоки.
    CLI: python youtube_to_srt.py <youtube_url> <output_dir>"

2. Импорты: re, subprocess, sys, from pathlib import Path

3. Константа BLOCK_SECONDS = 30

4. Регулярка TIMESTAMP_RE для матчинга SRT-таймстампов вида HH:MM:SS,mmm --> HH:MM:SS,mmm
   (с поддержкой как запятой, так и точки как разделителя миллисекунд).

5. Внутренние хелперы:
   - _ts_to_ms(h, m, s, ms) -> int  — конвертит части таймстампа в миллисекунды
   - _ms_to_ts(ms) -> str — обратно в "HH:MM:SS,mmm"

6. parse_srt(content: str) -> list[dict]
   — парсит SRT-строку в список сегментов
   — каждый сегмент: {'index': int, 'start_ms': int, 'end_ms': int, 'text': str}
   — text — это строки текста, склеенные через пробел (без переноса)
   — пустые блоки игнорируются
   — если первая строка блока не число, считает её таймстамп-строкой

7. format_srt(segments: list[dict]) -> str
   — сериализует обратно в SRT-формат
   — индексы перенумеровываются с 1
   — формат: "{i}\n{HH:MM:SS,mmm} --> {HH:MM:SS,mmm}\n{text}\n"
   — блоки разделяются пустой строкой

Контракт задают тесты в .claude/skills/konspekt/tests/test_youtube_to_srt.py — прочитай их (особенно тесты с префиксом test_parse_srt_), реализация должна проходить все. Функцию rebucket пока не реализовывай — она будет в следующем шаге.
```

- [ ] **Step 2: Запустить codex exec**

Run (PowerShell):

```powershell
Get-Content _codex_prompt_parse_srt.txt | codex exec --ephemeral
```

(Точные флаги — в `vibecoding vault/knowledge/codex-as-subagent.md`. На Bash: `cat _codex_prompt_parse_srt.txt | codex exec --ephemeral`. Если codex просит расположение для вывода — указать `.claude/skills/konspekt/youtube_to_srt.py`.)

- [ ] **Step 3: Ревью результата**

Прочитать `.claude/skills/konspekt/youtube_to_srt.py`. Проверить:

- Импорты, BLOCK_SECONDS, TIMESTAMP_RE, _ts_to_ms, _ms_to_ts, parse_srt, format_srt — все на месте.
- Стиль соответствует существующему `md_parser.py` (4 пробела, snake_case, type hints).
- Никаких лишних функций (нет преждевременного `rebucket`, `download_subtitles` — они в следующих задачах).

Если что-то не так — поправить руками или перезапустить codex с уточнённым промптом.

- [ ] **Step 4: Запустить тесты на `parse_srt`**

Run:

```bash
cd .claude/skills/konspekt && python -m pytest tests/test_youtube_to_srt.py -v -k parse_srt
```

Expected: 5 PASS, 0 FAIL.

- [ ] **Step 5: Удалить временный файл и закоммитить**

```bash
rm _codex_prompt_parse_srt.txt
git add .claude/skills/konspekt/youtube_to_srt.py
git commit -m "feat(preview): parse_srt + format_srt (codex implementation)"
```

---

## Task 8: Python — тесты на `rebucket` (Claude пишет тесты)

**Files:**
- Modify: `.claude/skills/konspekt/tests/test_youtube_to_srt.py`

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
```

- [ ] **Step 2: Запустить тесты — `rebucket` должен упасть на `ImportError`**

Run:

```bash
cd .claude/skills/konspekt && python -m pytest tests/test_youtube_to_srt.py -v -k rebucket
```

Expected: `ImportError` на `from youtube_to_srt import ... rebucket ...`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/tests/test_youtube_to_srt.py
git commit -m "test(preview): тесты rebucket для youtube_to_srt"
```

---

## Task 9: Python — реализация `rebucket` через `codex exec`

**Files:**
- Modify: `.claude/skills/konspekt/youtube_to_srt.py`

- [ ] **Step 1: Подготовить промпт для codex**

Создать `_codex_prompt_rebucket.txt`:

```text
В файл .claude/skills/konspekt/youtube_to_srt.py добавь функцию rebucket после format_srt:

rebucket(segments: list[dict], block_seconds: int = BLOCK_SECONDS) -> list[dict]
  — склеивает короткие сегменты в блоки по N секунд

Правила:
- Каждый блок имеет фиксированную границу start_ms = floor(seg.start_ms / block_ms) * block_ms.
- Сегмент идёт в блок, в котором он начался (по start_ms).
- Если несколько сегментов попали в один блок — их text склеивается через пробел, end_ms блока = end_ms последнего сегмента в нём.
- Если сегмент длиннее block_seconds — оставляется в своём блоке как есть, end_ms блока = его реальный end_ms.
- Индексы выходного списка перенумеровываются с 1.
- На пустом входе вернуть [].

Контракт — тесты test_rebucket_* в .claude/skills/konspekt/tests/test_youtube_to_srt.py. Прочитай их и реализуй так, чтобы все проходили.

Не трогай существующий код (parse_srt, format_srt) и не добавляй других функций.
```

- [ ] **Step 2: Запустить codex exec**

Run:

```powershell
Get-Content _codex_prompt_rebucket.txt | codex exec --ephemeral
```

- [ ] **Step 3: Ревью результата**

Прочитать обновлённый `youtube_to_srt.py`. Проверить:

- Функция `rebucket` появилась после `format_srt`.
- Старый код `parse_srt`, `format_srt`, хелперы — без изменений.
- Логика соответствует описанию: блоки по `floor(start_ms / block_ms)`, склейка текста через пробел, индексы с 1.

- [ ] **Step 4: Запустить все тесты — должны пройти**

Run:

```bash
cd .claude/skills/konspekt && python -m pytest tests/test_youtube_to_srt.py -v
```

Expected: все ~10 тестов PASS.

- [ ] **Step 5: Удалить временный файл и закоммитить**

```bash
rm _codex_prompt_rebucket.txt
git add .claude/skills/konspekt/youtube_to_srt.py
git commit -m "feat(preview): rebucket для 30-сек блоков (codex implementation)"
```

---

## Task 10: Python — `download_subtitles` и CLI через `codex exec`

**Files:**
- Modify: `.claude/skills/konspekt/youtube_to_srt.py`

- [ ] **Step 1: Подготовить промпт для codex**

Создать `_codex_prompt_download.txt`:

```text
В файл .claude/skills/konspekt/youtube_to_srt.py добавь функции после rebucket:

1. _slugify(title: str) -> str
   — убирает спецсимволы, заменяет пробелы на _, обрезает до 80 символов
   — поддерживает Unicode (кириллица сохраняется)
   — если результат пустой — возвращает 'youtube_video'

2. _get_video_title(url: str) -> str
   — вызывает: yt-dlp --get-title --no-warnings <url>
   — capture_output=True, text=True, encoding='utf-8'
   — при returncode != 0 — RuntimeError с stderr в сообщении

3. download_subtitles(url: str, output_dir: Path) -> Path
   — алгоритм:
     a) Получить title через _get_video_title, сделать slug через _slugify
     b) output_dir.mkdir(parents=True, exist_ok=True)
     c) tmp_template = str(output_dir / f'_tmp_{slug}.%(ext)s')
     d) Попытка 1: yt-dlp с --write-subs --sub-langs orig --sub-format srt --skip-download --no-warnings -o tmp_template <url>
        Найти tmp файлы через output_dir.glob(f'_tmp_{slug}*.srt').
     e) Если ничего не нашли — Попытка 2 с --write-auto-subs вместо --write-subs.
     f) Если и после этого нет файлов — print('ERROR: У этого видео нет субтитров (ни ручных, ни авто).', file=sys.stderr); sys.exit(2)
     g) Взять первый найденный tmp_srt
     h) Прочитать его, прогнать через parse_srt → rebucket → format_srt
     i) Финальное имя: base_name = f'SRC_transcript_{slug}', final_path = output_dir / f'{base_name}.srt'
        Если уже есть — добавить суффикс _v2, _v3 и т.д. до свободного имени.
     j) Записать результат в final_path с encoding='utf-8'
     k) Удалить tmp_srt
     l) Вернуть final_path

4. main()
   — если len(sys.argv) != 3:
       print('Usage: youtube_to_srt.py <youtube_url> <output_dir>', file=sys.stderr)
       sys.exit(1)
   — url, output_dir = sys.argv[1], Path(sys.argv[2])
   — final_path = download_subtitles(url, output_dir)
   — print(str(final_path))

5. В конце файла:
   if __name__ == '__main__':
       main()

Не трогай существующий код (parse_srt, format_srt, rebucket, хелперы _ts_to_ms, _ms_to_ts).
```

- [ ] **Step 2: Запустить codex exec**

Run:

```powershell
Get-Content _codex_prompt_download.txt | codex exec --ephemeral
```

- [ ] **Step 3: Ревью результата**

Проверить:

- `_slugify`, `_get_video_title`, `download_subtitles`, `main` появились.
- В вызовах `subprocess.run` используются `capture_output=True`, `text=True`, `encoding='utf-8'`.
- Алгоритм соответствует промпту (две попытки: ручные → авто; правильные коды выхода).
- `if __name__ == '__main__': main()` в конце.

- [ ] **Step 4: Прогнать все юнит-тесты — ничего не сломалось**

Run:

```bash
cd .claude/skills/konspekt && python -m pytest tests/test_youtube_to_srt.py -v
```

Expected: все ~10 тестов PASS (новые функции тестами не покрыты — это интеграция, проверяется в Task 12).

- [ ] **Step 5: Smoke-тест CLI справки**

Run:

```bash
python .claude/skills/konspekt/youtube_to_srt.py
```

Expected: на stderr `Usage: youtube_to_srt.py <youtube_url> <output_dir>`, exit code 1.

- [ ] **Step 6: Удалить временный файл и закоммитить**

```bash
rm _codex_prompt_download.txt
git add .claude/skills/konspekt/youtube_to_srt.py
git commit -m "feat(preview): download_subtitles + CLI (codex implementation)"
```

---

## Task 11: End-to-end проверка на локальном SRT (Claude)

**Files:**
- Read: `F:/Наш Архив/ИИ/Ледовских/Вайбкодинг/Модуль 3. Спринт по заработку/М3-Д4. Быстрые каналы заработка-2/SRC_Тайминг_Вайбкодинг  М3 Д4  Быстрые каналы заработка_RU.srt`

- [ ] **Step 1: Запустить режим preview на локальном SRT**

Из новой сессии:

```text
/konspekt preview F:/Наш Архив/ИИ/Ледовских/Вайбкодинг/Модуль 3. Спринт по заработку/М3-Д4. Быстрые каналы заработка-2/SRC_Тайминг_Вайбкодинг  М3 Д4  Быстрые каналы заработка_RU.srt
```

- [ ] **Step 2: Сверить результат с эталоном «второго пилота»**

Эталон — обзор М3-Д4 из брейнсторминговой сессии 2026-05-28:
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
- Нет элементов шаблона мастер-MD (`## Сегмент N`, `### Карта`, `### Текст`, `**Ключевая мысль:**`).
- Агент не пытался применить правила сегментации или другие правила режима `master`.

- [ ] **Step 3: Если есть протечка правил `master` или другие расхождения — править**

Самое вероятное место правки — `preview.md`, раздел «ВАЖНО: изоляция от правил мастер-MD». Если протекают конкретные правила (например, агент сделал `## Сегмент N` или применил `**Ключевая мысль:**`) — добавить их явно в раздел 2.3 «Что НЕ должно быть».

- [ ] **Step 4: Commit правок (если были)**

```bash
git add .claude/skills/konspekt/preview.md
git commit -m "fix(preview): уточнить preview.md после end-to-end теста"
```

(Если правок не было — пропустить.)

---

## Task 12: End-to-end проверка на YouTube-ссылке (Claude)

**Files:** —

- [ ] **Step 1: Выбрать тестовое YouTube-видео**

Условия:
- На русском или английском (для проверки перевода).
- 10–30 минут (не слишком короткое, не слишком длинное).
- Есть субтитры (ручные или авто).
- Желательно не из курса Ледовских (избежать дублирования с локальными транскриптами).

- [ ] **Step 2: Запустить режим preview с YouTube-ссылкой**

```text
/konspekt preview https://www.youtube.com/watch?v=<id>
```

- [ ] **Step 3: Проверить артефакты**

- В `transcripts/` появился файл `SRC_transcript_<slug>.srt` с 30-секундными блоками.
- В `transcripts/` появился файл `<slug>_обзор.md` рядом.
- Обзор соответствует формату.
- Длительность взята из таймстампов (последний `00:HH:MM,...`).

- [ ] **Step 4: Проверить кейс «нет субтитров»**

Найти YouTube-видео без субтитров (короткие shorts иногда без них). Запустить.

Expected: сообщение «У этого видео нет субтитров. Транскрибируй отдельно...» и остановка. Никакого мусорного обзора не сгенерировано.

- [ ] **Step 5: Если есть проблемы — править**

Например: `--sub-langs orig` не сработал → уточнить аргумент (`ru`, `en`, или `.*` с пост-выбором). Скрипт падает на UTF-8 → добавить `errors='replace'`. preview.md не упоминает edge case → дописать.

Правки в Python — могут идти через codex (создать промпт «вот текущий код, вот проблема, исправь только X»), либо вручную, если правка маленькая.

- [ ] **Step 6: Commit правок (если были)**

```bash
git add .claude/skills/konspekt/
git commit -m "fix(preview): уточнения после YouTube end-to-end теста"
```

(Если правок не было — пропустить.)

---

## Task 13: Документация проекта

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Добавить упоминание режима preview в CLAUDE.md**

Найти в `CLAUDE.md` (корень проекта) раздел про скилл `/konspekt`. Дополнить упоминание режимов:

```markdown
Когда пользователь даёт транскрипт или просит создать карту смыслов / конспект / виджет —
использовать скилл `/konspekt`. Он содержит полный пайплайн и все необходимые инструкции.

Режимы скилла:
- `/konspekt <путь>` — полный мастер-MD (основной режим).
- `/konspekt — сделай виджет из <файл>` — виджет (Слой 2 + Слой 3).
- `/konspekt preview <путь или YouTube-URL>` — предварительный обзор видео (~800–950 слов).
```

(Точная формулировка может отличаться — встроить в существующий текст так, чтобы органично смотрелось.)

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: упомянуть режим /konspekt preview в CLAUDE.md"
```

---

## Task 14: Финальная проверка и обновление хранилища

**Files:** —

- [ ] **Step 1: Прогнать всё ещё раз кратко**

- Все тесты проходят: `cd .claude/skills/konspekt && python -m pytest tests/test_youtube_to_srt.py -v`
- Структура файлов соответствует разделу «File Structure» этого плана.
- Спека и план закоммичены.
- Существующие тесты режима `master` не сломались: `cd .claude/skills/konspekt && python -m pytest tests/ -v` (вся папка tests).

- [ ] **Step 2: Сказать пользователю «обнови хранилище»**

Сообщить, что режим готов, попросить пользователя сказать «обнови хранилище» — тогда обновится `D:/Users/Вова/Desktop/Work/VibeCoding/vibecoding vault/projects/konspekt-project.md` (запись про новый режим `preview` внутри `/konspekt`).

---

## Notes for the implementer

### Про codex

- **Точные флаги `codex exec`** — см. `D:/Users/Вова/Desktop/Work/VibeCoding/vibecoding vault/knowledge/codex-as-subagent.md`. Если что-то не работает — там же подводные камни Windows-путей.
- **Качество ~75–80% от Opus.** Готовься ревьюить и иногда править руками. Если codex даёт что-то сильно «не то» — лучше переформулировать промпт или дописать руками, чем гонять циклы.
- **Накладные расходы.** На 3 Python-задачах экономия скромная. Если кажется, что промпт писать дольше, чем код — пиши код сам.
- **Кодировки.** Все Python-вызовы `subprocess.run` должны быть с `encoding='utf-8'` — на Windows иначе ломается кириллица в заголовках YouTube. Если в коде от codex этого нет — добавить вручную.

### Про PowerShell

- Для запуска тестов из PowerShell: `cd .claude/skills/konspekt ; python -m pytest tests/test_youtube_to_srt.py -v` (точка с запятой вместо `&&`).
- `rm` в bash. В PowerShell: `Remove-Item _codex_prompt_*.txt`.

### Про SKILL.md / preview.md

- **При расхождении обзора с эталоном** — не «починить вручную в файле», а **найти и поправить правило в `preview.md`**, после чего перегенерировать.
- **При протечке правил мастер-MD** — усилить раздел «ВАЖНО: изоляция» в `preview.md` или дописать конкретные запреты в раздел 2.3 «Что НЕ должно быть».
- При первом запуске режима после изменений в `SKILL.md` или `preview.md` — рассмотреть перезапуск сессии Claude Code, чтобы наверняка прочитать актуальную версию.

### Про `--sub-langs orig`

- Это специальное значение yt-dlp для оригинального языка видео. Если на конкретном видео не работает — fallback на конкретные коды (`ru`, `en`) или `--sub-langs '.*'` с последующим выбором первого `.srt`.

### Про существующие тесты режима `master`

- В `.claude/skills/konspekt/tests/` уже есть тесты других модулей (`test_widget_generator.py`, `test_preprocessor.py`, `test_route_block.py`). После каждой Python-задачи проверять, что они не сломались:
  ```bash
  cd .claude/skills/konspekt && python -m pytest tests/ -v
  ```
