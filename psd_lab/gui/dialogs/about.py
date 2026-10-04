"""Справка → О программе; заставка при запуске."""
from __future__ import annotations

import platform
import tkinter as tk

from ... import APP_NAME, PROJECT, __version__
from .. import theme
from ..widgets import Dialog


def library_versions() -> str:
    import matplotlib
    import numpy
    import openpyxl
    import pandas
    import PIL
    import scipy
    import xlrd

    libs = [("numpy", numpy), ("scipy", scipy), ("pandas", pandas), ("matplotlib", matplotlib),
            ("xlrd", xlrd), ("openpyxl", openpyxl), ("Pillow", PIL)]
    return ", ".join(f"{n} {getattr(m, '__version__', '?')}" for n, m in libs)


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
    """Серое окно с тёмно-синей полосой: «PSD-Lab для Windows, версия 1.0 / Загрузка модулей…»."""

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.overrideredirect(True)
        self.configure(background=theme.FACE, relief="raised", borderwidth=2)
        bar = tk.Frame(self, background=theme.TITLE_BG)
        bar.pack(fill="x", padx=2, pady=2)
        tk.Label(bar, text=APP_NAME, background=theme.TITLE_BG, foreground=theme.TITLE_FG,
                 font=theme.FONTS["big"], padx=10, pady=6).pack(side="left")
        body = tk.Frame(self, background=theme.FACE, padx=16, pady=12)
        body.pack(fill="both", expand=True)
        tk.Label(body, image=theme.load_icon(self, "app", 32)).pack(side="left", padx=(0, 14))
        right = tk.Frame(body, background=theme.FACE)
        right.pack(side="left", fill="both")
        tk.Label(right, text=f"{APP_NAME} для Windows, версия {__version__}", font=theme.FONTS["bold"]).pack(anchor="w")
        tk.Label(right, text="Анализ гранулометрии порошков").pack(anchor="w")
        self.status = tk.Label(right, text="Загрузка модулей…")
        self.status.pack(anchor="w", pady=(10, 0))
        self.update_idletasks()
        w, h = max(380, self.winfo_reqwidth()), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.lift()
