from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import requests
from PIL import Image, ImageTk

from . import __version__
from .config import (
    DEFAULT_CONFIG,
    default_gui_download_dir,
    load_credentials,
    load_gui_settings,
    resolve_config_path,
    save_credentials,
    save_gui_settings,
)
from .downloader import DownloadRunner
from .i18n import TEXT, normalize_language, tr
from .models import Credentials, Post, SearchOptions
from .providers import (
    DEFAULT_PROVIDER_IDS,
    PROVIDER_MAP,
    PROVIDER_SPECS,
    USER_AGENT,
    provider_label,
    provider_referer,
)

ABOUT_LINKS = {
    "website": "https://ntdmn.xyz/",
    "github": "https://github.com/netdaemon91",
    "project": "https://github.com/netdaemon91/BooruGet",
    "original_project": "https://github.com/fhrach4/BooruGet",
}


class BooruGetGUI(tk.Tk):
    MAX_ROWS = 500
    PREVIEW_SIZE = (380, 420)

    def __init__(self, config_path: str = DEFAULT_CONFIG):
        super().__init__()
        self.title(f"BooruGet {__version__}")
        self.geometry("1180x850")
        self.minsize(980, 700)

        self.config_path = resolve_config_path(config_path)
        self.credentials = load_credentials(config_path)
        self.settings = load_gui_settings()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.items: dict[str, str] = {}
        self.posts: dict[str, Post] = {}
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.preview_key = ""
        self.selected_post: Post | None = None
        self.last_destination: Path | None = None
        self.presets: dict[str, dict] = {}
        self.style = ttk.Style(self)
        self.language = tk.StringVar(value="de")
        self._status_key = "status.ready"
        self._status_values: dict[str, object] = {}
        self._last_stats: dict[str, int] = {
            "seen": 0,
            "accepted": 0,
            "downloaded": 0,
            "failed": 0,
        }
        self.item_status_keys: dict[str, str] = {}
        self._about_window: tk.Toplevel | None = None

        self.protocol("WM_DELETE_WINDOW", self._close)
        self._set_icon()
        self._build()
        self._restore()
        self._apply_language()
        self._apply_theme()
        self.after(100, self._pump)

    @staticmethod
    def _resource(*parts: str) -> Path:
        base = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(__file__).resolve().parent.parent,
            )
        )
        return base.joinpath(*parts)

    def _set_icon(self) -> None:
        path = self._resource("assets", "booruget.png")
        if path.exists():
            try:
                self._icon = tk.PhotoImage(file=str(path))
                self.iconphoto(True, self._icon)
            except tk.TclError:
                pass

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(8, weight=1)

        head = ttk.Frame(root)
        head.grid(
            row=0,
            column=0,
            columnspan=5,
            sticky="ew",
            pady=(0, 8),
        )
        head.columnconfigure(0, weight=1)
        ttk.Label(
            head,
            text="BooruGet",
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.subtitle = tk.StringVar(
            value=self._t("app.subtitle", version=__version__)
        )
        ttk.Label(
            head,
            textvariable=self.subtitle,
        ).grid(row=1, column=0, sticky="w")

        self.status = tk.StringVar(value=self._t("status.ready"))
        ttk.Label(
            head,
            textvariable=self.status,
        ).grid(row=0, column=1, rowspan=2, padx=10)

        self.theme = tk.StringVar(value="dark")
        self.theme_btn = ttk.Button(
            head,
            command=self._toggle_theme,
            width=10,
        )
        self.theme_btn.grid(row=0, column=2, rowspan=2)

        self.language_btn = ttk.Button(
            head,
            command=self._toggle_language,
            width=5,
        )
        self.language_btn.grid(
            row=0,
            column=3,
            rowspan=2,
            padx=(6, 0),
        )

        self.about_btn = ttk.Button(
            head,
            text=self._t("about.button"),
            command=self._show_about,
            width=8,
        )
        self.about_btn.grid(
            row=0,
            column=4,
            rowspan=2,
            padx=(6, 0),
        )

        self.tags = tk.StringVar()
        self.output = tk.StringVar(
            value=str(default_gui_download_dir())
        )
        self.preset = tk.StringVar()
        self._entry_row(root, 1, self._t("label.tags"), self.tags, combo=True)

        ttk.Label(root, text=self._t("label.preset")).grid(
            row=2,
            column=0,
            sticky="w",
        )
        self.preset_box = ttk.Combobox(
            root,
            textvariable=self.preset,
            state="readonly",
        )
        self.preset_box.grid(
            row=2,
            column=1,
            columnspan=2,
            sticky="ew",
            pady=4,
        )
        self.preset_box.bind(
            "<<ComboboxSelected>>",
            self._load_preset,
        )
        ttk.Button(
            root,
            text=self._t("button.save_favorite"),
            command=self._save_preset,
        ).grid(
            row=2,
            column=3,
            padx=(8, 0),
            sticky="ew",
        )
        ttk.Button(
            root,
            text=self._t("button.remove"),
            command=self._delete_preset,
        ).grid(
            row=2,
            column=4,
            padx=(8, 0),
            sticky="ew",
        )

        ttk.Label(root, text=self._t("label.output")).grid(
            row=3,
            column=0,
            sticky="w",
        )
        ttk.Entry(
            root,
            textvariable=self.output,
        ).grid(
            row=3,
            column=1,
            columnspan=2,
            sticky="ew",
            pady=4,
        )
        ttk.Button(
            root,
            text=self._t("button.folder"),
            command=self._choose_output,
        ).grid(
            row=3,
            column=3,
            padx=(8, 0),
            sticky="ew",
        )
        ttk.Button(
            root,
            text=self._t("button.open"),
            command=self._open_output,
        ).grid(
            row=3,
            column=4,
            padx=(8, 0),
            sticky="ew",
        )

        opts = ttk.LabelFrame(
            root,
            text=self._t("frame.sources"),
            padding=8,
        )
        opts.grid(
            row=4,
            column=0,
            columnspan=5,
            sticky="ew",
            pady=6,
        )

        self.provider_vars: dict[str, tk.BooleanVar] = {
            spec.id: tk.BooleanVar(
                value=spec.id in DEFAULT_PROVIDER_IDS
            )
            for spec in PROVIDER_SPECS
        }

        sources = ttk.Frame(opts)
        sources.grid(
            row=0,
            column=0,
            columnspan=10,
            sticky="ew",
        )
        for col in range(4):
            sources.columnconfigure(col, weight=1)
        for index, spec in enumerate(PROVIDER_SPECS):
            label = spec.label
            if spec.adult_site:
                label += " (18+)"
            ttk.Checkbutton(
                sources,
                text=label,
                variable=self.provider_vars[spec.id],
            ).grid(
                row=index // 4,
                column=index % 4,
                sticky="w",
                padx=(0, 14),
                pady=2,
            )

        self.any_size = tk.BooleanVar(value=True)
        self.allow_nsfw = tk.BooleanVar(value=False)
        self.width = tk.StringVar(value="1920")
        self.height = tk.StringVar(value="1080")
        self.max_results = tk.StringVar(value="0")
        self.max_pages = tk.StringVar(value="0")
        self.workers = tk.StringVar(value="4")

        ttk.Checkbutton(
            opts,
            text=self._t("option.any_resolution"),
            variable=self.any_size,
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Checkbutton(
            opts,
            text=self._t("option.allow_nsfw"),
            variable=self.allow_nsfw,
        ).grid(
            row=1,
            column=2,
            columnspan=2,
            sticky="w",
            padx=(10, 0),
            pady=(8, 0),
        )

        fields = (
            (self._t("field.width"), self.width),
            (self._t("field.height"), self.height),
            (self._t("field.max_results"), self.max_results),
            (self._t("field.max_pages"), self.max_pages),
            (self._t("field.parallel"), self.workers),
        )
        for col, (label, var) in enumerate(fields):
            ttk.Label(
                opts,
                text=label,
            ).grid(
                row=2,
                column=col * 2,
                sticky="e",
                pady=(7, 0),
            )
            ttk.Entry(
                opts,
                width=8,
                textvariable=var,
            ).grid(
                row=2,
                column=col * 2 + 1,
                padx=(4, 12),
                pady=(7, 0),
            )

        creds = ttk.LabelFrame(
            root,
            text=self._t("frame.credentials"),
            padding=8,
        )
        creds.grid(
            row=5,
            column=0,
            columnspan=5,
            sticky="ew",
            pady=6,
        )
        creds.columnconfigure(1, weight=1)
        creds.columnconfigure(3, weight=1)

        self.dan_user = tk.StringVar(
            value=self.credentials.danbooru_username
        )
        self.dan_key = tk.StringVar(
            value=self.credentials.danbooru_api_key
        )
        self.gel_user = tk.StringVar(
            value=self.credentials.gelbooru_user_id
        )
        self.gel_key = tk.StringVar(
            value=self.credentials.gelbooru_api_key
        )
        credential_fields = (
            (self._t("field.danbooru_user"), self.dan_user, False),
            (self._t("field.danbooru_key"), self.dan_key, True),
            (self._t("field.gelbooru_user"), self.gel_user, False),
            (self._t("field.gelbooru_key"), self.gel_key, True),
        )
        for i, (label, var, secret) in enumerate(
            credential_fields
        ):
            row, pair = divmod(i, 2)
            base = pair * 2
            ttk.Label(
                creds,
                text=label,
            ).grid(
                row=row,
                column=base,
                sticky="w",
                pady=2,
            )
            ttk.Entry(
                creds,
                textvariable=var,
                show="•" if secret else "",
            ).grid(
                row=row,
                column=base + 1,
                sticky="ew",
                padx=(5, 14),
                pady=2,
            )

        ttk.Button(
            creds,
            text=self._t("button.save"),
            command=self._save_credentials,
        ).grid(
            row=0,
            column=4,
            rowspan=2,
            sticky="ns",
        )
        ttk.Label(
            creds,
            text=self._t("credentials.note"),
            wraplength=850,
        ).grid(
            row=2,
            column=0,
            columnspan=5,
            sticky="w",
            pady=(5, 0),
        )

        controls = ttk.Frame(root)
        controls.grid(
            row=6,
            column=0,
            columnspan=5,
            sticky="ew",
            pady=6,
        )
        self.start_btn = ttk.Button(
            controls,
            text=self._t("button.start_download"),
            command=lambda: self._start(False),
        )
        self.start_btn.pack(side="left")
        self.search_btn = ttk.Button(
            controls,
            text=self._t("button.search_only"),
            command=lambda: self._start(True),
        )
        self.search_btn.pack(side="left", padx=7)
        self.cancel_btn = ttk.Button(
            controls,
            text=self._t("button.cancel"),
            command=self._cancel,
            state="disabled",
        )
        self.cancel_btn.pack(side="left")
        ttk.Button(
            controls,
            text=self._t("button.clear"),
            command=self._clear,
        ).pack(side="right")

        prog = ttk.Frame(root)
        prog.grid(
            row=7,
            column=0,
            columnspan=5,
            sticky="ew",
        )
        prog.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(
            prog,
            mode="indeterminate",
        )
        self.progress.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        self.stats = tk.StringVar(
            value=self._t("stats", **self._last_stats)
        )
        ttk.Label(
            prog,
            textvariable=self.stats,
        ).grid(
            row=0,
            column=1,
            padx=(10, 0),
        )

        self.book = ttk.Notebook(root)
        book = self.book
        book.grid(
            row=8,
            column=0,
            columnspan=5,
            sticky="nsew",
            pady=(7, 0),
        )
        queue_tab = ttk.Frame(book, padding=5)
        log_tab = ttk.Frame(book, padding=5)
        self.queue_tab = queue_tab
        self.log_tab = log_tab
        book.add(queue_tab, text=self._t("tab.queue"))
        book.add(log_tab, text=self._t("tab.log"))

        queue_tab.rowconfigure(0, weight=1)
        queue_tab.columnconfigure(0, weight=1)
        pane = ttk.Panedwindow(
            queue_tab,
            orient="horizontal",
        )
        pane.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        left = ttk.Frame(pane)
        right = ttk.LabelFrame(
            pane,
            text=self._t("frame.preview"),
            padding=7,
        )
        pane.add(left, weight=3)
        pane.add(right, weight=2)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        cols = (
            "provider",
            "id",
            "size",
            "rating",
            "status",
            "progress",
        )
        self.queue_view = ttk.Treeview(
            left,
            columns=cols,
            show="headings",
            selectmode="browse",
        )
        self._tree_heading_keys = {
            "provider": "tree.provider",
            "id": "tree.post",
            "size": "tree.resolution",
            "rating": "tree.rating",
            "status": "tree.status",
            "progress": "tree.progress",
        }
        for col in cols:
            self.queue_view.heading(
                col,
                text=self._t(self._tree_heading_keys[col]),
            )
        for col, width in zip(
            cols,
            (105, 95, 95, 75, 165, 80),
        ):
            self.queue_view.column(
                col,
                width=width,
                anchor="w",
            )
        self.queue_view.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        self.queue_view.bind(
            "<<TreeviewSelect>>",
            self._select,
        )
        sb = ttk.Scrollbar(
            left,
            orient="vertical",
            command=self.queue_view.yview,
        )
        sb.grid(
            row=0,
            column=1,
            sticky="ns",
        )
        self.queue_view.configure(
            yscrollcommand=sb.set
        )

        self.preview_label = ttk.Label(
            right,
            text=self._t("preview.select"),
            anchor="center",
        )
        self.preview_label.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        self.preview_info = tk.StringVar()
        ttk.Label(
            right,
            textvariable=self.preview_info,
            wraplength=360,
            justify="left",
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            pady=6,
        )
        self.open_post_btn = ttk.Button(
            right,
            text=self._t("button.open_post"),
            command=self._open_post,
            state="disabled",
        )
        self.open_post_btn.grid(
            row=2,
            column=0,
            sticky="ew",
        )

        log_tab.rowconfigure(0, weight=1)
        log_tab.columnconfigure(0, weight=1)
        self.log = tk.Text(
            log_tab,
            wrap="word",
            borderwidth=0,
        )
        self.log.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

    @staticmethod
    def _entry_row(
        root,
        row: int,
        label: str,
        var: tk.StringVar,
        combo: bool = False,
    ) -> None:
        ttk.Label(
            root,
            text=label,
        ).grid(
            row=row,
            column=0,
            sticky="w",
        )
        widget = (
            ttk.Combobox(root, textvariable=var)
            if combo
            else ttk.Entry(root, textvariable=var)
        )
        widget.grid(
            row=row,
            column=1,
            columnspan=4,
            sticky="ew",
            pady=4,
        )
        if combo:
            widget.bind(
                "<Return>",
                lambda _e: root.winfo_toplevel()._start(False),
            )
        top = root.winfo_toplevel()
        if combo:
            top.tags_box = widget

    def _apply_theme(self) -> None:
        dark = self.theme.get() == "dark"
        if dark:
            bg, fg, field, accent = (
                "#171a1f",
                "#e8e8e8",
                "#242932",
                "#3b82f6",
            )
        else:
            bg, fg, field, accent = (
                "#f4f5f7",
                "#202124",
                "#ffffff",
                "#2563eb",
            )

        self.configure(bg=bg)
        self.option_add("*Text.background", field)
        self.option_add("*Text.foreground", fg)
        self.style.theme_use("clam")
        self.style.configure(
            ".",
            background=bg,
            foreground=fg,
            fieldbackground=field,
        )
        self.style.configure(
            "TEntry",
            fieldbackground=field,
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=field,
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", field)],
            foreground=[("readonly", fg)],
        )
        self.style.configure(
            "Treeview",
            background=field,
            foreground=fg,
            fieldbackground=field,
        )
        self.style.map(
            "Treeview",
            background=[("selected", accent)],
        )
        self.log.configure(
            bg=field,
            fg=fg,
            insertbackground=fg,
        )
        self.theme_btn.configure(
            text=(
                self._t("theme.light")
                if dark
                else self._t("theme.dark")
            )
        )

    def _t(self, key: str, **values) -> str:
        return tr(self.language.get(), key, **values)

    @staticmethod
    def _literal_translation_keys() -> dict[str, str]:
        result: dict[str, str] = {}
        for translations in TEXT.values():
            for key, value in translations.items():
                if "{" not in value:
                    result[value] = key
        return result

    def _walk_widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self._walk_widgets(child)

    def _apply_language(self) -> None:
        literal_keys = self._literal_translation_keys()
        for widget in self._walk_widgets(self):
            try:
                current = str(widget.cget("text"))
            except (tk.TclError, AttributeError):
                continue
            key = literal_keys.get(current)
            if key:
                try:
                    widget.configure(text=self._t(key))
                except tk.TclError:
                    pass

        self.subtitle.set(
            self._t("app.subtitle", version=__version__)
        )
        self.language_btn.configure(
            text=(
                self._t("language.switch_to_en")
                if self.language.get() == "de"
                else self._t("language.switch_to_de")
            )
        )
        self.about_btn.configure(text=self._t("about.button"))
        self.theme_btn.configure(
            text=(
                self._t("theme.light")
                if self.theme.get() == "dark"
                else self._t("theme.dark")
            )
        )
        self._render_status()
        self._render_stats()

        self.book.tab(
            self.queue_tab,
            text=self._t("tab.queue"),
        )
        self.book.tab(
            self.log_tab,
            text=self._t("tab.log"),
        )
        for col, key in self._tree_heading_keys.items():
            self.queue_view.heading(
                col,
                text=self._t(key),
            )

        for item, key in list(self.item_status_keys.items()):
            if not self.queue_view.exists(item):
                self.item_status_keys.pop(item, None)
                continue
            values = list(
                self.queue_view.item(item, "values")
            )
            if len(values) >= 5:
                values[4] = self._t(key) if key else ""
                self.queue_view.item(item, values=values)

        self._refresh_selected_post_info()

        if (
            self._about_window is not None
            and self._about_window.winfo_exists()
        ):
            self._about_window.destroy()
            self._about_window = None

    def _toggle_language(self) -> None:
        self.language.set(
            "en"
            if self.language.get() == "de"
            else "de"
        )
        self._apply_language()
        self._save_settings()

    def _set_status(self, key: str, **values) -> None:
        self._status_key = key
        self._status_values = dict(values)
        self._render_status()

    def _render_status(self) -> None:
        self.status.set(
            self._t(
                self._status_key,
                **self._status_values,
            )
        )

    def _render_stats(self) -> None:
        self.stats.set(
            self._t("stats", **self._last_stats)
        )

    def _toggle_theme(self) -> None:
        self.theme.set(
            "light"
            if self.theme.get() == "dark"
            else "dark"
        )
        self._apply_theme()
        self._save_settings()

    def _selected_provider_ids(self) -> list[str]:
        return [
            spec.id
            for spec in PROVIDER_SPECS
            if self.provider_vars[spec.id].get()
        ]

    def _set_provider_ids(self, values) -> None:
        selected = {
            str(value)
            for value in values
            if str(value) in PROVIDER_MAP
        }
        for spec in PROVIDER_SPECS:
            self.provider_vars[spec.id].set(
                spec.id in selected
            )

    def _restore(self) -> None:
        s = self.settings
        self.output.set(
            str(s.get("output", self.output.get()))
        )

        saved_providers = s.get("providers")
        if isinstance(saved_providers, list):
            self._set_provider_ids(saved_providers)
        else:
            legacy = []
            if bool(s.get("use_danbooru", True)):
                legacy.append("danbooru")
            if bool(s.get("use_gelbooru", True)):
                legacy.append("gelbooru")
            self._set_provider_ids(legacy)

        self.any_size.set(
            bool(s.get("any_size", True))
        )
        self.allow_nsfw.set(
            bool(s.get("allow_nsfw", False))
        )
        for var, key, default in (
            (self.width, "width", "1920"),
            (self.height, "height", "1080"),
            (self.max_results, "max_results", "0"),
            (self.max_pages, "max_pages", "0"),
            (self.workers, "workers", "4"),
        ):
            var.set(str(s.get(key, default)))

        saved_theme = str(s.get("theme", "dark"))
        self.theme.set(
            saved_theme
            if saved_theme in {"dark", "light"}
            else "dark"
        )
        self.language.set(
            normalize_language(
                str(s.get("language", "de"))
            )
        )

        hist = s.get("history", [])
        self.tags_box["values"] = (
            hist[:25]
            if isinstance(hist, list)
            else []
        )

        raw = s.get("presets", {})
        self.presets = (
            raw
            if isinstance(raw, dict)
            else {}
        )
        self._refresh_presets()

        geom = s.get("geometry")
        if isinstance(geom, str) and "x" in geom:
            try:
                self.geometry(geom)
            except tk.TclError:
                pass

    def _settings(self) -> dict:
        history = list(self.tags_box["values"])
        current = self.tags.get().strip()
        if current:
            history = [
                current,
                *[x for x in history if x != current],
            ]
        selected = self._selected_provider_ids()
        return {
            "history": history[:25],
            "presets": self.presets,
            "output": self.output.get().strip(),
            "providers": selected,
            # Keep the historical keys for downgrade compatibility.
            "use_gelbooru": "gelbooru" in selected,
            "use_danbooru": "danbooru" in selected,
            "any_size": self.any_size.get(),
            "allow_nsfw": self.allow_nsfw.get(),
            "width": self.width.get(),
            "height": self.height.get(),
            "max_results": self.max_results.get(),
            "max_pages": self.max_pages.get(),
            "workers": self.workers.get(),
            "theme": self.theme.get(),
            "language": self.language.get(),
            "geometry": self.geometry(),
        }

    def _save_settings(self) -> None:
        data = self._settings()
        try:
            save_gui_settings(data)
        except OSError:
            pass
        self.tags_box["values"] = data["history"]

    def _preset_data(self) -> dict:
        selected = self._selected_provider_ids()
        return {
            "tags": self.tags.get(),
            "providers": selected,
            "use_gelbooru": "gelbooru" in selected,
            "use_danbooru": "danbooru" in selected,
            "any_size": self.any_size.get(),
            "allow_nsfw": self.allow_nsfw.get(),
            "width": self.width.get(),
            "height": self.height.get(),
            "max_results": self.max_results.get(),
            "max_pages": self.max_pages.get(),
            "workers": self.workers.get(),
        }

    def _refresh_presets(self) -> None:
        self.preset_box["values"] = sorted(
            self.presets,
            key=str.casefold,
        )

    def _save_preset(self) -> None:
        name = simpledialog.askstring(
            self._t("dialog.preset_save_title"),
            self._t("dialog.preset_save_prompt"),
            initialvalue=(
                self.preset.get()
                or self.tags.get()[:40]
            ),
            parent=self,
        )
        if name and name.strip():
            name = name.strip()[:80]
            self.presets[name] = self._preset_data()
            self.preset.set(name)
            self._refresh_presets()
            self._save_settings()

    def _delete_preset(self) -> None:
        name = self.preset.get()
        if (
            name in self.presets
            and messagebox.askyesno(
                self._t("dialog.preset_remove_title"),
                self._t(
                    "dialog.preset_remove_question",
                    name=name,
                ),
                parent=self,
            )
        ):
            del self.presets[name]
            self.preset.set("")
            self._refresh_presets()
            self._save_settings()

    def _load_preset(self, _e=None) -> None:
        data = self.presets.get(
            self.preset.get(),
            {},
        )
        if not isinstance(data, dict):
            return

        if isinstance(data.get("providers"), list):
            self._set_provider_ids(data["providers"])
        else:
            legacy = []
            if bool(data.get("use_danbooru", True)):
                legacy.append("danbooru")
            if bool(data.get("use_gelbooru", True)):
                legacy.append("gelbooru")
            self._set_provider_ids(legacy)

        mapping = {
            "tags": self.tags,
            "any_size": self.any_size,
            "allow_nsfw": self.allow_nsfw,
            "width": self.width,
            "height": self.height,
            "max_results": self.max_results,
            "max_pages": self.max_pages,
            "workers": self.workers,
        }
        for key, var in mapping.items():
            if key in data:
                var.set(data[key])

    def _credentials(self) -> Credentials:
        return Credentials(
            danbooru_username=self.dan_user.get().strip(),
            danbooru_api_key=self.dan_key.get().strip(),
            gelbooru_user_id=self.gel_user.get().strip(),
            gelbooru_api_key=self.gel_key.get().strip(),
        )

    def _save_credentials(self) -> None:
        try:
            path = save_credentials(
                self._credentials(),
                self.config_path,
            )
            self._set_status(
                "status.credentials_saved",
                path=path,
            )
        except OSError as exc:
            messagebox.showerror(
                self._t("dialog.error_title"),
                str(exc),
                parent=self,
            )

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(
            initialdir=(
                self.output.get()
                or str(Path.home())
            ),
            parent=self,
        )
        if path:
            self.output.set(path)

    def _open_output(self) -> None:
        path = (
            self.last_destination
            or Path(self.output.get()).expanduser()
        )
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            __import__("os").startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _build_search_options(
        self,
        dry: bool,
    ) -> SearchOptions | None:
        tags = self.tags.get().strip()
        if not tags:
            messagebox.showwarning(
                self._t("dialog.warning_title"),
                self._t("warning.tags_required"),
                parent=self,
            )
            return None

        selected = set(self._selected_provider_ids())
        if not selected:
            messagebox.showwarning(
                self._t("dialog.warning_title"),
                self._t("warning.provider_required"),
                parent=self,
            )
            return None

        try:
            width, height, results, pages, workers = map(
                int,
                (
                    self.width.get(),
                    self.height.get(),
                    self.max_results.get(),
                    self.max_pages.get(),
                    self.workers.get(),
                ),
            )
        except ValueError:
            messagebox.showerror(
                self._t("dialog.error_title"),
                self._t("error.integer_fields"),
                parent=self,
            )
            return None

        return SearchOptions(
            tags=tags,
            output_dir=(
                self.output.get().strip()
                or "downloads"
            ),
            use_danbooru="danbooru" in selected,
            use_gelbooru="gelbooru" in selected,
            provider_ids=selected,
            any_size=self.any_size.get(),
            target_width=width,
            target_height=height,
            allow_nsfw=self.allow_nsfw.get(),
            max_results=max(0, results),
            max_pages=max(0, pages),
            workers=max(1, min(16, workers)),
            dry_run=dry,
        )

    def _start(self, dry: bool) -> None:
        if self.worker and self.worker.is_alive():
            return
        options = self._build_search_options(dry)
        if not options:
            return

        self._save_settings()
        self.cancel_event.clear()
        self.progress.start(12)
        self.start_btn.configure(state="disabled")
        self.search_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self._set_status(
            "status.search_running"
            if dry
            else "status.download_running"
        )

        def work():
            try:
                DownloadRunner(
                    options,
                    self._credentials(),
                    log=lambda value: self.events.put(
                        ("log", value)
                    ),
                    cancel_event=self.cancel_event,
                    event_callback=lambda event, payload: (
                        self.events.put((event, payload))
                    ),
                ).run()
            except Exception as exc:
                self.events.put(
                    ("log", f"ERROR: {exc}")
                )
                self.events.put(
                    ("fatal", str(exc))
                )
            finally:
                self.events.put(("done", None))

        self.worker = threading.Thread(
            target=work,
            daemon=True,
        )
        self.worker.start()

    def _cancel(self) -> None:
        self.cancel_event.set()
        self._set_status("status.cancel_requested")

    def _key(self, post: Post) -> str:
        return f"{post.provider}:{post.post_id}"

    def _row(
        self,
        post: Post,
        status_key: str = "",
    ) -> str | None:
        key = self._key(post)
        item = self.items.get(key)
        if item and self.queue_view.exists(item):
            return item
        if len(self.items) >= self.MAX_ROWS:
            return None

        item = self.queue_view.insert(
            "",
            "end",
            values=(
                provider_label(post.provider),
                post.post_id,
                f"{post.width}×{post.height}",
                post.rating,
                self._t(status_key) if status_key else "",
                "",
            ),
        )
        self.items[key] = item
        self.posts[item] = post
        self.item_status_keys[item] = status_key
        return item

    def _set_row(
        self,
        post: Post,
        status_key: str | None = None,
        progress: str | None = None,
    ) -> None:
        item = self._row(post, status_key or "")
        if not item:
            return
        values = list(
            self.queue_view.item(
                item,
                "values",
            )
        )
        if status_key is not None:
            self.item_status_keys[item] = status_key
            values[4] = self._t(status_key)
        if progress is not None:
            values[5] = progress
        self.queue_view.item(
            item,
            values=values,
        )

    def _update_stats(self, data: dict | None) -> None:
        if data:
            self._last_stats = {
                "seen": int(data.get("seen", 0)),
                "accepted": int(data.get("accepted", 0)),
                "downloaded": int(data.get("downloaded", 0)),
                "failed": int(data.get("failed", 0)),
            }
            self._render_stats()

    def _runner_event(
        self,
        event: str,
        payload: dict,
    ) -> None:
        self._update_stats(payload.get("stats"))
        post = payload.get("post")

        if event == "destination":
            self.last_destination = Path(
                payload["path"]
            )
        elif event == "searching":
            label = (
                payload.get("label")
                or provider_label(
                    payload.get("provider", "")
                )
            )
            self._set_status(
                "status.searching",
                provider=label,
            )
        elif isinstance(post, Post):
            states = {
                "post_accepted": ("row.accepted", None),
                "download_queued": ("row.queued", "0 %"),
                "download_started": ("row.downloading", "0 %"),
                "download_finished": ("row.saved", "100 %"),
                "download_exists": (
                    "row.existing",
                    "100 %",
                ),
                "download_failed": ("row.error", "—"),
                "download_cancelled": ("row.cancelled", "—"),
                "dry_run": (
                    "row.dry_run",
                    "—",
                ),
            }
            if event == "download_progress":
                if payload.get("total"):
                    progress = (
                        f"{int(payload.get('percent') or 0)} %"
                    )
                else:
                    progress = (
                        f"{int(payload.get('received') or 0) // 1024} KiB"
                    )
                self._set_row(
                    post,
                    "row.downloading",
                    progress,
                )
            elif event in states:
                self._set_row(
                    post,
                    *states[event],
                )

        if event == "run_finished":
            self._set_status(
                "status.cancelled"
                if payload.get("cancelled")
                else "status.finished"
            )
        elif event == "provider_error":
            label = (
                payload.get("label")
                or provider_label(
                    payload.get("provider", "")
                )
            )
            self._set_status(
                "status.provider_error",
                provider=label,
            )

    def _select(self, _e=None) -> None:
        selection = self.queue_view.selection()
        post = (
            self.posts.get(selection[0])
            if selection
            else None
        )
        if not post:
            return

        self.selected_post = post
        self.open_post_btn.configure(
            state=(
                "normal"
                if post.post_url
                else "disabled"
            )
        )
        self._refresh_selected_post_info()
        self._load_preview(post)

    def _refresh_selected_post_info(self) -> None:
        post = self.selected_post
        if not post:
            self.preview_info.set("")
            return
        tags = " ".join(post.tags.split())
        if len(tags) > 180:
            tags = tags[:179] + "…"
        self.preview_info.set(
            self._t(
                "preview.info",
                provider=provider_label(post.provider),
                post_id=post.post_id,
                width=post.width,
                height=post.height,
                rating=post.rating or "—",
                tags=tags,
            )
        )

    def _load_preview(self, post: Post) -> None:
        key = self._key(post)
        self.preview_key = key
        self.preview_photo = None
        self.preview_label.configure(
            image="",
            text=self._t("preview.loading"),
        )
        url = post.preview_url or post.file_url
        if not url:
            self.preview_label.configure(
                text=self._t("preview.none")
            )
            return

        def work():
            try:
                response = requests.get(
                    url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Referer": provider_referer(
                            post.provider
                        ),
                    },
                    timeout=(8, 25),
                )
                response.raise_for_status()
                if len(response.content) > 15 * 1024 * 1024:
                    raise ValueError(
                        "preview too large"
                    )
                self.events.put(
                    (
                        "preview",
                        {
                            "key": key,
                            "data": response.content,
                        },
                    )
                )
            except Exception as exc:
                self.events.put(
                    (
                        "preview_error",
                        {
                            "key": key,
                            "error": str(exc),
                        },
                    )
                )

        threading.Thread(
            target=work,
            daemon=True,
        ).start()

    def _show_preview(self, payload: dict) -> None:
        if payload.get("key") != self.preview_key:
            return
        try:
            image = Image.open(
                BytesIO(payload["data"])
            )
            image.thumbnail(
                self.PREVIEW_SIZE,
                Image.Resampling.LANCZOS,
            )
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            self.preview_photo = ImageTk.PhotoImage(
                image
            )
            self.preview_label.configure(
                image=self.preview_photo,
                text="",
            )
        except Exception:
            self.preview_label.configure(
                image="",
                text=self._t("preview.unavailable"),
            )

    def _show_about(self) -> None:
        if (
            self._about_window is not None
            and self._about_window.winfo_exists()
        ):
            self._about_window.lift()
            self._about_window.focus_force()
            return

        window = tk.Toplevel(self)
        self._about_window = window
        window.title(self._t("about.title"))
        window.transient(self)
        window.resizable(False, False)
        if hasattr(self, "_icon"):
            try:
                window.iconphoto(True, self._icon)
            except tk.TclError:
                pass

        frame = ttk.Frame(window, padding=20)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="BooruGet",
            font=("Segoe UI", 18, "bold"),
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
        )
        ttk.Label(
            frame,
            text=self._t("about.description"),
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(2, 14),
        )
        ttk.Label(
            frame,
            text=f'{self._t("about.coded_by")} NetDaemon',
            font=("Segoe UI", 10, "bold"),
        ).grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
        )

        self._about_link(
            frame,
            3,
            "about.website",
            ABOUT_LINKS["website"],
        )
        self._about_link(
            frame,
            4,
            "about.github",
            ABOUT_LINKS["github"],
        )
        self._about_link(
            frame,
            5,
            "about.project",
            ABOUT_LINKS["project"],
        )

        ttk.Separator(
            frame,
            orient="horizontal",
        ).grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=12,
        )

        ttk.Label(
            frame,
            text=(
                f'{self._t("about.original_idea")}: '
                "fhrach4"
            ),
            font=("Segoe UI", 10, "bold"),
        ).grid(
            row=7,
            column=0,
            columnspan=2,
            sticky="w",
        )
        self._about_link(
            frame,
            8,
            "about.original_project",
            ABOUT_LINKS["original_project"],
        )

        ttk.Separator(
            frame,
            orient="horizontal",
        ).grid(
            row=9,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=12,
        )

        ttk.Label(
            frame,
            text=self._t("about.version"),
        ).grid(
            row=10,
            column=0,
            sticky="w",
        )
        ttk.Label(
            frame,
            text=__version__,
        ).grid(
            row=10,
            column=1,
            sticky="w",
            padx=(12, 0),
        )

        ttk.Button(
            frame,
            text=self._t("about.close"),
            command=window.destroy,
        ).grid(
            row=11,
            column=0,
            columnspan=2,
            sticky="e",
            pady=(16, 0),
        )
        window.protocol(
            "WM_DELETE_WINDOW",
            window.destroy,
        )
        window.bind(
            "<Destroy>",
            lambda _e: self._clear_about_reference(window),
        )

        window.update_idletasks()
        x = self.winfo_rootx() + (
            self.winfo_width() - window.winfo_width()
        ) // 2
        y = self.winfo_rooty() + (
            self.winfo_height() - window.winfo_height()
        ) // 2
        window.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _about_link(
        self,
        parent,
        row: int,
        label_key: str,
        url: str,
    ) -> None:
        ttk.Label(
            parent,
            text=self._t(label_key),
        ).grid(
            row=row,
            column=0,
            sticky="w",
            pady=2,
        )
        ttk.Button(
            parent,
            text=url,
            command=lambda target=url: webbrowser.open(
                target,
                new=2,
            ),
        ).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(12, 0),
            pady=2,
        )

    def _clear_about_reference(
        self,
        window: tk.Toplevel,
    ) -> None:
        if self._about_window is window:
            self._about_window = None

    def _open_post(self) -> None:
        if (
            self.selected_post
            and self.selected_post.post_url
        ):
            webbrowser.open(
                self.selected_post.post_url,
                new=2,
            )

    def _pump(self) -> None:
        try:
            while True:
                event, payload = (
                    self.events.get_nowait()
                )
                if event == "log":
                    self.log.insert(
                        "end",
                        str(payload) + "\n",
                    )
                    self.log.see("end")
                elif event == "done":
                    self.progress.stop()
                    self.start_btn.configure(
                        state="normal"
                    )
                    self.search_btn.configure(
                        state="normal"
                    )
                    self.cancel_btn.configure(
                        state="disabled"
                    )
                    if self._status_key not in {
                        "status.finished",
                        "status.cancelled",
                    }:
                        self._set_status("status.ready")
                elif event == "fatal":
                    self._set_status("status.error")
                elif event == "preview":
                    self._show_preview(payload)
                elif (
                    event == "preview_error"
                    and payload.get("key")
                    == self.preview_key
                ):
                    self.preview_label.configure(
                        image="",
                        text=self._t("preview.unavailable"),
                    )
                elif isinstance(payload, dict):
                    self._runner_event(
                        event,
                        payload,
                    )
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def _clear(self) -> None:
        for item in self.queue_view.get_children():
            self.queue_view.delete(item)
        self.items.clear()
        self.posts.clear()
        self.item_status_keys.clear()
        self.selected_post = None
        self.preview_key = ""
        self.preview_photo = None
        self.preview_label.configure(
            image="",
            text=self._t("preview.select"),
        )
        self.preview_info.set("")
        self.open_post_btn.configure(
            state="disabled"
        )

    def _close(self) -> None:
        if (
            self.worker
            and self.worker.is_alive()
            and not messagebox.askyesno(
                self._t("dialog.close_title"),
                self._t("dialog.close_question"),
                parent=self,
            )
        ):
            return
        self.cancel_event.set()
        self._save_settings()
        self.destroy()


def launch_gui(config_path: str = DEFAULT_CONFIG) -> None:
    BooruGetGUI(config_path).mainloop()
