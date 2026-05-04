#!/usr/bin/env python3
"""
preprocessor.py — Предобработка транскрипта для скилла /konspekt.

Команды:
  python preprocessor.py info <файл>                       # Статистика файла
  python preprocessor.py windows <файл>                    # Окна для LLM-анализа границ
  python preprocessor.py split <файл> --at HH:MM:SS,...   # Нарезка по таймингам
"""
import os
import re
import argparse

TOKENS_PER_CHAR = 0.25   # ~4 символа на токен для русского текста
CHUNK_SIZE = 16_000       # Целевой размер куска (токенов)
WINDOW_SIZE = 2_500       # Окно для LLM-анализа границы (токенов с каждой стороны)
OVERLAP = 500             # Перекрытие между кусками (токенов)
LARGE_THRESHOLD = 25_000  # Порог «большого» транскрипта


def estimate_tokens(text: str) -> int:
    return int(len(text) * TOKENS_PER_CHAR)


def time_to_seconds(t: str) -> int:
    parts = list(map(int, t.strip().split(':')))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def parse_transcript_lines(text: str) -> list:
    """Разбирает транскрипт в список dict: time, seconds, text."""
    result = []
    for raw in text.strip().split('\n'):
        m = re.match(r'\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s*(.*)', raw)
        if m:
            first, mm, s, body = m.groups()
            secs = (int(first) * 3600 + int(mm) * 60 + int(s)) if s else (int(first) * 60 + int(mm))
            time_str = f"{int(first):02d}:{int(mm):02d}" + (f":{int(s):02d}" if s else "")
            result.append({'time': time_str, 'seconds': secs, 'text': body.strip()})
        elif raw.strip() and result:
            result[-1]['text'] += ' ' + raw.strip()
    return result


def info(path: str) -> None:
    with open(path, encoding='utf-8') as f:
        text = f.read()
    tokens = estimate_tokens(text)
    lines = parse_transcript_lines(text)

    print(f"Файл:             {path}")
    print(f"Символов:         {len(text):,}")
    print(f"Токенов (оценка): {tokens:,}")
    print(f"Строк с тайм.:    {len(lines)}")
    if lines:
        print(f"Диапазон:         {lines[0]['time']} – {lines[-1]['time']}")

    if tokens > LARGE_THRESHOLD:
        n = (tokens // CHUNK_SIZE) + 1
        print(f"\n⚠  Транскрипт большой. Рекомендуется разбить на ~{n} части.")
        print(f"   Запустите: python preprocessor.py windows \"{path}\"")
    else:
        print(f"\n✓  Помещается в один проход (≤ {LARGE_THRESHOLD:,} токенов).")


def windows(path: str) -> None:
    with open(path, encoding='utf-8') as f:
        text = f.read()
    lines = parse_transcript_lines(text)

    boundary_indices = []
    acc = 0
    prev_acc = 0
    for i, ln in enumerate(lines):
        acc += estimate_tokens(ln['text'])
        if acc - prev_acc >= CHUNK_SIZE:
            boundary_indices.append(i)
            prev_acc = acc

    if not boundary_indices:
        print("Нарезка не требуется.")
        return

    for b_num, center in enumerate(boundary_indices):
        win_tok = 0
        start = center
        while start > 0 and win_tok < WINDOW_SIZE // 2:
            start -= 1
            win_tok += estimate_tokens(lines[start]['text'])

        win_tok = 0
        end = center
        while end < len(lines) - 1 and win_tok < WINDOW_SIZE // 2:
            end += 1
            win_tok += estimate_tokens(lines[end]['text'])

        window = '\n'.join(f"[{ln['time']}] {ln['text']}" for ln in lines[start:end + 1])

        print(f"\n{'=' * 60}")
        print(f"ТОЧКА {b_num + 1} | около {lines[center]['time']}")
        print('=' * 60)
        print(window)
        print(f"\n--- ЗАДАЧА ДЛЯ LLM ---")
        print("В этом фрагменте найди точку, где заканчивается смысловой блок.")
        print("Верни тайминг (HH:MM:SS) начала СЛЕДУЮЩЕГО блока.")
        print("Если не уверен — напиши явно: «Не уверен: [причина]»")


def split(path: str, boundary_times: list) -> list:
    with open(path, encoding='utf-8') as f:
        text = f.read()
    lines = parse_transcript_lines(text)
    boundaries = sorted(time_to_seconds(t) for t in boundary_times)

    groups = []
    current = []
    b_idx = 0

    for ln in lines:
        if b_idx < len(boundaries) and ln['seconds'] >= boundaries[b_idx]:
            groups.append(current)
            overlap, ov_tok = [], 0
            for prev in reversed(current):
                t = estimate_tokens(prev['text'])
                if ov_tok + t > OVERLAP:
                    break
                overlap.insert(0, prev)
                ov_tok += t
            current = list(overlap)
            b_idx += 1
        current.append(ln)
    groups.append(current)

    base = os.path.splitext(path)[0]
    out_paths = []
    for i, grp in enumerate(groups, 1):
        out = f"{base}_chunk{i:02d}.txt"
        with open(out, 'w', encoding='utf-8') as f:
            for ln in grp:
                f.write(f"[{ln['time']}] {ln['text']}\n")
        tok = sum(estimate_tokens(l['text']) for l in grp)
        print(f"Часть {i}: {out}  (~{tok:,} токенов, {len(grp)} строк)")
        out_paths.append(out)
    return out_paths


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Предобработка транскрипта')
    sub = ap.add_subparsers(dest='cmd')

    p_info = sub.add_parser('info')
    p_info.add_argument('transcript')

    p_win = sub.add_parser('windows')
    p_win.add_argument('transcript')

    p_split = sub.add_parser('split')
    p_split.add_argument('transcript')
    p_split.add_argument('--at', required=True, help='Тайминги через запятую: HH:MM:SS,HH:MM:SS')

    args = ap.parse_args()
    if args.cmd == 'info':
        info(args.transcript)
    elif args.cmd == 'windows':
        windows(args.transcript)
    elif args.cmd == 'split':
        split(args.transcript, [t.strip() for t in args.at.split(',')])
    else:
        ap.print_help()
