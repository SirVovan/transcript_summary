import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from widget_generator import build_reconstruction_html, build_timeline_html, build_html


# --- Item 1: build_reconstruction_html ---

def test_build_reconstruction_html_prose_passthrough():
    """prose arrives as pre-converted HTML — must not be double-wrapped in <p>"""
    recon = {
        'prose': '<p>Спикер <strong>вводит концепцию</strong>.</p>',
        'table': []
    }
    result = build_reconstruction_html(recon)
    assert '<p><p>' not in result
    assert '<strong>вводит концепцию</strong>' in result


def test_build_reconstruction_html_empty():
    assert build_reconstruction_html(None) == ''
    assert build_reconstruction_html({}) == ''


def test_build_reconstruction_html_with_table():
    """table renders correctly alongside prose"""
    recon = {
        'prose': '<p>Текст.</p>',
        'table': [{'segment': '1', 'role': 'Тезис', 'move': 'Формулирует вопрос'}]
    }
    result = build_reconstruction_html(recon)
    assert 'Тезис' in result
    assert 'Формулирует вопрос' in result
    assert '<p><p>' not in result


# --- Item 2: build_timeline_html ---

def test_build_timeline_html_none():
    """trajectory=None returns empty string"""
    assert build_timeline_html(None) == ''


def test_build_timeline_html_basic():
    """timeline renders blocks with correct move labels and goTo calls"""
    trajectory = {
        'prose': '<p>Спикер идёт от проблемы к решению.</p>',
        'moves': [
            {'segment': '1', 'timing': '00:00–10:00', 'move': 'концепт', 'description': 'вводит идею'},
            {'segment': '2', 'timing': '10:00–22:00', 'move': 'практика', 'description': 'показывает'},
        ]
    }
    result = build_timeline_html(trajectory)
    assert 'концепт' in result
    assert 'практика' in result
    assert 'goTo' in result


def test_build_timeline_html_unknown_move_uses_default_color():
    """unknown move type gets default gray color"""
    trajectory = {
        'prose': '',
        'moves': [
            {'segment': '1', 'timing': '00:00–05:00', 'move': 'неизвестный', 'description': 'что-то'},
        ]
    }
    result = build_timeline_html(trajectory)
    assert '#888888' in result


# --- Item 2: build_html trajectory first ---

def _make_sample_data(with_trajectory=True):
    data = {
        'meta': {'badge': 'Курс', 'title': 'Тест', 'out': 'test.html'},
        'reconstruction': {
            'prose': '<p>Реконструкция.</p>',
            'table': []
        },
        'segments': [
            {
                'id': '01', 'type': 'concept', 'title': 'Введение',
                'timing': '00:00–10:00',
                'body': '<p>Текст сегмента.</p>',
                'right': '<div class="insights"></div>'
            }
        ],
        'prompts': {}
    }
    if with_trajectory:
        data['trajectory'] = {
            'prose': '<p>Траектория.</p>',
            'moves': [
                {'segment': '1', 'timing': '00:00–10:00', 'move': 'концепт', 'description': 'вводит идею'}
            ]
        }
    return data


def test_build_html_trajectory_first_slide():
    """when trajectory present, its title appears before reconstruction title"""
    html = build_html(_make_sample_data(with_trajectory=True))
    idx_traj = html.index('Траектория')
    idx_recon = html.index('Логическая реконструкция')
    assert idx_traj < idx_recon


def test_build_html_no_trajectory_no_crash():
    """widget builds fine without trajectory field"""
    html = build_html(_make_sample_data(with_trajectory=False))
    assert 'Логическая реконструкция' in html
