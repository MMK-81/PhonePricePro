"""پروفایل های داخلی سایت ها.

انتخابگرها به عنوان پشتیبان در نظر گرفته شده اند؛ استخراج اصلی از طریق
JSON-LD، __NEXT_DATA__ و الگوهای متنی انجام می شود. کاربر می تواند chooses
انتخابگرها را از تب «تنظیمات سایت ها» ویرایش کند.
"""
from __future__ import annotations

from urllib.parse import urlparse

from ..models import SiteProfile

BUILTIN_PROFILES: list[SiteProfile] = [
    SiteProfile(
        key="digikala",
        name="دیجی کالا",
        domains=("digikala.com",),
        price_selectors=(
            '[data-testid="product-price"]',
            '[data-testid="product-price-current"]',
            ".product-price__amount",
            '[class*="Price"]',
        ),
        title_selectors=(
            '[data-testid="product-title"]',
            "h1",
            "meta[property='og:title']",
        ),
        color_selectors=(
            '[data-testid*="variant"]',
            '[class*="color"]',
        ),
        variant_selectors=(
            '[data-testid="product-variant"]',
            '[data-testid*="variants"]',
            '[class*="variant"]',
        ),
    ),
    SiteProfile(
        key="teknolife",
        name="تکنولایف",
        domains=("teknolife.ir", "teknolife.com"),
        price_selectors=(
            ".price .amount",
            ".product-price",
            ".woocommerce-Price-amount",
            '[class*="price"]',
        ),
        title_selectors=(
            "h1.product_title",
            "h1",
            "meta[property='og:title']",
        ),
        color_selectors=(
            ".variations li",
            '[class*="color"]',
        ),
        variant_selectors=(
            ".variations",
            "#product-variations",
            '[class*="variation"]',
        ),
    ),
    SiteProfile(
        key="hamrahtel",
        name="همراه تل",
        domains=("hamrahtel.com", "hamrahtel.ir"),
        price_selectors=(
            '[data-testid*="price"]',
            '[class*="price"]',
            ".price",
        ),
        title_selectors=(
            "h1",
            "meta[property='og:title']",
        ),
        color_selectors=(
            '[data-testid*="color"]',
            '[class*="color"]',
        ),
        variant_selectors=(
            '[data-testid*="variant"]',
            '[class*="variant"]',
        ),
    ),
]


def builtin_dict() -> dict[str, dict]:
    return {p.key: p.to_dict() for p in BUILTIN_PROFILES}


def merge_profiles(saved: dict | None) -> dict[str, SiteProfile]:
    """پروفایل های داخلی را با ویرایش های کاربر ترکیب می کند."""
    saved = saved or {}
    result: dict[str, SiteProfile] = {p.key: p for p in BUILTIN_PROFILES}
    for key, data in saved.items():
        if key in result and isinstance(data, dict):
            base = result[key].to_dict()
            base.update({k: v for k, v in data.items() if k in base})
            result[key] = SiteProfile.from_dict(base)
    return result


def detect_profile(url: str, profiles: dict[str, SiteProfile]) -> SiteProfile:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        host = ""
    host = host.lower().removeprefix("www.")
    for profile in profiles.values():
        if any(host == d or host.endswith("." + d) for d in profile.domains):
            return profile
    return profiles.get(
        "generic",
        SiteProfile(key="generic", name="سایت دلخواه", domains=()),
    )
