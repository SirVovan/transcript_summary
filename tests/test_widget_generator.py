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
