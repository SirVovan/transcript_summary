#!/usr/bin/env python3
"""
md_parser.py - парсер мастер-MD конспекта в dict-структуру виджета.

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


LABEL_COLORS = {
    'idea': ('#ECF2FB', '#2562B0'),    # (И) синий
    'method': ('#EBF5EB', '#2E6E2E'),  # (М) зелёный
    'demo': ('#FAF0E4', '#96580F'),    # (Д) оранжевый
}

# Точные метки (нормализованные, lowercase, без точек)
LABEL_TABLE = {
    'ключевая идея': 'idea',
    'главная идея': 'idea',
    'принцип': 'idea',
    'лайфхак': 'idea',
    'методология': 'method',
    'критерии': 'method',
    'правило': 'method',
    'шаблон': 'method',
    'пример': 'demo',
    'пример декомпозиции': 'demo',
    'демонстрация': 'demo',
    'важно': 'demo',
}

SEGMENT_TYPE_COLORS = {
    'concept': '#2562B0',
    'method': '#2E6E2E',
    'demo': '#96580F',
}

SEGMENT_TYPE_RULES = [
    # (паттерны в **Тип**, тип виджета)
    (['тезис', 'открытие', 'мотивация', 'введение'], 'concept'),
    (['инструктаж', 'настройка', 'метод', 'инструкция'], 'method'),
    (['демонстрация', 'практика', 'разбор', 'q&a', 'призыв'], 'demo'),
]


def parse_master_md(path):
    """Главная функция: читает файл, возвращает dict для build_html."""
    text = Path(path).read_text(encoding='utf-8')
    sections = _split_sections(text)
    meta = _parse_meta(sections['header'], path)
    route = _parse_route(sections['route']) if sections['route'] else None
    reconstruction = _parse_reconstruction(sections['reconstruction']) if sections['reconstruction'] else None
    prompt_counter = [0]
    segments = [_parse_segment(b, i + 1, prompt_counter) for i, b in enumerate(sections['segments'])]
    return {
        'meta': meta,
        'route': route,
        'reconstruction': reconstruction,
        'trajectory': None,
        'segments': segments,
        'prompts': {},
    }


def _split_sections(text):
    """Режет мастер-MD на header, route (опц.), reconstruction (опц.), segments[]."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    parts = re.split(r'\n---\n', text)
    parts = [p.strip() for p in parts if p.strip()]

    if not parts:
        raise MasterMDParseError("Пустой файл")

    header = parts[0]
    if not header.startswith('# '):
        raise MasterMDParseError(f"Первый блок не начинается с `# Название`, найдено: {header[:60]!r}")

    route = None
    reconstruction = None
    segments = []
    for part in parts[1:]:
        if part.startswith('## Замысел и маршрут'):
            route = part
        elif part.startswith('## Логическая реконструкция'):
            reconstruction = part
        elif part.startswith('## Сегмент '):
            segments.append(part)
        else:
            raise MasterMDParseError(
                f"Неизвестный раздел верхнего уровня: {part.splitlines()[0]!r}"
            )

    if not segments:
        raise MasterMDParseError("Не найдено ни одного `## Сегмент N | ...`")

    return {'header': header, 'route': route, 'reconstruction': reconstruction, 'segments': segments}


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
    #  ---- badge parts ------  -- title prefix --  -- title tail -----
    if ':' in full_title:
        before_colon, after_colon = full_title.split(':', 1)
        parts = [p.strip() for p in before_colon.split('.') if p.strip()]
        # badge = первые две части через ` · `; если частей < 2, берём что есть
        if len(parts) >= 2:
            badge = ' · '.join(parts[:2])
            title_prefix = parts[-1]  # последняя часть - «Урок 2»
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


def _parse_route(block):
    """`## Замысел и маршрут\n\n<prose>\n\n**<Label>:**\n\n<list>` -> {'prose', 'structure'}.

    Маркер опорной структуры — любая строка целиком вида `**Label:**` (без текста после).
    Парсер не интерпретирует форму списка — отдаёт как нумерованный/маркированный список HTML.
    Если маркера нет — весь блок считается прозой, structure == ''.
    """
    body = re.sub(r'^##\s+Замысел и маршрут\s*\n', '', block, count=1)
    lines = body.split('\n')

    # Находим строку-маркер: `**...:**` на своей строке (после strip — ровно эта запись).
    marker_re = re.compile(r'^\*\*[^*\n]+:\*\*\s*$')
    split_idx = None
    for idx, line in enumerate(lines):
        if marker_re.match(line.strip()):
            split_idx = idx
            break

    if split_idx is None:
        prose_lines = lines
        structure_lines = []
    else:
        prose_lines = lines[:split_idx]
        structure_lines = lines[split_idx + 1:]

    prose_html = _render_paragraphs(prose_lines)
    structure_html = _render_list(structure_lines)

    return {'prose': prose_html, 'structure': structure_html}


def _render_paragraphs(lines):
    """Список строк (с пустыми разделителями) -> склейка `<p>...</p>` через _apply_inline."""
    paragraphs = []
    buf = []
    for line in lines:
        if line.strip() == '':
            if buf:
                paragraphs.append(_apply_inline(' '.join(buf).strip()))
                buf = []
        else:
            buf.append(line.strip())
    if buf:
        paragraphs.append(_apply_inline(' '.join(buf).strip()))
    return ''.join(f'<p>{p}</p>' for p in paragraphs)


def _render_list(lines):
    """Строки после маркера -> `<ol>` если нумерованный, `<ul>` если маркированный, иначе абзацы."""
    items = [l.strip() for l in lines if l.strip()]
    if not items:
        return ''

    if all(re.match(r'\d+\.\s+', it) for it in items):
        body = ''.join(
            f'<li>{_apply_inline(re.match(r"\d+\.\s+(.*)", it).group(1))}</li>'
            for it in items
        )
        return f'<ol style="margin:6px 0 0 18px">{body}</ol>'
    if all(it.startswith('- ') for it in items):
        body = ''.join(f'<li>{_apply_inline(it[2:])}</li>' for it in items)
        return f'<ul style="margin:6px 0 0 18px">{body}</ul>'

    # Смесь форматов или просто абзацы — рендерим как абзацы для устойчивости.
    return _render_paragraphs(lines)


def _parse_reconstruction(block):
    """`## Логическая реконструкция\n\n...` -> {prose, table}."""
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


def _parse_segment(block, idx, prompt_counter):
    """
    block - `## Сегмент N | ... | ...` + всё содержимое до следующего разделителя.
    idx - порядковый номер (1-based) для `id` ("01", "02", ...).
    prompt_counter - список [int] для сквозной нумерации промптов.
    """
    lines = block.split('\n')
    # Заголовок: `## Сегмент N | HH:MM:SS-HH:MM:SS | Тема`
    header = lines[0]
    m = re.match(r'##\s+Сегмент\s+\d+\s*\|\s*([\d:]+\s*[–-]\s*[\d:]+)\s*\|\s*(.+)', header)
    if not m:
        raise MasterMDParseError(f"Не разобран заголовок сегмента: {header!r}")
    raw_timing = m.group(1).strip()
    title = m.group(2).strip()

    # Тайминг: «HH:MM:SS-HH:MM:SS» -> «HH:MM-HH:MM» (как в эталонном JSON)
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


def _classify_type(raw_type):
    norm = raw_type.lower()
    # Берём первый из подстрок, который встретится - иначе concept
    # Порядок: ищем первое совпадение по приоритету правил.
    for patterns, t in SEGMENT_TYPE_RULES:
        if any(p in norm for p in patterns):
            return t
    return 'concept'


def _shorten_timing(raw):
    """`00:00:00-00:03:38` -> `00:00-03:38`. Если уже короткий - оставляем."""
    parts = re.split(r'\s*[–-]\s*', raw)
    if len(parts) != 2:
        return raw

    def short(t):
        bits = t.split(':')
        if len(bits) == 3:
            return f'{bits[0]}:{bits[1]}' if bits[0] != '00' else f'{bits[1]}:{bits[2]}'
        return t

    return f'{short(parts[0])}–{short(parts[1])}'


def _apply_inline(text):
    """`**жирное**` -> <strong>, `*курсив*` -> <em>. Жирное обрабатываем первым."""
    # Сначала жирное (двойные звёздочки)
    text = re.sub(r'\*\*([^\n]+?)\*\*', r'<strong>\1</strong>', text)
    # Потом курсив (одиночные звёздочки, не часть **)
    text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)
    return text


def _label_color(label):
    """Метка -> (bg, border) hex-цвета."""
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
    # Дефолт - оранжевый (примеры/предупреждения)
    return LABEL_COLORS['demo']


def _render_blockquote(lines):
    """
    Список «голых» строк блока (без `> ` префикса) -> coloured <div>.
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

    # Отрезаем хвостовую прозу: список + пустая `>` + проза → разделяем.
    tail_prose_lines = []
    if '' in rest:
        blank_idx = rest.index('')
        tail_prose_lines = [l for l in rest[blank_idx + 1:] if l]
        rest = rest[:blank_idx]

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
        if tail_prose_lines:
            body += f'<div style="margin-top:6px">{_apply_inline(" ".join(tail_prose_lines))}</div>'
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
        if tail_prose_lines:
            body += f'<div style="margin-top:6px">{_apply_inline(" ".join(tail_prose_lines))}</div>'
        prefix = f'{_apply_inline(inline_after_label)}' if inline_after_label else ''
        return f'<div style="{style}"><strong>{label}:</strong> {prefix}{body}</div>'
    else:
        # Простая проза - склеиваем строки через пробел
        full = inline_after_label
        if rest:
            full = (full + ' ' + ' '.join(rest)).strip() if full else ' '.join(rest)
        return f'<div style="{style}"><strong>{label}:</strong> {_apply_inline(full)}</div>'


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


def _parse_text(block, prompt_counter):
    """
    block - содержимое после `### Текст` до конца сегмента (без самой строки `### Текст`).
    prompt_counter - список [int] (используется как изменяемая ссылка для сквозной нумерации p1, p2...).
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
        m = re.match(r'\*\*((?:Промпт|Скрипт)[^*]*?):\*\*\s*$', first.strip())
        if m and len(bq_buffer) == 1:
            # Метка промпта - отложим, ждём fenced
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
            # pending_prompt_label НЕ сбрасываем - между меткой и fenced может быть пустая строка
            i += 1
            continue

        # Здесь начинается «обычный» контент -> flush bq и сбрасываем pending_prompt
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

        # Обычный абзац - копим строки до пустой
        para_lines = []
        while (
            i < len(lines)
            and lines[i].strip() != ''
            and not lines[i].strip().startswith(('>', '#### ', '```', '- '))
            and not re.match(r'\d+\.\s+', lines[i].strip())
        ):
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


def _parse_map(block, segment_type):
    """
    block - содержимое после `### Карта` до `### Текст` (или конца).
    segment_type - 'concept'/'method'/'demo' - определяет цвет border-left.
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
        # Первое **...** - метка уровня (И)/(М)/(Д), остальное - текст
        items.append(
            f'<div class="insight" style="border-left-color:{color}">{_apply_inline(body)}</div>'
        )
    if not items:
        raise MasterMDParseError("Пустой `### Карта`")
    return f'<div class="insights">{"".join(items)}</div>'


if __name__ == '__main__':
    import sys
    import json
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    print(json.dumps(parse_master_md(sys.argv[1]), ensure_ascii=False, indent=2))
