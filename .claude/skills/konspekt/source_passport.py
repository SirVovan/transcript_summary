"""Минимальный паспорт продукта /konspekt для контракта с /card (10.2).

Это НЕ «знание про базу знаний» — это дешёвая строчка-паспорт в шапке продукта.
/konspekt всё равно читает Clipping (поле source:), отсюда и берём.
"""
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qs


def _youtube_id(url: str) -> str | None:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host == "youtu.be":
        return parts.path.lstrip("/").split("/")[0] or None
    if host.endswith("youtube.com"):
        # parts.query без ведущего '?' — парсим через parse_qs, а не [?&]v=
        qs = parse_qs(parts.query)
        return qs["v"][0] if qs.get("v") else None
    return None


def passport_from_clipping(clipping_path: Path) -> dict:
    text = Path(clipping_path).read_text(encoding="utf-8")
    m = re.search(r'^source:\s*"?([^"\n]+)"?\s*$', text, re.MULTILINE)
    url = m.group(1).strip() if m else ""
    sid = _youtube_id(url) or url
    return {"source_id": sid, "source_url": url}


def passport_lines(source_id: str, source_url: str) -> str:
    return f"source_id: {source_id}\nsource_url: {source_url}"


if __name__ == "__main__":
    # CLI для master.md: `python source_passport.py <clipping.md>` -> печатает паспорт.
    import sys
    if len(sys.argv) != 2:
        print("usage: python source_passport.py <clipping.md>", file=sys.stderr)
        sys.exit(2)
    p = passport_from_clipping(Path(sys.argv[1]))
    print(passport_lines(p["source_id"], p["source_url"]))
