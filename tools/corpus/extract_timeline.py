"""Таймлайн правок по конкретным сессиям: чередование реплик пользователя и
строк-заголовков из ответов ассистента (тела сегментов отбрасываются).

Цель — увидеть пары «было -> стало» в контексте конкретной правки.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

IN = Path(r"D:/Users/Вова/.claude/projects/D--Users------Desktop-Work-VibeCoding-K-T-P")
OUT = Path(r"D:/Users/Вова/Desktop/Work/VibeCoding/konspekt-project/.corpus-scratch/timelines.md")

# Строки, похожие на заголовок сегмента (а не тело)
HEADING_PATTERNS = [
    re.compile(r"^#{1,4}\s+\S"),                         # markdown ## / ###
    re.compile(r"^Сегмент\s*\d+\s*\|"),                  # навигационная карта
    re.compile(r"^(Блок|Этап|Глава|Часть|Сегмент)\s*\d+", re.I),
    re.compile(r"^\s*\d+\.\s+\*\*"),                     # нумерованный список с жирным
    re.compile(r"^[-*]\s+\*\*[^*]+\*\*\s*[:—-]"),        # буллет «**Заголовок:** ...»
]
GENERIC = re.compile(r"замысел и маршрут|логическ|артефакт|главная мысль|шаг \d|самопровер", re.I)


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


def heading_lines(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(p.match(line) or p.match(s) for p in HEADING_PATTERNS):
            out.append(s)
    return out


def norm(t: str, limit: int = 500) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


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
            txt = re.sub(r"<command-(message|name)>.*?</command-\1>", "", txt, flags=re.S)
            txt = re.sub(r"<command-args>(.*?)</command-args>", r"\1", txt, flags=re.S)
            txt = re.sub(r"<[^>]+>.*?</[^>]+>", "", txt, flags=re.S)
            txt = norm(txt)
            if txt and not txt.startswith("Base directory"):
                lines.append(f"**[USER]** {txt}")
                lines.append("")
        elif role == "assistant":
            hs = heading_lines(text_of(content))
            hs = [h for h in hs if not GENERIC.search(h)]
            if hs:
                lines.append("[ASSISTANT headings]")
                lines.extend(f"  {h}" for h in hs)
                lines.append("")
    return lines


def main() -> None:
    targets = sys.argv[1:]
    files = []
    for t in targets:
        matches = list(IN.glob(f"{t}*.jsonl"))
        files.extend(matches)
    out = ["# Таймлайны правок (заголовки + реплики)", ""]
    for path in files:
        out.extend(process(path))
        out.append("\n---\n")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"written {OUT}; files={len(files)}")


if __name__ == "__main__":
    main()
