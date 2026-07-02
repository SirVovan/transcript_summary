"""Спецификация cookies для yt-dlp (служебный профиль браузера).

Вынесено из youtube_to_srt.py: диагностика cookie-lock / cookie-error
остаётся там, здесь только построение --cookies-from-browser.
"""

import os
from pathlib import Path


APP_DATA_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "konspekt-youtube"
DEFAULT_BROWSER = "edge"


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


def cookies_from_browser_args(browser: str) -> list[str]:
    """Список аргументов yt-dlp для cookies из служебного профиля браузера.

    Возвращает [] при пустом/falsy browser.
    """
    if not browser:
        return []
    return ["--cookies-from-browser", _cookies_browser_spec(browser)]
