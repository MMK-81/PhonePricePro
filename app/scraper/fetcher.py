"""دریافت صفحات با HTTP سریع و پشتیبان مرورگر مخفی Playwright."""
from __future__ import annotations

from typing import Callable

import requests

from ..models import FetchResult

BLOCK_MARKERS = (
    "captcha",
    "robot check",
    "access denied",
    "too many requests",
    "just a moment",
    "verify you are human",
    "cloudflare",
    "ربات",
    "کپچا",
    "دسترسی محدود",
)

USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
)


class Fetcher:
    def __init__(self, settings: dict, log: Callable[[str, str], None] | None = None):
        self.settings = settings
        self.log = log or (lambda level, message: None)
        self.session = requests.Session()
        self._pw = None
        self._browser = None
        self._agent_index = 0

    def _headers(self) -> dict[str, str]:
        agent = USER_AGENTS[self._agent_index % len(USER_AGENTS)]
        self._agent_index += 1
        return {
            "User-Agent": agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        }

    @staticmethod
    def looks_blocked(html: str, status: int) -> bool:
        if status in (401, 403, 429, 503):
            return True
        if len(html) < 800:
            return True
        lowered = html[:40000].lower()
        return any(marker in lowered for marker in BLOCK_MARKERS)

    def fetch(self, url: str, force_browser: bool = False) -> FetchResult:
        if not force_browser:
            result = self._fetch_http(url)
            if not self.looks_blocked(result.html, result.status) and not result.error:
                return result
            self.log(
                "warn",
                f"درخواست سریع موفق نبود ({result.error or result.status}); تلاش با مرورگر مخفی...",
            )
        return self._fetch_browser(url)

    def _fetch_http(self, url: str) -> FetchResult:
        timeout = int(self.settings.get("request_timeout", 20) or 20)
        for attempt in range(2):
            try:
                response = self.session.get(
                    url,
                    headers=self._headers(),
                    timeout=timeout,
                    allow_redirects=True,
                )
                return FetchResult(
                    html=response.text,
                    status=response.status_code,
                    final_url=response.url,
                )
            except Exception as error:  # noqa: BLE001
                if attempt == 1:
                    return FetchResult(error=f"{type(error).__name__}: {error}")
        return FetchResult(error="درخواست ناموفق")

    def _ensure_browser(self):
        if self._browser is not None:
            return self._browser
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        last_error: Exception | None = None
        # Chromium دانلود شده توسط Playwright در برخی کشورها در دسترس نیست؛
        # بنابراین ابتدا از مرورگر نصب شده ویندوز (Edge/Chrome) استفاده می کنیم.
        for channel in ("msedge", "chrome", None):
            try:
                kwargs = {
                    "headless": True,
                    "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                }
                if channel:
                    kwargs["channel"] = channel
                self._browser = self._pw.chromium.launch(**kwargs)
                self.log("ok", f"مرورگر مخفی ({channel or 'Chromium'}) آماده شد.")
                return self._browser
            except Exception as error:  # noqa: BLE001
                last_error = error
        raise RuntimeError(f"هیچ مرورگری برای استخراج پیدا نشد: {last_error}")

    def _fetch_browser(self, url: str) -> FetchResult:
        try:
            browser = self._ensure_browser()
            context = browser.new_context(
                locale="fa-IR",
                user_agent=USER_AGENTS[0],
                viewport={"width": 1365, "height": 900},
            )
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            status = response.status if response else 0
            wait_ms = int(self.settings.get("browser_wait_ms", 2500) or 2500)
            page.wait_for_timeout(wait_ms)
            for _ in range(3):
                page.mouse.wheel(0, 2400)
                page.wait_for_timeout(400)
            html = page.content()
            final_url = page.url
            context.close()
            return FetchResult(html=html, status=status, used_browser=True, final_url=final_url)
        except Exception as error:  # noqa: BLE001
            message = str(error)
            if "Executable doesn't exist" in message or "playwright install" in message:
                message += " | لطفاً از تب تنظیمات، دکمه «نصب مرورگر مخفی» را بزنید."
            return FetchResult(error=f"{type(error).__name__}: {message}", used_browser=True)

    def close(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._pw = None
