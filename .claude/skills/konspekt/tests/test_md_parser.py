import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from md_parser import MasterMDParseError, parse_master_md, _classify_type


MASTER_BODY = """# Тест. Модуль 1: заголовок

**Спикер:** Кто-то

---

## Сегмент 1 | 00:00:00-00:03:38 | Тема

**Тип:** Тезис
**Ключевая мысль:** мысль

### Карта

- **Метка:** пункт

### Текст

Текст сегмента.
"""

FRONTMATTER = """---
source_id: SR6TTf4q1uw
source_url: https://www.youtube.com/watch?v=SR6TTf4q1uw
---
"""


def test_parser_accepts_master_md_without_frontmatter(tmp_path):
    path = tmp_path / "MASTER_Тест.md"
    path.write_text(MASTER_BODY, encoding='utf-8')

    data = parse_master_md(path)

    assert data['meta']['title'] == 'Модуль 1: заголовок · Кто-то'
    assert len(data['segments']) == 1
    assert data['segments'][0]['title'] == 'Тема'


def test_parser_skips_leading_source_passport_frontmatter(tmp_path):
    path = tmp_path / "MASTER_Тест.md"
    path.write_text(MASTER_BODY, encoding='utf-8')
    expected = parse_master_md(path)

    path.write_text(FRONTMATTER + MASTER_BODY, encoding='utf-8')

    assert parse_master_md(path) == expected


def test_parser_rejects_missing_separator_between_segments(tmp_path):
    path = tmp_path / "MASTER_Тест.md"
    segment_block = MASTER_BODY.split('---\n\n', 1)[1]
    second_segment_block = segment_block.replace(
        '## Сегмент 1 | 00:00:00-00:03:38 | Тема',
        '## Сегмент 2 | 00:03:38-00:05:00 | Продолжение',
    )
    # Два `## Сегмент` без `---` между ними -> склеиваются в один блок сплита.
    path.write_text(MASTER_BODY + '\n' + second_segment_block, encoding='utf-8')

    with pytest.raises(MasterMDParseError, match='пропущен разделитель'):
        parse_master_md(path)


# --- Типы блоков пяти профилей -> группа цвета (расширено 2026-08-18) ---

PROFILE_TYPES = {
    'base': [
        ('Введение', 'concept'), ('Основное содержание', 'concept'), ('Пример', 'demo'),
        ('Обсуждение', 'concept'), ('Итоги', 'final'), ('Орг. момент', 'concept'),
        ('Другое', 'concept'),
    ],
    'lecture': [
        ('Введение', 'concept'), ('Концепция', 'concept'), ('Методология', 'method'),
        ('Инструмент / практика', 'method'), ('Пример / кейс', 'demo'),
        ('Демонстрация', 'demo'), ('Задание / ДЗ', 'method'),
        ('Вопросы / ответы', 'demo'), ('Орг. момент', 'concept'),
        ('Итоги / резюме', 'final'),
    ],
    'conference': [
        ('Открытие / приветствие', 'concept'), ('Концепция', 'concept'),
        ('Методология', 'method'), ('Кейс / пример', 'demo'), ('Демонстрация', 'demo'),
        ('Панельная дискуссия', 'concept'), ('Вопросы / ответы', 'demo'),
        ('Маркетинговый блок', 'demo'), ('Орг. момент', 'concept'), ('Закрытие', 'final'),
    ],
    'custdev': [
        ('Установление контакта', 'concept'), ('Контекст / бэкграунд', 'concept'),
        ('Проблема', 'concept'), ('Потребность', 'concept'), ('Текущее решение', 'demo'),
        ('Реакция на концепцию', 'concept'), ('Инсайт', 'concept'),
        ('Возражение', 'demo'), ('Договорённость / next step', 'method'),
        ('Орг. момент', 'concept'),
    ],
    'meeting': [
        ('Открытие / повестка', 'concept'), ('Обсуждение', 'concept'),
        ('Проблема', 'concept'), ('Решение', 'method'),
        ('Голосование / согласование', 'method'), ('Action item', 'method'),
        ('Информирование', 'concept'), ('Орг. момент', 'concept'), ('Закрытие', 'final'),
    ],
}


@pytest.mark.parametrize('profile,pairs', sorted(PROFILE_TYPES.items()))
def test_classify_type_covers_profile_dictionary(profile, pairs):
    """Каждый тип блока из словаря профиля попадает в свою группу, не в фолбэк."""
    for raw, expected in pairs:
        assert _classify_type(raw) == expected, f'{profile}: {raw}'


def test_segment_carries_raw_type_as_label(tmp_path):
    """Сырой **Тип:** едет в сегмент — плашка виджета показывает его, не ярлык темы."""
    path = tmp_path / "MASTER_Тест.md"
    path.write_text(MASTER_BODY, encoding='utf-8')
    data = parse_master_md(path)
    assert data['segments'][0]['label']
