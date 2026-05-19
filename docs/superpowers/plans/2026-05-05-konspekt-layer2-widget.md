# Слой 2 — Виджет: план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать Слой 2 скилла /konspekt — конвертацию мастер-MD в HTML-виджет через JSON-промежуточный слой.

**Architecture:** Три изменения: (1) расширить `widget_generator.py` — добавить `build_reconstruction_html` и препендить реконструкцию как сегмент `'00'` в JS-данные; (2) создать `layer2_widget.md` с инструкциями для Claude; (3) обновить `SKILL.md`.

**Механика реконструкции:** `reconstruction` из JSON становится первым экраном виджета (сегмент `id='00'`, title='Логическая реконструкция') — пользователь открывает виджет, видит вводную главу, навигирует «Далее» к Сегменту 1. Никаких фиксированных блоков над контентом.

**Tech Stack:** Python 3, pytest

---

## Карта файлов

| Действие | Файл | Ответственность |
|---|---|---|
| Create | `tests/test_widget_generator.py` | Unit-тесты для `build_reconstruction_html` и `build_html` |
| Modify | `.claude/skills/konspekt/widget_generator.py` | Новая функция + 5 строк в `build_html` |
| Create | `.claude/skills/konspekt/layer2_widget.md` | Инструкции Claude для конвертации мастер-MD → JSON |
| Modify | `.claude/skills/konspekt/SKILL.md` | Добавить ШАГ 2 и обновить ссылку на файл виджета |

---

## Task 1: Поддержка `reconstruction` в `widget_generator.py`

**Files:**
- Create: `tests/test_widget_generator.py`
- Modify: `.claude/skills/konspekt/widget_generator.py` (строки 279–298, после них)

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
    assert '<p>Автор строит аргументацию через три шага.</p>' in html
    assert 'Формулирует парадокс' in html
    assert '<table' in html


def test_reconstruction_no_table():
    recon = {'prose': 'Один сегмент — единая тема.', 'table': []}
    html = build_reconstruction_html(recon)
    assert '<p>Один сегмент — единая тема.</p>' in html
    assert '<table' not in html


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
    assert 'Тестовая реконструкция.' in html        # в BODY['00']
    assert '"00"' in html                             # сегмент 00 в SEG
    assert 'Логическая реконструкция' in html         # title в SEG


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
    assert '"00"' not in html
    assert 'Логическая реконструкция' not in html
```

- [ ] **Шаг 2: Запустить тесты — убедиться, что падают**

```
cd d:\Users\Вова\Desktop\Work\VibeCoding\konspekt-project
python -m pytest tests/test_widget_generator.py -v
```

Ожидаемый результат: `ImportError: cannot import name 'build_reconstruction_html'`

- [ ] **Шаг 3: Добавить функцию `build_reconstruction_html` в `widget_generator.py`**

Вставить сразу после функции `js_arr` (строка 298), перед `# ──── HTML-сборка`:

```python
def build_reconstruction_html(recon):
    if not recon:
        return ''
    prose = recon.get('prose', '')
    table_rows = recon.get('table', [])
    parts = [f'<p>{prose}</p>']
    if table_rows:
        cell = 'style="color:#4A4438;padding:3px 14px 3px 0;vertical-align:top;font-size:12px"'
        th   = 'style="font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#8C8278;text-align:left;padding:2px 14px 4px 0;border-bottom:1px solid rgba(60,52,36,.15)"'
        parts += [
            '<table style="width:100%;border-collapse:collapse;margin-top:10px">',
            f'<thead><tr><th {th}>#</th><th {th}>Риторическая роль</th><th {th}>Ключевой ход автора</th></tr></thead>',
            '<tbody>',
        ]
        for row in table_rows:
            parts.append(
                f'<tr>'
                f'<td {cell}>{row.get("segment","")}</td>'
                f'<td {cell}>{row.get("role","")}</td>'
                f'<td {cell}>{row.get("move","")}</td>'
                f'</tr>'
            )
        parts += ['</tbody></table>']
    return '\n'.join(parts)
```

- [ ] **Шаг 4: Препендить реконструкцию как сегмент `'00'` в `build_html`**

В функции `build_html` заменить:

```python
    body_dict  = {s['id']: s['body']  for s in segments}
    right_dict = {s['id']: s['right'] for s in segments}

    # PR больше не нужен в JS — cp() читает текст из DOM (.pr-text)
    # Сохраняем для обратной совместимости (пустой объект если промптов нет)
    pr_js    = 'var PR = ' + js_obj(prompts) + ';'
```

на:

```python
    body_dict  = {s['id']: s['body']  for s in segments}
    right_dict = {s['id']: s['right'] for s in segments}

    recon = data.get('reconstruction')
    if recon:
        body_dict  = {'00': build_reconstruction_html(recon), **body_dict}
        right_dict = {'00': '<div class="insights"></div>', **right_dict}
        segments   = [{'id': '00', 'type': 'concept', 'title': 'Логическая реконструкция', 'timing': ''}] + list(segments)

    pr_js    = 'var PR = ' + js_obj(prompts) + ';'
```

- [ ] **Шаг 5: Запустить тесты — убедиться, что все проходят**

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

- [ ] **Шаг 6: Регрессионная проверка**

```
python ".claude/skills/konspekt/widget_generator.py" "transcripts/Виджет — Тайминг Практикум День 1 ч1.json"
```

Ожидаемый результат: `✅ JS syntax OK`. Виджет без `reconstruction` в JSON работает, сегменты `01`/`02`/`03` на месте, `'00'` отсутствует.

- [ ] **Шаг 7: Коммит**

```
git add tests/test_widget_generator.py .claude/skills/konspekt/widget_generator.py
git commit -m "feat(konspekt): add reconstruction as intro chapter (segment 00)"
```

---

## Task 2: Создать `layer2_widget.md`

**Files:**
- Create: `.claude/skills/konspekt/layer2_widget.md`

- [ ] **Шаг 1: Создать файл**

Содержимое файла `.claude/skills/konspekt/layer2_widget.md`:

````markdown
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
  Если таблицы нет (один сегмент в мастер-MD) — `"table": []`

Реконструкция становится первым экраном виджета («Логическая реконструкция», сегмент 00).

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

**`body`** — полный `### Текст` → HTML (см. раздел ниже)

**`right`** — полный `### Карта` → HTML (см. раздел ниже)

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
2. Первый экран — «Логическая реконструкция» с абзацем и таблицей (если сегментов > 1)
3. Кнопка «Далее» ведёт к Сегменту 1
4. Левая колонка каждого сегмента = полный `### Текст`
5. Правая колонка = все карточки из `### Карта`
6. Специальные блоки (Лайфхак/Важно/Демонстрация) с цветной левой рамкой
````

- [ ] **Шаг 2: Коммит**

```
git add .claude/skills/konspekt/layer2_widget.md
git commit -m "feat(konspekt): add layer2_widget.md"
```

---

## Task 3: Обновить `SKILL.md`

**Files:**
- Modify: `.claude/skills/konspekt/SKILL.md`

- [ ] **Шаг 1: Обновить ссылку на файл виджета**

В разделе «Файлы скилла» заменить строку:

```
- `widget.md` — виджет (Слой 2, отдельный пайплайн)
```

на:

```
- `layer2_widget.md` — виджет (Слой 2, конвертация мастер-MD → JSON → HTML)
```

- [ ] **Шаг 2: Добавить раздел «Слой 2»**

После раздела `## Выходной файл` (перед `## Точки остановки`) добавить:

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

- [ ] **Добавить `reconstruction` в тестовый JSON и регенерировать виджет**

Добавить поле `reconstruction` в `transcripts/Виджет — Тайминг Практикум День 1 ч1.json`:

```json
"reconstruction": {
  "prose": "Никита выстраивает первую часть практикума в три хода: сначала задаёт формат работы и объясняет логику инструмента, затем разбирает настройку таймера на конкретном примере, наконец переходит к живой практике — пишет instructions.md вместе с участниками.",
  "table": [
    {"segment": "1", "role": "Открытие / мотивация", "move": "Задаёт формат, объясняет зачем нужен таймер"},
    {"segment": "2", "role": "Инструктаж-практика", "move": "Объясняет настройку, разбирает кейс участника"},
    {"segment": "3", "role": "Демонстрация + практика", "move": "Показывает, как писать instructions.md вместе с участниками"}
  ]
}
```

Затем регенерировать:

```
python ".claude/skills/konspekt/widget_generator.py" "transcripts/Виджет — Тайминг Практикум День 1 ч1.json"
```

Ожидаемый результат: `✅ JS syntax OK`

Открыть в браузере: первый экран — «Логическая реконструкция» с абзацем и таблицей из 3 строк. Кнопка «Далее» → Сегмент 01.

- [ ] **Коммит**

```
git add "transcripts/Виджет — Тайминг Практикум День 1 ч1.json" "transcripts/Виджет — Тайминг Практикум День 1 ч1.html"
git commit -m "feat(konspekt): add reconstruction to validation widget"
```
