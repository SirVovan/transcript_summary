#!/usr/bin/env python3
"""
preprocessor.py — Предобработка транскрипта для скилла /konspekt.

Команды:
  python preprocessor.py info <файл>                                       # Статистика файла
  python preprocessor.py windows <файл>                                    # Окна для LLM-анализа границ
  python preprocessor.py split <файл> --at HH:MM:SS,...                    # Нарезка по таймингам (Фаза 1)
  python preprocessor.py slice <чанк> --from HH:MM:SS --to HH:MM:SS        # Отрезок чанка по границам сегмента (Фаза 2)
"""
import os
import re
import argparse

TOKENS_PER_CHAR = 0.25      # ~4 символа на токен для русского текста
CHUNK_DURATION_SEC = 3600   # 60 минут — целевой размер чанка (тайминг-режим)
CHUNK_SIZE_TOKENS = 12_000  # ~60 мин в токенах — фоллбэк без тайминга
WINDOW_SIZE = 2_500         # Окно для LLM-анализа границы (токенов с каждой стороны)
OVERLAP = 500               # Перекрытие между кусками (токенов)


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


def has_timestamps(lines: list) -> bool:
    """True если транскрипт содержит валидные временные метки."""
    return len(lines) >= 2 and lines[-1]['seconds'] > lines[0]['seconds']


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


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

    if has_timestamps(lines):
        duration_sec = lines[-1]['seconds'] - lines[0]['seconds']
        print(f"Длительность:     {format_duration(duration_sec)}")

        if duration_sec > CHUNK_DURATION_SEC:
            n = (duration_sec // CHUNK_DURATION_SEC) + 1
            print(f"\n⚠  Транскрипт большой ({format_duration(duration_sec)}). Рекомендуется разбить на ~{n} части.")
            print(f"   Запустите: python preprocessor.py windows \"{path}\"")
        else:
            print(f"\n✓  Помещается в один чанк (≤ 60 минут).")
    else:
        print(f"\n⚠  Тайминг в транскрипте не обнаружен — используется режим токенов.")
        if tokens > CHUNK_SIZE_TOKENS:
            n = (tokens // CHUNK_SIZE_TOKENS) + 1
            print(f"   Рекомендуется разбить на ~{n} части (~{CHUNK_SIZE_TOKENS:,} токенов каждая).")
            print(f"   Запустите: python preprocessor.py windows \"{path}\"")
        else:
            print(f"   Помещается в один чанк (≤ {CHUNK_SIZE_TOKENS:,} токенов).")


def windows(path: str) -> None:
    with open(path, encoding='utf-8') as f:
        text = f.read()
    lines = parse_transcript_lines(text)

    if has_timestamps(lines):
        start_sec = lines[0]['seconds']
        total_duration = lines[-1]['seconds'] - start_sec

        if total_duration <= CHUNK_DURATION_SEC:
            print("Нарезка не требуется — транскрипт ≤ 60 минут.")
            return

        n_boundaries = total_duration // CHUNK_DURATION_SEC
        boundary_indices = []
        for k in range(1, n_boundaries + 1):
            target_sec = start_sec + k * CHUNK_DURATION_SEC
            closest = min(range(len(lines)), key=lambda i: abs(lines[i]['seconds'] - target_sec))
            boundary_indices.append(closest)

        mode_label = "тайминг-режим"
    else:
        # Фоллбэк: накапливать токены до CHUNK_SIZE_TOKENS
        boundary_indices = []
        acc = 0
        prev_acc = 0
        for i, ln in enumerate(lines):
            acc += estimate_tokens(ln['text'])
            if acc - prev_acc >= CHUNK_SIZE_TOKENS:
                boundary_indices.append(i)
                prev_acc = acc

        mode_label = "токен-режим"

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

        center_label = lines[center]['time'] if has_timestamps(lines) else f"строка {center}"

        print(f"\n{'=' * 60}")
        print(f"ТОЧКА {b_num + 1} | около {center_label}  [{mode_label}]")
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


def slice_chunk(path: str, from_time: str, to_time: str) -> None:
    """Печатает в stdout строки чанка в диапазоне [from_time, to_time]."""
    with open(path, encoding='utf-8') as f:
        text = f.read()
    lines = parse_transcript_lines(text)
    from_sec = time_to_seconds(from_time)
    to_sec = time_to_seconds(to_time)
    for ln in lines:
        if from_sec <= ln['seconds'] <= to_sec:
            print(f"[{ln['time']}] {ln['text']}")


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

    p_slice = sub.add_parser('slice')
    p_slice.add_argument('chunk')
    p_slice.add_argument('--from', dest='from_time', required=True, help='Начало сегмента: HH:MM:SS')
    p_slice.add_argument('--to', dest='to_time', required=True, help='Конец сегмента: HH:MM:SS')

    args = ap.parse_args()
    if args.cmd == 'info':
        info(args.transcript)
    elif args.cmd == 'windows':
        windows(args.transcript)
    elif args.cmd == 'split':
        split(args.transcript, [t.strip() for t in args.at.split(',')])
    elif args.cmd == 'slice':
        slice_chunk(args.chunk, args.from_time, args.to_time)
    else:
        ap.print_help()
