# PhonePricePro (قیمت یار)

A Windows desktop app that extracts mobile-phone prices from product pages and exports a formatted Excel workbook. Version 1.0.0 — by Mohammad Mahdi Kashi (محمد مهدی کاشی).

[راهنمای فارسی / Persian README](README.fa.md)

## Features

- Add product links (model name + URL) in the **Extract prices** tab; three Samsung Galaxy A07 sample links are preloaded (Digikala, Teknolife, Hamrahtel).
- Extraction from JSON-LD, `__NEXT_DATA__` blobs, editable CSS selectors and Persian/English text patterns.
- Persian/Arabic digits are normalized; Rial prices are converted to Toman; suspiciously cheap variants (<25% of the maximum) are filtered out.
- Fast `requests` fetch with rotating user agents; automatic fallback to headless Playwright (installed Microsoft Edge/Chrome, or Playwright Chromium) when a site blocks the request.
- Hamrahtel special path using its internal Saleor GraphQL API for variant prices.
- Styled `.xlsx` output with three sheets:
  - **قیمت ها** — prices, hyperlinks, frozen headers, autofilter, RTL view,
  - **خلاصه** — per model/color min/max/average plus a bar chart of cheapest prices,
  - **گزارش** — run metadata (author, version, counts, extraction method).
- Site settings tab for per-site CSS selectors, timeouts, delay, browser wait, appearance, export folder and GitHub repo.
- Update tab: check GitHub Releases, download a portable `.zip` or `.exe` installer and apply it.

## Stack

| Area | Technology |
|---|---|
| GUI | CustomTkinter + tkinter/ttk (`Treeview`, `filedialog`, `messagebox`) |
| Fetching | `requests`, BeautifulSoup (`html.parser`), optional Playwright Chromium |
| Excel | `openpyxl` (styling + chart) |
| Packaging | PyInstaller one-dir build, Inno Setup 6 installer |
| Python | 3.12.10 used for builds; source requires 3.10+ (`int | None`, `str.removeprefix`) |

Dependencies (minimum versions, see `requirements.txt`): `customtkinter>=5.2.2`, `requests>=2.31.0`, `beautifulsoup4>=4.12.0`, `openpyxl>=3.1.0`, `playwright>=1.44.0`, `lxml>=4.9.0`, `pillow>=10.0.0`, `pyinstaller>=6.0.0`.

## Run from source (Windows)

```bat
cd /d "C:\Users\Kashi\Documents\Default Project\PhonePricePro"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

`python main.py` is an equivalent entry shim. A hidden smoke test opens and closes the GUI:

```bat
python -m app.main --smoke
```

For the browser fallback, install Microsoft Edge or Chrome. Alternatively:

```bat
python -m playwright install chromium
```

(the download may be blocked in some regions).

Extraction runs in a daemon background thread; results and logs are passed to the UI through a `queue.Queue` polled via `after(120, ...)`. Stop is cooperative and takes effect after the current URL finishes.

## Tests

```bat
python -m unittest discover -s tests -v
```

`tests/test_core.py` covers money normalization (Persian digits, Rial→Toman, invalid values), parsing (JSON-LD, `__NEXT_DATA__`, selector/text fallback), site profiles, updater version comparison/repo normalization, and Excel writing. All tests are offline; there are no integration/network tests.

## Build a portable exe

```bat
python -m PyInstaller --noconfirm --clean PhonePricePro.spec
```

or simply run `build.bat` (it ends with `pause`, so it waits for a keypress).

Output: `dist\PhonePricePro\PhonePricePro.exe` plus `dist\PhonePricePro\_internal\`. PyInstaller working files go to `build\PhonePricePro\`.

The spec collects Playwright/Openpyxl/CustomTkinter/bs4 submodules, bundles `assets`, excludes heavy optional modules, uses `assets/app.ico`, `console=False` and UPX.

To regenerate the icon:

```bat
python make_icon.py
```

## Build the installer

Requires Inno Setup 6:

```bat
ISCC.exe installer.iss
```

Output: `installer_output\PhonePricePro_Setup.exe`. It installs the portable folder into `{autopf}\PhonePricePro`, optionally creates a desktop shortcut and Start-menu entries, and launches the app after installation.

When bumping the version, update **both** `VERSION` in `app/config.py` and `MyAppVersion` in `installer.iss`, then publish a GitHub release tagged like `v1.0.1` with the exe and/or a zip of the portable folder.

## Settings and data locations

| Item | Path |
|---|---|
| Settings | `%APPDATA%\PhonePricePro\settings.json` (fallback `~/.phone_price_pro/PhonePricePro/settings.json`) |
| Downloaded releases | `%APPDATA%\PhonePricePro\downloads\` |
| Staged portable update | `%APPDATA%\PhonePricePro\pending_update\` |
| Generated update script | `%APPDATA%\PhonePricePro\apply_update.bat` |
| Excel output | `settings.export_folder` or Desktop; default name `قیمت_گوشی_YYYYmmdd_HHMM.xlsx` |
| Built-in site profiles | `app/sites/profiles.py` (Digikala, Teknolife, Hamrahtel) |

Defaults include `request_timeout=20`, `delay_between_requests=1.5`, `use_browser_fallback=true`, `browser_wait_ms=2500`, `appearance="dark"`. `github_repo` defaults to `MMK-81/PhonePricePro`, so update checks work out of the box; it can be changed in the Update tab.

## Updater behavior

- `.zip` releases are unzipped to `pending_update\` and applied by a generated batch script that kills the running exe and copies files over the app folder.
- `.exe` releases are downloaded and launched as installers.
- Version tags must match `VERSION` in `app/config.py`.
- No code signing is configured.

## Limitations

- Windows-only in practice: `%APPDATA%`, Inno Setup, `os.startfile`, Edge/Chrome Playwright channels and Windows detached-process flags are used.
- E-commerce sites frequently block scraping; selectors may break and need editing in the UI.
- The `<25% of max` filter and the 1,000–10,000,000,000 validation range can drop legitimate prices.
- Hamrahtel support depends on an internal GraphQL endpoint that may change without notice.
- `build.bat` uses `pause` and will block unattended builds.
- PyInstaller's `warn-PhonePricePro.txt` lists optional missing modules — usually harmless.

## License

Personal project; no license file is included.
