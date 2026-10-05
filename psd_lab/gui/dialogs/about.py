"""Справка → О программе; заставка при запуске."""
from __future__ import annotations

import platform
import tkinter as tk

from ... import APP_NAME, PROJECT, __version__
from .. import theme
from ..widgets import ChunkProgress, Dialog


def library_versions() -> str:
    import importlib

    out = []
    for name, mod in (("numpy", "numpy"), ("scipy", "scipy"), ("matplotlib", "matplotlib"),
                      ("xlrd", "xlrd"), ("openpyxl", "openpyxl"), ("Pillow", "PIL")):
        try:
            out.append(f"{name} {importlib.import_module(mod).__version__}")
        except Exception:  # noqa: BLE001 — модуль может быть исключён из сборки
            pass
    return ", ".join(out)


class AboutDialog(Dialog):
    def __init__(self, parent):
        super().__init__(parent, f"О программе {APP_NAME}", buttons=("OK",))
        b = self.body
        tk.Label(b, image=theme.load_icon(self, "app", 32)).grid(row=0, column=0, rowspan=6, sticky="n", padx=(0, 14))
        tk.Label(b, text=f"{APP_NAME} для Windows", font=theme.FONTS["bold"]).grid(row=0, column=1, sticky="w")
        tk.Label(b, text=f"Версия {__version__}").grid(row=1, column=1, sticky="w")
        tk.Label(b, text="Анализ гранулометрического состава порошков\n(лазерная дифракция, Fritsch ANALYSETTE 22)",
                 justify="left").grid(row=2, column=1, sticky="w", pady=(6, 0))
        tk.Label(b, text=f"Проект: «{PROJECT}»\nРуководитель: Г. М. Марков", justify="left",
                 wraplength=380).grid(row=3, column=1, sticky="w", pady=(6, 0))
        tk.Frame(b, height=2, relief="groove", borderwidth=1).grid(row=4, column=1, sticky="we", pady=8)
        tk.Label(b, text=f"Python {platform.python_version()}, Tk {tk.TkVersion}\n{library_versions()}",
                 justify="left", wraplength=380).grid(row=5, column=1, sticky="w")


class Splash(tk.Toplevel):
    """Заставка: тёмно-синяя полоса с названием, значок, «Загрузка модулей…» и блочный индикатор."""

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.overrideredirect(True)
        self.configure(background=theme.FACE, relief="raised", borderwidth=2)
        w = theme.px(420)
        bar_h = theme.px(46)
        c = tk.Canvas(self, width=w, height=bar_h, highlightthickness=0, borderwidth=0, background=theme.TITLE_BG)
        c.pack(fill="x", padx=2, pady=2)
        c.create_text(theme.px(12), bar_h // 2, text=APP_NAME, anchor="w", fill="white", font=theme.FONTS["big"])
        c.create_text(w - theme.px(12), bar_h // 2, text=f"версия {__version__}", anchor="e", fill="white",
                      font=theme.FONTS["ui"])
        body = tk.Frame(self, background=theme.FACE, padx=theme.px(16), pady=theme.px(12))
        body.pack(fill="both", expand=True)
        tk.Label(body, image=theme.load_icon(self, "app", 64 if theme.SCALE["total"] >= 1.5 else 32)).pack(
            side="left", padx=(0, theme.px(16)), anchor="n")
        right = tk.Frame(body, background=theme.FACE)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text=f"{APP_NAME} для Windows, версия {__version__}", font=theme.FONTS["bold"]).pack(anchor="w")
        tk.Label(right, text="Анализ гранулометрии порошков\nдля аддитивного производства", justify="left").pack(
            anchor="w")
        self.status = tk.Label(right, text="Загрузка модулей…")
        self.status.pack(anchor="w", pady=(theme.px(10), theme.px(4)))
        self.bar = ChunkProgress(right, width=theme.px(260), height=theme.px(16))
        self.bar.pack(anchor="w")
        self.update_idletasks()
        sw, sh = self.winfo_reqwidth(), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - sw) // 2
        y = (self.winfo_screenheight() - sh) // 3
        self.geometry(f"+{x}+{y}")
        self.lift()
        self._step = 0
        self.after(60, self._tick)

    def _tick(self):
        if not self.winfo_exists():
            return
        self._step += 1
        self.bar.set(min(1.0, self._step / 14))
        msgs = ["Загрузка модулей…", "Чтение настроек…", "Подготовка графиков…", "Открытие базы данных…"]
        self.status.configure(text=msgs[min(len(msgs) - 1, self._step // 4)])
        if self._step < 14:
            self.after(60, self._tick)
