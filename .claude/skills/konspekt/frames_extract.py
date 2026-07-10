"""Извлечение кадров-кандидатов для opt-in ветки виджета /konspekt."""
import argparse
import json
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

class SegmentBoundsError(ValueError):
    """Мастер-MD не удовлетворяет контракту границ сегментов."""

_SEG_HEADER = re.compile(
    r'##\s+Сегмент\s+\d+\s*\|\s*([\d:]+)\s*[–-]\s*([\d:]+)\s*\|')

def _hms_to_sec(s):
    sec = 0
    for p in s.strip().split(':'):
        sec = sec * 60 + int(p)
    return float(sec)

def segment_bounds(master_md_text):
    bounds = []
    for i, m in enumerate(_SEG_HEADER.finditer(master_md_text), 1):
        bounds.append({'id': f'{i:02d}',
                       'start': _hms_to_sec(m.group(1)),
                       'end': _hms_to_sec(m.group(2))})
    if not bounds:
        raise SegmentBoundsError(
            'в мастер-MD не найден ни один заголовок '
            '"## Сегмент N | HH:MM:SS-HH:MM:SS | ..." — границы сегментов обязательны')
    for b in bounds:
        if not b['start'] < b['end']:
            raise SegmentBoundsError(
                f"сегмент {b['id']}: пустой/обратный диапазон {b['start']}–{b['end']}")
    for cur, nxt in zip(bounds, bounds[1:]):
        if nxt['start'] < cur['end']:
            raise SegmentBoundsError(
                f"сегменты {cur['id']} и {nxt['id']} пересекаются")
    return bounds

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
    """Deduplicate timecodes; cap=1 keeps the last frame as the final, most informative one."""
    kept = []
    for t in sorted(set(timecodes)):
        if not kept or t - kept[-1] >= min_gap:
            kept.append(t)
    if cap <= 0:
        return []
    if len(kept) <= cap:
        return kept
    if cap == 1:
        return [kept[-1]]
    if len(kept) > cap:
        last = len(kept) - 1
        step = last / (cap - 1)
        kept = [kept[round(i * step)] for i in range(cap)]
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

def codex_available():
    try:
        return subprocess.run(['codex', '--version'],
                              capture_output=True).returncode == 0
    except Exception:
        return False

def build_candidates(video, srt_text, work_dir, threshold=0.3, min_gap=3.0, cap=60):
    work = Path(work_dir); work.mkdir(parents=True, exist_ok=True)
    tcs = dedup_by_gap(scene_timecodes(video, threshold) + cue_timecodes(srt_text),
                       min_gap=min_gap, cap=cap)
    out = []
    success_idx = 0
    for idx, t in enumerate(tcs, 1):
        tmp = work / f'_tmp_{idx:04d}.png'
        try:
            extract_frame(video, t, tmp)
        except subprocess.CalledProcessError:
            # плохой таймкод (например, seek за конец видео) не рушит весь батч
            if tmp.exists():
                tmp.unlink()
            continue
        if tmp.exists():
            success_idx += 1
            f = work / f'cand_{success_idx:04d}.png'
            tmp.replace(f)
            out.append((f, t))
    return out

def main():
    parser = argparse.ArgumentParser(description='Извлечение кадров-кандидатов для виджета /konspekt.')
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--url', help='YouTube URL для скачивания видео')
    src.add_argument('--video', help='путь к локальному видеофайлу')
    parser.add_argument('--srt', required=True, help='путь к .srt транскрипту')
    parser.add_argument('--work-dir', required=True, help='рабочая папка для кадров и простыни')
    parser.add_argument('--threshold', type=float, default=0.3, help='порог scene-detect ffmpeg')
    parser.add_argument('--dry-run', action='store_true', help='остановиться после сборки простыни')
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    if args.url:
        video = download_video(args.url, work_dir)
    else:
        video = Path(args.video)

    srt_text = Path(args.srt).read_text(encoding='utf-8')
    cands = build_candidates(video, srt_text, work_dir, threshold=args.threshold)
    sheet_path = contact_sheet([f for f, _ in cands], work_dir / 'contact_sheet.png')
    manifest_path = work_dir / 'candidates.json'
    manifest_path.write_text(
        json.dumps([{'cand_id': _cand_num(f), 'timecode': t} for f, t in cands], ensure_ascii=False, indent=2),
        encoding='utf-8')

    print(f'Кандидатов найдено: {len(cands)}')
    print(f'Contact-sheet: {sheet_path}')
    print(f'Манифест: {manifest_path}')

    if args.dry_run:
        return

if __name__ == '__main__':
    main()
