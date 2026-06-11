"""Найти диалог про ПРИНЦИПЫ заголовков: ранжируем сессии по объёму
пользовательских реплик, где обсуждаются заголовки/принципы/границы.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

PROJECTS = Path(r"D:/Users/Вова/.claude/projects")
FOLDERS = [
    "d--Users------Desktop-Work-VibeCoding-konspekt-project",
    "D--Users------Desktop-Work-VibeCoding-K-T-P",
    "D--Users------Desktop-Work-VibeCoding-konspekt-workflow",
]
KEY = re.compile(r"загол|принцип|назывн|глагол|формулиров|границ сегмент|сегментац", re.I)


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b["text"] for b in content
            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)
        )
    return ""


def is_tool_result(content) -> bool:
    return isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    )


def norm(t: str, limit: int = 280) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


def score(path: Path):
    total = 0
    samples = []
    for raw in path.open(encoding="utf-8"):
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        msg = ev.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if is_tool_result(content):
            continue
        txt = text_of(content)
        if txt.startswith("Base directory") or "<command-" in txt or "<local-command" in txt:
            continue
        if KEY.search(txt):
            total += len(txt)
            samples.append(norm(txt))
    return total, samples


def main() -> None:
    rows = []
    for folder in FOLDERS:
        d = PROJECTS / folder
        if not d.exists():
            continue
        for path in d.glob("*.jsonl"):
            total, samples = score(path)
            if total == 0:
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            rows.append((total, mtime, folder.split("VibeCoding-")[-1], path.name, samples))
    rows.sort(reverse=True, key=lambda r: r[0])
    for total, mtime, folder, name, samples in rows[:12]:
        print(f"\n=== {total} chars | {mtime:%Y-%m-%d} | {folder} | {name} ===")
        for s in samples[:6]:
            print(f"  - {s}")


if __name__ == "__main__":
    main()
