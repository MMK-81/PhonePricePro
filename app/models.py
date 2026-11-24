"""ساختمان داده های مورد استفاده در برنامه."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SiteProfile:
    key: str
    name: str
    domains: tuple[str, ...]
    price_selectors: tuple[str, ...] = ()
    title_selectors: tuple[str, ...] = ()
    color_selectors: tuple[str, ...] = ()
    variant_selectors: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SiteProfile":
        return cls(
            key=str(data.get("key", "generic")),
            name=str(data.get("name", "سایت دلخواه")),
            domains=tuple(data.get("domains", ())),
            price_selectors=tuple(data.get("price_selectors", ())),
            title_selectors=tuple(data.get("title_selectors", ())),
            color_selectors=tuple(data.get("color_selectors", ())),
            variant_selectors=tuple(data.get("variant_selectors", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "domains": list(self.domains),
            "price_selectors": list(self.price_selectors),
            "title_selectors": list(self.title_selectors),
            "color_selectors": list(self.color_selectors),
            "variant_selectors": list(self.variant_selectors),
        }


@dataclass
class ScrapeJob:
    url: str
    model: str = ""
    profile_key: str = "auto"


@dataclass
class PriceRow:
    site: str
    model: str
    color: str
    price: int | None
    url: str
    title: str = ""
    status: str = "موفق"
    note: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def as_tuple(self) -> tuple:
        return (
            self.site,
            self.model,
            self.color,
            self.price,
            self.status,
            self.timestamp,
            self.url,
        )


@dataclass
class FetchResult:
    html: str = ""
    status: int = 0
    used_browser: bool = False
    error: str = ""
    final_url: str = ""
