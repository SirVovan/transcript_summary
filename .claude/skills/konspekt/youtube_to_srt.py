"""Скачивание субтитров с YouTube и переразбивка SRT на 30-секундные блоки.
CLI: python youtube_to_srt.py <youtube_url> <output_dir> [--cookies-browser edge|chrome|firefox]

YouTube для большинства видео требует cookies авторизованного пользователя
(сообщение "Sign in to confirm you're not a bot"). Скрипт использует
служебный профиль выбранного браузера в %LOCALAPPDATA%/konspekt-youtube/<browser>-profile.
При первом запуске профиль пуст — скрипт сообщит, как открыть служебный профиль
и войти в YouTube.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


BLOCK_SECONDS = 30

APP_DATA_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "konspekt-youtube"
DEFAULT_COOKIES_BROWSER = "edge"
SUPPORTED_COOKIES_BROWSERS = ("edge", "chrome", "firefox")

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


def _service_profile_root(browser: str) -> Path:
    """Папка служебного профиля для выбранного браузера."""
    return APP_DATA_ROOT / f"{browser}-profile"


def _cookies_browser_spec(browser: str) -> str:
    """Спецификация --cookies-from-browser для yt-dlp.

    Для chromium-based браузеров (edge, chrome) указываем абсолютный путь до
    подпапки Default — это служебный профиль, который мы создаём отдельно от
    основного браузера пользователя. Для firefox yt-dlp хочет путь до
    профиля целиком, без Default.
    """
    profile_root = _service_profile_root(browser)
    profile_root.mkdir(parents=True, exist_ok=True)
    if browser in ("edge", "chrome"):
        default_dir = profile_root / "Default"
        default_dir.mkdir(parents=True, exist_ok=True)
        return f"{browser}:{default_dir}"
    return f"{browser}:{profile_root}"


def _find_browser_executable(browser: str) -> str | None:
    """Находит исполняемый файл браузера на Windows."""
    candidates_by_browser = {
        "edge": [
            os.environ.get("EDGE_PATH"),
            shutil.which("msedge"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "chrome": [
            os.environ.get("CHROME_PATH"),
            shutil.which("chrome"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "firefox": [
            os.environ.get("FIREFOX_PATH"),
            shutil.which("firefox"),
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
    }
    for candidate in candidates_by_browser.get(browser, []):
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def _open_service_profile_hint(browser: str) -> str:
    """Формирует подсказку: как открыть служебный профиль для входа в YouTube."""
    exe = _find_browser_executable(browser)
    profile_root = _service_profile_root(browser)
    if browser == "firefox":
        if exe:
            cmd = f'"{exe}" -profile "{profile_root}" -no-remote https://www.youtube.com/'
        else:
            cmd = f'firefox -profile "{profile_root}" -no-remote https://www.youtube.com/'
    else:
        if exe:
            cmd = f'"{exe}" --user-data-dir="{profile_root}" --profile-directory=Default https://www.youtube.com/'
        else:
            cmd = f'{browser} --user-data-dir="{profile_root}" --profile-directory=Default https://www.youtube.com/'
    return (
        f"Служебный профиль {browser} ещё пуст или не содержит cookies YouTube.\n"
        f"  1. Открой служебный профиль командой:\n"
        f"     {cmd}\n"
        f"  2. Войди в YouTube в открывшемся окне.\n"
        f"  3. Закрой это окно.\n"
        f"  4. Перезапусти эту команду."
    )


def _is_cookie_error(stderr: str) -> bool:
    """Определяет, требует ли ошибка yt-dlp обновления cookies."""
    s = (stderr or "").lower()
    return (
        "sign in to confirm" in s and "bot" in s
        or "could not find" in s and "cookies database" in s
        or "could not copy" in s and "cookie database" in s
    )


def _is_cookies_db_locked(stderr: str) -> bool:
    """Cookies-база заблокирована открытым основным браузером."""
    s = (stderr or "").lower()
    return "could not copy" in s and "cookie database" in s


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s]", "", title, flags=re.UNICODE).strip()
    slug = re.sub(r"\s+", "_", slug, flags=re.UNICODE)[:80].strip("_")
    return slug or "youtube_video"


def _get_video_title(url: str, cookies_browser: str) -> str:
    cmd = [
        "yt-dlp",
        "--get-title",
        "--no-warnings",
        "--cookies-from-browser",
        _cookies_browser_spec(cookies_browser),
        url,
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        if _is_cookies_db_locked(result.stderr):
            raise RuntimeError(
                f"Не удалось прочитать cookies из {cookies_browser}: "
                f"файл cookies заблокирован открытым браузером. "
                f"Закрой все окна {cookies_browser} и попробуй ещё раз."
            )
        if _is_cookie_error(result.stderr):
            raise RuntimeError(_open_service_profile_hint(cookies_browser))
        raise RuntimeError(f"yt-dlp failed to get video title: {result.stderr.strip()}")
    return result.stdout.strip()


def _try_yt_dlp_subs(url: str, tmp_template: str, sub_flag: str, cookies_browser: str):
    """Один запуск yt-dlp за субтитрами. Возвращает CompletedProcess."""
    cmd = [
        "yt-dlp",
        sub_flag,
        "--sub-langs",
        "orig",
        "--sub-format",
        "srt",
        "--skip-download",
        "--no-warnings",
        "--cookies-from-browser",
        _cookies_browser_spec(cookies_browser),
        "-o",
        tmp_template,
        url,
    ]
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def download_subtitles(url: str, output_dir: Path, cookies_browser: str = DEFAULT_COOKIES_BROWSER) -> Path:
    if cookies_browser not in SUPPORTED_COOKIES_BROWSERS:
        raise ValueError(
            f"cookies-browser должен быть одним из {SUPPORTED_COOKIES_BROWSERS}, получено: {cookies_browser}"
        )

    title = _get_video_title(url, cookies_browser)
    slug = _slugify(title)
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_template = str(output_dir / f"_tmp_{slug}.%(ext)s")

    for sub_flag in ("--write-subs", "--write-auto-subs"):
        result = _try_yt_dlp_subs(url, tmp_template, sub_flag, cookies_browser)
        if result.returncode != 0 and _is_cookie_error(result.stderr):
            print(
                f"ERROR: {_open_service_profile_hint(cookies_browser)}",
                file=sys.stderr,
            )
            sys.exit(3)
        tmp_files = sorted(output_dir.glob(f"_tmp_{slug}*.srt"))
        if tmp_files:
            break
    else:
        tmp_files = []

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


def _parse_args(argv: list[str]) -> tuple[str, Path, str]:
    """Парсит argv: <url> <output_dir> [--cookies-browser edge|chrome|firefox]."""
    cookies_browser = DEFAULT_COOKIES_BROWSER
    positional: list[str] = []
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--cookies-browser":
            if i + 1 >= len(argv):
                raise ValueError("--cookies-browser требует значение")
            cookies_browser = argv[i + 1]
            i += 2
            continue
        positional.append(arg)
        i += 1
    if len(positional) != 2:
        raise ValueError(
            "Usage: youtube_to_srt.py <youtube_url> <output_dir> "
            "[--cookies-browser edge|chrome|firefox]"
        )
    return positional[0], Path(positional[1]), cookies_browser


def main():
    try:
        url, output_dir, cookies_browser = _parse_args(sys.argv)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    try:
        final_path = download_subtitles(url, output_dir, cookies_browser=cookies_browser)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(3)
    print(str(final_path))


if __name__ == "__main__":
    main()
