"""پالت رنگ و استایل مشترک رابط کاربری."""
from __future__ import annotations

BG = "#0B1020"
BG_2 = "#0F172A"
PANEL = "#151F35"
PANEL_2 = "#1B2942"
CARD = "#1E293B"
BORDER = "#2B3A55"
TEXT = "#E8EEF9"
TEXT_MUTED = "#9AA8C0"
ACCENT = "#22D3EE"
ACCENT_2 = "#7C6CF6"
GREEN = "#34D399"
RED = "#FB7185"
YELLOW = "#FBBF24"
FONT = "Segoe UI"
FONT_FA = "Tahoma"

LEVEL_COLORS = {
    "info": TEXT_MUTED,
    "ok": GREEN,
    "warn": YELLOW,
    "error": RED,
}


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
