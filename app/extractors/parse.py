"""تجزیه صفحات محصول و استخراج عنوان، رنگ ها و قیمت ها."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from bs4 import BeautifulSoup

from ..models import SiteProfile
from .money import parse_price, to_english_digits

PRICE_KEYS = (
    "price",
    "pricewithdiscount",
    "price_with_discount",
    "discountedprice",
    "discounted_price",
    "finalprice",
    "final_price",
    "sellprice",
    "sell_price",
    "saleprice",
    "currentprice",
    "priceamount",
    "price_value",
    "amount",
    "toman",
)
COLOR_KEYS = (
    "color",
    "colorname",
    "color_name",
    "colour",
    "variantcolor",
    "variant_color",
    "selectedcolor",
    "rang",
)

COLOR_NAMES = (
    "مشکی", "سیاه", "black", "آبی", "abi", "blue", "طلایی", "gold", "طلا",
    "خاکستری", "gray", "grey", "سفید", "white", "سبز", "green", "قرمز", "red",
    "بنفش", "purple", "نقره ای", "نقره‌ای", "silver", "کرم", "cream", "قهوه ای",
    "قهوه‌ای", "brown", "صورتی", "pink", "زرد", "yellow", "نارنجی", "orange",
    "یاسی", "لیمویی", "فیروزه ای", "آبی روشن", "آبی تیره", "دودی", "بژ",
    "خاکی", "سرمه ای", "سرمه‌ای", "marine", "сияه",
)

PRICE_RE = re.compile(
    r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d{4,10})(?=\s*(?:تومان|ریال|تومان\b))",
    re.IGNORECASE,
)
PRICE_RE_BEFORE = re.compile(
    r"(?:تومان|ریال)\s*:?\s*(\d{1,3}(?:,\d{3})+|\d{4,10})(?!\d)",
    re.IGNORECASE,
)


@dataclass
class ParsedPage:
    title: str = ""
    variants: list[tuple[str, int]] = field(default_factory=list)
    prices: list[int] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _clean_color(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" :-")
    if not text or len(text) > 50 or "<" in text or "{" in text:
        return ""
    return text


def extract_title(soup: BeautifulSoup, profile: SiteProfile) -> str:
    selectors = list(profile.title_selectors) + ["h1", "meta[property='og:title']", "title"]
    for selector in selectors:
        try:
            element = soup.select_one(selector)
        except Exception:
            continue
        if element is None:
            continue
        value = element.get("content") or element.get_text(" ", strip=True)
        value = re.sub(r"\s+", " ", str(value)).strip()
        if value:
            return value[:200]
    return ""


def _json_blobs(html: str, only_ld: bool = False) -> list[Any]:
    blobs: list[Any] = []
    soup = _soup(html)
    for script in soup.find_all("script"):
        kind = (script.get("type") or "").lower()
        ident = (script.get("id") or "").lower()
        is_ld = "ld+json" in kind
        if only_ld:
            if not is_ld:
                continue
        elif "json" not in kind and "next_data" not in ident:
            continue
        raw = script.string or script.get_text() or ""
        try:
            blobs.append(json.loads(raw))
        except (ValueError, TypeError):
            continue
    return blobs


def _iter_products(obj: Any, depth: int = 0) -> Iterator[dict]:
    """درخت JSON-LD را جستجو می کند تا محصولات را پیدا کند."""
    if depth > 20:
        return
    if isinstance(obj, list):
        for item in obj[:200]:
            yield from _iter_products(item, depth + 1)
    elif isinstance(obj, dict):
        kinds = obj.get("@type")
        kinds = {str(k).lower() for k in kinds} if isinstance(kinds, list) else {str(kinds).lower()}
        if "product" in kinds or "productgroup" in kinds or "offers" in obj:
            yield obj
        for value in obj.values():
            yield from _iter_products(value, depth + 1)


def extract_ld_variants(html: str) -> list[tuple[str, int]]:
    """قیمت را از شبکه داده های استاندارد محصول (JSON-LD) می گیرد."""
    results: list[tuple[str, int]] = []
    for blob in _json_blobs(html, only_ld=True):
        for product in _iter_products(blob):
            color = _clean_color(product.get("color") or product.get("colour") or "")
            variants = product.get("hasVariant")
            if isinstance(variants, list) and variants:
                for variant in variants[:40]:
                    if not isinstance(variant, dict):
                        continue
                    variant_color = _clean_color(variant.get("color") or variant.get("colour") or color)
                    offers = variant.get("offers")
                    prices = _offer_prices(offers)
                    for price in prices[:3]:
                        results.append((variant_color, price))
                continue
            for price in _offer_prices(product.get("offers"))[:3]:
                results.append((color, price))
    return results


def _offer_prices(offers: Any) -> list[int]:
    prices: list[int] = []
    if isinstance(offers, dict):
        for key in ("price", "lowPrice", "priceSpecification"):
            value = offers.get(key)
            if isinstance(value, dict):
                prices.extend(_offer_prices(value))
            else:
                price = parse_price(value)
                if price:
                    prices.append(price)
    elif isinstance(offers, list):
        for offer in offers[:20]:
            prices.extend(_offer_prices(offer))
    return list(dict.fromkeys(prices))


def _walk_json(obj: Any, inherited_color: str = "", depth: int = 0) -> Iterator[tuple[str, int]]:
    if depth > 30:
        return
    if isinstance(obj, list):
        for item in obj[:600]:
            yield from _walk_json(item, inherited_color, depth + 1)
        return
    if not isinstance(obj, dict):
        return

    lowered = {str(k).lower(): v for k, v in obj.items()}
    color = inherited_color
    for key in COLOR_KEYS:
        value = lowered.get(key)
        if isinstance(value, (str, int, float)):
            candidate = _clean_color(value)
            if candidate:
                color = candidate
                break

    for key in PRICE_KEYS:
        value = lowered.get(key)
        if value is None:
            continue
        price = parse_price(value) if not isinstance(value, (dict, list)) else None
        if price:
            yield color, price
            break

    for key, value in obj.items():
        if str(key).lower() in PRICE_KEYS:
            continue
        yield from _walk_json(value, color, depth + 1)


def extract_json_variants(html: str) -> list[tuple[str, int]]:
    results: list[tuple[str, int]] = []
    for blob in _json_blobs(html):
        for color, price in _walk_json(blob):
            results.append((color, price))
    return results


def _text_prices(text: str) -> list[int]:
    normalized = to_english_digits(text)
    values: list[int] = []
    for match in PRICE_RE.finditer(normalized):
        price = parse_price(match.group(1).replace(",", ""))
        if price:
            values.append(price)
    for match in PRICE_RE_BEFORE.finditer(normalized):
        price = parse_price(match.group(1).replace(",", ""))
        if price:
            values.append(price)
    return values


def extract_colors(text: str) -> list[str]:
    normalized = to_english_digits(text).lower()
    found: list[str] = []
    for name in COLOR_NAMES:
        if name.lower() in normalized:
            label = _clean_color(name)
            if label and label.lower() not in [x.lower() for x in found]:
                found.append(label)
    for match in re.finditer(r"رنگ\s*[:\-]?\s*([^\n,،|]{2,25})", normalized):
        label = _clean_color(match.group(1))
        label_words = label.split()
        if not label or len(label_words) > 2 or len(label) > 20:
            continue
        if not any(name.lower() in label.lower() for name in COLOR_NAMES):
            continue
        if label.lower() not in [x.lower() for x in found]:
            found.append(label)
    return found[:20]


def extract_nearby_colors(text: str) -> list[str]:
    """فقط رنگ هایی که در نزدیکی قیمت ذکر شده اند را برمی گرداند."""
    normalized = to_english_digits(text)
    found: list[str] = []
    for match in PRICE_RE.finditer(normalized):
        for name in extract_colors(normalized[max(0, match.start() - 140) : match.end() + 140]):
            if name.lower() not in [x.lower() for x in found]:
                found.append(name)
    return found[:12]


def extract_selector_variants(soup: BeautifulSoup, profile: SiteProfile) -> list[tuple[str, int]]:
    results: list[tuple[str, int]] = []

    def price_from(element: Any) -> int | None:
        for attr in ("data-price", "data-value", "content", "value", "title"):
            value = element.get(attr)
            if value:
                price = parse_price(value)
                if price:
                    return price
        return parse_price(element.get_text(" ", strip=True))

    def color_from(element: Any) -> str:
        for attr in ("data-color", "data-title", "title", "aria-label", "alt"):
            value = _clean_color(element.get(attr))
            if value:
                return value
        for selector in profile.color_selectors:
            try:
                child = element.select_one(selector)
            except Exception:
                continue
            if child:
                value = _clean_color(child.get_text(" ", strip=True))
                if value:
                    return value
        parent = element.parent
        if parent is not None:
            for attr in ("data-color", "data-title", "title", "aria-label", "alt"):
                value = _clean_color(parent.get(attr))
                if value:
                    return value
            own_text = element.get_text(" ", strip=True)
            if len(own_text) < 80:
                colors = extract_colors(own_text)
                if colors:
                    return colors[0]
        return ""

    for selector in profile.variant_selectors:
        try:
            containers = soup.select(selector)
        except Exception:
            continue
        for container in containers[:60]:
            text = container.get_text(" ", strip=True)
            prices = _text_prices(text)
            if not prices:
                continue
            colors = extract_nearby_colors(text[:2000]) or extract_colors(text[:500])
            for index, price in enumerate(prices[:10]):
                color = colors[index] if index < len(colors) else (colors[0] if colors else "")
                results.append((color, price))

    for selector in profile.price_selectors:
        try:
            elements = soup.select(selector)
        except Exception:
            continue
        for element in elements[:60]:
            price = price_from(element)
            if not price:
                continue
            results.append((color_from(element), price))

    return results


def _dedupe(variants: list[tuple[str, int]]) -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    result: list[tuple[str, int]] = []
    for color, price in variants:
        key = (color.lower(), price)
        if key in seen:
            continue
        seen.add(key)
        result.append((color or "پیش فرض", price))

    # قیمت محصولات پیشنهادی/لوازم جانبی معمولاً خیلی کمتر از قیمت محصول اصلی است.
    if len(result) > 1:
        highest = max(price for _, price in result)
        result = [(color, price) for color, price in result if price >= highest * 0.25]
    return result[:60]


def parse_page(html: str, profile: SiteProfile) -> ParsedPage:
    soup = _soup(html)
    text = soup.get_text(" ", strip=True)
    title = extract_title(soup, profile)
    colors = extract_colors(text[:200000])

    variants = extract_ld_variants(html)
    if not variants:
        variants = extract_json_variants(html)
    variants.extend(extract_selector_variants(soup, profile))
    variants = _dedupe(variants)

    prices = _text_prices(text[:200000])
    prices = list(dict.fromkeys(prices))

    if not variants and prices:
        colors = extract_nearby_colors(text[:200000]) or colors
        if colors:
            for color in colors:
                variants.append((color, prices[0]))
            if len(prices) > len(colors):
                variants.append(("", prices[-1]))
        else:
            variants = [("", price) for price in prices]
        variants = _dedupe(variants)

    return ParsedPage(title=title, variants=variants, prices=prices, colors=colors)
