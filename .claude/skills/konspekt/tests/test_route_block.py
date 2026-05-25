import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from md_parser import parse_master_md, MasterMDParseError


def _write_master(tmp_path, body):
    """Записывает body в tmp/master.md и возвращает путь."""
    p = tmp_path / "master.md"
    p.write_text(body, encoding='utf-8')
    return str(p)


MINIMAL_SEGMENT = """
## Сегмент 1 | 00:00:00–00:05:00 | Введение

**Тип:** Введение
**Ключевая мысль:** Запускаем разбор.

### Карта

- **(И)** Открытие темы.

### Текст

Спикер вводит тему.
"""


def test_parser_accepts_route_block(tmp_path):
    """Раздел `## Замысел и маршрут` должен парситься без ошибки."""
    body = """# Тест

**Спикер:** Тестовый

---

## Замысел и маршрут

Автор разбирает тему пошагово.

**Этапы:**

1. Этап 1 — открыть тему.
2. Этап 2 — углубить.

---
""" + MINIMAL_SEGMENT
    path = _write_master(tmp_path, body)
    data = parse_master_md(path)  # не должно бросить
    assert 'route' in data


def test_parser_route_is_none_when_block_missing(tmp_path):
    """Мастер-MD без блока: data['route'] is None, парсер не падает."""
    body = """# Тест

**Спикер:** Тестовый

---
""" + MINIMAL_SEGMENT
    path = _write_master(tmp_path, body)
    data = parse_master_md(path)
    assert data['route'] is None
