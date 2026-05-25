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


def test_route_block_parses_prose_and_structure(tmp_path):
    """Проза до `**Этапы:**` идёт в route_prose, нумерованный список — в structure."""
    body = """# Тест

**Спикер:** Тестовый

---

## Замысел и маршрут

Автор разбирает тему **пошагово**.

Это второй абзац прозы.

**Этапы:**

1. Этап 1 — открыть тему.
2. Этап 2 — углубить.

---
""" + MINIMAL_SEGMENT
    path = _write_master(tmp_path, body)
    data = parse_master_md(path)
    route = data['route']

    # Проза: два абзаца, жирное конвертировано в <strong>
    assert '<p>Автор разбирает тему <strong>пошагово</strong>.</p>' in route['prose']
    assert '<p>Это второй абзац прозы.</p>' in route['prose']
    # В прозе не должно быть текста этапов
    assert 'Этап 1' not in route['prose']

    # Структура: нумерованный список
    assert '<ol' in route['structure']
    assert '<li>Этап 1 — открыть тему.</li>' in route['structure']
    assert '<li>Этап 2 — углубить.</li>' in route['structure']


def test_route_block_structure_bullets(tmp_path):
    """Маркированный список после маркера рендерится как <ul>."""
    body = """# Тест

**Спикер:** Тестовый

---

## Замысел и маршрут

Лекция о ключевых тезисах.

**Тезисы:**

- Первый тезис.
- Второй тезис.

---
""" + MINIMAL_SEGMENT
    path = _write_master(tmp_path, body)
    data = parse_master_md(path)
    structure = data['route']['structure']
    assert '<ul' in structure
    assert '<li>Первый тезис.</li>' in structure
    assert '<li>Второй тезис.</li>' in structure


def test_route_block_only_prose(tmp_path):
    """Если маркера `**...:**` нет — весь блок идёт в prose, structure пуст."""
    body = """# Тест

**Спикер:** Тестовый

---

## Замысел и маршрут

Просто проза без опорной структуры — короткий разбор.

---
""" + MINIMAL_SEGMENT
    path = _write_master(tmp_path, body)
    route = parse_master_md(path)['route']
    assert '<p>Просто проза без опорной структуры — короткий разбор.</p>' == route['prose']
    assert route['structure'] == ''
