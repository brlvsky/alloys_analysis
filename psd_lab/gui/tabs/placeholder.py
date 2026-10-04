"""Заглушки вкладок модулей, которые появятся на следующих этапах."""
from __future__ import annotations

import tkinter as tk

from .. import theme
from ..widgets import PanelTitle, groupbox

PLANNED = {
    "Популяции": ("М2. Популяции частиц", 5,
                  "Разложение распределения на 1–3 логнормальные популяции: доля, медиана и σ каждой."),
    "Технология": ("М3+М4. Технология и выход годного", 5,
                   "Доли в окнах СЛС (15–45, 15–53, 20–63 мкм) и СЭЛС (45–105, 45–150 мкм), выход годного после рассева."),
    "Поверхность": ("М5. Удельная поверхность", 5,
                    "Удельная поверхность по D[3,2] и вклад мелкой фракции в поверхность (риск по кислороду)."),
    "Упаковка": ("М6. Упаковка слоя", 7,
                 "Оценка плотности упаковки бимодальной смеси (линейная модель Yu–Standish)."),
    "Кинетика": ("М9. Кинетика помола", 7,
                 "Изменение d10/d50/d90 от времени обработки (данные 6/8/10 ч)."),
    "База данных": ("М1. База «структура — свойства»", 6,
                    "Партии, измерения, СЭМ, РФА, химанализ, режимы печати и механические испытания."),
    "Методика": ("М8. Методика измерения", 8,
                 "Методика лазерной дифракции и чек-лист качества для каждого измерения."),
}


class PlaceholderTab(tk.Frame):
    def __init__(self, parent, name):
        super().__init__(parent, background=theme.FACE)
        title, stage, text = PLANNED[name]
        PanelTitle(self, title).pack(fill="x")
        g = groupbox(self, "Модуль в разработке")
        g.pack(anchor="nw", padx=12, pady=12)
        tk.Label(g, image=theme.load_icon(self, "flag_info")).grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 8))
        tk.Label(g, text=text, justify="left", wraplength=460).grid(row=0, column=1, sticky="w")
        tk.Label(g, text=f"Появится на этапе {stage}.", foreground=theme.SHADOW).grid(row=1, column=1, sticky="w", pady=(6, 0))
