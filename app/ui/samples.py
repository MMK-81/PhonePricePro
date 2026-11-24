"""لینک های نمونه گوشی Samsung Galaxy A07 4/64GB.

دیجی کالا و همراه تل: لینک محصول واقعی پیدا شده است.
تکنولایف: دامنه فعلی سایت teknolife.com است و لینک جستجو به عنوان نمونه قرار داده شده؛
در صورت تغییر سایت می توانید لینک محصول دقیق را از داخل برنامه جایگزین کنید.
"""
from __future__ import annotations

from ..models import ScrapeJob

SAMPLE_JOBS: list[ScrapeJob] = [
    ScrapeJob(
        url="https://www.digikala.com/product/dkp-20109389/",
        model="A07 64/4",
    ),
    # تکنولایف پشت Cloudflare است؛ لینک جستجو به عنوان نمونه قرار دارد.
    ScrapeJob(
        url="https://teknolife.com/?s=A07",
        model="A07 64/4",
    ),
    ScrapeJob(
        url=(
            "https://hamrahtel.com/products/"
            "galaxy-a07-64gb-ram-4gb-black-mobile-phone-bundle-with-25w-wall-charger-"
            "samsung-ep-t2510-two-pin-with-18-months-corporate-warranty-black"
        ),
        model="A07 64/4",
    ),
]
