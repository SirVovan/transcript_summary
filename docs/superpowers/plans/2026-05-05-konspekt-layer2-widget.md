# Слой 2 — Виджет: план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать Слой 2 скилла /konspekt — конвертацию мастер-MD в HTML-виджет через JSON-промежуточный слой.

**Architecture:** Три изменения: (1) расширить `widget_generator.py` поддержкой блока `reconstruction`; (2) создать `layer2_widget.md` с инструкциями для Claude; (3) обновить `SKILL.md`, добавив ШАГ 2.

**Tech Stack:** Python 3, pytest, node (для JS-валидации виджета)

---

## Карта файлов

| Действие | Файл | Ответственность |
|---|---|---|
| Create | `tests/test_widget_generator.py` | Unit-тесты для `build_reconstruction_html` и `build_html` |
| Modify | `.claude/skills/konspekt/widget_generator.py` | CSS + новая функция + рефакторинг `build_html` |
| Create | `.claude/skills/konspekt/layer2_widget.md` | Инструкции Claude для конвертации мастер-MD → JSON |
| Modify | `.claude/skills/konspekt/SKILL.md` | Добавить ШАГ 2 и обновить ссылку на файл виджета |

---

## Task 1: Поддержка `reconstruction` в `widget_generator.py`

**Files:**
- Create: `tests/test_widget_generator.py`
- Modify: `.claude/skills/konspekt/widget_generator.py`

- [ ] **Шаг 1: Написать падающие тесты**

Создать файл `tests/test_widget_generator.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.claude', 'skills', 'konspekt'))
from widget_generator import build_reconstruction_html, build_html


def test_reconstruction_with_table():
    recon = {
        'prose': 'Автор строит аргументацию через три шага.',
        'table': [
            {'segment': '1', 'role': 'Открытие', 'move': 'Формулирует парадокс'},
            {'segment': '2', 'role': 'Демонстрация', 'move': 'Показывает кейс'},
        ]
    }
    html = build_reconstruction_html(recon)
    assert 'class="recon"' in html
    assert 'Автор строит аргументацию через три шага.' in html
    assert 'Формулирует парадокс' in html
    assert 'class="recon-table"' in html


def test_reconstruction_no_table():
    recon = {'prose': 'Один сегмент — единая тема.', 'table': []}
    html = build_reconstruction_html(recon)
    assert 'class="recon"' in html
    assert 'Один сегмент — единая тема.' in html
    assert 'recon-table' not in html


def test_reconstruction_none():
    assert build_reconstruction_html(None) == ''


def test_build_html_includes_reconstruction():
    data = {
        'meta': {'badge': 'Test', 'title': 'Test Widget', 'out': 'test.html'},
        'reconstruction': {
            'prose': 'Тестовая реконструкция.',
            'table': [{'segment': '1', 'role': 'Тезис', 'move': 'Вводит проблему'}]
        },
        'prompts': {},
        'segments': [
            {'id': '01', 'type': 'concept', 'title': 'Тест', 'timing': '0:00–5:00',
             'body': '<p>Текст</p>', 'right': '<div class="insights"></div>'}
        ]
    }
    html = build_html(data)
    assert 'class="recon"' in html
    assert 'Тестовая реконструкция.' in html
    assert 'Вводит проблему' in html


def test_build_html_no_reconstruction():
    data = {
        'meta': {'badge': 'Test', 'title': 'Test', 'out': 'test.html'},
        'prompts': {},
        'segments': [
            {'id': '01', 'type': 'concept', 'title': 'Тест', 'timing': '0:00–5:00',
             'body': '<p>Текст</p>', 'right': '<div class="insights"></div>'}
        ]
    }
    html = build_html(data)
    assert 'class="recon"' not in html
```

- [ ] **Шаг 2: Запустить тесты — убедиться, что падают**

```
cd d:\Users\Вова\Desktop\Work\VibeCoding\konspekt-project
python -m pytest tests/test_widget_generator.py -v
```

Ожидаемый результат: `ImportError: cannot import name 'build_reconstruction_html'` (или аналогичная ошибка — функция ещё не существует).

- [ ] **Шаг 3: Добавить CSS для блока `recon` в `widget_generator.py`**

В конце константы `CSS` (перед закрывающим `"""`), заменить:

```python
.toc-item:not(.active):hover .toc-text{color:rgba(255,255,255,.75)}"""
```

на:

```python
.toc-item:not(.active):hover .toc-text{color:rgba(255,255,255,.75)}

.recon { flex-shrink:0; max-height:130px; overflow-y:auto; padding:10px 24px; border-bottom:1px solid var(--border); background:var(--surface2); }
.recon::-webkit-scrollbar{width:3px} .recon::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
.recon-title { font-size:10px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--tx3); margin-bottom:5px; }
.recon-prose { font-size:12.5px; color:var(--tx2); line-height:1.5; margin-bottom:6px; }
.recon-table { width:100%; font-size:11px; border-collapse:collapse; }
.recon-table th { font-size:10px; font-weight:700; letter-spacing:.04em; text-transform:uppercase; color:var(--tx3); text-align:left; padding:2px 14px 4px 0; border-bottom:1px solid var(--border2); }
.recon-table td { color:var(--tx2); padding:3px 14px 3px 0; vertical-align:top; line-height:1.4; }"""
```

- [ ] **Шаг 4: Добавить функцию `build_reconstruction_html` в `widget_generator.py`**

Вставить после функции `js_arr` (перед `def build_html`):

```python
def build_reconstruction_html(recon):
    if not recon:
        return ''
    prose = recon.get('prose', '')
    table_rows = recon.get('table', [])
    parts = [
        '<div class="recon">',
        '  <div class="recon-title">Логическая реконструкция</div>',
        f'  <p class="recon-prose">{prose}</p>',
    ]
    if table_rows:
        parts += [
            '  <table class="recon-table">',
            '    <thead><tr><th>Сегмент</th><th>Риторическая роль</th><th>Ключевой ход автора</th></tr></thead>',
            '    <tbody>',
        ]
        for row in table_rows:
            seg  = row.get('segment', '')
            role = row.get('role', '')
            move = row.get('move', '')
            parts.append(f'      <tr><td>{seg}</td><td>{role}</td><td>{move}</td></tr>')
        parts += ['    </tbody>', '  </table>']
    parts.append('</div>')
    return '\n'.join(parts)
```

- [ ] **Шаг 5: Рефакторинг `build_html` — вставить `reconstruction` в HTML**

Заменить функцию `build_html` целиком:

```python
def build_html(data):
    meta     = data['meta']
    prompts  = data.get('prompts', {})
    segments = data['segments']

    badge = meta['badge']
    title = meta['title']

    body_dict  = {s['id']: s['body']  for s in segments}
    right_dict = {s['id']: s['right'] for s in segments}

    pr_js    = 'var PR = ' + js_obj(prompts) + ';'
    body_js  = 'var BODY = ' + js_obj(body_dict) + ';'
    right_js = 'var RIGHT = ' + js_obj(right_dict) + ';'
    seg_js   = 'var SEG = ' + js_arr(segments) + ';'

    recon_html = build_reconstruction_html(data.get('reconstruction'))

    lines = [
        '<!DOCTYPE html>',
        '<html lang="ru">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">',
        f'<title>{title}</title>',
        '<style>',
        CSS,
        '</style>',
        '</head>',
        '<body>',
        '',
        '<div class="shell">',
        '  <div class="topbar">',
        '    <div class="topbar-left">',
        f'      <span class="course-badge">{badge}</span>',
        f'      <span class="course-title">{title}</span>',
        '    </div>',
        '    <div class="tabs" id="tabs"></div>',
        '  </div>',
        '  <div class="stripe" id="stripe"></div>',
    ]

    if recon_html:
        lines.append(recon_html)

    lines += [
        '  <div class="body" id="body"></div>',
        '  <div class="footer">',
        '    <span class="f-info" id="finfo"></span>',
        '    <div class="pw"><div class="pt"><div class="pf" id="pf" style="width:6%"></div></div></div>',
        '    <div class="nav">',
        '      <button class="btn" id="pb" onclick="go(-1)" disabled>← Назад</button>',
        '      <button class="btn primary" id="nb" onclick="go(1)">Далее →</button>',
        '    </div>',
        '  </div>',
        '</div>',
        '',
        '<script>',
        JS_T,
        '',
        pr_js,
        '',
        body_js,
        '',
        right_js,
        '',
        seg_js,
        '',
        JS_ENGINE,
        '</script>',
        '</body>',
        '</html>',
    ]

    return '\n'.join(lines)
```

- [ ] **Шаг 6: Запустить тесты — убедиться, что все проходят**

```
python -m pytest tests/test_widget_generator.py -v
```

Ожидаемый результат:
```
tests/test_widget_generator.py::test_reconstruction_with_table PASSED
tests/test_widget_generator.py::test_reconstruction_no_table PASSED
tests/test_widget_generator.py::test_reconstruction_none PASSED
tests/test_widget_generator.py::test_build_html_includes_reconstruction PASSED
tests/test_widget_generator.py::test_build_html_no_reconstruction PASSED
5 passed
```

- [ ] **Шаг 7: Регрессионная проверка — регенерировать существующий виджет**

```
python ".claude/skills/konspekt/widget_generator.py" "transcripts/Виджет — Тайминг Практикум День 1 ч1.json"
```

Ожидаемый результат: `✅ JS syntax OK`. Виджет открывается в браузере, сегменты работают (у этого виджета нет `reconstruction` в JSON — убедиться, что блок просто отсутствует и ничего не сломалось).

- [ ] **Шаг 8: Коммит**

```
git add tests/test_widget_generator.py .claude/skills/konspekt/widget_generator.py
git commit -m "feat(konspekt): add reconstruction panel to widget_generator"
```

---

## Task 2: Создать `layer2_widget.md`

**Files:**
- Create: `.claude/skills/konspekt/layer2_widget.md`

- [ ] **Шаг 1: Создать файл `.claude/skills/konspekt/layer2_widget.md` с точным содержимым:**

```markdown
# Слой 2: Виджет

## Назначение

Конвертировать мастер-MD в HTML-виджет через промежуточный JSON.

Принцип: механический перенос без редакции. Весь контент мастер-MD переносится без потерь — левая колонка = полный `### Текст`, правая колонка = полный `### Карта`.

---

## Шаг 1. Прочитать мастер-MD

Мастер-MD находится в `transcripts/[название]_мастер.md`. Прочитать полностью.

---

## Шаг 2. Собрать JSON

Создать файл `transcripts/Виджет — [Название].json`.

### Поле `meta`

- `badge` — `"Курс · Подтема"` (из названия урока или серийного контекста)
- `title` — `"[Название выступления] · [Спикер]"` (спикер из заголовка мастер-MD)
- `out` — `"Виджет — [Название].html"`

### Поле `reconstruction`

Взять из раздела `## Логическая реконструкция` мастер-MD:

- `prose` — абзац прозой целиком, без изменений
- `table` — массив строк таблицы:
  ```json
  [{"segment": "1", "role": "Риторическая роль", "move": "Ключевой ход автора"}]
  ```
  Если таблицы нет (один сегмент в мастер-MD) → `"table": []`

### Поле `segments`

По каждому `## Сегмент N | HH:MM:SS–HH:MM:SS | [Тема]`:

**`id`** — номер с ведущим нулём: `"01"`, `"02"`, `"03"`, ...

**`type`** — по полю `**Тип:**` в мастер-MD:

| Риторическая роль | type |
|---|---|
| открытие, мотивация, введение | `concept` |
| инструктаж, настройка, метод | `method` |
| демонстрация, практика, разбор, Q&A | `demo` |

При неясности — использовать `concept`.

**`title`** — тема из заголовка сегмента (часть после последнего `|`)

**`timing`** — таймштампы из заголовка, формат `"HH:MM–HH:MM"`

**`body`** — полный `### Текст` → HTML (см. ниже)

**`right`** — полный `### Карта` → HTML (см. ниже)

---

## Конвертация `body` (### Текст → HTML)

Каждый абзац прозы → `<p>текст</p>`

`**текст**` → `<strong>текст</strong>`

Маркированный список:
```
- пункт А
- пункт Б
```
→
```html
<ul style="margin:4px 0 9px 20px;padding:0"><li style="margin-bottom:4px">пункт А</li><li style="margin-bottom:4px">пункт Б</li></ul>
```

Нумерованный список:
```
1. пункт А
2. пункт Б
```
→
```html
<ol style="margin:4px 0 9px 18px"><li style="margin-bottom:4px">пункт А</li><li style="margin-bottom:4px">пункт Б</li></ol>
```

Специальные блоки:

`> **Лайфхак:** текст`
→
```html
<div style="background:#ECF2FB;border-left:3px solid #2562B0;border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;font-size:12.5px;line-height:1.55"><strong>Лайфхак:</strong> текст</div>
```

`> **Важно:** текст`
→
```html
<div style="background:#FAF0E4;border-left:3px solid #96580F;border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;font-size:12.5px;line-height:1.55"><strong>Важно:</strong> текст</div>
```

`> **Демонстрация:** текст`
→
```html
<div style="background:#F0F4F8;border-left:3px solid #607D8B;border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;font-size:12.5px;line-height:1.55"><strong>Демонстрация:</strong> текст</div>
```

---

## Конвертация `right` (### Карта → HTML)

Каждый буллет `### Карта` → одна insight-карточка. Все буллеты без исключения.

Цвет `border-left-color` по типу сегмента: `concept` → `#2562B0`, `method` → `#2E6E2E`, `demo` → `#96580F`

```markdown
- **Термин:** пояснение
- **Другой:** другое
```
→
```html
<div class="insights"><div class="insight" style="border-left-color:#2562B0"><strong>Термин:</strong> пояснение</div><div class="insight" style="border-left-color:#2562B0"><strong>Другой:</strong> другое</div></div>
```

---

## Технические ограничения

- Никаких `var()` в inline-стилях — только хардкод hex-цветов
- JSON-строки однострочные — никаких литеральных переносов строк внутри значений
- Кавычки в HTML-атрибутах → `&quot;`

---

## Шаг 3. Запустить генератор

```
python ".claude/skills/konspekt/widget_generator.py" "transcripts/Виджет — [Название].json"
```

Скрипт выводит путь к HTML и проверяет JS-синтаксис. Ожидаемый результат: `✅ JS syntax OK`

---

## Шаг 4. Проверить

1. Открыть HTML в браузере
2. Блок «Логическая реконструкция» виден над сегментами
3. Левая колонка каждого сегмента = полный `### Текст` (текст, не буллеты)
4. Правая колонка = все карточки из `### Карта` (без сокращений)
5. Специальные блоки (Лайфхак/Важно/Демонстрация) отображаются с цветной левой рамкой
6. Навигация между сегментами работает
```

- [ ] **Шаг 2: Коммит**

```
git add .claude/skills/konspekt/layer2_widget.md
git commit -m "feat(konspekt): add layer2_widget.md — master-MD to widget conversion instructions"
```

---

## Task 3: Обновить `SKILL.md`

**Files:**
- Modify: `.claude/skills/konspekt/SKILL.md`

- [ ] **Шаг 1: Обновить ссылку на файл виджета в разделе «Файлы скилла»**

Заменить:
```
- `widget.md` — виджет (Слой 2, отдельный пайплайн)
```
на:
```
- `layer2_widget.md` — виджет (Слой 2, конвертация мастер-MD → JSON → HTML)
```

- [ ] **Шаг 2: Добавить раздел «Слой 2» в `SKILL.md`**

После раздела `## Выходной файл` (после строки «Используется:...» и перед `## Точки остановки`) добавить:

```markdown
---

## Слой 2: Виджет

Когда пользователь просит создать виджет из мастер-MD — прочитать `layer2_widget.md` и следовать инструкциям.

Мастер-MD должен уже существовать в `transcripts/` до начала Слоя 2.
```

- [ ] **Шаг 3: Коммит**

```
git add .claude/skills/konspekt/SKILL.md
git commit -m "feat(konspekt): add Layer 2 step to SKILL.md"
```

---

## Финальная проверка

- [ ] **Регенерировать тестовый виджет с `reconstruction`**

Добавить `reconstruction` в `transcripts/Виджет — Тайминг Практикум День 1 ч1.json` на основе данных из `transcripts/validation_formatting_мастер.md`, затем регенерировать виджет:

```
python ".claude/skills/konspekt/widget_generator.py" "transcripts/Виджет — Тайминг Практикум День 1 ч1.json"
```

Открыть в браузере: блок реконструкции должен отображаться над сегментами.
