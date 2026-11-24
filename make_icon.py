"""ساخت آیکون ساده برنامه (بدون نیاز به فایل خارجی)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "assets" / "app.ico"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    size = 512
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((24, 24, 488, 488), radius=96, fill="#0F172A", outline="#22D3EE", width=12)

    # گوشی
    draw.rounded_rectangle((168, 88, 344, 424), radius=38, fill="#1E293B", outline="#7C6CF6", width=12)
    draw.rounded_rectangle((190, 132, 322, 384), radius=16, fill="#0B1020")
    draw.ellipse((246, 392, 266, 412), fill="#22D3EE")

    # نمودار 가격
    points = [(204, 320), (244, 268), (280, 292), (314, 190)]
    draw.line(points, fill="#34D399", width=18, joint="curve")
    for x, y in points:
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill="#34D399")

    try:
        font = ImageFont.truetype("arialbd.ttf", 74)
        draw.text((176, 170), "Q", font=font, fill="#22D3EE")
    except OSError:
        pass

    image.save(OUT, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(OUT)


if __name__ == "__main__":
    main()
