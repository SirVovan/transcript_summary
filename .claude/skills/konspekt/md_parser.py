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
