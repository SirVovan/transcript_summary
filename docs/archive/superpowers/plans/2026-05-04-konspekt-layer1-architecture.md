# Новая архитектура скилла /konspekt (Слой 1) — План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переписать скилл /konspekt под архитектуру Слоя 1: транскрипт читается один раз, пайплайн ШАГ 0→1а→1б→1в производит единственный артефакт — мастер-MD.

**Architecture:** ШАГ 0 (preprocessor.py нарезает транскрипты > 25K токенов) → ШАГ 1а (Claude сегментирует + самопроверка по 4 критериям) → ШАГ 1б (N параллельных subagents по segmentu, каждый по subagent_writer.md) → ШАГ 1в (бригадир по brigadir.md: верификация, гармонизация, переходы, сборка мастер-MD). SKILL.md оркестрирует весь поток.

**Tech Stack:** Python 3 (preprocessor.py), Claude Code skills (markdown-инструкции).

---

## Карта файлов

**Создать:**
- `.claude/skills/konspekt/preprocessor.py` — скрипт: подсчёт токенов, извлечение окон, нарезка транскрипта
- `.claude/skills/konspekt/tests/test_preprocessor.py` — тесты скрипта
- `.claude/skills/konspekt/tov_spec.md` — базовая ToV-спецификация (голос спикера)
- `.claude/skills/konspekt/segmentator.md` — инструкции ШАГ 1а
- `.claude/skills/konspekt/subagent_writer.md` — инструкции для subagent'а ШАГ 1б
- `.claude/skills/konspekt/brigadir.md` — инструкции бригадира ШАГ 1в

**Изменить:**
- `.claude/skills/konspekt/SKILL.md` — полная перезапись под новый пайплайн

**Переименовать (архив, не удалять):**
- `kartograf.md` → `_archived_kartograf.md`
- `konspektolog.md` → `_archived_konspektolog.md`
- `konstitutsiya.md` → `_archived_konstitutsiya.md`
- `xlsx_template.py` → `_archived_xlsx_template.py`
- `karta_example.html` → `_archived_karta_example.html`

**Оставить без изменений:**
- `kartograf_profile_*.md` — справочник, детальная переработка — отдельный спек
- `widget.md`, `widget_generator.py`, `validate_widget.py` — не входят в Слой 1

---

### Task 1: Скрипт предобработки (preprocessor.py)

**Files:**
- Create: `.claude/skills/konspekt/preprocessor.py`
- Create: `.claude/skills/konspekt/tests/test_preprocessor.py`

- [ ] **Step 1: Создать директорию tests и написать тесты**

Create `.claude/skills/konspekt/tests/test_preprocessor.py`:

```python
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
```

- [ ] **Step 2: Запустить тесты — убедиться что падают**

```
cd .claude/skills/konspekt
python -m pytest tests/test_preprocessor.py -v
```

Ожидание: `ModuleNotFoundError: No module named 'preprocessor'`

- [ ] **Step 3: Написать preprocessor.py**

Create `.claude/skills/konspekt/preprocessor.py`:

```python
#!/usr/bin/env python3
"""
preprocessor.py — Предобработка транскрипта для скилла /konspekt.

Команды:
  python preprocessor.py info <файл>                       # Статистика файла
  python preprocessor.py windows <файл>                    # Окна для LLM-анализа границ
  python preprocessor.py split <файл> --at HH:MM:SS,...   # Нарезка по таймингам
"""
import os
import re
import argparse

TOKENS_PER_CHAR = 0.25   # ~4 символа на токен для русского текста
CHUNK_SIZE = 16_000       # Целевой размер куска (токенов)
WINDOW_SIZE = 2_500       # Окно для LLM-анализа границы (токенов с каждой стороны)
OVERLAP = 500             # Перекрытие между кусками (токенов)
LARGE_THRESHOLD = 25_000  # Порог «большого» транскрипта


def estimate_tokens(text: str) -> int:
    return int(len(text) * TOKENS_PER_CHAR)


def time_to_seconds(t: str) -> int:
    parts = list(map(int, t.strip().split(':')))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def parse_transcript_lines(text: str) -> list:
    """Разбирает транскрипт в список dict: time, seconds, text."""
    result = []
    for raw in text.strip().split('\n'):
        m = re.match(r'\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s*(.*)', raw)
        if m:
            h, mm, s, body = m.groups()
            secs = (int(h) * 3600 + int(mm) * 60 + int(s)) if s else (int(h) * 60 + int(mm))
            time_str = f"{int(h):02d}:{int(mm):02d}" + (f":{int(s):02d}" if s else "")
            result.append({'time': time_str, 'seconds': secs, 'text': body.strip()})
        elif raw.strip() and result:
            result[-1]['text'] += ' ' + raw.strip()
    return result


def info(path: str) -> None:
    text = open(path, encoding='utf-8').read()
    tokens = estimate_tokens(text)
    lines = parse_transcript_lines(text)

    print(f"Файл:             {path}")
    print(f"Символов:         {len(text):,}")
    print(f"Токенов (оценка): {tokens:,}")
    print(f"Строк с тайм.:    {len(lines)}")
    if lines:
        print(f"Диапазон:         {lines[0]['time']} – {lines[-1]['time']}")

    if tokens > LARGE_THRESHOLD:
        n = (tokens // CHUNK_SIZE) + 1
        print(f"\n⚠  Транскрипт большой. Рекомендуется разбить на ~{n} части.")
        print(f"   Запустите: python preprocessor.py windows \"{path}\"")
    else:
        print(f"\n✓  Помещается в один проход (≤ {LARGE_THRESHOLD:,} токенов).")


def windows(path: str) -> None:
    text = open(path, encoding='utf-8').read()
    lines = parse_transcript_lines(text)

    boundary_indices = []
    acc = 0
    prev_acc = 0
    for i, ln in enumerate(lines):
        acc += estimate_tokens(ln['text'])
        if acc - prev_acc >= CHUNK_SIZE:
            boundary_indices.append(i)
            prev_acc = acc

    if not boundary_indices:
        print("Нарезка не требуется.")
        return

    for b_num, center in enumerate(boundary_indices):
        # Идти назад до WINDOW_SIZE // 2 токенов
        win_tok = 0
        start = center
        while start > 0 and win_tok < WINDOW_SIZE // 2:
            start -= 1
            win_tok += estimate_tokens(lines[start]['text'])

        # Идти вперёд до WINDOW_SIZE // 2 токенов
        win_tok = 0
        end = center
        while end < len(lines) - 1 and win_tok < WINDOW_SIZE // 2:
            end += 1
            win_tok += estimate_tokens(lines[end]['text'])

        window = '\n'.join(f"[{l['time']}] {l['text']}" for l in lines[start:end + 1])

        print(f"\n{'=' * 60}")
        print(f"ТОЧКА {b_num + 1} | около {lines[center]['time']}")
        print('=' * 60)
        print(window)
        print(f"\n--- ЗАДАЧА ДЛЯ LLM ---")
        print("В этом фрагменте найди точку, где заканчивается смысловой блок.")
        print("Верни тайминг (HH:MM:SS) начала СЛЕДУЮЩЕГО блока.")
        print("Если не уверен — напиши явно: «Не уверен: [причина]»")


def split(path: str, boundary_times: list) -> list:
    text = open(path, encoding='utf-8').read()
    lines = parse_transcript_lines(text)
    boundaries = sorted(time_to_seconds(t) for t in boundary_times)

    groups = []
    current = []
    b_idx = 0

    for ln in lines:
        if b_idx < len(boundaries) and ln['seconds'] >= boundaries[b_idx]:
            groups.append(current)
            # Перекрытие: берём последние ~OVERLAP токенов из предыдущей группы
            overlap, ov_tok = [], 0
            for prev in reversed(current):
                t = estimate_tokens(prev['text'])
                if ov_tok + t > OVERLAP:
                    break
                overlap.insert(0, prev)
                ov_tok += t
            current = list(overlap)
            b_idx += 1
        current.append(ln)
    groups.append(current)

    base = os.path.splitext(path)[0]
    out_paths = []
    for i, grp in enumerate(groups, 1):
        out = f"{base}_chunk{i:02d}.txt"
        with open(out, 'w', encoding='utf-8') as f:
            for ln in grp:
                f.write(f"[{ln['time']}] {ln['text']}\n")
        tok = sum(estimate_tokens(l['text']) for l in grp)
        print(f"Часть {i}: {out}  (~{tok:,} токенов, {len(grp)} строк)")
        out_paths.append(out)
    return out_paths


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Предобработка транскрипта')
    sub = ap.add_subparsers(dest='cmd')

    p_info = sub.add_parser('info')
    p_info.add_argument('transcript')

    p_win = sub.add_parser('windows')
    p_win.add_argument('transcript')

    p_split = sub.add_parser('split')
    p_split.add_argument('transcript')
    p_split.add_argument('--at', required=True, help='Тайминги через запятую: HH:MM:SS,HH:MM:SS')

    args = ap.parse_args()
    if args.cmd == 'info':
        info(args.transcript)
    elif args.cmd == 'windows':
        windows(args.transcript)
    elif args.cmd == 'split':
        split(args.transcript, [t.strip() for t in args.at.split(',')])
    else:
        ap.print_help()
```

- [ ] **Step 4: Запустить тесты — убедиться что проходят**

```
python -m pytest tests/test_preprocessor.py -v
```

Ожидание: все тесты PASS.

- [ ] **Step 5: Проверить вручную**

```
echo "[00:00:00] Привет это тест." > /tmp/tr.txt
python preprocessor.py info /tmp/tr.txt
```

Ожидание: статистика без ошибок, сообщение `✓ Помещается в один проход`.

- [ ] **Step 6: Коммит**

```bash
git add .claude/skills/konspekt/preprocessor.py .claude/skills/konspekt/tests/
git commit -m "feat(konspekt): add preprocessor.py with token count, windowing, splitting"
```

---

### Task 2: Базовая ToV-спецификация (tov_spec.md)

**Files:**
- Create: `.claude/skills/konspekt/tov_spec.md`

- [ ] **Step 1: Создать tov_spec.md**

Create `.claude/skills/konspekt/tov_spec.md`:

```markdown
# Голос и стиль (ToV-спецификация)

Базовые правила голоса и стиля для написания конспекта.
Используется в ШАГ 1б (subagent_writer.md) и ШАГ 1в (brigadir.md).

---

## Базовые правила (фиксированные)

**Лицо:** Первое лицо единственного числа. Пишешь от имени спикера: «я думаю», «я показываю», «мы разобрали».

**Голос:** Живая разговорная речь — не академический текст, не деловой отчёт. Без канцеляризмов, без пассивного залога там, где можно использовать активный.

**Структура аргументации:** Сначала конкретный пример или история — потом тезис. Читатель должен сначала увидеть ситуацию, потом услышать вывод.

**Абзацы:** Короткие. 2–4 предложения. Одна мысль — один абзац.

**Переходы между абзацами:** Живые связки: «вот почему», «отсюда следует», «но здесь важный момент», «и вот тут я понял». Не бюрократические «во-первых / во-вторых».

**Запрещено:**
- «Таким образом» в конце каждого блока
- Перечисление без пояснений («первое... второе... третье...» без контекста)
- Обобщения без примеров
- Пассивный залог: «было сказано», «является», «рассматривается»
- Академические клише: «в рамках данного», «следует отметить», «необходимо подчеркнуть»

---

## Динамическая часть (заполняется автоматически в ШАГ 1б)

Перед запуском subagents Claude читает первые ~2–3K токенов транскрипта
и выделяет характерные черты речи спикера. Результат вставляется в каждый промпт subagent'а:

```
[TOV_DYNAMIC]
Характерные обороты: ...
Темп и формальность: ...
Фирменные фразы / обращения к аудитории: ...
[/TOV_DYNAMIC]
```

Если характерных черт не выявлено — блок остаётся пустым, работают только базовые правила выше.
```

- [ ] **Step 2: Перенести правила из konstitutsiya.md**

Прочитать `.claude/skills/konspekt/_archive_2026-05-04/konstitutsiya.md`.
Найти правила, которые не дублируют уже написанные базовые правила в tov_spec.md,
и добавить их в раздел «Базовые правила» (запрещённые приёмы, структурные требования и т.п.).

- [ ] **Step 3: Коммит**

```bash
git add .claude/skills/konspekt/tov_spec.md
git commit -m "feat(konspekt): add base ToV specification with rules from konstitutsiya"
```

---

### Task 3: Инструкции сегментатора (segmentator.md)

**Files:**
- Create: `.claude/skills/konspekt/segmentator.md`

- [ ] **Step 1: Создать segmentator.md**

Create `.claude/skills/konspekt/segmentator.md`:

```markdown
# ШАГ 1а: Сегментация транскрипта

## Роль

Ты читаешь фрагмент транскрипта и разбиваешь его на смысловые сегменты.
Результат — навигационная карта: список сегментов с метаданными.
Карта используется в ШАГ 1б как общий ориентир для всех subagents.

---

## Входные данные

- Фрагмент транскрипта (~15–25K токенов)
- Профиль контента (лекция / custdev / встреча / конференция)

Профиль объявляется пользователем в начале сессии.
Если не объявлен — определи автоматически по первым 1–2K токенам:
- **Лекция:** один спикер, учебный нарратив, последовательное изложение теории/практики
- **Custdev:** диалог, короткие реплики, вопросы исследователя + ответы респондента
- **Встреча:** несколько участников, обсуждение задач, решения, экшн-пункты
- **Конференция:** несколько докладчиков, каждый со своим временным слотом

---

## Процесс

### Шаг 1 — Черновая сегментация

Прочитай транскрипт. Для каждого смыслового блока запиши метаданные в формате:

```
## Сегмент N | HH:MM:SS–HH:MM:SS | [Тема одной строкой]

**Тип блока:** [лекция-теория / лекция-практика / история / Q&A / обсуждение / вступление / заключение]
**Спикер:** [имя или «основной» если один спикер на всё выступление]
**Суть:**
- [ключевой тезис 1]
- [ключевой тезис 2]
- [пример или аргумент]
```

**Что считать сегментом:** одна связная мысль. Переход к новому сегменту — смена темы,
смена типа блока, или явная пауза/переключение в речи.

**Ориентир по длине:** 5–20 минут на сегмент.
- Сегмент длиннее 30 минут без явной причины — скорее всего несколько тем слились.
- Короче 2 минут — возможно фрагмент, который стоит присоединить к соседнему.

---

### Шаг 2 — Самопроверка

После черновой сегментации проверь по четырём критериям:

**Критерий 1 — Связность:**
Каждый сегмент содержит одну связную мысль? Тема не обрывается и не смешивается с другой?

**Критерий 2 — Логические переходы:**
Между соседними сегментами читается логическая связь? Понятно, почему этот следует за предыдущим?

**Критерий 3 — Аномалии длины:**
Есть сегменты < 2 минут или > 30 минут без явной причины?

**Критерий 4 — Ход мысли автора:**
Порядок сегментов отражает то, как автор выстраивал аргументацию?

---

### Шаг 3 — Действие по результату

**Все критерии выполнены →** показать список сегментов пользователю одним сообщением
(информационно) и сразу продолжить без ожидания ответа.

Формат информационного сообщения:
```
Сегментация готова. Найдено N сегментов:

| # | Время | Тема | Тип | Ключевые тезисы |
|---|---|---|---|---|
| 1 | 00:00:00–00:14:30 | [Тема] | лекция-теория | тезис 1; тезис 2 |
| 2 | ... | ... | ... | ... |

Перехожу к ШАГ 1б.
```

**Найдена проблема →** остановиться. Описать конкретно что не так, предложить варианты. Ждать ответа.

Пример:
```
Проблема: сегмент 3 (00:22:00–00:48:00) длиной 26 минут содержит две темы:
разбор кейса (22:00–35:00) и общие выводы (35:00–48:00).

Варианты:
А) Разбить на два сегмента: «Кейс» и «Выводы»
Б) Оставить как есть, если считаете это единой нитью

Как поступить?
```

---

## Результат

Навигационная карта — список сегментов с метаданными в формате Шага 1.
Объём: ~1–2K токенов.
```

- [ ] **Step 2: Проверить покрытие спека**

Прочитать `docs/superpowers/specs/2026-05-04-konspekt-architecture-redesign.md`, секцию «ШАГ 1а».
Убедиться:
- Черновой прогон — ✓
- Самопроверка, 4 критерия (точные формулировки) — ✓
- «Продолжить без ожидания» при OK — ✓
- Пауза + объяснение при проблеме — ✓
- Профиль и автоопределение — ✓

- [ ] **Step 3: Коммит**

```bash
git add .claude/skills/konspekt/segmentator.md
git commit -m "feat(konspekt): add segmentator instructions for step 1a"
```

---

### Task 4: Инструкции для subagent-писателей (subagent_writer.md)

**Files:**
- Create: `.claude/skills/konspekt/subagent_writer.md`

- [ ] **Step 1: Создать subagent_writer.md**

Create `.claude/skills/konspekt/subagent_writer.md`:

```markdown
# ШАГ 1б: Subagent — Обработка сегмента

## Роль

Ты — subagent, обрабатывающий один сегмент транскрипта.
Твоя задача: по транскрипту сегмента написать два блока — Карту и Текст.

---

## Входные данные

Ты получаешь три раздела:

**[NAV MAP]** — навигационная карта всего выступления.
Используй для понимания контекста: что было до и что будет после твоего сегмента.
Не копируй из неё формулировки в свои блоки.

**[TOV SPEC]** — спецификация голоса и стиля.
Следуй при написании блока Текст.

**[TRANSCRIPT SEGMENT]** — твой кусок транскрипта.
Это единственный источник содержания.

---

## Что произвести

### Карта

Структурированный список ключевого содержания сегмента.

```markdown
### Карта

- [Ключевой тезис — одно предложение]
- [Аргумент или контраргумент с кратким пояснением]
- [Конкретный пример или история (если есть)]
- [Вывод или связующее утверждение]
```

Правила:
- Каждый буллет — самостоятельное утверждение, не «также» и не «ещё один пример»
- 4–8 буллетов на сегмент
- Порядок буллетов = порядок аргументации спикера в транскрипте
- Выражай суть, не пересказывай слово в слово

### Текст

Связный нарратив от первого лица спикера, следующий ToV-спецификации.

```markdown
### Текст

[Абзац 1 — начать с конкретного примера или ситуации]

[Абзац 2 — тезис или вывод из примера]

[Абзац 3 — развитие или следующий аргумент...]
```

Правила:
- Первое лицо: «я объясню», «мы посмотрим», «я показываю»
- Начинай с конкретного примера или ситуации, потом тезис — не наоборот
- Короткие абзацы, 2–4 предложения
- Живые связки между абзацами («вот почему», «отсюда следует»)
- Текст раскрывает буллеты Карты, а не копирует их
- Не упоминай другие сегменты напрямую («как я говорил раньше» — избегать)

---

## Чего не делать

- Не добавляй заголовки выше `### Карта` и `### Текст` — они встроятся в мастер-MD
- Не пиши пояснения к своим блокам («В карте я выделил...», «Текст написан в стиле...»)
- Не резюмируй после вывода, что ты сделал
- Не ссылайся на «навигационную карту», «subagent», «бригадира» в тексте
```

- [ ] **Step 2: Дополнить правилами из konspektolog.md**

Прочитать `.claude/skills/konspekt/_archive_2026-05-04/konspektolog.md`.
Найти конкретные правила написания конспекта (что включать, что опускать, как работать с примерами),
которые не отражены в текущих разделах subagent_writer.md — добавить в раздел «### Текст».

- [ ] **Step 3: Проверить покрытие спека**

Прочитать spec, секцию «ШАГ 1б». Убедиться:
- Получает: nav map + ToV spec + срез — ✓
- Производит: ### Карта + ### Текст — ✓
- Не видит соседних subagents — ✓ (явно прописано в «чего не делать»)
- Не думает про форматы вывода — ✓

- [ ] **Step 4: Коммит**

```bash
git add .claude/skills/konspekt/subagent_writer.md
git commit -m "feat(konspekt): add subagent writer instructions with konspektolog rules"
```

---

### Task 5: Инструкции агента-бригадира (brigadir.md)

**Files:**
- Create: `.claude/skills/konspekt/brigadir.md`

- [ ] **Step 1: Создать brigadir.md**

Create `.claude/skills/konspekt/brigadir.md`:

```markdown
# ШАГ 1в: Агент-бригадир

## Роль

Ты получаешь результаты всех subagents (блоки ### Карта + ### Текст по каждому сегменту)
и навигационную карту из ШАГ 1а.
Твоя задача: верифицировать, гармонизировать и собрать финальный мастер-MD.

---

## Входные данные

- Навигационная карта (из ШАГ 1а) — список сегментов с метаданными и ключевыми тезисами
- Результаты N subagents — N блоков «### Карта + ### Текст»

---

## Три задачи

### Задача 1 — Верификация покрытия

По каждому сегменту: сопоставь буллеты из навигационной карты с блоком ### Карта subagent'а.

Вопрос: все ключевые тезисы сегмента, зафиксированные в навигационной карте, отражены в блоке?

Если тезис из карты отсутствует в блоке Карта и не раскрыт в блоке Текст — это пропуск.
Фиксируй пропуски для Задачи 3.

### Задача 2 — Гармонизация стиля

Прочитай все блоки Текст подряд. Выровняй:
- Единый голос (первое лицо, живой стиль по ToV-спецификации из `tov_spec.md`)
- Единый темп и уровень детализации между сегментами
- Единые переходные выражения (убери разнобой связок)

Небольшие правки делай прямо в тексте — не переписывай блоки целиком без нужды.

### Задача 3 — Переходы между сегментами

Между каждой парой соседних сегментов добавь 1–2 связующих предложения.

Переход ставится между концом блока ### Текст сегмента N и заголовком ## Сегмент N+1.
Переход должен:
- Завершать мысль предыдущего сегмента или обозначать итог
- Обозначать направление следующего сегмента
- Звучать в голосе спикера (первое лицо, живая речь)

Пример:
```
...и именно это я имею в виду, когда говорю про системное мышление.

Теперь давайте посмотрим, как это работает на практике — на реальном кейсе из моей работы.
```

---

## Исправление проблем

**Стиль или связность** → исправляешь сам, продолжаешь без остановки.

**Пропущен ключевой тезис из навигационной карты** → отправь subagent'у на переделку:

```
Запрос переделки — Сегмент [N]:
В навигационной карте для этого сегмента указан тезис: «[тезис]»
Он отсутствует в блоке Карта и не раскрыт в блоке Текст.
Переделай оба блока (Карта и Текст) с учётом этого тезиса.
```

После переделки повтори проверку Задачи 1 для этого сегмента.

**Второй прогон тоже неудовлетворителен** → поставь метку `⚠️ требует проверки`
в начале блока сегмента и продолжи сборку.

---

## Сборка мастер-MD

После гармонизации и добавления переходов собери файл:

```markdown
# [Название выступления]

**Спикер:** [имя]
**Дата:** [дата]
**Длительность:** [HH:MM:SS]
**Профиль:** [лекция / custdev / встреча / конференция]
**Сегментов:** [N]

---

## Сегмент 1 | HH:MM:SS–HH:MM:SS | [Тема]

**Тип блока:** [метка]
**Спикер:** [имя или «основной»]

### Карта

- [буллет]
- [буллет]

### Текст

[связный текст]

[переход к следующему сегменту]

---

## Сегмент 2 | ...
```

Сохранить как `[название]_мастер.md` в папке `transcripts/`.

---

## После сборки

**Режим «с проверкой»** (пользователь выбрал в начале сессии):
Показать мастер-MD, ждать «ок» от пользователя.

**Режим «автоматический»:**
Сообщить о завершении одной строкой:
```
Мастер-MD готов: transcripts/[название]_мастер.md ([N] сегментов[, X сегментов ⚠️ если есть]).
```
```

- [ ] **Step 2: Проверить покрытие спека**

Прочитать spec, секцию «ШАГ 1в». Убедиться:
- Задача 1: верификация по навигационной карте — ✓
- Задача 2: гармонизация стиля — ✓
- Задача 3: переходы между сегментами — ✓ (отдельная задача, не смешана с исправлением)
- Стиль → сам, пропуск → переделка subagent'а с конкретным промптом — ✓
- Второй сбой → ⚠️ — ✓
- Формат мастер-MD совпадает со spec — ✓
- Режим с проверкой — ✓

- [ ] **Step 3: Коммит**

```bash
git add .claude/skills/konspekt/brigadir.md
git commit -m "feat(konspekt): add brigadir (foreman) instructions for step 1c"
```

---

### Task 6: Переписать SKILL.md

**Files:**
- Modify: `.claude/skills/konspekt/SKILL.md`

- [ ] **Step 1: Прочитать текущий SKILL.md**

Read `.claude/skills/konspekt/SKILL.md` — убедиться, что файл прочитан перед редактированием.

- [ ] **Step 2: Заменить содержимое SKILL.md**

Replace the entire content of `.claude/skills/konspekt/SKILL.md` with:

```markdown
---
name: konspekt
description: Обрабатывает транскрипт видеовыступления и создаёт мастер-MD через параллельные subagents. Единственный артефакт Слоя 1. Форматы вывода (Слой 2) — отдельный пайплайн.
---

# Скилл: Обработка транскрипта выступления

## Файлы скилла

- `preprocessor.py` — подсчёт токенов, нарезка транскрипта (ШАГ 0)
- `segmentator.md` — сегментация + самопроверка (ШАГ 1а)
- `tov_spec.md` — базовая ToV-спецификация (ШАГ 1б и 1в)
- `subagent_writer.md` — инструкции для каждого subagent'а (ШАГ 1б)
- `brigadir.md` — гармонизация и сборка мастер-MD (ШАГ 1в)
- `kartograf_profile_*.md` — профили контента (справочник; детальная переработка — отдельный спек)
- `widget.md` — виджет (Слой 2, отдельный пайплайн)

---

## Пайплайн (Слой 1)

```
Транскрипт
    ↓
ШАГ 0: Предобработка (если транскрипт > 25K токенов)
    ↓
ШАГ 1а: Сегментация + самопроверка
    ↓
ШАГ 1б: Параллельные subagents (по одному на сегмент)
    ↓
ШАГ 1в: Бригадир (верификация + гармонизация + сборка)
    ↓
Мастер-MD  →  сохранить в transcripts/
```

Транскрипт читается ровно один раз (ШАГ 0 + ШАГ 1а).
Subagents читают только свой срез.

---

## ШАГ 0: Запуск — сбор контекста

Выполнить автоматически, без вопросов к пользователю:

1. Проверить `transcripts/` на наличие `*_мастер.md` — для определения серийного контекста.
   Если найдены — прочитать и сообщить одной строкой.

2. Запустить:
   ```
   python .claude/skills/konspekt/preprocessor.py info [путь к транскрипту]
   ```
   Получить оценку токенов.

Затем задать пользователю **одним сообщением**:

```
1. Имя спикера (если не указано в транскрипте)
2. Профиль контента:
   - [ ] Лекция
   - [ ] Custdev-интервью
   - [ ] Встреча / синк
   - [ ] Конференция / конференс-доклад
   Если не уверен — Claude определит автоматически по транскрипту.
3. Режим работы:
   - Автоматический (без промежуточных проверок)
   - С проверкой (показывать сегментацию перед стартом subagents; показать мастер-MD в конце)
```

Начинать работу только после получения ответов.

---

## ШАГ 0: Предобработка (при транскрипте > 25K токенов)

**Если preprocessor.py info сообщил, что токенов > 25K:**

1. Запустить:
   ```
   python .claude/skills/konspekt/preprocessor.py windows [транскрипт]
   ```
   Скрипт выведет окна (~2–3K токенов каждое) вокруг потенциальных точек нарезки.

2. Для каждого окна проанализировать (Claude, не subagent):
   *«Где в этом фрагменте заканчивается смысловой блок? Какой тайминг начала следующего?»*

   - Уверен → зафиксировать тайминг, продолжить.
   - Не уверен → сообщить пользователю: показать окно, объяснить неясность, запросить тайминг.

3. Запустить нарезку:
   ```
   python .claude/skills/konspekt/preprocessor.py split [транскрипт] --at HH:MM:SS,HH:MM:SS,...
   ```
   Получить chunk-файлы (~15–18K токенов каждый, перекрытие ~500 токенов).

4. Каждый chunk проходит ШАГ 1а → 1б → 1в независимо.
   В конце объединить результаты в один мастер-MD в хронологическом порядке.
   *(Детальный алгоритм объединения — отдельный спек.)*

**Если токенов ≤ 25K** → перейти сразу к ШАГ 1а.

---

## ШАГ 1а: Сегментация

**Прочитать:** `segmentator.md`

Выполнить инструкции из `segmentator.md`:
- Определить профиль (или использовать объявленный пользователем)
- Выделить смысловые сегменты с метаданными
- Провести самопроверку по 4 критериям
- При OK: показать карту пользователю, продолжить без ожидания
- При проблеме: остановиться, объяснить, запросить решение

**Результат:** Навигационная карта (~1–2K токенов).

---

## ШАГ 1б: Параллельные subagents

**Перед запуском — извлечь динамический ToV:**

Прочитать первые ~2–3K токенов транскрипта. Выделить:
- Характерные обороты спикера
- Темп и уровень формальности
- Фирменные фразы и обращения к аудитории

Записать как `[TOV_DYNAMIC]...[/TOV_DYNAMIC]` блок (~150–200 токенов).

**Запустить subagents параллельно** — по одному на каждый сегмент.

Каждый subagent получает в промпте:
1. `[NAV MAP]` — полная навигационная карта из ШАГ 1а
2. `[TOV SPEC]` — базовые правила из `tov_spec.md` + динамический блок ToV
3. `[TRANSCRIPT SEGMENT]` — срез транскрипта только своего сегмента

Инструкции для subagent'а: `subagent_writer.md`

Каждый subagent производит: `### Карта` + `### Текст` для своего сегмента.

---

## ШАГ 1в: Бригадир

**Прочитать:** `brigadir.md`

Выполнить инструкции из `brigadir.md`:
- Верифицировать покрытие по навигационной карте
- Гармонизировать стиль
- Написать переходы между сегментами
- Исправить проблемы (стиль — сам; пропуски — переделка subagent'а; ⚠️ при втором сбое)
- Собрать мастер-MD и сохранить как `[название]_мастер.md` в `transcripts/`

---

## Выходной файл

`transcripts/[название]_мастер.md`

Используется:
- Как источник для Слоя 2 (форматы вывода — отдельный пайплайн)
- Как контекст для будущих сессий вместо перечитывания транскрипта

---

## Точки остановки

| Точка | Триггер | Действие |
|---|---|---|
| ШАГ 0 предобработка | LLM не уверен в точке реза | Показать окно + объяснить + запросить тайминг |
| ШАГ 1а | Найдена проблема сегментации | Описать проблему + предложить варианты + ждать |
| ШАГ 1а | Всё OK | Показать карту, продолжить автоматически |
| После ШАГ 1в | Режим «с проверкой» | Показать мастер-MD, ждать «ок» |
```

- [ ] **Step 3: Проверить что старые файлы не упоминаются**

```bash
grep -E "kartograf\.md|konspektolog\.md|konstitutsiya\.md|xlsx_template|karta_example|DOCX|XLSX" .claude/skills/konspekt/SKILL.md
```

Ожидание: пустой вывод.

- [ ] **Step 4: Коммит**

```bash
git add .claude/skills/konspekt/SKILL.md
git commit -m "feat(konspekt): rewrite SKILL.md for new Layer 1 pipeline"
```

---

### Task 7: Архивирование устаревших файлов

**Files:**
- Rename: `kartograf.md` → `_archived_kartograf.md`
- Rename: `konspektolog.md` → `_archived_konspektolog.md`
- Rename: `konstitutsiya.md` → `_archived_konstitutsiya.md`
- Rename: `xlsx_template.py` → `_archived_xlsx_template.py`
- Rename: `karta_example.html` → `_archived_karta_example.html`

- [ ] **Step 1: Переименовать файлы**

```bash
cd .claude/skills/konspekt
mv kartograf.md _archived_kartograf.md
mv konspektolog.md _archived_konspektolog.md
mv konstitutsiya.md _archived_konstitutsiya.md
mv xlsx_template.py _archived_xlsx_template.py
mv karta_example.html _archived_karta_example.html
```

- [ ] **Step 2: Убедиться что SKILL.md не ссылается на старые имена**

```bash
grep -rE "_archived_" .claude/skills/konspekt/SKILL.md
```

Ожидание: пустой вывод (SKILL.md не должен ссылаться на архивные файлы).

- [ ] **Step 3: Проверить что новые файлы на месте**

```bash
ls .claude/skills/konspekt/*.md .claude/skills/konspekt/*.py
```

Ожидание: в списке есть `SKILL.md`, `segmentator.md`, `tov_spec.md`, `subagent_writer.md`,
`brigadir.md`, `preprocessor.py`. Старые файлы — только с префиксом `_archived_`.

- [ ] **Step 4: Коммит**

```bash
git add .claude/skills/konspekt/
git commit -m "chore(konspekt): archive obsolete files from old 3-step pipeline"
```

---

## Self-Review

### Покрытие спека

| Требование из spec | Покрыто в |
|---|---|
| ШАГ 0: hybrid script+LLM нарезка | Task 1 (preprocessor.py) + SKILL.md |
| ШАГ 0: confidence-based пауза | SKILL.md (раздел «Предобработка») |
| ШАГ 1а: черновой прогон + метаданные | Task 3 (segmentator.md) |
| ШАГ 1а: самопроверка, 4 критерия | Task 3 (segmentator.md) |
| ШАГ 1а: auto-continue при OK | Task 3 (segmentator.md) |
| ШАГ 1а: профиль / автоопределение | Task 3 (segmentator.md) |
| ToV: база + динамика | Task 2 (tov_spec.md) + SKILL.md |
| ШАГ 1б: nav map + ToV + срез | Task 4 (subagent_writer.md) + SKILL.md |
| ШАГ 1б: ### Карта + ### Текст | Task 4 (subagent_writer.md) |
| ШАГ 1в: верификация по карте | Task 5 (brigadir.md) |
| ШАГ 1в: гармонизация стиля | Task 5 (brigadir.md) |
| ШАГ 1в: переходы между сегментами | Task 5 (brigadir.md) |
| ШАГ 1в: переделка subagent'а | Task 5 (brigadir.md) |
| ШАГ 1в: ⚠️ при втором сбое | Task 5 (brigadir.md) |
| Формат мастер-MD | Task 5 (brigadir.md) |
| Точки остановки | SKILL.md (таблица) |
| Удаление XLSX / DOCX / карта-MD | Task 7 + SKILL.md |
| Многочастевая сборка | SKILL.md (упомянуто как отложенное) |
| Детальные профили | Отложено (spec, раздел «Отложено») |
| Слой 2 | Отложено (spec, раздел «Отложено») |

### Плейсхолдеры

Ни одного TBD, TODO, «implement later» в задачах нет.

### Консистентность типов

- `preprocessor.py`: функции `estimate_tokens`, `parse_transcript_lines`, `time_to_seconds`, `split` — все импортируются в тестах именно под этими именами.
- Константы `CHUNK_SIZE`, `WINDOW_SIZE`, `OVERLAP`, `LARGE_THRESHOLD` определены в начале файла и нигде не переопределяются.
- Выходной формат `split()` — список строк (пути к файлам) — соответствует использованию в тестах.
