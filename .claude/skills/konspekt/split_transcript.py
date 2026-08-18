#!/usr/bin/env python3
"""
split_transcript.py — нарезка длинного транскрипта на части по смысловым швам.

Гибрид: детерминированная часть (парсинг, расчёт целевых точек, нарезка) — здесь;
смысловая часть (выбор конкретного шва в окне) — агент /konspekt (см. master.md ШАГ 0.3).

Команды:
  python split_transcript.py info    <файл> [--target-min N]
      Формат, длительность, нужна ли резка (порог 100 мин), на сколько частей.

  python split_transcript.py windows <файл> [--target-min N]
      Для каждой из N-1 целевых точек печатает окно текста [target-10мин … target+10мин]
      с таймкодами + памятку правила выбора шва. Агент читает окна и возвращает тайминги.

  python split_transcript.py split   <файл> --at HH:MM:SS,HH:MM:SS,... [--base ИМЯ]
      Режет по переданным агентом таймингам, пишет <base>_ч1.txt … _чN.txt.

Поддерживаемые форматы входа:
  .srt                — блоки `N / HH:MM:SS,mmm --> ... / текст` (берётся start блока);
  [HH:MM:SS] / [MM:SS] — «Тайминг.»-txt;
  плоский txt без таймингов — только оценка в `info` (резать на источнике).
"""
import os
import re
import sys
import math
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TOKENS_PER_CHAR = 0.25       # ~4 символа на токен для русского текста
TARGET_MIN_DEFAULT = 90      # целевой размер части, минут
TOLERANCE_MIN = 10           # допуск на шов: не резать, если длительность ≤ target+допуск
WINDOW_AHEAD_SEC = 10 * 60   # окно поиска шва вперёд от целевой точки
WINDOW_BACK_SEC = 10 * 60    # сколько назад показать для fallback-выбора

SRT_TIME = re.compile(r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->')
BRACKET_TIME = re.compile(r'^\s*\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s*(.*)')


def estimate_tokens(text: str) -> int:
    return int(len(text) * TOKENS_PER_CHAR)


def time_to_seconds(t: str) -> int:
    parts = list(map(int, t.strip().split(':')))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def format_hms(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def detect_format(text: str) -> str:
    if '-->' in text:
        return 'srt'
    for raw in text.splitlines():
        if BRACKET_TIME.match(raw) and BRACKET_TIME.match(raw).group(1) is not None:
            # строка вида [MM:SS]/[HH:MM:SS] ...
            if raw.lstrip().startswith('['):
                return 'bracket'
    return 'flat'


def parse_srt(text: str) -> list:
    """SRT → список dict {seconds, time, text}: один пункт на блок, start-таймкод блока."""
    result = []
    cur_start = None
    cur_text = []
    for raw in text.splitlines():
        m = SRT_TIME.search(raw)
        if m:
            if cur_start is not None:
                result.append(_mk(cur_start, ' '.join(cur_text)))
            h, mm, s, _ms = m.groups()
            cur_start = int(h) * 3600 + int(mm) * 60 + int(s)
            cur_text = []
        elif raw.strip().isdigit() and not cur_text:
            continue  # номер блока
        elif raw.strip():
            cur_text.append(raw.strip())
    if cur_start is not None:
        result.append(_mk(cur_start, ' '.join(cur_text)))
    return result


def parse_bracket(text: str) -> list:
    """[HH:MM:SS]/[MM:SS]-txt → список dict {seconds, time, text}."""
    result = []
    for raw in text.splitlines():
        m = BRACKET_TIME.match(raw)
        if m and raw.lstrip().startswith('['):
            first, mm, s, body = m.groups()
            secs = (int(first) * 3600 + int(mm) * 60 + int(s)) if s else (int(first) * 60 + int(mm))
            result.append(_mk(secs, body.strip()))
        elif raw.strip() and result:
            result[-1]['text'] += ' ' + raw.strip()
    return result


def _mk(seconds: int, text: str) -> dict:
    return {'seconds': seconds, 'time': format_hms(seconds), 'text': text}


def load(path: str):
    """Возвращает (lines, fmt). lines пуст для flat-формата."""
    with open(path, encoding='utf-8') as f:
        text = f.read()
    fmt = detect_format(text)
    if fmt == 'srt':
        return parse_srt(text), fmt
    if fmt == 'bracket':
        return parse_bracket(text), fmt
    return [], 'flat'


def duration_sec(lines: list) -> int:
    return lines[-1]['seconds'] - lines[0]['seconds'] if len(lines) >= 2 else 0


def n_parts(total_sec: int, target_min: int) -> int:
    """Число равных частей. 1, если длительность ≤ target+допуск; иначе ceil(total/target)."""
    if total_sec <= 0 or total_sec <= (target_min + TOLERANCE_MIN) * 60:
        return 1
    return math.ceil(total_sec / (target_min * 60))


def target_points(lines: list, target_min: int) -> list:
    """Целевые секунды реза (N-1 точек на равных интервалах total/N)."""
    total = duration_sec(lines)
    n = n_parts(total, target_min)
    if n <= 1:
        return []
    start = lines[0]['seconds']
    step = total / n
    return [int(start + k * step) for k in range(1, n)]


# ---------------------------------------------------------------- info

def info(path: str, target_min: int) -> None:
    with open(path, encoding='utf-8') as f:
        text = f.read()
    lines, fmt = load(path)
    tokens = estimate_tokens(text)

    print(f"Файл:      {path}")
    print(f"Формат:    {fmt}")
    print(f"Символов:  {len(text):,}")
    print(f"Токенов:   ~{tokens:,}")

    if fmt == 'flat' or len(lines) < 2:
        print("\n⚠  Временных меток нет — точная резка по времени невозможна.")
        approx = max(1, round(tokens / (target_min * 60 * 2.5)))  # ~2.5 токена/сек речи
        print(f"   Грубо ~{approx} част(и) по объёму. Режьте на источнике (нужны таймкоды).")
        return

    total = duration_sec(lines)
    print(f"Длительность: {format_hms(total)}")

    n = n_parts(total, target_min)
    limit_min = target_min + TOLERANCE_MIN
    if n <= 1:
        print(f"\n✓  Резать не нужно (≤ {limit_min} мин) — обрабатывать одним проходом.")
        return

    pts = target_points(lines, target_min)
    print(f"\n⚠  Длиннее {limit_min} мин → резать на {n} част(и) по ~{format_hms(total // n)}.")
    print(f"   Целевые точки реза: {', '.join(format_hms(p) for p in pts)}")
    print(f"   Дальше: python split_transcript.py windows \"{path}\" --target-min {target_min}")


# ---------------------------------------------------------------- windows

def windows(path: str, target_min: int) -> None:
    lines, fmt = load(path)
    if len(lines) < 2:
        print("Нет временных меток — окна недоступны. Режьте на источнике.")
        return

    pts = target_points(lines, target_min)
    if not pts:
        print("Нарезка не требуется.")
        return

    print("ПРАВИЛО ВЫБОРА ШВА (для каждой точки):")
    print("  1. Сначала смотри ВПЕРЁД от целевой точки на ближайшие 5–10 мин.")
    print("     Если автор в этом окне закрывает тему и переходит к новой —")
    print("     режь на этом шве (ближайший к целевой точке).")
    print("  2. Если тема ещё активна (впереди шва нет) — двигайся СТРОГО НАЗАД,")
    print("     уменьшая фрагмент, до ближайшего предыдущего шва.")
    print("  3. НЕ резать посреди активной темы. Верни тайминг начала НОВОГО блока (HH:MM:SS).")
    print(f"\nНужно выбрать {len(pts)} шов(а). Затем:")
    print(f"  python split_transcript.py split \"{path}\" --at <шов1>,<шов2>,...")

    for i, target in enumerate(pts, 1):
        lo = target - WINDOW_BACK_SEC
        hi = target + WINDOW_AHEAD_SEC
        window = [ln for ln in lines if lo <= ln['seconds'] <= hi]

        print(f"\n{'=' * 64}")
        print(f"ОКНО {i}/{len(pts)} | целевая точка {format_hms(target)} "
              f"(допустимо вперёд до {format_hms(hi)}, иначе назад)")
        print('=' * 64)
        marked = False
        for ln in window:
            mark = ""
            if not marked and ln['seconds'] >= target:
                mark = "  <<< ЦЕЛЕВАЯ ТОЧКА"
                marked = True
            print(f"[{ln['time']}] {ln['text']}{mark}")


# ---------------------------------------------------------------- split

def split(path: str, at_times: list, base: str | None) -> None:
    lines, fmt = load(path)
    if len(lines) < 2:
        print("Нет временных меток — резать нечем. Режьте на источнике.")
        return

    boundaries = sorted(time_to_seconds(t) for t in at_times)
    groups, current, b = [], [], 0
    for ln in lines:
        if b < len(boundaries) and ln['seconds'] >= boundaries[b]:
            groups.append(current)
            current = []
            b += 1
        current.append(ln)
    groups.append(current)

    if base is None:
        base = os.path.splitext(path)[0]

    for i, grp in enumerate(groups, 1):
        out = f"{base}_ч{i}.txt"
        with open(out, 'w', encoding='utf-8') as f:
            for ln in grp:
                f.write(f"[{ln['time']}] {ln['text']}\n")
        if grp:
            span = f"{grp[0]['time']}–{grp[-1]['time']}"
        else:
            span = "пусто"
        tok = sum(estimate_tokens(l['text']) for l in grp)
        print(f"Часть {i}: {out}  ({span}, ~{tok:,} токенов, {len(grp)} реплик)")


# ---------------------------------------------------------------- cli

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Нарезка длинного транскрипта на части')
    sub = ap.add_subparsers(dest='cmd')

    p_info = sub.add_parser('info')
    p_info.add_argument('transcript')
    p_info.add_argument('--target-min', type=int, default=TARGET_MIN_DEFAULT)

    p_win = sub.add_parser('windows')
    p_win.add_argument('transcript')
    p_win.add_argument('--target-min', type=int, default=TARGET_MIN_DEFAULT)

    p_split = sub.add_parser('split')
    p_split.add_argument('transcript')
    p_split.add_argument('--at', required=True, help='Тайминги швов через запятую: HH:MM:SS,HH:MM:SS')
    p_split.add_argument('--base', default=None, help='Базовое имя для частей (по умолчанию — имя файла)')

    args = ap.parse_args()
    if args.cmd == 'info':
        info(args.transcript, args.target_min)
    elif args.cmd == 'windows':
        windows(args.transcript, args.target_min)
    elif args.cmd == 'split':
        split(args.transcript, [t.strip() for t in args.at.split(',')], args.base)
    else:
        ap.print_help()
