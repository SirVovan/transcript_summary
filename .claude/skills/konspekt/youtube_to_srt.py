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


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s]", "", title, flags=re.UNICODE).strip()
    slug = re.sub(r"\s+", "_", slug, flags=re.UNICODE)[:80].strip("_")
    return slug or "youtube_video"


def _get_video_title(url: str) -> str:
    result = subprocess.run(
        ["yt-dlp", "--get-title", "--no-warnings", url],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed to get video title: {result.stderr.strip()}")
    return result.stdout.strip()


def download_subtitles(url: str, output_dir: Path) -> Path:
    title = _get_video_title(url)
    slug = _slugify(title)
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_template = str(output_dir / f"_tmp_{slug}.%(ext)s")

    subprocess.run(
        [
            "yt-dlp",
            "--write-subs",
            "--sub-langs",
            "orig",
            "--sub-format",
            "srt",
            "--skip-download",
            "--no-warnings",
            "-o",
            tmp_template,
            url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    tmp_files = sorted(output_dir.glob(f"_tmp_{slug}*.srt"))

    if not tmp_files:
        subprocess.run(
            [
                "yt-dlp",
                "--write-auto-subs",
                "--sub-langs",
                "orig",
                "--sub-format",
                "srt",
                "--skip-download",
                "--no-warnings",
                "-o",
                tmp_template,
                url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        tmp_files = sorted(output_dir.glob(f"_tmp_{slug}*.srt"))

    if not tmp_files:
        print(
            "ERROR: У этого видео нет субтитров (ни ручных, ни авто).",
            file=sys.stderr,
        )
        sys.exit(2)

    tmp_srt = tmp_files[0]
    content = tmp_srt.read_text(encoding="utf-8")
    formatted = format_srt(rebucket(parse_srt(content)))

    base_name = f"SRC_transcript_{slug}"
    final_path = output_dir / f"{base_name}.srt"
    version = 2
    while final_path.exists():
        final_path = output_dir / f"{base_name}_v{version}.srt"
        version += 1

    final_path.write_text(formatted, encoding="utf-8")
    tmp_srt.unlink()
    return final_path


def main():
    if len(sys.argv) != 3:
        print("Usage: youtube_to_srt.py <youtube_url> <output_dir>", file=sys.stderr)
        sys.exit(1)

    url, output_dir = sys.argv[1], Path(sys.argv[2])
    final_path = download_subtitles(url, output_dir)
    print(str(final_path))


if __name__ == "__main__":
    main()
