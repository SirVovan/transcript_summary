"""Извлечь ленту пользовательских реплик по каждой сессии K_T_P.

Первичный индекс для дообучения сегментации/заголовков: реплики короткие,
в них суть правок. Артефактный дифф ненадёжен (мастер пишется в файл через
инструмент, в текст чата не попадает), поэтому опора — на реплики.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

IN = Path(r"D:/Users/Вова/.claude/projects/D--Users------Desktop-Work-VibeCoding-K-T-P")
OUT = Path(r"D:/Users/Вова/Desktop/Work/VibeCoding/konspekt-project/.corpus-scratch/user_replies.md")

SKIP_PREFIXES = ("Base directory for this skill", "Caveat:")


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
                parts.append(b["text"])
        return "\n".join(parts)
    return ""


def is_tool_result(content) -> bool:
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
    return False


def norm(t: str, limit: int = 600) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


def process(path: Path):
    turns: list[str] = []
    cmd = None
    has_nav = False
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        msg = ev.get("message")
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role == "assistant":
            if re.search(r"^Сегмент\s*\d+\s*\|", text_of(content), re.M):
                has_nav = True
            continue
        if role != "user" or is_tool_result(content):
            continue
        txt = text_of(content)
        m = re.search(r"<command-args>(.*?)</command-args>", txt, re.S)
        if m and cmd is None:
            cmd = norm(m.group(1), 200)
        if txt.startswith(SKIP_PREFIXES):
            continue
        clean = re.sub(r"<command-(message|name)>.*?</command-\1>", "", txt, flags=re.S)
        clean = re.sub(r"<command-args>(.*?)</command-args>", r"\1", clean, flags=re.S)
        clean = re.sub(r"<system-reminder>.*?</system-reminder>", "", clean, flags=re.S)
        clean = norm(clean)
        if clean:
            turns.append(clean)
    date = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return path.name, date, cmd, has_nav, turns


def main() -> None:
    files = sorted(IN.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = ["# Ленты пользовательских реплик по сессиям", "",
           f"Сессий: {len(files)} (новые сверху). Источник: K_T_P transcripts.", ""]
    for path in files:
        name, date, cmd, has_nav, turns = process(path)
        out.append(f"## {name} — {date}")
        out.append(f"- Команда: {cmd or '(не зафиксирована)'}")
        out.append(f"- Навигац. карта в чате: {'да' if has_nav else 'нет'}")
        out.append(f"- Реплик пользователя: {len(turns)}")
        out.append("")
        for i, t in enumerate(turns, 1):
            out.append(f"{i}. {t}")
        out.append("")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"written {OUT}; sessions={len(files)}")


if __name__ == "__main__":
    main()
