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

def parse_showinfo_pts(stderr):
    return [float(m) for m in re.findall(r'pts_time:([0-9.]+)', stderr)]

def dedup_by_gap(timecodes, min_gap=3.0, cap=60):
    kept = []
    for t in sorted(set(timecodes)):
        if not kept or t - kept[-1] >= min_gap:
            kept.append(t)
    if len(kept) > cap:
        step = len(kept) / cap
        kept = [kept[int(i * step)] for i in range(cap)]
    return kept

def download_video(url, out_dir, browser=None):
    from cookies_spec import cookies_from_browser_args, DEFAULT_BROWSER
    if browser is None:
        browser = DEFAULT_BROWSER
    out = Path(out_dir) / 'video.%(ext)s'
    cmd = ['yt-dlp', '-f', 'bv[height<=720]/best[height<=720]',
           '-o', str(out), *cookies_from_browser_args(browser), url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'yt-dlp упал: {r.stderr.strip()[:300]}')
    vids = sorted(Path(out_dir).glob('video.*'))
    if not vids:
        raise RuntimeError('yt-dlp: видео не скачано')
    return vids[0]

def scene_timecodes(video, threshold=0.3):
    cmd = ['ffmpeg', '-i', str(video), '-vf',
           f"select='gt(scene,{threshold})',showinfo", '-f', 'null', '-']
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'ffmpeg scene-detect упал: {r.stderr.strip()[:300]}')
    return parse_showinfo_pts(r.stderr)

def extract_frame(video, t, out, shift=0.7):
    # -ss ПЕРЕД -i = быстрый seek; shift выводит на устоявшийся кадр после перехода.
    cmd = ['ffmpeg', '-y', '-ss', str(max(0.0, t + shift)), '-i', str(video),
           '-frames:v', '1', '-q:v', '2', str(out)]
    subprocess.run(cmd, check=True, capture_output=True)

def _cand_num(path):
    m = re.search(r'(\d+)', Path(path).stem)
    return int(m.group(1)) if m else 0

def contact_sheet(frames, out, cols=5, thumb_w=320):
    """Пронумерованная простыня из списка кадров (PIL). Номер = _cand_num(файла)."""
    from PIL import Image, ImageDraw
    if not frames:
        raise RuntimeError('contact_sheet: нет кадров')
    thumbs = []
    for f in frames:
        im = Image.open(f).convert('RGB')
        h = round(im.height * thumb_w / im.width)
        im = im.resize((thumb_w, h))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 46, 22], fill=(0, 0, 0))
        d.text((5, 4), str(_cand_num(f)), fill=(255, 230, 0))
        thumbs.append(im)
    cell_h = max(t.height for t in thumbs)
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * thumb_w, rows * cell_h), (28, 28, 32))
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(t, (c * thumb_w, r * cell_h))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return Path(out)
