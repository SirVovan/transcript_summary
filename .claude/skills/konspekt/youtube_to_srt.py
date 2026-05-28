"""Скачивание субтитров с YouTube и переразбивка SRT на 30-секундные блоки.
CLI: python youtube_to_srt.py <youtube_url> <output_dir>
"""

import re
import subprocess
import sys
from pathlib import Path


BLOCK_SECONDS = 30

TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s+-->\s+"
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def _ts_to_ms(h, m, s, ms) -> int:
    return (
        int(h) * 60 * 60 * 1000
        + int(m) * 60 * 1000
        + int(s) * 1000
        + int(ms)
    )


def _ms_to_ts(ms) -> str:
    ms = int(ms)
    hours, remainder = divmod(ms, 60 * 60 * 1000)
    minutes, remainder = divmod(remainder, 60 * 1000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_srt(content: str) -> list[dict]:
    segments = []

    for block in re.split(r"\n\s*\n", content.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        index = 0
        timestamp_line_index = 0
        if lines[0].isdigit():
            index = int(lines[0])
            timestamp_line_index = 1

        if timestamp_line_index >= len(lines):
            continue

        match = TIMESTAMP_RE.match(lines[timestamp_line_index])
        if not match:
            continue

        groups = match.groups()
        text = " ".join(lines[timestamp_line_index + 1 :]).strip()
        if not text:
            continue

        segments.append(
            {
                "index": index,
                "start_ms": _ts_to_ms(*groups[:4]),
                "end_ms": _ts_to_ms(*groups[4:]),
                "text": text,
            }
        )

    return segments


def format_srt(segments: list[dict]) -> str:
    blocks = []
    for i, segment in enumerate(segments, start=1):
        blocks.append(
            f"{i}\n"
            f"{_ms_to_ts(segment['start_ms'])} --> {_ms_to_ts(segment['end_ms'])}\n"
            f"{segment['text']}\n"
        )
    return "\n".join(blocks)


def rebucket(segments: list[dict], block_seconds: int = BLOCK_SECONDS) -> list[dict]:
    if not segments:
        return []

    block_ms = block_seconds * 1000
    buckets = []
    current_bucket = None

    for segment in segments:
        block_start_ms = (segment["start_ms"] // block_ms) * block_ms
        is_long_segment = segment["end_ms"] - segment["start_ms"] > block_ms

        if is_long_segment:
            if current_bucket is not None:
                buckets.append(current_bucket)
                current_bucket = None
            buckets.append(
                {
                    "index": 0,
                    "start_ms": block_start_ms,
                    "end_ms": segment["end_ms"],
                    "text": segment["text"],
                }
            )
            continue

        if current_bucket and current_bucket["start_ms"] == block_start_ms:
            current_bucket["text"] = f"{current_bucket['text']} {segment['text']}"
            current_bucket["end_ms"] = segment["end_ms"]
        else:
            if current_bucket is not None:
                buckets.append(current_bucket)
            current_bucket = {
                "index": 0,
                "start_ms": block_start_ms,
                "end_ms": segment["end_ms"],
                "text": segment["text"],
            }

    if current_bucket is not None:
        buckets.append(current_bucket)

    for index, bucket in enumerate(buckets, start=1):
        bucket["index"] = index

    return buckets
