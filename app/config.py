"""پیکربندی کلی، نسخه و مسیرهای ذخیره سازی برنامه."""
from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "قیمت یار"
APP_NAME_EN = "PhonePricePro"
AUTHOR = "محمد مهدی کاشی"
VERSION = "1.0.0"
GITHUB_REPO_DEFAULT = "MMK-81/PhonePricePro"
GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"

DEFAULT_SETTINGS = {
    "github_repo": GITHUB_REPO_DEFAULT,
    "request_timeout": 20,
    "delay_between_requests": 1.5,
    "use_browser_fallback": True,
    "browser_wait_ms": 2500,
    "appearance": "dark",
    "export_folder": "",
    "sites": {},
}


def app_dir() -> Path:
    """مسیر پوشه ای که برنامه از آن اجرا می شود (در حالت exe هم درست کار می کند)."""
    if getattr(__import__("sys"), "frozen", False):
        return Path(__import__("sys").executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    base = os.environ.get("APPDATA")
    path = Path(base) if base else Path.home() / ".phone_price_pro"
    path = path / APP_NAME_EN
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    path = settings_path()
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update(loaded)
        except (OSError, ValueError):
            pass
    return settings


def save_settings(settings: dict) -> None:
    settings_path().write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def desktop_path() -> Path:
    desktop = Path.home() / "Desktop"
    return desktop if desktop.exists() else Path.home()
