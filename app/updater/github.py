"""بررسی Release جدید GitHub، دانلود و جایگزینی ایمن فایل ها."""
from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

from ..config import GITHUB_API, VERSION, app_dir, data_dir

VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass
class ReleaseInfo:
    version: str
    name: str
    notes: str
    url: str
    assets: list[dict]


def normalize_repo(repo: str) -> str:
    value = (repo or "").strip()
    value = re.sub(r"^https?://(www\.)?github\.com/", "", value, flags=re.I)
    return value.strip("/")


def version_tuple(version: str) -> tuple[int, int, int]:
    match = VERSION_RE.search(version or "")
    return tuple(int(x) for x in match.groups()) if match else (0, 0, 0)  # type: ignore[return-value]


def is_newer(candidate: str, current: str = VERSION) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def check_release(repo: str, timeout: int = 15) -> tuple[ReleaseInfo | None, str]:
    """آخرین Release را برمی گرداند. در صورت خطا، پیام خطا هم برگردانده می شود."""
    repo = normalize_repo(repo)
    if not repo or "/" not in repo:
        return None, "آدرس مخزن معتبر نیست. مثال: USER/REPO"
    try:
        response = requests.get(
            GITHUB_API.format(repo=repo),
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "PhonePricePro-Updater",
            },
            timeout=timeout,
        )
    except Exception as error:  # noqa: BLE001
        return None, f"خطای ارتباطی: {type(error).__name__}: {error}"
    if response.status_code == 404:
        return None, "مخزن پیدا نشد یا Release ای منتشر نشده است."
    if response.status_code != 200:
        return None, f"خطای GitHub: {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        return None, "پاسخ GitHub قابل خواندن نبود."

    tag = str(data.get("tag_name") or data.get("name") or "0.0.0")
    return (
        ReleaseInfo(
            version=tag.lstrip("vV"),
            name=str(data.get("name") or tag),
            notes=str(data.get("body") or "توضیحاتی ثبت نشده است."),
            url=str(data.get("html_url") or f"https://github.com/{repo}/releases"),
            assets=list(data.get("assets") or []),
        ),
        "",
    )


def pick_asset(release: ReleaseInfo, preference: str = "auto") -> dict | None:
    assets = release.assets
    if not assets:
        return None
    if preference == "zip":
        matches = [a for a in assets if str(a.get("name", "")).lower().endswith(".zip")]
        return matches[0] if matches else None
    if preference == "exe":
        matches = [a for a in assets if str(a.get("name", "")).lower().endswith(".exe")]
        return matches[0] if matches else None
    for suffix in (".zip", ".exe"):
        for asset in assets:
            if str(asset.get("name", "")).lower().endswith(suffix):
                return asset
    return assets[0]


def download_asset(
    asset: dict,
    progress: Callable[[int, int], None] | None = None,
    chunk_size: int = 128 * 1024,
) -> Path:
    url = str(asset.get("browser_download_url") or "")
    name = Path(str(asset.get("name") or "update.bin")).name
    folder = data_dir() / "downloads"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0)
        downloaded = 0
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                if progress:
                    progress(downloaded, total)
    return target


def _write_apply_bat(source: Path, destination: Path) -> Path:
    bat = data_dir() / "apply_update.bat"
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "ping 127.0.0.1 -n 3 >nul",
    ]
    if getattr(sys, "frozen", False):
        lines.append(f'taskkill /F /IM "{destination.name}" >nul 2>&1')
    lines.extend(
        [
            f'xcopy /E /Y /I /Q "{source}\\*" "{destination}\\" >nul',
            f'start "" "{destination / "PhonePricePro.exe"}"',
            f'del /F /Q "%~f0"',
        ]
    )
    bat.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return bat


def apply_downloaded(file: Path, settings: dict) -> str:
    """فایل دانلود شده را نصب یا جایگزین می کند و پیام وضعیت را برمی گرداند."""
    destination = app_dir()
    if file.suffix.lower() == ".exe":
        subprocess.Popen(
            [str(file)],
            shell=True,
            close_fds=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        return "نصب کننده اجرا شد. برنامه بسته می شود."

    if file.suffix.lower() == ".zip":
        folder = data_dir() / "pending_update"
        if folder.exists():
            import shutil

            shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(file) as archive:
            archive.extractall(folder)
        candidates = list(folder.rglob("PhonePricePro.exe"))
        source = candidates[0].parent if candidates else folder
        bat = _write_apply_bat(source, destination)
        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            close_fds=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        return "به روزرسانی در حال نصب است. برنامه بسته می شود."

    return "نوع فایل دانلود شده پشتیبانی نمی شود."


def install_browser() -> tuple[bool, str]:
    """اطمینان از وجود مرورگر مخفی؛ Edge/Chrome نصب شده ترجیح داده می شود."""
    installed = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    )
    if any(path.exists() for path in installed):
        return True, "Microsoft Edge / Chrome نصب شده است و توسط برنامه استفاده می شود."

    if getattr(sys, "frozen", False):
        import shutil

        python = shutil.which("py") or shutil.which("python")
        if not python:
            return False, "لطفاً Microsoft Edge یا Chrome را نصب کنید؛ برنامه از آنها به عنوان مرورگر مخفی استفاده می کند."
        command = [python, "-m", "playwright", "install", "chromium"]
    else:
        command = [sys.executable, "-m", "playwright", "install", "chromium"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=900,
        )
        if result.returncode == 0:
            return True, "مرورگر مخفی (Chromium) با موفقیت نصب شد."
        detail = result.stderr[-1000:] or result.stdout[-1000:]
        return False, (
            f"{detail}\nاگر دانلود در کشور شما مسدود است، کافی است Microsoft Edge یا Chrome را نصب کنید."
        )
    except Exception as error:  # noqa: BLE001
        return False, f"{type(error).__name__}: {error}"
