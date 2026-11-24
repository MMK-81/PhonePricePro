import json
import tempfile
import unittest
from pathlib import Path

from app.extractors.excel import export_excel
from app.extractors.money import clean_number, parse_price
from app.extractors.parse import parse_page
from app.models import PriceRow, SiteProfile
from app.sites.profiles import BUILTIN_PROFILES, detect_profile
from app.updater.github import is_newer, normalize_repo, version_tuple

SAMPLE_PROFILE = SiteProfile(
    key="test",
    name=" تستی",
    domains=("example.com",),
    price_selectors=(".price",),
    color_selectors=(".color",),
    variant_selectors=(".variant",),
)


class MoneyTests(unittest.TestCase):
    def test_persian_digits(self):
        self.assertEqual(clean_number("۲٬۴۵۰٬۰۰۰"), 2450000)

    def test_toman_and_rial(self):
        self.assertEqual(parse_price("1,250,000 تومان"), 1250000)
        self.assertEqual(parse_price("12500000 ریال"), 1250000)

    def test_invalid(self):
        self.assertIsNone(parse_price("12"))
        self.assertIsNone(parse_price("abc"))


class ParseTests(unittest.TestCase):
    def test_json_ld(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type":"Product","name":"Galaxy A07","offers":{"price":"2450000","priceCurrency":"IRR"}}
        </script></head><body><h1>Galaxy A07 4/64</h1></body></html>
        """
        parsed = parse_page(html, SAMPLE_PROFILE)
        self.assertEqual(parsed.title, "Galaxy A07 4/64")
        self.assertTrue(any(price == 2450000 for _, price in parsed.variants))

    def test_next_data_variants(self):
        payload = {
            "props": {
                "pageProps": {
                    "variants": [
                        {"color": "مشکی", "price": 2300000},
                        {"color": "آبی", "price": 2350000},
                    ]
                }
            }
        }
        html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></html>'
        parsed = parse_page(html, SAMPLE_PROFILE)
        self.assertEqual(len(parsed.variants), 2)
        self.assertIn(("مشکی", 2300000), parsed.variants)

    def test_selector_and_text_fallback(self):
        html = """
        <html><body>
        <div class="variant"><span class="color">مشکی</span> ۱,۹۰۰,۰۰۰ تومان </div>
        <div class="variant"><span class="color">طلایی</span> ۱,۹۵۰,۰۰۰ تومان </div>
        </body></html>
        """
        parsed = parse_page(html, SAMPLE_PROFILE)
        self.assertTrue(parsed.variants)
        self.assertTrue(any(price in (1900000, 1950000) for _, price in parsed.variants))


class ProfileTests(unittest.TestCase):
    def test_detect(self):
        profiles = {p.key: p for p in BUILTIN_PROFILES}
        self.assertEqual(detect_profile("https://www.digikala.com/product/dkp-1/", profiles).key, "digikala")
        self.assertEqual(detect_profile("https://hamrahtel.com/product/a07", profiles).key, "hamrahtel")
        self.assertEqual(detect_profile("https://example.com/a", profiles).key, "generic")


class UpdaterTests(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(version_tuple("v1.2.3"), (1, 2, 3))
        self.assertTrue(is_newer("1.1.0", "1.0.9"))
        self.assertFalse(is_newer("1.0.0", "1.0.0"))

    def test_repo_normalization(self):
        self.assertEqual(normalize_repo("https://github.com/user/repo"), "user/repo")


class ExcelTests(unittest.TestCase):
    def test_export(self):
        rows = [
            PriceRow(site="دیجی کالا", model="A07", color="مشکی", price=1900000, url="https://example.com"),
            PriceRow(site="همراه تل", model="A07", color="آبی", price=1950000, url="https://example.com/2"),
        ]
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "out.xlsx"
            result = export_excel(rows, target)
            self.assertTrue(result.exists())
            self.assertGreater(result.stat().st_size, 3000)


if __name__ == "__main__":
    unittest.main()
