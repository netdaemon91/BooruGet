"""Resizable image viewer; workers only communicate through a queue."""
from __future__ import annotations

from io import BytesIO
import queue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

import requests
from PIL import Image, ImageTk, ImageOps

from .providers import USER_AGENT, provider_referer, provider_label

MAX_IMAGE_BYTES = 40 * 1024 * 1024


def fetch_image(post):
    """Try the original first, then a thumbnail for videos/unsupported files."""
    for url in dict.fromkeys((post.file_url, post.preview_url)):
        if not url:
            continue
        try:
            with requests.get(url, headers={"User-Agent": USER_AGENT,
                              "Referer": provider_referer(post.provider)},
                              timeout=(8, 25), stream=True) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    data.extend(chunk)
                    if len(data) > MAX_IMAGE_BYTES:
                        raise ValueError("Image exceeds preview limit")
            with Image.open(BytesIO(data)) as source:
                image = ImageOps.exif_transpose(source)
                image.load()
                return image.convert("RGBA"), url != post.file_url
        except (requests.RequestException, OSError, ValueError, Image.DecompressionBombError):
            continue
    raise ValueError("No displayable image")


class ImageViewer(tk.Toplevel):
    def __init__(self, master, get_entries, select_entry, translate):
        super().__init__(master)
        self.get_entries = get_entries
        self.select_entry = select_entry
        self.t = translate
        self.entry = None
        self.post = None
        self.image = None
        self.photo = None
        self.token = 0
        self.fallback = False
        self.pending = queue.Queue()
        self.resize_job = None
        self.geometry("1000x760")
        self.minsize(480, 360)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background="#151515", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._resize)
        self.info = tk.StringVar()
        ttk.Label(self, textvariable=self.info, anchor="center").grid(row=1, column=0, sticky="ew", pady=6)
        bar = ttk.Frame(self, padding=8)
        bar.grid(row=2, column=0, sticky="ew")
        self.previous = ttk.Button(bar, command=lambda: self.move(-1))
        self.previous.pack(side="left")
        self.next = ttk.Button(bar, command=lambda: self.move(1))
        self.next.pack(side="left", padx=8)
        self.open_button = ttk.Button(bar, command=self._open)
        self.open_button.pack(side="right")
        self.bind("<Left>", lambda event: self.move(-1))
        self.bind("<Right>", lambda event: self.move(1))
        self.bind("<Escape>", lambda event: self.destroy())
        self.poll_job = self.after(80, self._poll)

    def show(self, entry):
        entries = self.get_entries()
        if entry not in entries:
            return
        self.entry = entry
        self.post = entries[entry]
        self.token += 1
        token = self.token
        self.image = self.photo = None
        self.fallback = False
        self._controls()
        self._message(self.t("preview.loading"))
        post = self.post

        def worker():
            try:
                image, fallback = fetch_image(post)
                self.pending.put((token, image, fallback))
            except Exception:
                self.pending.put((token, None, False))
        threading.Thread(target=worker, daemon=True).start()
        self.lift()
        self.focus_set()

    def _controls(self):
        entries = list(self.get_entries())
        index = entries.index(self.entry) if self.entry in entries else -1
        self.previous.configure(text=self.t("viewer.previous"), state="normal" if index > 0 else "disabled")
        self.next.configure(text=self.t("viewer.next"), state="normal" if 0 <= index < len(entries)-1 else "disabled")
        self.open_button.configure(text=self.t("button.open_post"), state="normal" if self.post and self.post.post_url else "disabled")
        self.title(self.t("viewer.title"))
        if self.post:
            self.info.set(f"{index+1} / {len(entries)} · {provider_label(self.post.provider)} #{self.post.post_id} · {self.post.width}×{self.post.height}")
            if self.fallback:
                self.info.set(self.info.get() + " · " + self.t("viewer.thumbnail"))

    def move(self, offset):
        entries = list(self.get_entries())
        if self.entry in entries:
            index = entries.index(self.entry) + offset
            if 0 <= index < len(entries):
                self.select_entry(entries[index])
                self.show(entries[index])
        return "break"

    def _open(self):
        if self.post and self.post.post_url:
            webbrowser.open(self.post.post_url)

    def _message(self, text):
        self.canvas.delete("all")
        self.canvas.create_text(self.canvas.winfo_width()/2, self.canvas.winfo_height()/2,
                                text=text, fill="white", tags="message")

    def _resize(self, event=None):
        if self.resize_job:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(100, self._render)

    def _render(self):
        self.resize_job = None
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.image is None:
            self.canvas.coords("message", width/2, height/2)
            return
        fitted = ImageOps.contain(self.image, (max(1, width-20), max(1, height-20)), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(fitted, master=self)
        self.canvas.delete("all")
        self.canvas.create_image(width/2, height/2, image=self.photo)

    def _poll(self):
        try:
            while True:
                token, image, fallback = self.pending.get_nowait()
                if token != self.token:
                    continue
                self.image = image
                self.fallback = fallback
                if image is None:
                    self._message(self.t("preview.unavailable"))
                else:
                    self._render()
                    self._controls()
        except queue.Empty:
            pass
        self._controls_if_changed()
        self.poll_job = self.after(80, self._poll)

    def _controls_if_changed(self):
        signature = (tuple(self.get_entries()), self.t("viewer.title"))
        if signature != getattr(self, "_signature", None):
            self._signature = signature
            self._controls()

    def destroy(self):
        self.token += 1
        if self.resize_job:
            self.after_cancel(self.resize_job)
        self.after_cancel(self.poll_job)
        super().destroy()
