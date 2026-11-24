"""هماهنگی کار استخراج در یک thread جداگانه."""
from __future__ import annotations

import threading
import time
from typing import Callable

from ..extractors.parse import parse_page
from ..models import FetchResult, PriceRow, ScrapeJob, SiteProfile
from ..sites.profiles import detect_profile
from .fetcher import Fetcher

Callbacks = dict[str, Callable]


class ScrapeEngine:
    def __init__(
        self,
        jobs: list[ScrapeJob],
        settings: dict,
        profiles: dict[str, SiteProfile],
        callbacks: Callbacks,
    ):
        self.jobs = jobs
        self.settings = settings
        self.profiles = profiles
        self.callbacks = callbacks
        self.stop_event = threading.Event()

    def _log(self, level: str, message: str) -> None:
        callback = self.callbacks.get("on_log")
        if callback:
            callback(level, message)

    def stop(self) -> None:
        self.stop_event.set()
        self._log("warn", "درخواست توقف داده شد؛ بعد از اتمام لینک جاری متوقف می شود.")

    def _handle_job(self, job: ScrapeJob, fetcher: Fetcher) -> list[PriceRow]:
        profile = detect_profile(job.url, self.profiles)
        if job.profile_key != "auto" and job.profile_key in self.profiles:
            profile = self.profiles[job.profile_key]
        self._log("info", f"[{profile.name}] شروع: {job.url}")

        result: FetchResult = fetcher.fetch(job.url)
        parsed = parse_page(result.html, profile)

        if (
            not parsed.variants
            and self.settings.get("use_browser_fallback", True)
            and not result.used_browser
        ):
            self._log("warn", "قیمتی از درخواست سریع بدست نیامد؛ تلاش با مرورگر مخفی...")
            result = fetcher.fetch(job.url, force_browser=True)
            parsed = parse_page(result.html, profile)

        # همراه تل اطلاعات محصول را در یک API داخلی قرار می دهد؛ حتی اگر صفحه مسدود شود
        # می توان قیمت را از آن API گرفت.
        if profile.key == "hamrahtel" and not parsed.variants:
            from ..sites.hamrahtel import fetch_variants

            title, variants = fetch_variants(job.url, int(self.settings.get("request_timeout", 20)))
            if variants:
                if title and not parsed.title:
                    parsed.title = title
                parsed.variants = variants
                result.error = ""
                self._log("ok", f"[{profile.name}] قیمت از API داخلی سایت بدست آمد.")

        if result.error:
            self._log("error", f"[{profile.name}] {result.error}")
            return [
                PriceRow(
                    site=profile.name,
                    model=job.model,
                    color="",
                    price=None,
                    url=job.url,
                    title=parsed.title,
                    status="خطا",
                    note=result.error,
                )
            ]

        if not parsed.variants:
            self._log("warn", f"[{profile.name}] قیمت یا رنگی در صفحه پیدا نشد.")
            lowered = result.html[:40000].lower()
            blocked = result.status in (401, 403, 429, 503) or any(
                marker in lowered for marker in ("cloudflare", "just a moment", "کپچا", "ربات")
            )
            note = (
                "سایت درخواست را مسدود کرد (Cloudflare/کپچا). لینک محصول را در مرورگر باز کنید "
                "و یا انتخابگرها را در تنظیمات سایت ها بررسی کنید."
                if blocked
                else "انتخابگرها را در تنظیمات سایت ها بررسی کنید."
            )
            return [
                PriceRow(
                    site=profile.name,
                    model=job.model,
                    color="",
                    price=None,
                    url=job.url,
                    title=parsed.title,
                    status="بدون نتیجه",
                    note=note,
                )
            ]

        rows = [
            PriceRow(
                site=profile.name,
                model=job.model,
                color=color,
                price=price,
                url=job.url,
                title=parsed.title,
            )
            for color, price in parsed.variants
        ]
        self._log(
            "ok",
            f"[{profile.name}] {len(rows)} ردیف قیمت پیدا شد "
            f"({'مرورگر مخفی' if result.used_browser else 'HTTP سریع'}).",
        )
        return rows

    def run(self) -> None:
        all_rows: list[PriceRow] = []
        fetcher = Fetcher(self.settings, lambda level, message: self._log(level, message))
        total = len(self.jobs)
        try:
            for index, job in enumerate(self.jobs, start=1):
                if self.stop_event.is_set():
                    break
                try:
                    rows = self._handle_job(job, fetcher)
                except Exception as error:  # noqa: BLE001
                    self._log("error", f"خطای غیرمنتظره: {type(error).__name__}: {error}")
                    rows = [
                        PriceRow(
                            site="—",
                            model=job.model,
                            color="",
                            price=None,
                            url=job.url,
                            status="خطا",
                            note=str(error),
                        )
                    ]
                all_rows.extend(rows)
                for row in rows:
                    callback = self.callbacks.get("on_row")
                    if callback:
                        callback(row)
                progress = self.callbacks.get("on_progress")
                if progress:
                    progress(index, total, job)
                delay = float(self.settings.get("delay_between_requests", 1.5) or 0)
                if delay > 0 and index < total:
                    self.stop_event.wait(delay)
        finally:
            fetcher.close()
            done = self.callbacks.get("on_done")
            if done:
                done(all_rows)
