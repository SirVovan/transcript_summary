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


# Заглушки - будут реализованы в следующих задачах:
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
            # Неизвестный раздел - упоминаем номер и первые 60 символов
            raise MasterMDParseError(
                f"Неизвестный раздел верхнего уровня: {part.splitlines()[0]!r}"
            )

    if not segments:
        raise MasterMDParseError("Не найдено ни одного `## Сегмент N | ...`")

    return {'header': header, 'reconstruction': reconstruction, 'segments': segments}


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
