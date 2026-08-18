import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from md_parser import MasterMDParseError, parse_master_md


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
