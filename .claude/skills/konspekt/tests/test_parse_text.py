"""Характеристические тесты `_parse_text` — самого большого непокрытого куска парсера.

Фиксируют текущее поведение конвертации `### Текст` → HTML, чтобы правки в
разметке сегмента не проходили молча (генератор печатает `✅ JS syntax OK`
даже когда структура разъехалась).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from md_parser import MasterMDParseError, _parse_text


def parse(text, base_dir=None):
    return _parse_text(text, [0], base_dir or os.path.dirname(__file__))


# --- проза, заголовки, списки ---

def test_paragraph_joins_wrapped_lines():
    html = parse('Первая строка\nпродолжение абзаца.')
    assert html == '<p>Первая строка продолжение абзаца.</p>'


def test_two_paragraphs_split_on_blank_line():
    html = parse('Первый.\n\nВторой.')
    assert html == '<p>Первый.</p><p>Второй.</p>'


def test_bold_becomes_strong():
    assert '<strong>важное</strong>' in parse('Тут **важное** слово.')


def test_h4_becomes_h3():
    assert parse('#### Подтема') == '<h3>Подтема</h3>'


def test_bullet_list():
    html = parse('- первый\n- второй')
    assert html.startswith('<ul')
    assert html.count('<li') == 2
    assert 'первый' in html and 'второй' in html


def test_numbered_list():
    html = parse('1. раз\n2. два')
    assert html.startswith('<ol')
    assert html.count('<li') == 2


def test_list_then_paragraph():
    html = parse('- пункт\n\nПосле списка.')
    assert html.index('<ul') < html.index('<p>')


# --- blockquote-блоки ---

def test_blockquote_renders_coloured_div():
    html = parse('> **Ключевая идея:** мысль автора.')
    assert '<div style=' in html
    assert '<strong>Ключевая идея:</strong>' in html
    assert 'мысль автора.' in html


def test_blockquote_with_nested_numbered_list_stays_one_div():
    html = parse('> **Критерии:**\n> 1. раз\n> 2. два')
    assert html.count('<div style=') == 1
    assert html.count('<li>') == 2


def test_unknown_label_still_renders():
    """Метка вне LABEL_TABLE не роняет парсер — цвет подбирается эвристикой."""
    html = parse('> **Неведомая метка:** текст.')
    assert '<strong>Неведомая метка:</strong>' in html


# --- промпты ---

PROMPT_BLOCK = '> **Промпт «Тест»:**\n\n```\nстрока 1\nстрока 2\n```'


def test_prompt_block_renders_pr_block():
    html = parse(PROMPT_BLOCK)
    assert 'pr-block' in html
    assert 'строка 1\nстрока 2' in html or 'строка 1' in html


def test_script_label_accepted():
    html = parse('> **Скрипт «Звонок»:**\n\n```\nздравствуйте\n```')
    assert 'pr-block' in html
    assert 'Скрипт «Звонок»' in html


def test_prompt_ids_are_sequential():
    counter = [0]
    first = _parse_text(PROMPT_BLOCK, counter, os.path.dirname(__file__))
    second = _parse_text(PROMPT_BLOCK, counter, os.path.dirname(__file__))
    assert "cp('p1')" in first
    assert "cp('p2')" in second


def test_prompt_label_without_code_block_raises():
    with pytest.raises(MasterMDParseError, match='без последующего fenced'):
        parse('> **Промпт «Тест»:**\n\nОбычный абзац вместо кода.')


def test_prompt_label_at_end_without_code_block_raises():
    with pytest.raises(MasterMDParseError, match='в конце'):
        parse('> **Промпт «Тест»:**')


def test_code_block_without_prompt_label_raises():
    with pytest.raises(MasterMDParseError, match='без предыдущей blockquote-метки'):
        parse('```\nголый код\n```')


def test_unclosed_code_block_raises():
    with pytest.raises(MasterMDParseError, match='Незакрытый'):
        parse('> **Промпт «Тест»:**\n\n```\nкод без закрытия')


# --- порядок и совместная работа ---

def test_mixed_block_order_preserved():
    html = parse(
        'Вступление.\n'
        '\n'
        '#### Подтема\n'
        '\n'
        '- пункт\n'
        '\n'
        '> **Принцип:** правило.\n'
        '\n'
        'Заключение.'
    )
    assert html.index('Вступление') < html.index('Подтема') < html.index('пункт')
    assert html.index('пункт') < html.index('правило') < html.index('Заключение')


# --- цитата без метки и многоабзацность (backlog п.21) ---

def test_bare_blockquote_renders_as_neutral_quote():
    """Дословная цитата без `**Метка:**` не роняет парсер — нейтральный серый блок."""
    html = parse('> Я написал пост, который сейчас зачитаю дословно.')
    assert '<div style=' in html
    assert '<strong>' not in html
    assert 'Я написал пост, который сейчас зачитаю дословно.' in html


def test_quote_label_gets_own_colour():
    """Метка «Цитата» — своя, не сваливается в дефолтный оранжевый."""
    from md_parser import _label_color
    assert _label_color('Цитата') != _label_color('Пример')
    html = parse('> **Цитата:** слова автора.')
    assert '<strong>Цитата:</strong>' in html


def test_bare_blockquote_keeps_paragraphs():
    """Многоабзацная цитата без метки: каждый абзац отдельным <p>, ничего не схлопывается."""
    html = parse('> Первый абзац.\n>\n> Второй абзац.\n>\n> Третий абзац.')
    assert html.count('<div style=') == 1
    assert '<p>Первый абзац.</p>' in html
    assert '<p>Второй абзац.</p>' in html
    assert '<p>Третий абзац.</p>' in html


def test_labelled_blockquote_keeps_tail_paragraphs():
    """Метка + несколько абзацев хвоста: абзацы не склеиваются в один."""
    html = parse('> **Цитата:**\n>\n> Первый абзац.\n>\n> Второй абзац.')
    assert html.count('<div style=') == 1
    assert '<p>Первый абзац.</p>' in html
    assert '<p>Второй абзац.</p>' in html
