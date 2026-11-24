"""پنجره اصلی برنامه با سه تب: استخراج، تنظیمات، آپدیت."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from .. import theme
from ..config import APP_NAME, AUTHOR, VERSION, desktop_path, load_settings, save_settings
from ..extractors.excel import export_excel
from ..models import PriceRow, ScrapeJob
from ..scraper.engine import ScrapeEngine
from ..sites.profiles import merge_profiles
from ..updater.github import (
    apply_downloaded,
    check_release,
    download_asset,
    install_browser,
    is_newer,
    normalize_repo,
    pick_asset,
)
from .samples import SAMPLE_JOBS

NAV_ITEMS = (
    ("extract", "استخراج قیمت"),
    ("settings", "تنظیمات سایت ها"),
    ("update", "آپدیت و درباره"),
)


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode(str(self._initial_setting("appearance", "dark")))
        ctk.set_default_color_theme("blue")

        self.settings = load_settings()
        self.profiles = merge_profiles(self.settings.get("sites", {}))
        self.jobs: list[ScrapeJob] = []
        self.rows: list[PriceRow] = []
        self.messages: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.engine: ScrapeEngine | None = None
        self.release_info = None
        self.last_excel: Path | None = None

        self.title(f"{APP_NAME}  |  طراح و سازنده: {AUTHOR}  |  نسخه {VERSION}")
        self.geometry("1240x820")
        self.minsize(1050, 700)
        self._set_icon()
        self._configure_tree_style()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_content()
        self._load_sample_jobs()
        self._show_view("extract")
        self.after(120, self._drain_queue)

    @staticmethod
    def _initial_setting(key: str, default: str) -> str:
        settings = load_settings()
        return str(settings.get(key, default))

    def _set_icon(self) -> None:
        path = Path(__file__).resolve().parent.parent.parent / "assets" / "app.ico"
        if path.exists():
            try:
                self.iconbitmap(str(path))
            except Exception:
                pass

    def _configure_tree_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("default")
        except tk.TclError:
            pass
        style.configure(
            "Treeview",
            background=theme.PANEL,
            foreground=theme.TEXT,
            fieldbackground=theme.PANEL,
            rowheight=28,
            font=(theme.FONT_FA, 10),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=theme.PANEL_2,
            foreground=theme.ACCENT,
            font=(theme.FONT_FA, 10, "bold"),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", theme.ACCENT_2)])

    # ---------------------------------------------------------------- sidebar
    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=theme.BG_2)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="قیمت یار",
            font=(theme.FONT_FA, 24, "bold"),
            text_color=theme.ACCENT,
        ).pack(pady=(28, 0), padx=24, anchor="w")
        ctk.CTkLabel(
            sidebar,
            text="PhonePricePro",
            font=(theme.FONT, 11),
            text_color=theme.TEXT_MUTED,
        ).pack(padx=24, anchor="w")
        ctk.CTkLabel(
            sidebar,
            text=f"نسخه {VERSION}",
            font=(theme.FONT_FA, 11),
            text_color=theme.TEXT_MUTED,
        ).pack(padx=24, pady=(4, 26), anchor="w")

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for key, label in NAV_ITEMS:
            button = ctk.CTkButton(
                sidebar,
                text=label,
                height=42,
                anchor="w",
                font=(theme.FONT_FA, 13),
                fg_color="transparent",
                hover_color=theme.PANEL_2,
                text_color=theme.TEXT_MUTED,
                command=lambda item=key: self._show_view(item),
            )
            button.pack(fill="x", padx=16, pady=5)
            self.nav_buttons[key] = button

        footer = ctk.CTkFrame(sidebar, fg_color=theme.PANEL, corner_radius=14)
        footer.pack(side="bottom", fill="x", padx=16, pady=20)
        ctk.CTkLabel(
            footer,
            text="ساخته شده توسط",
            font=(theme.FONT_FA, 10),
            text_color=theme.TEXT_MUTED,
        ).pack(pady=(12, 2))
        ctk.CTkLabel(
            footer,
            text=AUTHOR,
            font=(theme.FONT_FA, 14, "bold"),
            text_color=theme.GREEN,
        ).pack(pady=(0, 14))

    # ---------------------------------------------------------------- content
    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.views: dict[str, ctk.CTkFrame] = {
            "extract": self._build_extract_view(),
            "settings": self._build_settings_view(),
            "update": self._build_update_view(),
        }
        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")

    def _show_view(self, key: str) -> None:
        for name, view in self.views.items():
            view.tkraise()
        for name, button in self.nav_buttons.items():
            button.configure(
                fg_color=theme.ACCENT_2 if name == key else "transparent",
                text_color=theme.TEXT if name == key else theme.TEXT_MUTED,
            )
        self.views[key].tkraise()

    # ----------------------------------------------------------- extract view
    def _build_extract_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.content, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(view, fg_color=theme.PANEL, corner_radius=16)
        header.grid(row=0, column=0, sticky="ew", pady=(20, 10), padx=20)
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header,
            text="استخراج قیمت گوشی",
            font=(theme.FONT_FA, 20, "bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            header,
            text="لینک محصولات را اضافه کرده و استخراج را آغاز کنید",
            font=(theme.FONT_FA, 11),
            text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 12))

        self.model_entry = ctk.CTkEntry(
            header,
            placeholder_text="مدل (مثلاً A07 64/4)",
            width=210,
            height=38,
            font=(theme.FONT_FA, 12),
        )
        self.model_entry.grid(row=2, column=0, padx=(20, 8), pady=(0, 18), sticky="w")
        self.url_entry = ctk.CTkEntry(
            header,
            placeholder_text="آدرس صفحه محصول (digikala / teknolife / hamrahtel ...)",
            height=38,
            font=(theme.FONT_FA, 12),
        )
        self.url_entry.grid(row=2, column=1, padx=8, pady=(0, 18), sticky="ew")
        ctk.CTkButton(
            header,
            text="＋  افزودن لینک",
            width=120,
            height=38,
            fg_color=theme.ACCENT_2,
            command=self._add_job,
        ).grid(row=2, column=2, padx=(8, 20), pady=(0, 18))

        jobs_frame = ctk.CTkFrame(view, fg_color=theme.PANEL, corner_radius=16)
        jobs_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=6)
        jobs_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            jobs_frame,
            text="لیست لینک ها",
            font=(theme.FONT_FA, 12, "bold"),
            text_color=theme.ACCENT,
        ).pack(anchor="w", padx=16, pady=(10, 4))
        self.jobs_list = ctk.CTkScrollableFrame(jobs_frame, height=92, fg_color=theme.BG_2)
        self.jobs_list.pack(fill="x", padx=12, pady=(0, 12))
        self.jobs_list.grid_columnconfigure(0, weight=1)

        controls = ctk.CTkFrame(view, fg_color=theme.PANEL, corner_radius=16)
        controls.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        self.browser_switch = ctk.CTkSwitch(
            controls,
            text="پشتیبان مرورگر مخفی",
            font=(theme.FONT_FA, 11),
            command=self._update_from_controls,
        )
        self.browser_switch.select() if self.settings.get("use_browser_fallback", True) else self.browser_switch.deselect()
        self.browser_switch.pack(side="left", padx=(16, 12), pady=12)
        ctk.CTkLabel(controls, text="تاخیر (ثانیه)", font=(theme.FONT_FA, 11), text_color=theme.TEXT_MUTED).pack(side="left")
        self.delay_entry = ctk.CTkEntry(controls, width=70, height=30, font=(theme.FONT_FA, 11))
        self.delay_entry.insert(0, str(self.settings.get("delay_between_requests", 1.5)))
        self.delay_entry.pack(side="left", padx=6, pady=12)
        ctk.CTkButton(
            controls,
            text="لینک های نمونه A07",
            height=32,
            fg_color=theme.PANEL_2,
            hover_color=theme.ACCENT_2,
            font=(theme.FONT_FA, 11),
            command=self._load_sample_jobs,
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            controls,
            text="پاک کردن لیست",
            height=32,
            fg_color=theme.PANEL_2,
            hover_color="#991B1B",
            font=(theme.FONT_FA, 11),
            command=self._clear_jobs,
        ).pack(side="left", padx=4)
        self.auto_export_switch = ctk.CTkSwitch(
            controls,
            text="ذخیره خودکار اکسل",
            font=(theme.FONT_FA, 11),
        )
        if self.settings.get("auto_export", False):
            self.auto_export_switch.select()
        self.auto_export_switch.pack(side="left", padx=(16, 8), pady=12)

        results_frame = ctk.CTkFrame(view, fg_color=theme.PANEL, corner_radius=16)
        results_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=6)
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(2, weight=1)

        action_bar = ctk.CTkFrame(results_frame, fg_color="transparent")
        action_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        self.start_button = ctk.CTkButton(
            action_bar,
            text="شروع استخراج",
            height=38,
            width=160,
            fg_color=theme.GREEN,
            text_color="#062C21",
            font=(theme.FONT_FA, 12, "bold"),
            command=self._start,
        )
        self.start_button.pack(side="left", padx=(4, 8))
        self.stop_button = ctk.CTkButton(
            action_bar,
            text="توقف",
            height=38,
            width=100,
            fg_color=theme.RED,
            text_color="#3B0A13",
            font=(theme.FONT_FA, 12),
            state="disabled",
            command=self._stop,
        )
        self.stop_button.pack(side="left", padx=4)
        ctk.CTkButton(
            action_bar,
            text="ذخیره اکسل",
            height=38,
            width=120,
            fg_color=theme.ACCENT,
            text_color="#062C33",
            font=(theme.FONT_FA, 12, "bold"),
            command=self._save_excel,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            action_bar,
            text="باز کردن فایل",
            height=38,
            width=120,
            fg_color=theme.PANEL_2,
            font=(theme.FONT_FA, 12),
            command=self._open_excel,
        ).pack(side="left", padx=4)
        self.progress_label = ctk.CTkLabel(
            action_bar,
            text="آماده",
            font=(theme.FONT_FA, 11),
            text_color=theme.TEXT_MUTED,
        )
        self.progress_label.pack(side="right", padx=10)

        self.progress = ctk.CTkProgressBar(results_frame, height=8)
        self.progress.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 8))
        self.progress.set(0)

        table_holder = ctk.CTkFrame(results_frame, fg_color=theme.BG_2, corner_radius=10)
        table_holder.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        table_holder.grid_columnconfigure(0, weight=1)
        table_holder.grid_rowconfigure(0, weight=1)

        columns = ("site", "model", "color", "price", "status", "url")
        self.tree = ttk.Treeview(table_holder, columns=columns, show="headings")
        headings = {
            "site": ("سایت", 120),
            "model": ("مدل", 180),
            "color": ("رنگ", 140),
            "price": ("قیمت (تومان)", 150),
            "status": ("وضعیت", 110),
            "url": ("لینک", 420),
        }
        for key, (label, width) in headings.items():
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="center")
        scrollbar = ttk.Scrollbar(table_holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=6)

        log_frame = ctk.CTkFrame(results_frame, fg_color=theme.BG_2, corner_radius=10)
        log_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        ctk.CTkLabel(log_frame, text="گزارش اجرا", font=(theme.FONT_FA, 11, "bold"), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=10, pady=(6, 0))
        self.log_box = ctk.CTkTextbox(log_frame, height=86, font=(theme.FONT_FA, 10), fg_color="transparent")
        self.log_box.pack(fill="x", padx=8, pady=(2, 8))
        self.log_box.configure(state="disabled")
        return view

    # ---------------------------------------------------------- settings view
    def _build_settings_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.content, fg_color="transparent")
        scroll = ctk.CTkScrollableFrame(view, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        scroll.grid_columnconfigure(0, weight=1)
        self.settings_entries: dict[str, ctk.CTkEntry] = {}

        def section(title: str) -> ctk.CTkFrame:
            frame = ctk.CTkFrame(scroll, fg_color=theme.PANEL, corner_radius=16)
            frame.pack(fill="x", pady=8)
            ctk.CTkLabel(frame, text=title, font=(theme.FONT_FA, 14, "bold"), text_color=theme.ACCENT).pack(anchor="w", padx=18, pady=(14, 10))
            return frame

        def field(parent, key: str, label: str, width: int = 300) -> None:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=4)
            ctk.CTkLabel(row, text=label, font=(theme.FONT_FA, 11), text_color=theme.TEXT_MUTED, width=170, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=width, height=32, font=(theme.FONT_FA, 11))
            entry.insert(0, str(self.settings.get(key, "")))
            entry.pack(side="left", fill="x", expand=True)
            self.settings_entries[key] = entry

        general = section("تنظیمات عمومی")
        field(general, "github_repo", "آدرس مخزن GitHub:")
        field(general, "request_timeout", "زمان انتظار درخواست (ثانیه):", 120)
        field(general, "delay_between_requests", "تاخیر بین لینک ها (ثانیه):", 120)
        field(general, "browser_wait_ms", "زمان بارگذاری مرورگر (میلی ثانیه):", 120)
        field(general, "export_folder", "پوشه ذخیره اکسل:")

        row = ctk.CTkFrame(general, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(row, text="تم:", font=(theme.FONT_FA, 11), text_color=theme.TEXT_MUTED, width=170, anchor="w").pack(side="left")
        self.appearance_menu = ctk.CTkOptionMenu(
            row,
            values=["dark", "light", "system"],
            width=180,
            command=lambda _: self._save_settings(),
        )
        self.appearance_menu.set(str(self.settings.get("appearance", "dark")))
        self.appearance_menu.pack(side="left")

        self.update_pref_menu = ctk.CTkOptionMenu(row, values=["auto", "zip", "exe"], width=100)
        self.update_pref_menu.set(str(self.settings.get("update_preference", "auto")))
        self.update_pref_menu.pack(side="left", padx=12)

        ctk.CTkButton(
            general,
            text="انتخاب پوشه...",
            height=32,
            fg_color=theme.PANEL_2,
            font=(theme.FONT_FA, 11),
            command=self._choose_folder,
        ).pack(anchor="w", padx=18, pady=(6, 4))

        browser_frame = section("مرورگر مخفی (Playwright)")
        ctk.CTkLabel(
            browser_frame,
            text="برای سایت هایی که درخواست سریع را مسدود می کنند، نصب Chromium لازم است.",
            font=(theme.FONT_FA, 11),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=18)
        self.browser_status = ctk.CTkLabel(browser_frame, text="", font=(theme.FONT_FA, 11))
        self.browser_status.pack(anchor="w", padx=18, pady=6)
        ctk.CTkButton(
            browser_frame,
            text="نصب مرورگر مخفی",
            height=34,
            fg_color=theme.ACCENT_2,
            font=(theme.FONT_FA, 11),
            command=self._install_browser,
        ).pack(anchor="w", padx=18, pady=(2, 14))

        sites_frame = section("انتخابگرهای سایت ها (برای تغییرات سایت)")
        self.selector_entries: dict[str, dict[str, ctk.CTkEntry]] = {}
        for key, profile in self.profiles.items():
            card = ctk.CTkFrame(sites_frame, fg_color=theme.PANEL_2, corner_radius=12)
            card.pack(fill="x", padx=16, pady=8)
            ctk.CTkLabel(card, text=profile.name, font=(theme.FONT_FA, 12, "bold"), text_color=theme.GREEN).pack(anchor="w", padx=12, pady=(10, 4))
            self.selector_entries[key] = {}
            for field_key, label in (
                ("price_selectors", "قیمت"),
                ("color_selectors", "رنگ"),
                ("variant_selectors", "رنگ/قیمت"),
            ):
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=3)
                ctk.CTkLabel(row, text=label, width=90, anchor="w", font=(theme.FONT_FA, 10), text_color=theme.TEXT_MUTED).pack(side="left")
                entry = ctk.CTkEntry(row, height=30, font=(theme.FONT_FA, 10))
                entry.insert(0, ", ".join(getattr(profile, field_key)))
                entry.pack(side="left", fill="x", expand=True)
                self.selector_entries[key][field_key] = entry
            ctk.CTkLabel(card, text="دامنه ها: " + ", ".join(profile.domains), font=(theme.FONT_FA, 10), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=12, pady=(2, 10))

        ctk.CTkButton(
            scroll,
            text="ذخیره تنظیمات",
            height=40,
            fg_color=theme.GREEN,
            text_color="#062C21",
            font=(theme.FONT_FA, 12, "bold"),
            command=self._save_settings,
        ).pack(anchor="w", padx=18, pady=16)
        return view

    # ------------------------------------------------------------ update view
    def _build_update_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.content, fg_color="transparent")
        card = ctk.CTkFrame(view, fg_color=theme.PANEL, corner_radius=18)
        card.pack(fill="both", expand=True, padx=40, pady=40)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text=f"{APP_NAME}", font=(theme.FONT_FA, 28, "bold"), text_color=theme.ACCENT).grid(row=0, column=0, columnspan=2, sticky="w", padx=30, pady=(28, 4))
        ctk.CTkLabel(card, text="برنامه استخراج قیمت گوشی از سایت های دلخواه", font=(theme.FONT_FA, 13), text_color=theme.TEXT_MUTED).grid(row=1, column=0, columnspan=2, sticky="w", padx=30)

        info = [
            ("نسخه نصب شده", VERSION),
            ("سازنده", AUTHOR),
            ("سیستم آپدیت", "GitHub Releases"),
            ("مخزن", normalize_repo(str(self.settings.get("github_repo", ""))) or "تنظیم نشده"),
        ]
        for index, (label, value) in enumerate(info, start=3):
            ctk.CTkLabel(card, text=label, font=(theme.FONT_FA, 12), text_color=theme.TEXT_MUTED).grid(row=index, column=0, sticky="w", padx=30, pady=5)
            ctk.CTkLabel(card, text=value, font=(theme.FONT_FA, 12, "bold"), text_color=theme.TEXT).grid(row=index, column=1, sticky="w", pady=5)

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=8, column=0, columnspan=2, sticky="w", padx=30, pady=(22, 8))
        ctk.CTkButton(
            buttons,
            text="بررسی آپدیت",
            height=38,
            width=150,
            fg_color=theme.ACCENT_2,
            font=(theme.FONT_FA, 12, "bold"),
            command=self._check_update,
        ).pack(side="left", padx=(0, 10))
        self.download_button = ctk.CTkButton(
            buttons,
            text="دانلود و نصب",
            height=38,
            width=150,
            fg_color=theme.GREEN,
            text_color="#062C21",
            font=(theme.FONT_FA, 12, "bold"),
            state="disabled",
            command=self._download_update,
        )
        self.download_button.pack(side="left")

        self.update_status = ctk.CTkLabel(card, text="آماده بررسی آپدیت", font=(theme.FONT_FA, 12), text_color=theme.TEXT_MUTED)
        self.update_status.grid(row=9, column=0, columnspan=2, sticky="w", padx=30, pady=8)
        self.notes_box = ctk.CTkTextbox(card, height=160, font=(theme.FONT_FA, 11))
        self.notes_box.grid(row=10, column=0, columnspan=2, sticky="ew", padx=30, pady=(4, 30))
        self.notes_box.insert("1.0", "توضیحات نسخه جدید بعد از بررسی آپدیت نمایش داده می شود.")
        self.notes_box.configure(state="disabled")
        return view

    # ------------------------------------------------------------- job helpers
    def _add_job(self) -> None:
        url = self.url_entry.get().strip()
        if not url or "http" not in url:
            messagebox.showwarning(APP_NAME, "لطفاً یک آدرس معتبر وارد کنید.")
            return
        model = self.model_entry.get().strip() or "گوشی"
        self.jobs.append(ScrapeJob(url=url, model=model))
        self.url_entry.delete(0, "end")
        self._refresh_jobs()
        self._log("info", f"لینک اضافه شد: {url}")

    def _refresh_jobs(self) -> None:
        for widget in self.jobs_list.winfo_children():
            widget.destroy()
        for index, job in enumerate(self.jobs, start=1):
            row = ctk.CTkFrame(self.jobs_list, fg_color=theme.PANEL_2, corner_radius=8)
            row.pack(fill="x", pady=3, padx=2)
            ctk.CTkLabel(row, text=str(index), width=30, font=(theme.FONT_FA, 11), text_color=theme.ACCENT).pack(side="left", padx=6)
            ctk.CTkLabel(row, text=f"{job.model}  —  {job.url[:90]}", font=(theme.FONT_FA, 10), anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row,
                text="✕",
                width=28,
                height=24,
                fg_color="transparent",
                hover_color="#991B1B",
                font=(theme.FONT_FA, 11),
                command=lambda item=job: self._remove_job(item),
            ).pack(side="right", padx=4)

    def _remove_job(self, job: ScrapeJob) -> None:
        self.jobs.remove(job)
        self._refresh_jobs()

    def _clear_jobs(self) -> None:
        self.jobs.clear()
        self._refresh_jobs()

    def _load_sample_jobs(self) -> None:
        self.jobs = list(SAMPLE_JOBS)
        self._refresh_jobs()
        self._log("info", f"{len(self.jobs)} لینک نمونه A07 64/4 بارگذاری شد.")

    def _update_from_controls(self) -> None:
        self.settings["use_browser_fallback"] = bool(self.browser_switch.get())
        try:
            self.settings["delay_between_requests"] = float(self.delay_entry.get() or 1.5)
        except ValueError:
            pass

    # -------------------------------------------------------------- scrape flow
    def _start(self) -> None:
        self._update_from_controls()
        if not self.jobs:
            messagebox.showwarning(APP_NAME, "ابتدا حداقل یک لینک اضافه کنید.")
            return
        if self.worker and self.worker.is_alive():
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.rows.clear()
        self.progress.set(0)
        self.progress_label.configure(text="در حال استخراج...")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._log("info", f"شروع استخراج {len(self.jobs)} لینک.")

        callbacks = {
            "on_log": lambda level, message: self.messages.put(("log", (level, message))),
            "on_row": lambda row: self.messages.put(("row", row)),
            "on_progress": lambda done, total, job: self.messages.put(("progress", (done, total, job))),
            "on_done": lambda rows: self.messages.put(("done", rows)),
        }
        self.engine = ScrapeEngine(list(self.jobs), dict(self.settings), dict(self.profiles), callbacks)
        self.worker = threading.Thread(target=self.engine.run, daemon=True)
        self.worker.start()

    def _stop(self) -> None:
        if self.engine:
            self.engine.stop()
        self.stop_button.configure(state="disabled")

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "log":
                    self._append_log(*payload)
                elif kind == "row":
                    self._add_tree_row(payload)
                elif kind == "progress":
                    done, total, job = payload
                    self.progress.set(done / max(total, 1))
                    self.progress_label.configure(text=f"{done} / {total} — {job.url[:45]}")
                elif kind == "done":
                    self.rows = list(payload)
                    self.progress.set(1)
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.progress_label.configure(text=f"اتمام: {len(self.rows)} ردیف")
                    self._log("ok", f"استخراج تمام شد. {len(self.rows)} ردیف بدست آمد.")
                    if self.auto_export_switch.get():
                        self._save_excel(automatic=True)
        except queue.Empty:
            pass
        self.after(120, self._drain_queue)

    def _append_log(self, level: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{stamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _log(self, level: str, message: str) -> None:
        """نوشتن پیام در پنل گزارش (از thread اصلی)."""
        self._append_log(level, message)

    def _add_tree_row(self, row: PriceRow) -> None:
        self.tree.insert(
            "",
            "end",
            values=(
                row.site,
                row.model,
                row.color,
                f"{row.price:,}" if row.price else "—",
                row.status,
                row.url,
            ),
        )

    # ------------------------------------------------------------------- excel
    def _save_excel(self, automatic: bool = False) -> None:
        if not self.rows:
            if not automatic:
                messagebox.showinfo(APP_NAME, "ابتدا استخراج را اجرا کنید.")
            return
        folder = str(self.settings.get("export_folder") or desktop_path())
        default_name = f"قیمت_گوشی_{datetime.now():%Y%m%d_%H%M}.xlsx"
        if automatic:
            target = Path(folder) / default_name
        else:
            chosen = filedialog.asksaveasfilename(
                title="ذخیره فایل اکسل",
                initialdir=folder,
                initialfile=default_name,
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
            )
            if not chosen:
                return
            target = Path(chosen)
        try:
            self.last_excel = export_excel(self.rows, target, meta={"jobs": len(self.jobs)})
            self._log("ok", f"فایل اکسل ذخیره شد: {self.last_excel}")
            if not automatic:
                messagebox.showinfo(APP_NAME, f"فایل اکسل ذخیره شد:\n{self.last_excel}")
        except Exception as error:  # noqa: BLE001
            self._log("error", f"خطای ذخیره اکسل: {error}")
            messagebox.showerror(APP_NAME, f"خطای ذخیره اکسل:\n{error}")

    def _open_excel(self) -> None:
        if not self.last_excel or not self.last_excel.exists():
            messagebox.showinfo(APP_NAME, "ابتدا فایل اکسل را ذخیره کنید.")
            return
        import os
        import subprocess

        try:
            os.startfile(self.last_excel)  # type: ignore[attr-defined]
        except Exception:
            subprocess.Popen(["explorer", str(self.last_excel)])

    # ---------------------------------------------------------------- settings
    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=str(desktop_path()))
        if folder:
            self.settings_entries["export_folder"].delete(0, "end")
            self.settings_entries["export_folder"].insert(0, folder)

    def _save_settings(self) -> None:
        try:
            for key, entry in self.settings_entries.items():
                value = entry.get().strip()
                if key in ("request_timeout", "browser_wait_ms"):
                    self.settings[key] = int(value or 20)
                elif key == "delay_between_requests":
                    self.settings[key] = float(value or 1.5)
                else:
                    self.settings[key] = value
            self.settings["appearance"] = self.appearance_menu.get()
            self.settings["update_preference"] = self.update_pref_menu.get()
            self.settings["auto_export"] = bool(self.auto_export_switch.get())
            self.settings["use_browser_fallback"] = bool(self.browser_switch.get())
            sites = dict(self.settings.get("sites", {}))
            for key, fields in self.selector_entries.items():
                sites[key] = {
                    name: [item.strip() for item in value.get().split(",") if item.strip()]
                    for name, value in fields.items()
                }
            self.settings["sites"] = sites
            save_settings(self.settings)
            self.profiles = merge_profiles(sites)
            ctk.set_appearance_mode(str(self.settings["appearance"]))
            self._log("ok", "تنظیمات ذخیره شد.")
        except Exception as error:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"خطا در ذخیره تنظیمات:\n{error}")

    def _install_browser(self) -> None:
        self.browser_status.configure(text="در حال نصب Chromium... لطفاً صبر کنید.", text_color=theme.YELLOW)
        self.update_idletasks()

        def task() -> None:
            success, message = install_browser()
            self.after(
                0,
                lambda: self.browser_status.configure(
                    text=message[:300], text_color=theme.GREEN if success else theme.RED
                ),
            )

        threading.Thread(target=task, daemon=True).start()

    # ------------------------------------------------------------------ updater
    def _check_update(self) -> None:
        repo = self.settings_entries["github_repo"].get().strip()
        self.settings["github_repo"] = repo
        save_settings(self.settings)
        if not repo:
            self.update_status.configure(text="لطفاً آدرس مخزن GitHub را در تنظیمات وارد کنید.", text_color=theme.RED)
            return
        self.update_status.configure(text="در حال بررسی GitHub...", text_color=theme.YELLOW)
        self.update_idletasks()

        def task() -> None:
            release, error = check_release(repo)
            if error:
                self.after(0, lambda: self.update_status.configure(text=error, text_color=theme.RED))
                return
            if release is None:
                return
            self.release_info = release
            text = f"آخرین نسخه: {release.version}\n\n{release.notes}"
            new = is_newer(release.version)

            def finish() -> None:
                self.notes_box.configure(state="normal")
                self.notes_box.delete("1.0", "end")
                self.notes_box.insert("1.0", text[:6000])
                self.notes_box.configure(state="disabled")
                self.download_button.configure(state="normal" if new else "disabled")
                self.update_status.configure(
                    text=f"نسخه جدید {release.version} موجود است." if new else "شما از آخرین نسخه استفاده می کنید.",
                    text_color=theme.GREEN if new else theme.TEXT_MUTED,
                )

            self.after(0, finish)

        threading.Thread(target=task, daemon=True).start()

    def _download_update(self) -> None:
        if not self.release_info:
            return
        asset = pick_asset(self.release_info, str(self.settings.get("update_preference", "auto")))
        if not asset:
            self.update_status.configure(text="فایل قابل دانلودی در Release پیدا نشد.", text_color=theme.RED)
            return
        self.update_status.configure(text=f"در حال دانلود {asset.get('name')}...", text_color=theme.YELLOW)
        self.update_idletasks()

        def task() -> None:
            try:
                file = download_asset(
                    asset,
                    progress=lambda done, total: self.after(
                        0,
                        lambda: self.update_status.configure(
                            text=f"دانلود: {done // 1024} KB / {total // 1024 if total else '?'} KB",
                            text_color=theme.YELLOW,
                        ),
                    ),
                )
                message = apply_downloaded(file, self.settings)
                self.after(0, lambda: self.update_status.configure(text=message, text_color=theme.GREEN))
                self.after(1000, self.destroy)
            except Exception as error:  # noqa: BLE001
                self.after(0, lambda: self.update_status.configure(text=f"خطا: {error}", text_color=theme.RED))

        threading.Thread(target=task, daemon=True).start()
