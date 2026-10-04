"""Сервис → Настройки."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from ...core.settings import Settings, data_dir, format_windows, parse_windows
from .. import theme
from ..widgets import Dialog, groupbox


def _num_or_none(text: str, what: str):
    text = text.strip().replace(",", ".")
    if not text:
        return None
    v = float(text)
    if v <= 0:
        raise ValueError(f"{what}: нужно положительное число")
    return v


class SettingsDialog(Dialog):
    def __init__(self, parent, settings: Settings):
        super().__init__(parent, "Настройки")
        self.st = settings
        b = self.body

        g = groupbox(b, "Графики для экспорта")
        g.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        self.lang = tk.StringVar(value=settings.lang)
        tk.Label(g, text="Подписи осей:").grid(row=0, column=0, sticky="w")
        tk.Radiobutton(g, text="English (Size, μm)", variable=self.lang, value="en").grid(row=0, column=1, sticky="w")
        tk.Radiobutton(g, text="Русский (Размер, мкм)", variable=self.lang, value="ru").grid(row=1, column=1, sticky="w")
        tk.Label(g, text="Ширина столбика, мкм:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.bin = tk.Entry(g, width=10)
        self.bin.insert(0, "" if settings.bin_um is None else f"{settings.bin_um:g}")
        self.bin.grid(row=2, column=1, sticky="w", pady=(6, 0))
        tk.Label(g, text="(пусто — шаг сетки)", foreground=theme.SHADOW).grid(row=3, column=1, sticky="w")
        tk.Label(g, text="Предел оси X, мкм:").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.xmax = tk.Entry(g, width=10)
        self.xmax.insert(0, "" if settings.xmax is None else f"{settings.xmax:g}")
        self.xmax.grid(row=4, column=1, sticky="w", pady=(6, 0))
        tk.Label(g, text="(пусто — по d99)", foreground=theme.SHADOW).grid(row=5, column=1, sticky="w")
        self.show_name = tk.BooleanVar(value=settings.show_name)
        self.shared = tk.BooleanVar(value=not settings.independent_axes)
        tk.Checkbutton(g, text="Название образца в рамке", variable=self.show_name).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))
        tk.Checkbutton(g, text="Одинаковые оси у образцов одного файла", variable=self.shared).grid(
            row=7, column=0, columnspan=2, sticky="w")

        g2 = groupbox(b, "Расчёт")
        g2.grid(row=0, column=1, sticky="nsew", pady=(0, 6))
        tk.Label(g2, text="Окна долей, мкм:").grid(row=0, column=0, sticky="w")
        self.windows = tk.Entry(g2, width=34)
        self.windows.insert(0, format_windows(settings.windows))
        self.windows.grid(row=1, column=0, columnspan=2, sticky="w")
        tk.Label(g2, text="например: <15; 15-45; 15-53; 45-105; >53", foreground=theme.SHADOW).grid(
            row=2, column=0, columnspan=2, sticky="w")
        tk.Label(g2, text="Плотность материала, г/см³:").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.rho = tk.Entry(g2, width=8)
        self.rho.insert(0, f"{settings.density_g_cm3:g}")
        self.rho.grid(row=3, column=1, sticky="w", pady=(6, 0))
        self.average = tk.BooleanVar(value=settings.average)
        tk.Checkbutton(g2, text="Усреднять повторы с одинаковым названием", variable=self.average).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        g3 = groupbox(b, "Программа")
        g3.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.splash = tk.BooleanVar(value=settings.splash)
        tk.Checkbutton(g3, text="Показывать заставку при запуске", variable=self.splash).grid(row=0, column=0, sticky="w")
        tk.Label(g3, text="Папка данных:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        e = tk.Entry(g3, width=70)
        e.insert(0, str(data_dir()))
        e.configure(state="readonly", readonlybackground=theme.FACE)
        e.grid(row=2, column=0, sticky="we")

    def on_ok(self):
        try:
            bin_um = _num_or_none(self.bin.get(), "Ширина столбика")
            xmax = _num_or_none(self.xmax.get(), "Предел оси X")
            windows = parse_windows(self.windows.get())
            rho = _num_or_none(self.rho.get(), "Плотность")
        except ValueError as e:
            messagebox.showerror("Настройки", f"Проверьте значения.\n\n{e}", parent=self)
            return
        st = self.st
        st.lang, st.bin_um, st.xmax, st.windows = self.lang.get(), bin_um, xmax, windows
        st.density_g_cm3 = rho or 4.0
        st.show_name, st.independent_axes = self.show_name.get(), not self.shared.get()
        st.average, st.splash = self.average.get(), self.splash.get()
        self.result = True
        self.destroy()

