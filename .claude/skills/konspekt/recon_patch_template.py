"""
Шаблон patch-скрипта для Слоя 3 (кастомизация экрана «Логическая реконструкция»).

Использование:
  1. cp recon_patch_template.py _patches/patch_recon_<урок>.py
  2. Заполнить все TODO-секции.
  3. python _patches/patch_recon_<урок>.py

Папка `_patches/` — карантин для одноразовых патчей конкретных лекций. Игнорируется
git'ом (см. `.gitignore`). Самоуничтожение: при запуске старше 7 дней с момента
создания патч удаляет себя — патчи нужны для разовой сборки виджета и пары
правок «по горячему», дольше не живут. Правка патча обновляет mtime → таймер
продлевается.

Типовые формы SVG (выбрать по структуре урока):
  - параллельные ветви → один результат (несколько процессов сходятся)
  - горизонтальная цепь артефактов с правками (последовательная трансформация)
  - цикл (повторяющийся процесс с возвратом)
  - иерархия (родитель → дети → внуки)

Полные правила Слоя 3 — `layer3_recon.md`.
"""

import json
import re
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────
# Охранный запуск: отказать, если TODO ещё не заполнены
# ─────────────────────────────────────────────────────────────────────

_this_src = Path(__file__).read_text(encoding="utf-8")
_todo_count = _this_src.count("# TODO")
if _todo_count > 0:
    sys.exit(
        f"Шаблон не готов к запуску: найдено {_todo_count} незаполненных TODO-секций.\n"
        f"Отредактируй файл, замени все TODO на реальные значения."
    )

# ─────────────────────────────────────────────────────────────────────
# Путь к виджету
# ─────────────────────────────────────────────────────────────────────

WIDGET = Path(
    # TODO: вставить путь к HTML-виджету лекции.
    # Пример: "transcripts/WIDGET_Вайбкодинг. М2-У8. Название.html"
    "transcripts/TODO_WIDGET_PATH.html"
)

# ─────────────────────────────────────────────────────────────────────
# SVG-схема (опционально)
# ─────────────────────────────────────────────────────────────────────
#
# Нужен, если в лекции есть операциональная схема (цепочка, параллельные
# процессы, цикл, иерархия). Если схемы нет — удали SVG_SCHEME и убери
# его из BODY_00.
#
# Технические константы SVG:
#   viewBox="0 0 540 280", фон #F8F6F1, рамка rgba(60,52,36,.15), rx 10px
#   Цвета: синий #2562B0 (файлы), зелёный #2E6E2E (вывод), оранжевый #96580F (действия)
#   Шрифт основной: 'Manrope',system-ui,sans-serif
#   Шрифт моноширинный: JetBrains Mono, monospace (для имён файлов)
#   Маркер стрелок: именованный id="arr-<урок>", чтобы не конфликтовать
#
# Типовые формы: параллельные ветви (м2у6), горизонтальная цепь (м2у7).

SVG_SCHEME = '''
<!-- TODO: нарисовать SVG или удалить эту константу и убрать из BODY_00 -->
'''

# ─────────────────────────────────────────────────────────────────────
# Левая колонка: проза + SVG + «Главная идея»
# ─────────────────────────────────────────────────────────────────────
#
# Принципы:
#   - 4–6 коротких абзацев (1 абзац = 1 мысль), жирным 2–4 якоря на абзац.
#   - SVG вставляется между прозой и блоком «Главная идея» (если есть).
#   - Блок «Главная идея» всегда в конце.
#
# Если SVG не нужен — убрать {SVG_SCHEME} из f-строки и удалить SVG_SCHEME выше.

BODY_00 = f"""\
<p>
<!-- TODO: абзац 1 — ключевой вопрос или тезис урока.
     Пример: Урок отвечает на вопрос: <strong>как сделать X?</strong>
     Ответ — <strong>не делать это руками</strong>. -->
</p>

{SVG_SCHEME}

<p>
<!-- TODO: абзац 2 -->
</p>

<p>
<!-- TODO: абзац 3 -->
</p>

<p>
<!-- TODO: абзац 4 -->
</p>

<div style="background:#ECF2FB;border-left:3px solid #2562B0;border-radius:0 8px 8px 0;\
padding:10px 14px;margin:14px 0 6px;font-size:13px;line-height:1.55">\
<strong>Главная идея:</strong> \
<!-- TODO: одна формулировка главного тезиса из мастер-MD -->\
</div>\
"""

# ─────────────────────────────────────────────────────────────────────
# Хелперы правой колонки
# ─────────────────────────────────────────────────────────────────────

def section(label, items_html, goto_id=None):
    """Секция с заголовком. goto_id → кликабельный заголовок с ↗."""
    if goto_id:
        header = (
            f'<div class="sec-h" onclick="goTo(\'{goto_id}\')" '
            f'style="font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;'
            f'color:#8C8278;margin:0 0 7px 2px;cursor:pointer;display:flex;align-items:center;gap:6px;'
            f'transition:color .15s" '
            f'title="Перейти к сегменту {goto_id}">'
            f'<span>{label}</span>'
            f'<span style="font-size:11px;color:#B8B0A6;transition:color .15s,transform .15s">↗</span>'
            f'</div>'
        )
    else:
        header = (
            f'<div style="font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;'
            f'color:#8C8278;margin:0 0 7px 2px">{label}</div>'
        )
    return f'<div style="margin-bottom:14px">{header}{items_html}</div>'


def file_card(name, desc, color, goto_id=None):
    """
    Плашка с именем файла (моноширинный) + описанием.
    goto_id → стрелка ↗ в правом верхнем углу карточки.
    """
    arrow = ''
    if goto_id:
        arrow = (
            f'<span class="goto-arrow" onclick="event.stopPropagation();goTo(\'{goto_id}\')" '
            f'title="Перейти к сегменту {goto_id}" '
            f'style="position:absolute;top:6px;right:8px;cursor:pointer;color:#B8B0A6;font-size:13px;'
            f'transition:color .15s,transform .15s;line-height:1">↗</span>'
        )
    return (
        f'<div class="insight" style="border-left-color:{color};display:flex;gap:10px;align-items:flex-start;'
        f'margin-bottom:6px;position:relative;padding-right:24px">'
        f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:12px;font-weight:700;color:{color};flex-shrink:0">{name}</span>'
        f'<span style="font-size:11.5px;color:#4A4438;font-weight:500;line-height:1.5">{desc}</span>'
        f'{arrow}'
        f'</div>'
    )


def prompt_card(name, desc, color, prompt_text, pid, goto_id=None):
    """
    <details>-карточка с раскрываемым текстом промпта.
    pid — уникальный строковый id (например "rp1") для кнопки cp().
    goto_id → стрелка ↗ вне <summary>, с event.stopPropagation().
    """
    safe = (prompt_text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))
    arrow = ''
    if goto_id:
        # Стрелка вне <summary>: располагается поверх details, клик не разворачивает.
        arrow = (
            f'<span class="goto-arrow" onclick="event.stopPropagation();goTo(\'{goto_id}\')" '
            f'title="Перейти к сегменту {goto_id}" '
            f'style="position:absolute;top:8px;right:8px;cursor:pointer;color:#B8B0A6;font-size:13px;'
            f'transition:color .15s,transform .15s;line-height:1;z-index:2">↗</span>'
        )
    return (
        f'<details class="insight" style="border-left-color:{color};margin-bottom:6px;padding:0;cursor:default;position:relative">'
        f'{arrow}'
        f'<summary style="list-style:none;padding:8px 26px 8px 13px;cursor:pointer">'
        f'<span style="display:inline-block;margin-right:6px;color:{color};font-size:10px;transition:transform .15s">▶</span>'
        f'<span style="font-size:12px;font-weight:700;color:#1C1915">{name}</span>'
        f'<div style="font-size:11.5px;color:#4A4438;font-weight:500;line-height:1.5;margin:3px 0 0 18px">{desc}</div>'
        f'</summary>'
        f'<div class="pr-block" style="margin:4px 8px 8px;box-shadow:none">'
        f'<div class="pr-head"><span class="pr-label">Текст промпта</span>'
        f'<button class="pr-copy" id="cpb{pid}" onclick="event.stopPropagation();cp(\'{pid}\')">копировать</button></div>'
        f'<div class="pr-text" style="font-size:11px;line-height:1.55">{safe}</div>'
        f'</div>'
        f'</details>'
    )


def link_card(url, desc):
    """Компактная плашка с моноширинным URL + описанием."""
    return (
        f'<div class="insight" style="border-left-color:#5A6A7A;display:flex;gap:10px;align-items:baseline;margin-bottom:5px;padding:6px 12px 6px 13px">'
        f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:11.5px;font-weight:600;color:#1C1915;flex-shrink:0">{url}</span>'
        f'<span style="font-size:11px;color:#8C8278;font-weight:500">{desc}</span>'
        f'</div>'
    )


# ─────────────────────────────────────────────────────────────────────
# Контент правой колонки
# ─────────────────────────────────────────────────────────────────────
#
# Правила кликабельности:
#   - Все элементы секции → один сегмент: goto_id на section(), не на карточках.
#   - Элементы → разные сегменты: goto_id на каждой карточке, section() без goto_id.
#
# Цвета карточек:
#   синий  #2562B0 — файлы/артефакты
#   зелёный #2E6E2E — результат/вывод
#   оранжевый #96580F — действия/промпты
#
# Секции ниже — заготовки. Удали ненужные, добавь свои.

# TODO: Пример секции «Файлы в проекте».
# Раскомментируй и заполни, если в лекции создаются именованные файлы.
#
# FILES = section("Файлы в проекте", "".join([
#     file_card("filename.md", "Описание что внутри и зачем", "#2562B0", goto_id="01"),
# ]))

# TODO: Пример секции «Промпты».
# Раскомментируй и заполни текст каждого промпта дословно из мастер-MD.
#
# P1_TEXT = """Текст промпта 1 дословно..."""
#
# PROMPTS = section("Промпты (N) · клик — текст", "".join([
#     prompt_card("Название промпта", "Краткое описание что делает", "#96580F", P1_TEXT, "rp1", goto_id="02"),
# ]))

# TODO: Пример секции «Лайфхаки».
# Используй file_card без goto_id если все из одного сегмента → goto_id на section().
#
# LIFEHACKS = section("Лайфхаки урока", "".join([
#     file_card("Ctrl+Shift+P", "Описание лайфхака", "#2562B0", goto_id="03"),
# ]))

# TODO: Пример секции «Ресурсы».
# goto_id на section() если все ссылки упомянуты в одном сегменте.
#
# LINKS = section("Ресурсы", "".join([
#     link_card("example.com", "Описание сервиса"),
# ]), goto_id="02")

# TODO: Домашнее задание.
#
# HOMEWORK = section("Что сделать после урока", (
#     '<div class="insight" style="border-left-color:#2562B0;font-size:11.5px;line-height:1.6;color:#4A4438">'
#     '<ol style="margin:0 0 0 16px;padding:0;font-weight:500">'
#     '<li style="margin-bottom:4px"><strong>Шаг 1</strong></li>'
#     '<li><strong>Шаг 2</strong></li>'
#     '</ol>'
#     '</div>'
# ), goto_id="07")

# ─────────────────────────────────────────────────────────────────────
# CSS для деталей и hover на стрелках
# ─────────────────────────────────────────────────────────────────────

DETAILS_CSS = (
    '<style>'
    '.insights details summary::-webkit-details-marker{display:none}'
    '.insights details[open] summary > span:first-child{transform:rotate(90deg)}'
    '.insights details summary > span:first-child{display:inline-block;transition:transform .15s}'
    '.insights .sec-h:hover{color:#1C1915}'
    '.insights .sec-h:hover span:last-child{color:#2562B0;transform:translate(2px,-2px)}'
    '.insights .goto-arrow:hover{color:#2562B0;transform:translate(2px,-2px)}'
    '</style>'
)

# ─────────────────────────────────────────────────────────────────────
# Правая колонка: собрать из секций
# ─────────────────────────────────────────────────────────────────────
#
# TODO: заменить заглушки на реальные переменные секций.

RIGHT_00 = (
    '<div class="insights">'
    f'{DETAILS_CSS}'
    # TODO: добавить секции, например: f'{FILES}' f'{PROMPTS}' f'{LIFEHACKS}' f'{LINKS}' f'{HOMEWORK}'
    '</div>'
)

# ─────────────────────────────────────────────────────────────────────
# Функция адресной замены внутри var BODY / var RIGHT
# ─────────────────────────────────────────────────────────────────────

def patch_block(html_text, var_name, key, new_value):
    block_re = re.compile(rf'(var {var_name} = \{{\n)(.*?)(\n}};)', re.DOTALL)
    m = block_re.search(html_text)
    if not m:
        raise SystemExit(f"Не найден блок `var {var_name} = ...`")
    block_open, block_body, block_close = m.group(1), m.group(2), m.group(3)
    new_value_json = json.dumps(new_value, ensure_ascii=False)
    key_re = re.compile(rf'("{re.escape(key)}":\s*)"(?:[^"\\]|\\.)*"', re.DOTALL)
    new_body, n = key_re.subn(lambda mm: mm.group(1) + new_value_json, block_body, count=1)
    if n != 1:
        raise SystemExit(f"Ключ {key!r} не найден в блоке `var {var_name}` (n={n})")
    return html_text[:m.start()] + block_open + new_body + block_close + html_text[m.end():]

# ─────────────────────────────────────────────────────────────────────
# Применить патч
# ─────────────────────────────────────────────────────────────────────

html = WIDGET.read_text(encoding="utf-8")
html = patch_block(html, "BODY", "00", BODY_00)
html = patch_block(html, "RIGHT", "00", RIGHT_00)
WIDGET.write_text(html, encoding="utf-8")

print(f"Готово: {WIDGET}")
print(f"  BODY['00']  ← проза + SVG ({len(BODY_00)} симв.)")
print(f"  RIGHT['00'] ← артефакты ({len(RIGHT_00)} симв.)")

# ─────────────────────────────────────────────────────────────────────
# Самоуничтожение: патч старше 7 дней удаляется после успешного запуска
# ─────────────────────────────────────────────────────────────────────

import time

_SELF_DESTRUCT_DAYS = 7
_self = Path(__file__)
_age_days = (time.time() - _self.stat().st_mtime) / 86400
if _age_days >= _SELF_DESTRUCT_DAYS:
    print(f"  patch старше {_SELF_DESTRUCT_DAYS} дней (возраст {_age_days:.1f}д) — удаляю себя.")
    _self.unlink()
else:
    _days_left = _SELF_DESTRUCT_DAYS - _age_days
    print(f"  patch самоуничтожится через {_days_left:.1f} дн. при следующем запуске.")
