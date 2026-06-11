"""Полные пользовательские реплики + заголовки-контекст для конкретных сессий
(поиск по нескольким project-папкам по префиксу id). Для разбора ПРИНЦИПОВ.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECTS = Path(r"D:/Users/Вова/.claude/projects")
FOLDERS = [
    "d--Users------Desktop-Work-VibeCoding-konspekt-project",
    "D--Users------Desktop-Work-VibeCoding-K-T-P",
    "D--Users------Desktop-Work-VibeCoding-konspekt-workflow",
]
OUT = Path(r"D:/Users/Вова/Desktop/Work/VibeCoding/konspekt-project/.corpus-scratch/principles_context.md")

HEADING_PATTERNS = [
    re.compile(r"^#{1,4}\s+\S"),
    re.compile(r"^Сегмент\s*\d+\s*\|"),
    re.compile(r"^(Блок|Этап|Глава|Часть|Сегмент)\s*\d+", re.I),
]
GENERIC = re.compile(r"замысел и маршрут|логическ|артефакт|главная мысль|самопровер", re.I)
NOISE = re.compile(r"^<task-notification>|^This session is being continued|^<local-command|<command-")


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


def norm(t: str, limit: int = 1400) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


def heading_lines(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s and any(p.match(line) or p.match(s) for p in HEADING_PATTERNS) and not GENERIC.search(s):
            out.append(s)
    return out


def find(prefix: str) -> Path | None:
    for folder in FOLDERS:
        for p in (PROJECTS / folder).glob(f"{prefix}*.jsonl"):
            return p
    return None


def process(path: Path) -> list[str]:
    lines = [f"## {path.name}", ""]
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
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role == "user":
            if is_tool_result(content):
                continue
            txt = text_of(content)
            if NOISE.search(txt.strip()) or txt.startswith("Base directory"):
                continue
            txt = norm(txt)
            if txt:
                lines.append(f"**[USER]** {txt}")
                lines.append("")
        elif role == "assistant":
            hs = heading_lines(text_of(content))
            if hs:
                lines.append("[ASSISTANT headings] " + " // ".join(hs[:12]))
                lines.append("")
    return lines


def main() -> None:
    out = ["# Принципиальные диалоги: полные реплики + заголовки", ""]
    for prefix in sys.argv[1:]:
        path = find(prefix)
        if path is None:
            out.append(f"## {prefix} — НЕ НАЙДЕН\n")
            continue
        out.extend(process(path))
        out.append("\n---\n")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
