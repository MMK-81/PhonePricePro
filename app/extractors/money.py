"""تبدیل و تمیز کردن اعداد پولی."""
from __future__ import annotations

import re

FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
AR_TO_EN = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def to_english_digits(value: str) -> str:
    return value.translate(FA_TO_EN).translate(AR_TO_EN)


def clean_number(value: object) -> int | None:
    """تبدیل هر مقدار عددی به عدد صحیح. None در صورت نامعتبر بودن."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else None
    text = to_english_digits(str(value)).strip()
    if not text:
        return None
    text = re.sub(r"[^\d.,]", "", text)
    if not text:
        return None
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", "")
    elif "," in text:
        parts = text.split(",")
        text = "".join(parts) if all(len(p) == 3 for p in parts[1:]) else "".join(parts)
    elif "." in text and text.count(".") == 1 and len(text.split(".")[1]) <= 2:
        text = text.replace(".", "")
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    return int(digits) if int(digits) > 0 else None


def parse_price(value: object) -> int | None:
    """قیمت را بر حسب تومان برمی گرداند و ریال را به تومان تبدیل می کند."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = clean_number(value)
    else:
        text = str(value)
        number = clean_number(text)
        if "ریال" in text and "تومان" not in text and number is not None:
            number //= 10
    if number is None or number < 1000 or number > 10_000_000_000:
        return None
    return number


def format_price(number: int | None) -> str:
    if number is None:
        return "—"
    return f"{number:,}"
