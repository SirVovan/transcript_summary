# Konspekt MD-parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Научить `widget_generator.py` принимать мастер-MD напрямую (`python widget_generator.py master.md` → HTML), убрав промежуточный JSON-builder.

**Architecture:** Отдельный модуль `.claude/skills/konspekt/md_parser.py` экспортирует функцию `parse_master_md(path) -> dict`, возвращающую ту же структуру, что сейчас принимает `build_html(data)` (см. эталонный `transcripts/Виджет — Вайбкодинг. Модуль 1. Урок 2.json`). `widget_generator.py` определяет формат по расширению (`.md` → парсер, `.json` → как раньше). Парсер падает с понятной ошибкой при отклонении от ожидаемой структуры мастер-MD.

**Tech Stack:** Python 3 (stdlib only — `re`, `pathlib`, `html`). Без зависимостей.

---

## Файлы и ответственности

- **Создать** `.claude/skills/konspekt/md_parser.py` — парсер мастер-MD → dict-структура, идентичная JSON-формату.
- **Изменить** `.claude/skills/konspekt/widget_generator.py` — диспетчер по расширению, импорт парсера.
- **Изменить** `.claude/skills/konspekt/layer2_widget.md` — обновить инструкцию: основной путь теперь `widget_generator.py master.md`, JSON-режим оставлен как резервный.

Парсер декомпозируется на чистые функции (без классов), каждая решает одну подзадачу:
- `parse_master_md(path)` — главная функция, оркестрирует.
- `_split_sections(text)` — режет текст на шапку, реконструкцию, сегменты.
- `_parse_meta(header)` — извлекает badge/title из шапки.
- `_parse_reconstruction(block)` — prose + блок «Главная идея» + таблица.
- `_parse_segment(block, idx, prompt_counter)` — один сегмент: type, title, timing, body, right.
- `_parse_map(block, segment_type)` — `### Карта` → insights HTML.
- `_parse_text(block, prompt_counter)` — `### Текст` → HTML (абзацы, `<h3>` из `#### Шаг N`, жирное, курсив, blockquote-блоки, промпт-блоки).
- `_render_blockquote(label, content)` — `> **Метка:** ...` → coloured `<div>`.
- `_render_prompt(label, code, pid)` — промпт-блок → `.pr-block` HTML.
- `_apply_inline(text)` — `**жирное**`, `*курсив*` → `<strong>`, `<em>`.
- `_label_color(label)` — метка блока → (bg, border) по таблице + эвристика.

---

### Task 1: Создать `md_parser.py` со скелетом и точкой входа

**Files:**
- Create: `.claude/skills/konspekt/md_parser.py`

- [ ] **Step 1: Создать файл со скелетом**

```python
#!/usr/bin/env python3
"""
md_parser.py — парсер мастер-MD конспекта в dict-структуру виджета.

Возвращает словарь той же формы, что принимает widget_generator.build_html:
{
  "meta": {"badge": ..., "title": ..., "out": ...},
  "reconstruction": {"prose": <html>, "table": [...]} | None,
  "trajectory": None,
  "segments": [{"id", "type", "title", "timing", "body", "right"}, ...],
  "prompts": {}
}

Использование как библиотеки:
    from md_parser import parse_master_md
    data = parse_master_md("transcripts/...мастер.md")
"""

import html
import re
from pathlib import Path


class MasterMDParseError(Exception):
    """Бросается при отклонении мастер-MD от ожидаемой структуры."""
    pass


def parse_master_md(path):
    """Главная функция: читает файл, возвращает dict для build_html."""
    text = Path(path).read_text(encoding='utf-8')
    sections = _split_sections(text)
    meta = _parse_meta(sections['header'], path)
    reconstruction = _parse_reconstruction(sections['reconstruction']) if sections['reconstruction'] else None
    prompt_counter = [0]
    segments = [_parse_segment(b, i + 1, prompt_counter) for i, b in enumerate(sections['segments'])]
    return {
        'meta': meta,
        'reconstruction': reconstruction,
        'trajectory': None,
        'segments': segments,
        'prompts': {},
    }


# Заглушки — будут реализованы в следующих задачах:
def _split_sections(text):
    raise NotImplementedError

def _parse_meta(header, path):
    raise NotImplementedError

def _parse_reconstruction(block):
    raise NotImplementedError

def _parse_segment(block, idx, prompt_counter):
    raise NotImplementedError


if __name__ == '__main__':
    import sys
    import json
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    print(json.dumps(parse_master_md(sys.argv[1]), ensure_ascii=False, indent=2))
```

- [ ] **Step 2: Проверить, что файл импортируется**

Run: `python -c "from md_parser import parse_master_md; print('ok')"` (из `.claude/skills/konspekt/`)
Expected: `ok` (без ошибок импорта).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): скелет md_parser.py — структура и точка входа"
```

---

### Task 2: `_split_sections` — резка мастер-MD на блоки

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

`_split_sections` режет файл по горизонтальным разделителям `---` и заголовкам. Структура мастер-MD:

```
# Название
**Спикер:** ...
**Длительность:** ...
**Профиль:** ...
**Сегментов:** N

---

## Логическая реконструкция
...

---

## Сегмент 1 | HH:MM:SS–HH:MM:SS | Тема
...

---

## Сегмент 2 | ...
...
```

Раздел «Логическая реконструкция» опционален (если 1 сегмент — может отсутствовать).

- [ ] **Step 1: Реализовать `_split_sections`**

Заменить заглушку:

```python
def _split_sections(text):
    """Режет мастер-MD на header, reconstruction (опц.), segments[]."""
    # Нормализуем переносы строк
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Разбиваем по строчным разделителям `---` (с пустыми строками вокруг)
    parts = re.split(r'\n---\n', text)
    parts = [p.strip() for p in parts if p.strip()]

    if not parts:
        raise MasterMDParseError("Пустой файл")

    header = parts[0]
    if not header.startswith('# '):
        raise MasterMDParseError(f"Первый блок не начинается с `# Название`, найдено: {header[:60]!r}")

    reconstruction = None
    segments = []
    for part in parts[1:]:
        if part.startswith('## Логическая реконструкция'):
            reconstruction = part
        elif part.startswith('## Сегмент '):
            segments.append(part)
        else:
            # Неизвестный раздел — упоминаем номер и первые 60 символов
            raise MasterMDParseError(
                f"Неизвестный раздел верхнего уровня: {part.splitlines()[0]!r}"
            )

    if not segments:
        raise MasterMDParseError("Не найдено ни одного `## Сегмент N | ...`")

    return {'header': header, 'reconstruction': reconstruction, 'segments': segments}
```

- [ ] **Step 2: Проверить на эталонном мастер-MD**

Run:
```
cd .claude/skills/konspekt
python -c "from md_parser import _split_sections; import pathlib; t = pathlib.Path('../../../transcripts/Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект_мастер.md').read_text(encoding='utf-8'); s = _split_sections(t); print('header:', s['header'][:40]); print('recon:', s['reconstruction'][:40] if s['reconstruction'] else None); print('segments:', len(s['segments']))"
```
Expected: `header: # Вайбкодинг. Модуль 1. Урок 2...`, `recon: ## Логическая реконструкция`, `segments: 3`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _split_sections режет мастер-MD на блоки"
```

---

### Task 3: `_parse_meta` — извлечение badge/title из шапки

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

Шапка эталона:
```
# Вайбкодинг. Модуль 1. Урок 2: пошаговый алгоритм + личный проект

**Спикер:** Дмитрий Ледовских
**Длительность:** 21:15
**Профиль:** лекция
**Сегментов:** 3
```

Эталонный JSON:
```
"badge": "Вайбкодинг · Модуль 1"
"title": "Урок 2: пошаговый алгоритм + личный проект · Дмитрий Ледовских"
"out":   "Виджет — Вайбкодинг. Модуль 1. Урок 2.html"
```

Правила:
- `badge` — первая часть `# Название` до запятой второго уровня. Эталон: `Вайбкодинг. Модуль 1. Урок 2: ...` → `Вайбкодинг · Модуль 1` (берём до первого `.` после `Модуль N` или до первого `:`). Это нетривиально и зависит от структуры конкретного курса. **Решение:** не угадывать жёстко, а собирать badge как первые два «слова с точкой» до двоеточия. Если структура иная — пользователь правит вручную в мастер-MD (но мастер-MD пока такого поля не имеет).

  Поскольку в мастер-MD нет отдельного поля для badge, придерживаемся простой эвристики: всё до символа `:` в первой строке `# ...`, разбитое по `. ` (точка-пробел) и пересобранное через ` · `. Для эталона `# Вайбкодинг. Модуль 1. Урок 2: ...` → части `["Вайбкодинг", "Модуль 1", "Урок 2"]` → берём первые две → `Вайбкодинг · Модуль 1`. Для одночастных названий без `:` (`# Что-то простое`) — badge = всё название.
- `title` — часть `# ...` **после** `:` (плюс ` · Спикер`). Эталон: `# ... Урок 2: пошаговый алгоритм + личный проект` → `Урок 2: пошаговый алгоритм + личный проект · Дмитрий Ледовских`. Префикс «Урок N» восстанавливается: берём последний из частей до `:` (`Урок 2`) и склеиваем с хвостом после `:`.
- `out` — `Виджет — <название_файла_без_расширения_без_суффикса>.html`. Эталон: файл `Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект_мастер.md` → `out = Виджет — Вайбкодинг. Модуль 1. Урок 2.html` (без хвоста после третьей точки + без `_мастер`). Это сложная регулярка под имена эталона. **Решение проще:** `out = "Виджет — " + stem.replace("_мастер", "") + ".html"`, где stem — имя файла без расширения. Эталон: `Виджет — Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект.html`. Это **отличается** от эталонного `out` («Виджет — Вайбкодинг. Модуль 1. Урок 2.html»), но эталонный `out` — это сокращение, которое автор JSON делал руками. Для парсера логично оставить полное имя — оно однозначно выводится из имени файла, не теряет информацию и не требует эвристик. Финальный html-файл всё равно открывается из браузера, длина имени не критична.

- [ ] **Step 1: Реализовать `_parse_meta`**

```python
def _parse_meta(header, path):
    """Из шапки `# Название` + `**Спикер:** ...` собирает badge/title/out."""
    lines = header.split('\n')
    title_line = lines[0]
    if not title_line.startswith('# '):
        raise MasterMDParseError(f"Ожидалась строка `# Название`, нашёл: {title_line!r}")
    full_title = title_line[2:].strip()

    speaker = None
    for line in lines[1:]:
        m = re.match(r'\*\*Спикер:\*\*\s*(.+)', line.strip())
        if m:
            speaker = m.group(1).strip()
            break

    # badge и title из full_title:
    # «Вайбкодинг. Модуль 1. Урок 2: пошаговый алгоритм + личный проект»
    #  ──── badge parts ───────  ── title prefix ──  ── title tail ─────
    if ':' in full_title:
        before_colon, after_colon = full_title.split(':', 1)
        parts = [p.strip() for p in before_colon.split('.') if p.strip()]
        # badge = первые две части через ` · `; если частей < 2, берём что есть
        if len(parts) >= 2:
            badge = ' · '.join(parts[:2])
            title_prefix = parts[-1]  # последняя часть — «Урок 2»
            title = f"{title_prefix}:{after_colon}".strip()
        else:
            badge = parts[0] if parts else full_title
            title = after_colon.strip()
    else:
        badge = full_title
        title = full_title

    if speaker:
        title = f"{title} · {speaker}"

    stem = Path(path).stem
    out_stem = re.sub(r'_мастер$', '', stem)
    out = f"Виджет — {out_stem}.html"

    return {'badge': badge, 'title': title, 'out': out}
```

- [ ] **Step 2: Проверить на эталоне**

Run:
```
cd .claude/skills/konspekt
python -c "from md_parser import _parse_meta; print(_parse_meta('# Вайбкодинг. Модуль 1. Урок 2: пошаговый алгоритм + личный проект\n\n**Спикер:** Дмитрий Ледовских\n**Длительность:** 21:15', '../../../transcripts/Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект_мастер.md'))"
```
Expected:
```
{'badge': 'Вайбкодинг · Модуль 1', 'title': 'Урок 2: пошаговый алгоритм + личный проект · Дмитрий Ледовских', 'out': 'Виджет — Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект.html'}
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _parse_meta строит badge/title/out из шапки мастер-MD"
```

---

### Task 4: `_apply_inline` — жирное и курсив

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

`**жирное**` → `<strong>жирное</strong>`. `*курсив*` → `<em>курсив</em>`. Важно: применять `**...**` **до** `*...*`, иначе `*` внутри `**` сжуёт жирное.

- [ ] **Step 1: Реализовать `_apply_inline`**

```python
def _apply_inline(text):
    """`**жирное**` → <strong>, `*курсив*` → <em>. Жирное обрабатываем первым."""
    # Сначала жирное (двойные звёздочки)
    text = re.sub(r'\*\*([^*\n]+?)\*\*', r'<strong>\1</strong>', text)
    # Потом курсив (одиночные звёздочки, не часть **)
    text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)
    return text
```

- [ ] **Step 2: Sanity-check вручную**

Run:
```
cd .claude/skills/konspekt
python -c "from md_parser import _apply_inline; print(_apply_inline('текст **жирное** и *курсив* и **жирное с *курсивом* внутри** конец'))"
```
Expected: `текст <strong>жирное</strong> и <em>курсив</em> и <strong>жирное с <em>курсивом</em> внутри</strong> конец`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _apply_inline — жирное и курсив"
```

---

### Task 5: `_label_color` — цвет блока по метке

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

Таблица меток (из `layer2_widget.md`):

| Метка содержит | Уровень | bg | border |
|---|---|---|---|
| Ключевая идея, Принцип, Лайфхак, Главная идея | (И) | `#ECF2FB` | `#2562B0` |
| Методология, Критерии, Шаг N. Финальная формулировка, Правило, Шаблон | (М) | `#EBF5EB` | `#2E6E2E` |
| Пример, Пример декомпозиции, Демонстрация, Важно | (Д) | `#FAF0E4` | `#96580F` |

Метка вне таблицы → эвристика по словам в самой метке (содержит «идея»/«принцип» → синий; «правило»/«критер»/«шаг»/«шаблон»/«метод» → зелёный; иначе → оранжевый, как самый частый дефолт для предупреждений/примеров).

- [ ] **Step 1: Реализовать `_label_color`**

```python
LABEL_COLORS = {
    'idea':   ('#ECF2FB', '#2562B0'),  # (И) синий
    'method': ('#EBF5EB', '#2E6E2E'),  # (М) зелёный
    'demo':   ('#FAF0E4', '#96580F'),  # (Д) оранжевый
}

# Точные метки (нормализованные, lowercase, без точек)
LABEL_TABLE = {
    'ключевая идея': 'idea',
    'главная идея':  'idea',
    'принцип':       'idea',
    'лайфхак':       'idea',
    'методология':   'method',
    'критерии':      'method',
    'правило':       'method',
    'шаблон':        'method',
    'пример':        'demo',
    'пример декомпозиции': 'demo',
    'демонстрация':  'demo',
    'важно':         'demo',
}


def _label_color(label):
    """Метка → (bg, border) hex-цвета."""
    norm = label.strip().lower().rstrip(':').strip()
    # Точное совпадение
    if norm in LABEL_TABLE:
        return LABEL_COLORS[LABEL_TABLE[norm]]
    # Префиксные совпадения: «Шаг N. Финальная формулировка», «Критерии хорошей идеи»
    for key, level in LABEL_TABLE.items():
        if norm.startswith(key) or key in norm:
            return LABEL_COLORS[level]
    # Эвристика по словам
    if any(w in norm for w in ['идея', 'принцип', 'лайфхак']):
        return LABEL_COLORS['idea']
    if any(w in norm for w in ['правил', 'критер', 'метод', 'шаблон', 'шаг']):
        return LABEL_COLORS['method']
    # Дефолт — оранжевый (примеры/предупреждения)
    return LABEL_COLORS['demo']
```

- [ ] **Step 2: Sanity-check**

Run:
```
cd .claude/skills/konspekt
python -c "from md_parser import _label_color; print(_label_color('Важно')); print(_label_color('Принцип')); print(_label_color('Критерии хорошей идеи')); print(_label_color('Шаг 4. Финальная формулировка — три проверки')); print(_label_color('Шпаргалка'))"
```
Expected:
```
('#FAF0E4', '#96580F')
('#ECF2FB', '#2562B0')
('#EBF5EB', '#2E6E2E')
('#EBF5EB', '#2E6E2E')
('#FAF0E4', '#96580F')   # дефолт
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _label_color — цвет блокquote-блока по метке"
```

---

### Task 6: `_render_blockquote` — coloured `<div>` из `> **Метка:** ...`

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

Вход — список строк blockquote (каждая начинается с `> `, уже снят префикс `> ` снаружи). Первая строка содержит метку `**Метка:** [текст]`. Дальше может идти многострочное продолжение, в т.ч. нумерованный список `1. ...`, `2. ...`.

Шаблон HTML (из `layer2_widget.md`):
```html
<div style="background:[bg];border-left:3px solid [border];border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;font-size:12.5px;line-height:1.55"><strong>[Метка]:</strong> [содержимое]</div>
```

Для многострочного с нумерованным списком:
```html
<div style="..."><strong>[Метка]:</strong> [опц. inline-текст]<ol style="margin:6px 0 0 18px"><li>...</li><li>...</li></ol></div>
```

- [ ] **Step 1: Реализовать `_render_blockquote`**

```python
def _render_blockquote(lines):
    """
    Список «голых» строк блока (без `> ` префикса) → coloured <div>.
    Первая строка: `**Метка:** [опц. inline-текст]`
    Дальше: либо продолжение прозы, либо нумерованный/маркированный список.
    """
    if not lines:
        raise MasterMDParseError("Пустой blockquote-блок")

    first = lines[0]
    m = re.match(r'\*\*([^*]+?):\*\*\s*(.*)', first)
    if not m:
        raise MasterMDParseError(f"Ожидался `**Метка:** ...` в blockquote, нашёл: {first!r}")
    label, inline_after_label = m.group(1).strip(), m.group(2).strip()

    bg, border = _label_color(label)
    style = (
        f"background:{bg};border-left:3px solid {border};"
        f"border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;"
        f"font-size:12.5px;line-height:1.55"
    )

    rest = lines[1:]
    # Определяем тип хвоста: нумерованный список, маркированный, или просто проза.
    # ВАЖНО: между </strong> и <ol>/<ul> всегда ставим пробел (как в эталонном JSON).
    if rest and re.match(r'\d+\.\s+', rest[0]):
        items = []
        for line in rest:
            m_li = re.match(r'\d+\.\s+(.*)', line)
            if not m_li:
                raise MasterMDParseError(f"В нумерованном списке blockquote сломанный элемент: {line!r}")
            items.append(f'<li>{_apply_inline(m_li.group(1))}</li>')
        body = f'<ol style="margin:6px 0 0 18px">{"".join(items)}</ol>'
        prefix = f'{_apply_inline(inline_after_label)}' if inline_after_label else ''
        return f'<div style="{style}"><strong>{label}:</strong> {prefix}{body}</div>'
    elif rest and re.match(r'-\s+', rest[0]):
        items = []
        for line in rest:
            m_li = re.match(r'-\s+(.*)', line)
            if not m_li:
                raise MasterMDParseError(f"В маркированном списке blockquote сломанный элемент: {line!r}")
            items.append(f'<li>{_apply_inline(m_li.group(1))}</li>')
        body = f'<ul style="margin:6px 0 0 18px">{"".join(items)}</ul>'
        prefix = f'{_apply_inline(inline_after_label)}' if inline_after_label else ''
        return f'<div style="{style}"><strong>{label}:</strong> {prefix}{body}</div>'
    else:
        # Простая проза — склеиваем строки через пробел
        full = inline_after_label
        if rest:
            full = (full + ' ' + ' '.join(rest)).strip() if full else ' '.join(rest)
        return f'<div style="{style}"><strong>{label}:</strong> {_apply_inline(full)}</div>'
```

- [ ] **Step 2: Sanity-check**

Run:
```
cd .claude/skills/konspekt
python -c "from md_parser import _render_blockquote; print(_render_blockquote(['**Важно:** больше 70% IT-стартапов закрываются']))"
```
Expected: `<div style="background:#FAF0E4;border-left:3px solid #96580F;...><strong>Важно:</strong> больше 70% IT-стартапов закрываются</div>`

Run:
```
python -c "from md_parser import _render_blockquote; print(_render_blockquote(['**Критерии хорошей идеи:**', '1. Вам лично это интересно.', '2. Кому-то это нужно.', '3. Это реально сделать.']))"
```
Expected: содержит `<ol style="margin:6px 0 0 18px"><li>Вам лично это интересно.</li><li>Кому-то это нужно.</li><li>Это реально сделать.</li></ol>` и `<strong>Критерии хорошей идеи:</strong>` с зелёным фоном.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _render_blockquote — цветной div из > **Метка:** ..."
```

---

### Task 7: `_render_prompt` — `.pr-block` HTML

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

Промпт-блок в мастер-MD:
```
> **Промпт «Название»:**

```
текст
с переносами
```
```

→ HTML:
```html
<div class="pr-block"><div class="pr-head"><span class="pr-label">Промпт «Название»</span><button class="pr-copy" id="cpbp1" onclick="cp('p1')">копировать</button></div><div class="pr-text">[текст с экранированием HTML]</div></div>
```

- [ ] **Step 1: Реализовать `_render_prompt`**

```python
def _render_prompt(label_text, code_text, pid):
    """
    label_text: содержимое между `**` и `:**` из строки `> **Промпт «...»:**`
                (т.е. уже без префикса `> **` и без хвоста `:**`)
    code_text:  тело fenced code block, без обрамляющих ```
    pid:        строка идентификатора, напр. 'p1', 'p2'
    """
    safe_code = html.escape(code_text, quote=False)
    return (
        f'<div class="pr-block">'
        f'<div class="pr-head">'
        f'<span class="pr-label">{label_text}</span>'
        f'<button class="pr-copy" id="cpb{pid}" onclick="cp(\'{pid}\')">копировать</button>'
        f'</div>'
        f'<div class="pr-text">{safe_code}</div>'
        f'</div>'
    )
```

- [ ] **Step 2: Sanity-check**

Run:
```
cd .claude/skills/konspekt
python -c "from md_parser import _render_prompt; print(_render_prompt('Промпт «Тест»', 'строка1\nстрока2 с <html>', 'p1'))"
```
Expected: `<div class="pr-block"><div class="pr-head"><span class="pr-label">Промпт «Тест»</span><button class="pr-copy" id="cpbp1" onclick="cp('p1')">копировать</button></div><div class="pr-text">строка1\nстрока2 с &lt;html&gt;</div></div>`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _render_prompt — .pr-block HTML с экранированием"
```

---

### Task 8: `_parse_text` — `### Текст` → HTML

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

Самая объёмная задача. Содержимое `### Текст` — смесь:
- Абзацев прозы (текст между пустыми строками).
- Заголовков `#### Шаг N. Название (тайминг)` → `<h3>Шаг N. Название (тайминг)</h3>` (в эталоне используется `<h3>`, а не `<h4>`, — для CSS `.seg-body h3`).
- Blockquote-блоков `> **Метка:** ...` (одно- и многострочных).
- Промпт-блоков: `> **Промпт «...»:**` + пустая строка + fenced ` ``` ` ... ` ``` `.
- Маркированных списков `- ...` (вне blockquote).
- Нумерованных списков `1. ...` (вне blockquote).

Алгоритм — построчный sweep с буферами:
1. Сканируем строки.
2. Если встретили fenced открытие — собираем код до закрытия.
3. Если строка начинается с `> ` — копим в `bq_buffer`, на разрыве (не-`> ` строка) выгружаем.
4. После выгрузки blockquote: если следующее значимое — fenced code, это **промпт** (предыдущий blockquote был меткой промпта); иначе обычный coloured div.
5. Заголовки `#### `, списки, абзацы — стандартно.

- [ ] **Step 1: Реализовать `_parse_text`**

```python
def _parse_text(block, prompt_counter):
    """
    block — содержимое после `### Текст` до конца сегмента (без самой строки `### Текст`).
    prompt_counter — список [int] (используется как изменяемая ссылка для сквозной нумерации p1, p2...).
    Возвращает HTML-строку.
    """
    lines = block.split('\n')
    parts = []  # выходные HTML-куски
    i = 0
    bq_buffer = None  # список «голых» строк текущего blockquote, без `> ` префикса
    pending_prompt_label = None  # если последний bq был меткой промпта, ждём fenced

    def flush_bq():
        nonlocal bq_buffer, pending_prompt_label
        if bq_buffer is None:
            return
        # Проверяем, не метка ли промпта
        first = bq_buffer[0] if bq_buffer else ''
        m = re.match(r'\*\*(Промпт[^*]*?):\*\*\s*$', first.strip())
        if m and len(bq_buffer) == 1:
            # Метка промпта — отложим, ждём fenced
            pending_prompt_label = m.group(1).strip()
        else:
            parts.append(_render_blockquote(bq_buffer))
        bq_buffer = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        if stripped.startswith('```'):
            # Собираем код до закрывающего ```
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            if i >= len(lines):
                raise MasterMDParseError("Незакрытый fenced code block в `### Текст`")
            i += 1  # пропустить закрывающий ```
            code_text = '\n'.join(code_lines)

            flush_bq()
            if pending_prompt_label is None:
                raise MasterMDParseError(
                    f"Fenced code block без предыдущей blockquote-метки промпта в `### Текст`. Код: {code_text[:60]!r}"
                )
            prompt_counter[0] += 1
            pid = f'p{prompt_counter[0]}'
            parts.append(_render_prompt(pending_prompt_label, code_text, pid))
            pending_prompt_label = None
            continue

        # Blockquote
        if stripped.startswith('>'):
            content = re.sub(r'^>\s?', '', line)
            if bq_buffer is None:
                bq_buffer = []
            bq_buffer.append(content.strip())
            i += 1
            continue

        # Пустая строка
        if stripped == '':
            flush_bq()
            # pending_prompt_label НЕ сбрасываем — между меткой и fenced может быть пустая строка
            i += 1
            continue

        # Здесь начинается «обычный» контент → flush bq и сбрасываем pending_prompt
        if bq_buffer is not None:
            flush_bq()
        if pending_prompt_label is not None:
            raise MasterMDParseError(
                f"Метка промпта `**{pending_prompt_label}:**` без последующего fenced code block"
            )

        # Заголовок #### Шаг N
        if stripped.startswith('#### '):
            heading = stripped[5:].strip()
            parts.append(f'<h3>{_apply_inline(heading)}</h3>')
            i += 1
            continue

        # Маркированный список
        if stripped.startswith('- '):
            items = []
            while i < len(lines) and lines[i].strip().startswith('- '):
                items.append(f'<li style="margin-bottom:4px">{_apply_inline(lines[i].strip()[2:])}</li>')
                i += 1
            parts.append(f'<ul style="margin:4px 0 9px 18px;padding:0">{"".join(items)}</ul>')
            continue

        # Нумерованный список
        if re.match(r'\d+\.\s+', stripped):
            items = []
            while i < len(lines) and re.match(r'\d+\.\s+', lines[i].strip()):
                m_li = re.match(r'\d+\.\s+(.*)', lines[i].strip())
                items.append(f'<li style="margin-bottom:4px">{_apply_inline(m_li.group(1))}</li>')
                i += 1
            parts.append(f'<ol style="margin:4px 0 9px 18px">{"".join(items)}</ol>')
            continue

        # Обычный абзац — копим строки до пустой
        para_lines = []
        while i < len(lines) and lines[i].strip() != '' and not lines[i].strip().startswith(('>', '#### ', '```', '- ')) and not re.match(r'\d+\.\s+', lines[i].strip()):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            paragraph = ' '.join(para_lines)
            parts.append(f'<p>{_apply_inline(paragraph)}</p>')

    flush_bq()
    if pending_prompt_label is not None:
        raise MasterMDParseError(
            f"Метка промпта `**{pending_prompt_label}:**` в конце `### Текст` без fenced code block"
        )

    return ''.join(parts)
```

- [ ] **Step 2: Sanity-check на куске эталонного сегмента 1**

Run (мини-тест в Python REPL):
```
cd .claude/skills/konspekt
python -c "
from md_parser import _parse_text
sample = '''В этом видео я с вами разберу **пошаговый алгоритм создания личного проекта** — да и в целом любого проекта.

> **Важно:** больше 70% разных IT-стартапов закрываются в первый год.

*Это пошаговый, пятишаговый алгоритм создания продукта.*'''
counter = [0]
print(_parse_text(sample, counter))
"
```
Expected: `<p>В этом видео я с вами разберу <strong>пошаговый алгоритм создания личного проекта</strong> — да и в целом любого проекта.</p><div style="background:#FAF0E4;border-left:3px solid #96580F;..."><strong>Важно:</strong> больше 70% разных IT-стартапов закрываются в первый год.</div><p><em>Это пошаговый, пятишаговый алгоритм создания продукта.</em></p>`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _parse_text — Текст → HTML с абзацами, blockquote, fenced"
```

---

### Task 9: `_parse_map` — `### Карта` → insights HTML

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

`### Карта` — список буллетов `- **(И/М/Д)** содержимое`. Каждый → одна `.insight` карточка. Цвет `border-left-color` зависит от типа сегмента (concept → синий, method → зелёный, demo → оранжевый).

- [ ] **Step 1: Реализовать `_parse_map`**

```python
SEGMENT_TYPE_COLORS = {
    'concept': '#2562B0',
    'method':  '#2E6E2E',
    'demo':    '#96580F',
}


def _parse_map(block, segment_type):
    """
    block — содержимое после `### Карта` до `### Текст` (или конца).
    segment_type — 'concept'/'method'/'demo' — определяет цвет border-left.
    """
    color = SEGMENT_TYPE_COLORS.get(segment_type, SEGMENT_TYPE_COLORS['concept'])
    items = []
    for raw in block.split('\n'):
        line = raw.strip()
        if not line:
            continue
        if not line.startswith('- '):
            raise MasterMDParseError(f"В `### Карта` ожидался буллет `- ...`, нашёл: {line!r}")
        body = line[2:].strip()
        # Первое **...** — метка уровня (И)/(М)/(Д), остальное — текст
        items.append(
            f'<div class="insight" style="border-left-color:{color}">{_apply_inline(body)}</div>'
        )
    if not items:
        raise MasterMDParseError("Пустой `### Карта`")
    return f'<div class="insights">{"".join(items)}</div>'
```

- [ ] **Step 2: Sanity-check**

Run:
```
cd .claude/skills/konspekt
python -c "
from md_parser import _parse_map
sample = '''- **(И)** Без чёткой идеи проект бросают за три дня.
- **(М)** Системный подход = чёткая формулировка.
- **(Д)** Метафора фундамента дома.'''
print(_parse_map(sample, 'concept'))
"
```
Expected: `<div class="insights"><div class="insight" style="border-left-color:#2562B0"><strong>(И)</strong> Без чёткой идеи проект бросают за три дня.</div>...`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _parse_map — Карта → insights"
```

---

### Task 10: `_parse_segment` — оркестрация одного сегмента

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

Структура блока сегмента:
```
## Сегмент N | HH:MM:SS–HH:MM:SS | Тема

**Тип:** инструкция + демонстрация
**Спикер:** Имя

**Ключевая мысль:** ...

### Карта

- **(И)** ...
- **(М)** ...

### Текст

проза...
```

Маппинг **Тип** → виджетный тип сегмента (из `layer2_widget.md`):

| Подстрока в Типе | type |
|---|---|
| открытие, мотивация, введение, тезис | `concept` |
| инструктаж, настройка, метод, инструкция | `method` |
| демонстрация, практика, разбор, q&a, призыв к действию | `demo` |

Для составных типов (`инструкция + демонстрация`) берётся **первое** найденное вхождение по порядку priority выше.

- [ ] **Step 1: Реализовать `_parse_segment`**

```python
SEGMENT_TYPE_RULES = [
    # (паттерны в **Тип**, тип виджета)
    (['тезис', 'открытие', 'мотивация', 'введение'], 'concept'),
    (['инструктаж', 'настройка', 'метод', 'инструкция'], 'method'),
    (['демонстрация', 'практика', 'разбор', 'q&a', 'призыв'], 'demo'),
]


def _classify_type(raw_type):
    norm = raw_type.lower()
    # Берём первый из подстрок, который встретится — иначе concept
    # Порядок: ищем первое совпадение по приоритету правил.
    for patterns, t in SEGMENT_TYPE_RULES:
        if any(p in norm for p in patterns):
            return t
    return 'concept'


def _parse_segment(block, idx, prompt_counter):
    """
    block — `## Сегмент N | ... | ...` + всё содержимое до следующего разделителя.
    idx — порядковый номер (1-based) для `id` ("01", "02", ...).
    prompt_counter — список [int] для сквозной нумерации промптов.
    """
    lines = block.split('\n')
    # Заголовок: `## Сегмент N | HH:MM:SS–HH:MM:SS | Тема`
    header = lines[0]
    m = re.match(r'##\s+Сегмент\s+\d+\s*\|\s*([\d:]+\s*[–-]\s*[\d:]+)\s*\|\s*(.+)', header)
    if not m:
        raise MasterMDParseError(f"Не разобран заголовок сегмента: {header!r}")
    raw_timing = m.group(1).strip()
    title = m.group(2).strip()

    # Тайминг: «HH:MM:SS–HH:MM:SS» → «HH:MM–HH:MM» (как в эталонном JSON)
    timing = _shorten_timing(raw_timing)

    # Поля **Тип:**, **Ключевая мысль:**
    raw_type = None
    key_thought = None
    for line in lines[1:]:
        line_s = line.strip()
        m_t = re.match(r'\*\*Тип:\*\*\s*(.+)', line_s)
        if m_t:
            raw_type = m_t.group(1).strip()
            continue
        m_k = re.match(r'\*\*Ключевая мысль:\*\*\s*(.+)', line_s)
        if m_k:
            key_thought = m_k.group(1).strip()
            continue

    if raw_type is None:
        raise MasterMDParseError(f"В сегменте {idx} не найдено `**Тип:** ...`")
    if key_thought is None:
        raise MasterMDParseError(f"В сегменте {idx} не найдено `**Ключевая мысль:** ...`")

    segment_type = _classify_type(raw_type)

    # Режем оставшуюся часть блока на ### Карта и ### Текст
    body_text = '\n'.join(lines[1:])
    map_match = re.search(r'\n###\s+Карта\s*\n(.*?)(?=\n###\s+Текст\s*\n|\Z)', body_text, re.DOTALL)
    text_match = re.search(r'\n###\s+Текст\s*\n(.*)', body_text, re.DOTALL)

    if not map_match:
        raise MasterMDParseError(f"В сегменте {idx} не найден `### Карта`")
    if not text_match:
        raise MasterMDParseError(f"В сегменте {idx} не найден `### Текст`")

    map_block = map_match.group(1).strip()
    text_block = text_match.group(1).strip()

    right_html = _parse_map(map_block, segment_type)
    text_html = _parse_text(text_block, prompt_counter)
    body_html = f'<p><strong>Ключевая мысль:</strong> {_apply_inline(key_thought)}</p>{text_html}'

    return {
        'id': f'{idx:02d}',
        'type': segment_type,
        'title': title,
        'timing': timing,
        'body': body_html,
        'right': right_html,
    }


def _shorten_timing(raw):
    """`00:00:00–00:03:38` → `00:00–03:38`. Если уже короткий — оставляем."""
    parts = re.split(r'\s*[–-]\s*', raw)
    if len(parts) != 2:
        return raw
    def short(t):
        bits = t.split(':')
        if len(bits) == 3:
            return f'{bits[0]}:{bits[1]}' if bits[0] != '00' else f'{bits[1]}:{bits[2]}'
        return t
    return f'{short(parts[0])}–{short(parts[1])}'
```

Замечание про `_shorten_timing`: эталонный JSON использует `"timing": "00:00–03:38"` (не `00:00:00–00:03:38`). Мастер-MD пишет `00:00:00–00:03:38`. Логика: если час = `00`, отбрасываем час; иначе оставляем как есть.

- [ ] **Step 2: Sanity-check на сегменте эталона**

Run:
```
cd .claude/skills/konspekt
python -c "
from md_parser import _split_sections, _parse_segment
import pathlib
t = pathlib.Path('../../../transcripts/Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект_мастер.md').read_text(encoding='utf-8')
s = _split_sections(t)
seg = _parse_segment(s['segments'][0], 1, [0])
print('id:', seg['id'])
print('type:', seg['type'])
print('title:', seg['title'])
print('timing:', seg['timing'])
print('body preview:', seg['body'][:160])
print('right preview:', seg['right'][:160])
"
```
Expected:
```
id: 01
type: concept
title: Зачем нужна система
timing: 00:00–03:38
body preview: <p><strong>Ключевая мысль:</strong> Любой цифровой продукт умирает не из-за инструментов...
right preview: <div class="insights"><div class="insight" style="border-left-color:#2562B0"><strong>(И)</strong>...
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _parse_segment — оркестрация одного сегмента"
```

---

### Task 11: `_parse_reconstruction` — Логическая реконструкция

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py`

Содержимое раздела:
```
## Логическая реконструкция

Большой абзац прозы с **жирным**.

> **Главная идея:** Прежде чем брать инструмент, ...

| Сегмент | Риторическая роль | Ключевой ход автора |
| --- | --- | --- |
| 1 | Тезис + аргументация | Доказывает... |
| 2 | Инструкция (5 подразделов) | Разворачивает... |
| 3 | Инструкция + ДЗ | Переносит... |
```

Структура:
- prose: первый абзац + blockquote `> **Главная идея:** ...` → склеить в одну HTML-строку (точно как в эталонном JSON `reconstruction.prose`).
- table: массив `{segment, role, move}` из MD-таблицы.

- [ ] **Step 1: Реализовать `_parse_reconstruction`**

```python
def _parse_reconstruction(block):
    """`## Логическая реконструкция\n\n...` → {prose, table}."""
    # Удаляем строку заголовка
    body = re.sub(r'^##\s+Логическая реконструкция\s*\n', '', block, count=1)
    lines = body.split('\n')

    prose_parts = []  # HTML-куски
    table_rows = []
    i = 0
    bq_buffer = None

    def flush_bq():
        nonlocal bq_buffer
        if bq_buffer is not None:
            prose_parts.append(_render_blockquote(bq_buffer))
            bq_buffer = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Старт таблицы
        if stripped.startswith('|') and i + 1 < len(lines) and re.match(r'\|\s*-+\s*\|', lines[i + 1]):
            # Заголовок таблицы (строка с `|`)
            i += 2  # пропускаем заголовок и разделитель
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if len(cells) >= 3:
                    table_rows.append({
                        'segment': cells[0],
                        'role': cells[1],
                        'move': cells[2],
                    })
                i += 1
            continue

        if stripped.startswith('>'):
            content = re.sub(r'^>\s?', '', line)
            if bq_buffer is None:
                bq_buffer = []
            bq_buffer.append(content.strip())
            i += 1
            continue

        if stripped == '':
            flush_bq()
            i += 1
            continue

        if bq_buffer is not None:
            flush_bq()

        # Абзац
        para_lines = []
        while i < len(lines) and lines[i].strip() != '' and not lines[i].strip().startswith(('>', '|')):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            paragraph = ' '.join(para_lines)
            prose_parts.append(f'<p>{_apply_inline(paragraph)}</p>')

    flush_bq()

    return {
        'prose': ''.join(prose_parts),
        'table': table_rows,
    }
```

- [ ] **Step 2: Sanity-check на эталоне**

Run:
```
cd .claude/skills/konspekt
python -c "
from md_parser import _split_sections, _parse_reconstruction
import pathlib
t = pathlib.Path('../../../transcripts/Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект_мастер.md').read_text(encoding='utf-8')
s = _split_sections(t)
r = _parse_reconstruction(s['reconstruction'])
print('prose preview:', r['prose'][:200])
print('table rows:', len(r['table']))
print('row 0:', r['table'][0])
"
```
Expected:
```
prose preview: <p>Урок построен как <strong>аргумент в защиту дисциплины перед инструментами</strong>...
table rows: 3
row 0: {'segment': '1', 'role': 'Тезис + аргументация', 'move': 'Доказывает...'}
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "feat(konspekt): _parse_reconstruction — prose + table из реконструкции"
```

---

### Task 12: Интеграция в `widget_generator.py` — диспетчер по расширению

**Files:**
- Modify: `.claude/skills/konspekt/widget_generator.py`

Сейчас `main()` всегда читает JSON. Меняем: смотрим расширение, при `.md` вызываем парсер.

- [ ] **Step 1: Изменить `main()` в `widget_generator.py`**

Найти текущий блок (строки ~546-572):
```python
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f'Файл не найден: {json_path}', file=sys.stderr)
        sys.exit(1)

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    ...
```

Заменить на:
```python
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f'Файл не найден: {input_path}', file=sys.stderr)
        sys.exit(1)

    ext = os.path.splitext(input_path)[1].lower()
    if ext == '.md':
        # Импорт здесь, чтобы JSON-режим работал даже без md_parser
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from md_parser import parse_master_md, MasterMDParseError
        try:
            data = parse_master_md(input_path)
        except MasterMDParseError as e:
            print(f'Ошибка парсинга мастер-MD: {e}', file=sys.stderr)
            sys.exit(3)
    elif ext == '.json':
        with open(input_path, encoding='utf-8') as f:
            data = json.load(f)
    else:
        print(f'Неподдерживаемое расширение: {ext}. Ожидается .md или .json', file=sys.stderr)
        sys.exit(1)

    out_name = data['meta'].get('out', 'widget_output.html')
    out_dir  = os.path.dirname(os.path.abspath(input_path))

    html     = build_html(data)
    out_path = os.path.join(out_dir, out_name)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Виджет создан: {out_path}')
    ok, err = validate_js(out_path)
    if ok:
        print('✅ JS syntax OK')
    else:
        print(f'❌ JS syntax ERROR:\n{err}', file=sys.stderr)
        sys.exit(2)
```

Также обновить docstring модуля в начале файла:
Найти:
```python
"""
widget_generator.py — генератор HTML-виджета конспекта.

Читает JSON-файл с контентом, выдаёт готовый HTML-виджет.
JS-экранирование полностью выполняет Python (json.dumps) —
кириллические lookalike-символы в \\u-эскейпах исключены.

Использование:
    python widget_generator.py <content.json>

Формат input JSON — см. widget.md раздел «Формат JSON».
"""
```
Заменить на:
```python
"""
widget_generator.py — генератор HTML-виджета конспекта.

Принимает мастер-MD или JSON, выдаёт готовый HTML-виджет.
JS-экранирование полностью выполняет Python (json.dumps) —
кириллические lookalike-символы в \\u-эскейпах исключены.

Использование:
    python widget_generator.py <input.md>    # парсит мастер-MD напрямую
    python widget_generator.py <input.json>  # резервный путь
"""
```

- [ ] **Step 2: Прогнать эталонный мастер-MD**

Из корня репозитория (`konspekt-project/`):

PowerShell (Windows, основная среда пользователя):
```powershell
$env:PYTHONUTF8=1
python ".claude/skills/konspekt/widget_generator.py" "transcripts/Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект_мастер.md"
```

bash (если исполнитель работает в Linux/macOS/WSL):
```bash
PYTHONUTF8=1 python ".claude/skills/konspekt/widget_generator.py" "transcripts/Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект_мастер.md"
```
Expected:
```
Виджет создан: ...\transcripts\Виджет — Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект.html
✅ JS syntax OK
```

- [ ] **Step 3: Визуальная проверка в браузере**

Открыть `transcripts\Виджет — Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект.html` в браузере.

Чек-лист:
1. Первый экран — «Логическая реконструкция»: проза + блок «Главная идея» (синий) + таблица 3 строки.
2. Сегмент 1 «Зачем нужна система»: тип concept (синий), 3 insight-карточки справа, оранжевый блок «Важно» в проз тексте, курсив-переход в конце.
3. Сегмент 2 «Пятишаговый алгоритм»: тип method (зелёный), 4 insight, 5 подзаголовков `Шаг N`, оранжевый блок «Пример» (Шаг 1), промпт-блок «Аналитик цифровых продуктов» с кнопкой «копировать» (Шаг 2), синий блок «Принцип» (Шаг 3), промпт «Просим ИИ оценить идею» (Шаг 3), оранжевый «Пример декомпозиции» с нумерованным списком (Шаг 4), зелёный «Методология» с нумерованным списком (Шаг 5), курсив-переход в конце.
4. Сегмент 3: тип method, 3 insight, зелёный «Критерии хорошей идеи» с нумерованным списком, 4 промпт-блока подряд (Шаг 1/2/3/4 + Финальный), зелёный «Шаг 4. Финальная формулировка» с нумерованным списком.
5. Кнопки «копировать» во всех 6 промптах работают (id `cpbp1`–`cpbp6`).
6. Переключение между табами 1/2/3 + реконструкция работает.

Сравнить визуально с эталонным `transcripts/Виджет — Вайбкодинг. Модуль 1. Урок 2.html`. Имена файлов будут разные (новый — длиннее из-за полного stem), это норма.

- [ ] **Step 4: Если есть расхождения — править парсер**

Самые вероятные точки расхождения:
- Текст промпта: исходный fenced может содержать ведущий/трейлинг whitespace, а в эталоне он сохранён точно. Если расходится — править строку `code_text = '\n'.join(code_lines)` (возможно нужен `.rstrip()` хвостовых пустых строк).
- Метки blockquote с переносом строки (например, `> **Шаг 4. Финальная формулировка — три проверки:**` — длинная метка). Проверить, что регулярка `re.match(r'\*\*([^*]+?):\*\*\s*(.*)', first)` корректно ловит.
- `<br>` внутри blockquote не нужен — проза склеивается пробелами.

После правок — повторно прогнать и открыть HTML.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/konspekt/widget_generator.py
git commit -m "feat(konspekt): widget_generator принимает мастер-MD напрямую"
```

---

### Task 13: Обновить `layer2_widget.md` — новый основной путь

**Files:**
- Modify: `.claude/skills/konspekt/layer2_widget.md`

Сейчас вся инструкция описывает «соберите JSON руками». Меняем структуру: основной путь — одна команда. JSON остаётся как резервный.

- [ ] **Step 1: Заменить «Шаг 1. Прочитать мастер-MD» и «Шаг 2. Собрать JSON»**

Найти блок от строки `## Шаг 1. Прочитать мастер-MD` до `## Шаг 3. Запустить генератор` и заменить целиком на:

```markdown
## Шаг 1. Запустить генератор на мастер-MD

```
PYTHONUTF8=1 python ".claude/skills/konspekt/widget_generator.py" "transcripts/[Название]_мастер.md"
```

Скрипт сам парсит мастер-MD, собирает HTML, проверяет JS-синтаксис. Ожидаемый результат: `✅ JS syntax OK` и путь к созданному `Виджет — [Название].html`.

При ошибках парсинга — сообщение вида `Ошибка парсинга мастер-MD: [причина]`. Чаще всего причина — отклонение мастер-MD от ожидаемой структуры (нет `### Карта`, не разобран заголовок сегмента и т.п.). Исправить мастер-MD и перезапустить.

---

## Шаг 2. Проверить виджет

1. Открыть HTML в браузере
2. Первый экран — «Логическая реконструкция» с абзацем, блоком «Главная идея» и таблицей (если сегментов > 1)
3. Кнопка «Далее» ведёт к Сегменту 1
4. Левая колонка каждого сегмента = полный `### Текст`
5. Правая колонка = все карточки из `### Карта`
6. Специальные блоки (Лайфхак/Важно/Демонстрация/Принцип/Критерии…) с цветной левой рамкой
7. Промпт-блоки моноширинные, с кнопкой «копировать»

---

## Резервный путь: JSON

Если нужно тонко допилить виджет руками без правки мастер-MD — можно собрать JSON напрямую и запустить:

```
PYTHONUTF8=1 python ".claude/skills/konspekt/widget_generator.py" "transcripts/Виджет — [Название].json"
```

Формат JSON — см. структуру эталонного файла `transcripts/Виджет — Вайбкодинг. Модуль 1. Урок 2.json`. Правила mapping мастер-MD → JSON (метки блоков → цвета, типы сегментов, шаблон `.pr-block`) описаны ниже в разделах «Конвертация body», «Конвертация right», «Блок промпта» — они применимы и при ручной сборке, и описывают то, что делает парсер автоматически.
```

Разделы «Конвертация body», «Блок промпта», «Конвертация right», «Технические ограничения» — **оставить как есть**, они описывают правила mapping, актуальные и для парсера (как референс), и для ручной сборки JSON.

Старый раздел «## Шаг 4. Проверить» удалить — его содержимое уже переехало в новый «Шаг 2. Проверить виджет» (см. выше в этом же шаге).

- [ ] **Step 2: Прочитать получившийся файл целиком и убедиться, что структура читаемая**

Прочитать `.claude/skills/konspekt/layer2_widget.md` (через Read tool или `cat`/`type` — что доступно в среде исполнения).

Структура должна получиться:
1. Назначение
2. Шаг 1. Запустить генератор на мастер-MD
3. Шаг 2. Проверить виджет
4. Резервный путь: JSON
5. Конвертация body (### Текст → HTML)
6. Блок промпта
7. Конвертация right (### Карта → HTML)
8. Технические ограничения

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/konspekt/layer2_widget.md
git commit -m "docs(konspekt): layer2_widget — основной путь через мастер-MD, JSON резервный"
```

---

## Самопроверка плана

**Покрытие спека (handoff):**
- Шапка файла → Task 3 (`_parse_meta`). ✓
- Раздел Логическая реконструкция (проза + Главная идея + таблица) → Task 11. ✓
- Сегменты (Тип → concept/method/demo, Ключевая мысль, ### Карта, ### Текст с подзаголовками/жирным/курсивом/блоками/промптами) → Tasks 4, 5, 6, 7, 8, 9, 10. ✓
- Сквозная нумерация промптов p1, p2... → Task 8 (через `prompt_counter[0]`). ✓
- JSON-режим как резерв → Task 12 (диспетчер по расширению). ✓
- Падение с понятной ошибкой при отклонении структуры → `MasterMDParseError` во всех парсер-функциях. ✓
- Не делать редактуру (механический перенос) → парсер не модифицирует контент, только трансформирует разметку. ✓
- Тесты на регрессию → исключено по решению пользователя (визуальная проверка в Task 12 Step 3).

**Подводные камни из handoff:**
1. Многострочные blockquote → склеивается в один div в `_render_blockquote` (Task 6).
2. Промпт-блок = blockquote-метка + fenced → склеивается через `pending_prompt_label` в `_parse_text` (Task 8).
3. Метка вне таблицы → эвристика в `_label_color` (Task 5), не падает.
4. Жирное и курсив в Карте → `_apply_inline` применяется внутри `_parse_map`, метка `**(И)**` останется жирной, остальной текст с возможным внутренним `**` тоже разбирается (Task 9).
5. Курсив-переход в конце сегмента → универсально через `_apply_inline`, специальной эвристики нет.
6. Пустой `### Текст` после `#### Шаг N` → `_parse_text` не теряется, h3 просто эмитится, потом дальше абзацы (Task 8).

**Type consistency:** `parse_master_md` возвращает структуру `{meta, reconstruction, trajectory, segments, prompts}` — это ровно тот dict, что принимает `build_html(data)` в `widget_generator.py` (проверено по строкам 433-456). Каждый segment имеет `id, type, title, timing, body, right` — соответствует тому, что читается в `build_html`.

**Плейсхолдеры:** просканировано — нет TBD/TODO/«handle edge cases» без раскрытия. Все шаги содержат либо код, либо команду с ожидаемым выводом.

---

## Известные точки внимания при ревью

Места, где парсер делает осознанные допущения — если визуальная проверка покажет расхождение с эталоном, сначала проверь именно эти точки:

1. **Имя выходного HTML.** Парсер строит `out` как `Виджет — <stem без _мастер>.html`. Для эталона это длинное имя `Виджет — Вайбкодинг. Модуль 1. Урок 2. Пошаговый алгоритм + личный проект.html`. Эталонный короткий `Виджет — Вайбкодинг. Модуль 1. Урок 2.html` останется рядом нетронутым. Это норма, не баг.

2. **Тайминги.** Handoff упоминал формат `HH:MM:SS–HH:MM:SS`, но реальный мастер-MD использует уже сокращённый `HH:MM–HH:MM`. `_shorten_timing` обрабатывает оба варианта — оставляет короткий как есть, длинный сокращает.

3. **Метка вне таблицы цветов** (например, `**Шпаргалка:**`). `_label_color` применяет эвристику по словам и в крайнем случае возвращает оранжевый дефолт. Не падает.

4. **Метка blockquote с двумя `:` внутри** (`**Пример: вот так:**`). Регулярка `\*\*([^*]+?):\*\*` lazy и сматчит первое `:`, после которого нет `**` — упадёт с MasterMDParseError. В текущем мастер-MD таких меток нет.

5. **Жирное в ячейках таблицы реконструкции.** Не применяется `_apply_inline` к ячейкам — это соответствует поведению `build_reconstruction_html` в `widget_generator.py` (она рендерит ячейки как есть). Если в мастер-MD появится `**жирное**` в ячейке — попадёт в HTML как литералы.

6. **HTML-escape прозы.** Текст прозы не экранируется (`<`, `>`, `&`). В текущем эталоне таких символов нет. Внутри fenced code block (промптов) — экранируется через `html.escape`.

7. **Тип сегмента из `**Тип:** инструкция + демонстрация`.** `_classify_type` обходит правила в фиксированном приоритете (concept → method → demo). Для эталонного сегмента 2 `**Тип:** инструкция + демонстрация (5 подразделов)` → ловит `инструкция` первым → method. Для сегмента 3 `**Тип:** инструкция + призыв к действию` → method. Для сегмента 1 `**Тип:** тезис + аргументация` → concept (по `тезис`). Сверь с эталонным JSON — должны совпасть.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-konspekt-md-parser.md`. Two execution options:

**1. Subagent-Driven (recommended)** — диспатчу по одному subagent на задачу, ревьюю между задачами. Безопаснее при многошаговом рефакторе.

**2. Inline Execution** — выполняем задачи здесь же в одной сессии, чекпоинты между задачами для ревью. Быстрее.

Какой подход выбираешь?
