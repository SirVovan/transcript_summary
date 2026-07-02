"""Извлечение кадров-кандидатов для opt-in ветки виджета /konspekt."""
import re
import subprocess
from pathlib import Path

CUE_MARKERS = [
    'смотрите', 'на слайде', 'на экране', 'скопируйте',
    'вот промпт', 'вот код', 'покажу', 'видите',
]

def _srt_time_to_sec(t):
    h, m, rest = t.split(':')
    s, ms = rest.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def cue_timecodes(srt_text):
    out = []
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    for b in blocks:
        lines = b.splitlines()
        tc_line = next((l for l in lines if '-->' in l), None)
        if not tc_line:
            continue
        text = ' '.join(l for l in lines if '-->' not in l and not l.strip().isdigit()).lower()
        if any(mk in text for mk in CUE_MARKERS):
            start = tc_line.split('-->')[0].strip()
            out.append(_srt_time_to_sec(start))
    return sorted(set(out))
