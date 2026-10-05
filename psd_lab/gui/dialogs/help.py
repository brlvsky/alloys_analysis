"""Справка → Руководство пользователя: окно в духе справки Windows 95 — слева «Содержание», справа текст.

Текст — README.md программы (раздел «Для разработчика» не показывается). В exe README кладётся рядом с
ресурсами при сборке.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ... import APP_NAME
from ...core.settings import resource_dir
from .. import theme
from ..tabs.method import render_markdown, setup_text_tags
from ..widgets import PanelTitle, center_on, scrolled

DEV_SECTION = "## Для разработчика"


def guide_text() -> str:
    for base in (resource_dir(), resource_dir().parent):
        p = base / "README.md"
        if p.exists():
            md = p.read_text(encoding="utf-8")
            return md.split(DEV_SECTION, 1)[0].rstrip() + "\n"
    return "# Руководство\n\nФайл README.md не найден рядом с программой."


class HelpWindow(tk.Toplevel):
    _instance = None

    @classmethod
    def show(cls, parent, topic: str | None = None):
        """Одно окно справки на программу: повторный вызов поднимает уже открытое."""
        if cls._instance is not None and cls._instance.winfo_exists():
            w = cls._instance
            w.deiconify()
            w.lift()
        else:
            w = cls._instance = cls(parent)
        if topic:
            w.goto(topic)
        return w

    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.title(f"Справка {APP_NAME}")
        self.configure(background=theme.FACE)
        try:
            self.iconphoto(False, theme.load_icon(self, "help", 32))
        except tk.TclError:
            pass
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=theme.px(4), pady=(theme.px(4), 0))

        left = tk.Frame(pw, background=theme.FACE)
        PanelTitle(left, "Содержание").pack(fill="x")
        frame, self.toc = scrolled(left, tk.Listbox, activestyle="none", exportselection=False,
                                   relief="flat", borderwidth=0, width=40)
        frame.pack(fill="both", expand=True)
        pw.add(left, weight=0)

        right = tk.Frame(pw, background=theme.FACE)
        self.title_bar = PanelTitle(right, "Руководство пользователя")
        self.title_bar.pack(fill="x")
        frame, self.text = scrolled(right, tk.Text, wrap="word", relief="flat", borderwidth=0,
                                    padx=theme.px(12), pady=theme.px(8), background=theme.FIELD, cursor="arrow",
                                    spacing1=theme.px(1), spacing3=theme.px(2))
        frame.pack(fill="both", expand=True)
        setup_text_tags(self.text)
        pw.add(right, weight=1)

        bar = tk.Frame(self, background=theme.FACE, padx=theme.px(8), pady=theme.px(8))
        bar.pack(fill="x")
        ttk.Button(bar, text="Закрыть", command=self.destroy, default="active").pack(side="right")
        tk.Label(bar, text="Щёлкните раздел слева, чтобы перейти к нему.", foreground=theme.SHADOW).pack(
            side="left")

        self.heads = render_markdown(self.text, guide_text())
        self._flag_icons()
        for lvl, title, _ in self.heads:
            if lvl == 1:
                continue
            self.toc.insert("end", ("    " if lvl == 3 else "") + title)
        self._toc_heads = [h for h in self.heads if h[0] != 1]
        self.toc.bind("<<ListboxSelect>>", self._on_toc)
        self.bind("<Escape>", lambda e: self.destroy())

        self.geometry(f"{min(theme.px(1000), self.winfo_screenwidth() - 60)}x"
                      f"{min(theme.px(680), self.winfo_screenheight() - 100)}")
        center_on(self, parent)
        self.deiconify()

    def _flag_icons(self):
        """Настоящие значки флагов перед словами «красный круг», «жёлтый треугольник», «синий круг»."""
        t = self.text
        t.configure(state="normal")
        for phrase, icon in (("красный круг", "flag_error"), ("жёлтый треугольник", "flag_warn"),
                             ("синий круг", "flag_info")):
            start = "1.0"
            while True:
                pos = t.search(phrase, start, stopindex="end")
                if not pos:
                    break
                t.image_create(pos, image=theme.load_icon(self, icon), padx=theme.px(2))
                start = f"{pos}+{len(phrase) + 1}c"
        t.configure(state="disabled")

    def _on_toc(self, _e=None):
        sel = self.toc.curselection()
        if sel:
            self.text.see(self._toc_heads[sel[0]][2])
            self.text.yview(self._toc_heads[sel[0]][2])

    def goto(self, topic: str) -> bool:
        """Перейти к разделу, в названии которого есть topic (например, «Флаги»)."""
        for i, (_, title, mark) in enumerate(self._toc_heads):
            if topic.lower() in title.lower():
                self.toc.selection_clear(0, "end")
                self.toc.selection_set(i)
                self.toc.see(i)
                self.text.yview(mark)
                return True
        return False
