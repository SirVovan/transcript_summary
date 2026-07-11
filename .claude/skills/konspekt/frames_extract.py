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

def assign_segment(timecode, bounds):
    first, last = bounds[0], bounds[-1]
    if timecode < first['start']:
        return first['id']
    if timecode >= last['end']:
        return last['id']
    for b in bounds:
        if b['start'] <= timecode < b['end']:
            return b['id']
    # в щели между сегментами — сегмент с ближайшей границей
    return min(bounds,
               key=lambda b: min(abs(timecode - b['start']),
                                 abs(timecode - b['end'])))['id']

def average_hash(img):
    from PIL import Image
    im = img if isinstance(img, Image.Image) else Image.open(img)
    im = im.convert('L').resize((8, 8))
    px = list(im.getdata())
    avg = sum(px) / len(px)
    bits = 0
    for p in px:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return bits

def hamming(a, b):
    return bin(a ^ b).count('1')

def phash_dedup(frames, threshold=6, window=3):
    kept = []
    kept_hashes = []
    for item in frames:
        h = average_hash(item[0])
        if any(hamming(h, kh) <= threshold for kh in kept_hashes[-window:]):
            continue
        kept.append(item)
        kept_hashes.append(h)
    return kept

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

def bucket_timecodes(scene_tcs, cue_tcs, bounds,
                     min_gap=3.0, per_segment_cap=10, global_cap=150):
    buckets = {b['id']: [] for b in bounds}
    for t in sorted(set(scene_tcs) | set(cue_tcs)):
        buckets[assign_segment(t, bounds)].append(t)
    cap = per_segment_cap
    while True:
        result = []
        for sid, tcs in buckets.items():
            for t in dedup_by_gap(tcs, min_gap=min_gap, cap=cap):
                result.append((t, sid))
        if len(result) <= global_cap or cap <= 1:
            break
        cap -= 1
    result.sort()
    return result, cap

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

def build_candidates(video, srt_text, master_md_text, work_dir,
                     threshold=0.2, min_gap=3.0, per_segment_cap=10,
                     global_cap=150, phash_threshold=6):
    work = Path(work_dir); work.mkdir(parents=True, exist_ok=True)
    bounds = segment_bounds(master_md_text)
    tagged, final_cap = bucket_timecodes(
        scene_timecodes(video, threshold), cue_timecodes(srt_text), bounds,
        min_gap=min_gap, per_segment_cap=per_segment_cap, global_cap=global_cap)
    raw = []
    success_idx = 0
    for tc, sid in tagged:
        tmp = work / f'_tmp_{success_idx + 1:04d}.png'
        try:
            extract_frame(video, tc, tmp)
        except subprocess.CalledProcessError:
            if tmp.exists():
                tmp.unlink()
            continue
        if tmp.exists():
            success_idx += 1
            f = work / f'cand_{success_idx:04d}.png'
            tmp.replace(f)
            raw.append((f, tc, sid))
    return phash_dedup(raw, threshold=phash_threshold), final_cap

def adaptive_cap(n_segments):
    return max(12, n_segments + 10)

def select_frames(triage, candidates, cap):
    seg_by_cand = {c['cand_id']: c['segment_id'] for c in candidates}
    scored = [
        {'cand_id': tr['cand_id'], 'segment_id': seg_by_cand[tr['cand_id']],
         'type': tr['type'], 'confidence': tr['confidence']}
        for tr in triage
        if tr['type'] != 'drop' and tr['cand_id'] in seg_by_cand
    ]
    # Обязательная фаза: лучший non-drop на каждый сегмент
    best = {}
    for s in scored:
        sid = s['segment_id']
        if sid not in best or s['confidence'] > best[sid]['confidence']:
            best[sid] = s
    selected = [dict(s, phase='mandatory') for s in best.values()]
    chosen = {s['cand_id'] for s in selected}
    # Фаза бюджета: остаток по убыванию confidence по всему виджету
    budget = cap - len(selected)
    rest = sorted((s for s in scored if s['cand_id'] not in chosen),
                  key=lambda s: s['confidence'], reverse=True)
    selected.extend(dict(s, phase='budget') for s in rest[:max(0, budget)])
    return selected

def trim_to_weight(selection, size_by_cand, limit_bytes):
    kept = list(selection)

    def total():
        return sum(size_by_cand.get(s['cand_id'], 0) for s in kept)

    for s in sorted((s for s in kept if s['phase'] == 'budget'),
                    key=lambda s: s['confidence']):
        if total() <= limit_bytes:
            break
        kept.remove(s)
    lost = []
    if total() > limit_bytes:
        for s in sorted((s for s in kept if s['phase'] == 'mandatory'),
                        key=lambda s: s['confidence']):
            if total() <= limit_bytes:
                break
            kept.remove(s)
            lost.append(s['segment_id'])
    return kept, lost

def _cmd_extract(args):
    work_dir = Path(args.work_dir)
    video = download_video(args.url, work_dir) if args.url else Path(args.video)
    srt_text = Path(args.srt).read_text(encoding='utf-8')
    master_md_text = Path(args.master_md).read_text(encoding='utf-8')
    cands, final_cap = build_candidates(video, srt_text, master_md_text, work_dir,
                                        threshold=args.threshold)
    sheet_path = contact_sheet([f for f, _, _ in cands], work_dir / 'contact_sheet.png')
    manifest_path = work_dir / 'candidates.json'
    manifest_path.write_text(
        json.dumps([{'cand_id': _cand_num(f), 'timecode': t, 'segment_id': sid}
                    for f, t, sid in cands], ensure_ascii=False, indent=2),
        encoding='utf-8')
    print(f'Кандидатов найдено: {len(cands)} (cap на бакет: {final_cap})')
    print(f'Contact-sheet: {sheet_path}')
    print(f'Манифест: {manifest_path}')

def main():
    parser = argparse.ArgumentParser(description='Кадры-кандидаты для виджета /konspekt.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    ex = sub.add_parser('extract', help='кандидаты + contact-sheet + candidates.json')
    src = ex.add_mutually_exclusive_group(required=True)
    src.add_argument('--url', help='YouTube URL')
    src.add_argument('--video', help='путь к локальному видео')
    ex.add_argument('--srt', required=True, help='путь к .srt транскрипту')
    ex.add_argument('--master-md', required=True, help='путь к мастер-MD (границы сегментов)')
    ex.add_argument('--work-dir', required=True, help='папка для кадров и простыни')
    ex.add_argument('--threshold', type=float, default=0.2, help='порог scene-detect')
    ex.set_defaults(func=_cmd_extract)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
