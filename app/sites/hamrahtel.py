"""استخراج اختصاصی محصولات همراه تل از API داخلی Saleor سایت."""
from __future__ import annotations

from urllib.parse import urlparse

import requests

from ..extractors.money import parse_price

GRAPHQL_URL = "https://core-api.hamrahtel.com/graphql/"
QUERY = """
query ProductBySlug($slug: String!, $channel: String!) {
  product(slug: $slug, channel: $channel) {
    name
    variants {
      name
      pricing {
        price { gross { amount } }
        discount { gross { amount } }
      }
      attributes {
        attribute { name slug }
        values { name value }
      }
    }
  }
}
"""


def slug_from_url(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) >= 2 and parts[-2] in ("product", "products"):
        return parts[-1]
    return ""


def fetch_variants(url: str, timeout: int = 20) -> tuple[str, list[tuple[str, int]]]:
    """عنوان و لیست (رنگ، قیمت) را از GraphQL سایت می گیرد."""
    slug = slug_from_url(url)
    if not slug:
        return "", []
    try:
        response = requests.post(
            GRAPHQL_URL,
            json={
                "operationName": "ProductBySlug",
                "variables": {"slug": slug, "channel": "customer"},
                "query": QUERY,
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json",
                "Origin": "https://hamrahtel.com",
                "Referer": "https://hamrahtel.com/",
            },
            timeout=timeout,
        )
        data = response.json().get("data", {}).get("product")
    except Exception:
        return "", []
    if not data:
        return "", []

    title = str(data.get("name") or "")
    results: list[tuple[str, int]] = []
    for variant in data.get("variants") or []:
        pricing = variant.get("pricing") or {}
        price_value = (pricing.get("discount") or pricing.get("price") or {}).get("gross", {}).get("amount")
        price = parse_price(price_value)
        if not price:
            continue
        color = ""
        for attribute in variant.get("attributes") or []:
            name = str((attribute.get("attribute") or {}).get("name", "")).lower()
            if "رنگ" in name or "color" in name:
                values = attribute.get("values") or []
                if values:
                    color = str(values[0].get("name") or "")
                    break
        if not color:
            color = str(variant.get("name") or "")
        results.append((color, price))
    return title, results
