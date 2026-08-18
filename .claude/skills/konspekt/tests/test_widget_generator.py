import pytest
import os
import sys
import base64
from pathlib import Path
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from widget_generator import build_reconstruction_html, build_html
import widget_generator
import md_parser


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


# --- Item 2: build_html без Траектории (выпилена 2026-08-18) ---

def _make_sample_data():
    return {
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


def test_build_html_reconstruction_first_slide():
    """реконструкция идёт первым слайдом"""
    html = build_html(_make_sample_data())
    assert 'Логическая реконструкция' in html
    assert html.index('Логическая реконструкция') < html.index('Введение')


# --- Item 3: Output filename logic (MASTER_ -> WIDGET_) ---

# ВНИМАНИЕ: _parse_segment (md_parser.py:319) требует РЕАЛЬНЫЙ формат:
# заголовок `## Сегмент N | HH:MM:SS-HH:MM:SS | Тема`, строки `**Тип:**`
# и `**Ключевая мысль:**`, порядок `### Карта` ПЕРЕД `### Текст`.
# Этот хелпер даёт валидную минимальную фикстуру — переиспользуется тестами ниже.
_SEG = (
    "## Сегмент 1 | 00:00:00-00:01:00 | Заголовок\n\n"
    "**Тип:** идея\n**Ключевая мысль:** мысль\n\n"
    "### Карта\n\n- **Термин:** пояснение\n\n"
    "### Текст\n\n{body}\n"
)
def _master(body="Проза."):
    return "# Название\n\n---\n\n" + _SEG.format(body=body)

def test_out_name_master_prefix(tmp_path):
    p = tmp_path / "MASTER_Урок 2.md"
    p.write_text(_master(), encoding="utf-8")
    assert md_parser.parse_master_md(str(p))['meta']['out'] == "WIDGET_Урок 2.html"

def test_out_name_frames_copy_suffix(tmp_path):
    # Производная копия ветки кадров -> суффикс сохраняется в имени виджета,
    # чтобы не перезаписывать обычный WIDGET_<Название>.html той же лекции.
    p = tmp_path / "MASTER_Урок 2_с_кадрами.md"
    p.write_text(_master(), encoding="utf-8")
    assert md_parser.parse_master_md(str(p))['meta']['out'] == "WIDGET_Урок 2_с_кадрами.html"

def test_out_name_legacy_suffix(tmp_path):
    # Легаси-курсы (OUT_*_мастер.md): сохраняем прежнее поведение — снимаем _мастер.
    p = tmp_path / "OUT_Урок 2_мастер.md"
    p.write_text(_master(), encoding="utf-8")
    assert md_parser.parse_master_md(str(p))['meta']['out'] == "Виджет — OUT_Урок 2.html"


# --- Item 3: _render_image ---

def _make_png(path, size=(40, 20), color=(10, 20, 30)):
    Image.new("RGB", size, color).save(path)


def test_encode_frame_webp(tmp_path):
    p = tmp_path / "cand_0001.png"
    Image.new("RGB", (100, 60), (120, 30, 30)).save(p)
    mime, b64 = md_parser._encode_frame_b64(p)
    assert mime == "image/webp"
    raw = base64.b64decode(b64)
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"


def test_render_image_embeds_base64(tmp_path):
    _make_png(tmp_path / "f.png")
    # alt с кавычкой, <, & — идёт в атрибут alt="...", кавычки обязаны экранироваться
    out = md_parser._render_image('Слайд "12" <b>&', 'f.png', tmp_path)
    assert out.startswith('<figure')
    assert 'data:image/webp;base64,' in out
    assert '<figcaption>' in out
    assert '&lt;b&gt;' in out and '&amp;' in out and '&quot;' in out
    assert '<b>' not in out


def test_render_image_missing_file(tmp_path):
    out = md_parser._render_image('Нет файла', 'missing.png', tmp_path)
    assert out == ''


def test_render_image_pil_import_failure_degrades(tmp_path, monkeypatch):
    # Отсутствие/поломка Pillow не должна валить всю сборку виджета - только эту картинку.
    monkeypatch.setitem(sys.modules, 'PIL', None)
    out = md_parser._render_image('Alt', 'whatever.png', tmp_path)
    assert out == ''


# --- Item 4: строка-картинка в _parse_text ---

def test_parse_text_image_line(tmp_path):
    _make_png(tmp_path / "cand_01.png")
    md = tmp_path / "MASTER_X.md"
    md.write_text(_master("Абзац до.\n\n![Слайд 12](cand_01.png)\n\nАбзац после."), encoding="utf-8")
    data = md_parser.parse_master_md(str(md))
    body = data['segments'][0]['body']
    assert '<figure' in body and 'data:image/' in body
    assert body.index('<p>Абзац до.</p>') < body.index('<figure')
    assert body.index('<figure') < body.index('<p>Абзац после.</p>')


def test_parse_text_malformed_image_raises(tmp_path):
    # Строка на "![" без закрывающей ")" не должна вешать парсер бесконечным циклом.
    md = tmp_path / "MASTER_X.md"
    md.write_text(_master("Абзац.\n\n![Слайд](cand_01.png\n\nАбзац после."), encoding="utf-8")
    with pytest.raises(md_parser.MasterMDParseError):
        md_parser.parse_master_md(str(md))


# --- Item 5: figure.frame CSS в собранном HTML ---

def test_build_html_with_frame(tmp_path):
    _make_png(tmp_path / "c.png")
    md = tmp_path / "MASTER_X.md"
    md.write_text(_master("![Слайд](c.png)"), encoding="utf-8")
    data = md_parser.parse_master_md(str(md))
    out_html = widget_generator.build_html(data)
    assert 'figure.frame' in out_html          # CSS присутствует
    assert 'data:image/webp;base64,' in out_html


# --- Task 4.4: control_weight / frame_weights / data-cand ---

from md_parser import frame_weights, _render_image
from PIL import Image

def _figure(cand, nbytes):
    # фейковая figure заданного «веса»: балласт в base64-поле + метка data-cand
    return (f'<figure class="frame" data-cand="{cand}">'
            f'<img src="data:image/jpeg;base64,{"A" * nbytes}"></figure>')

def test_control_weight_noop_under_limit():
    html = '<x>' + _figure(1, 10) + '</x>'
    sel = [{'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'}]
    out, lost = widget_generator.control_weight(html, {1: 10}, sel, limit_bytes=10_000)
    assert out == html and lost == []

def test_control_weight_drops_budget_figure_first():
    html = '<x>' + _figure(1, 100) + _figure(2, 100) + '</x>'
    weights = {1: 100, 2: 100}
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 2, 'segment_id': '01', 'confidence': 0.2, 'phase': 'budget'},
    ]
    limit = len(html.encode('utf-8')) - 100        # надо срезать ~один кадр
    out, lost = widget_generator.control_weight(html, weights, sel, limit_bytes=limit)
    assert 'data-cand="2"' not in out and 'data-cand="1"' in out
    assert lost == []                              # обязательный не тронут

def test_control_weight_degrades_mandatory_reports_segment():
    html = '<x>' + _figure(1, 100) + _figure(2, 100) + '</x>'
    weights = {1: 100, 2: 100}
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 2, 'segment_id': '02', 'confidence': 0.1, 'phase': 'mandatory'},
    ]
    limit = len(html.encode('utf-8')) - 100        # места только на один кадр
    out, lost = widget_generator.control_weight(html, weights, sel, limit_bytes=limit)
    assert 'data-cand="2"' not in out and 'data-cand="1"' in out
    assert lost == ['02']

def test_frame_weights_and_data_cand(tmp_path):
    Image.new('RGB', (120, 80), (10, 20, 30)).save(tmp_path / 'cand_07.png')
    Image.new('RGB', (120, 80), (90, 90, 90)).save(tmp_path / 'cand_12.png')
    md = "![Слайд 7](cand_07.png)\n\n![Схема 12](cand_12.png)\n"
    w = frame_weights(md, tmp_path)
    assert set(w) == {7, 12} and all(v > 0 for v in w.values())
    assert 'data-cand="7"' in _render_image('Слайд', 'cand_07.png', tmp_path)


# Task 4.2: trim_to_weight tests
def test_trim_to_weight_drops_budget_first():
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 2, 'segment_id': '01', 'confidence': 0.8, 'phase': 'budget'},
        {'cand_id': 3, 'segment_id': '01', 'confidence': 0.2, 'phase': 'budget'},
    ]
    size = {1: 4, 2: 4, 3: 4}
    kept, lost = widget_generator.trim_to_weight(sel, size, limit_bytes=8)
    assert {s['cand_id'] for s in kept} == {1, 2}    # выбит бюджетный с меньшим conf (3)
    assert lost == []                                # обязательный не тронут

def test_trim_to_weight_degrades_mandatory_last():
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 2, 'segment_id': '02', 'confidence': 0.1, 'phase': 'mandatory'},
    ]
    size = {1: 6, 2: 6}
    kept, lost = widget_generator.trim_to_weight(sel, size, limit_bytes=8)
    assert {s['cand_id'] for s in kept} == {1}       # оставлен более уверенный
    assert lost == ['02']

def test_trim_to_weight_noop_when_fits():
    sel = [{'cand_id': 1, 'segment_id': '01', 'confidence': 0.5, 'phase': 'mandatory'}]
    kept, lost = widget_generator.trim_to_weight(sel, {1: 3}, limit_bytes=8)
    assert kept == sel and lost == []

def test_trim_drops_marker_last():
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.2, 'phase': 'marker'},
        {'cand_id': 2, 'segment_id': '01', 'confidence': 0.9, 'phase': 'mandatory'},
        {'cand_id': 3, 'segment_id': '01', 'confidence': 0.9, 'phase': 'budget'},
    ]
    size = {1: 6, 2: 6, 3: 6}
    kept, lost = widget_generator.trim_to_weight(sel, size, limit_bytes=8)
    # выбиты budget(3) и mandatory(2); marker(1) выжил, хоть и conf ниже
    assert {s['cand_id'] for s in kept} == {1}
    assert lost == ['01']   # потерян mandatory сегмента 01

def test_trim_degrades_marker_only_when_forced():
    sel = [
        {'cand_id': 1, 'segment_id': '01', 'confidence': 0.1, 'phase': 'marker'},
        {'cand_id': 2, 'segment_id': '02', 'confidence': 0.9, 'phase': 'marker'},
    ]
    size = {1: 6, 2: 6}
    kept, lost = widget_generator.trim_to_weight(sel, size, limit_bytes=8)
    assert {s['cand_id'] for s in kept} == {2}   # оставлен более уверенный маркер
    assert lost == ['01']
