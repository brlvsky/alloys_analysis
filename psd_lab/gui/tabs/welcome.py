"""Стартовая страница: что открыть, последние файлы, подсказка о форматах."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ... import APP_NAME, __version__
from .. import theme
from ..widgets import PanelTitle, groupbox, scrolled


TIPS = [
    "Наведите мышь на любой график — появится подсказка со значениями в этой точке.",
    "Флажки в списке слева включают и выключают образцы в сравнении, сводке и отчёте.",
    "Клавиша F2 переименовывает образец, а «Вид → Усреднять повторы» отключает усреднение.",
    "Строки сводки можно выделить и нажать Ctrl+C — они вставятся в Excel с десятичной запятой.",
    "Кнопка «Отчёт» делает один файл report.html — его можно сразу отправить руководителю.",
    "Красный значок у образца — отрицательная обскурация: фон был записан неверно, измерение лучше повторить.",
    "Кривые никогда не растягиваются до 100 %: если кривая не доходит до 100 %, программа это покажет.",
    "Вкладка «Популяции» раскладывает распределение на группы частиц — так видно, сколько у порошка «мелочи».",
    "«Анализ → Структура — свойства» строит график любых двух величин из базы, например d50 и прочности.",
    "Резервная копия всех данных — это просто копия папки PSD-Lab-data рядом с программой.",
    "Если интерфейс мелкий или крупный — «Вид → Масштаб интерфейса».",
    "На вкладке «Методика» есть чек-лист качества: его отметки видны в сводке в колонке QC.",
]


class WelcomePanel(tk.Frame):
    def __init__(self, parent, on_open_files, on_open_folder, on_open_examples, on_open_recent):
        super().__init__(parent, background=theme.FACE)
        self.on_open_recent = on_open_recent
        PanelTitle(self, "Начало работы").pack(fill="x")
        body = tk.Frame(self, background=theme.FACE, padx=theme.px(16), pady=theme.px(12))
        body.pack(fill="both", expand=True)

        head = tk.Frame(body, background=theme.FACE)
        head.pack(fill="x", pady=(0, theme.px(12)))
        tk.Label(head, image=theme.load_icon(self, "app", theme.toolbar_px())).pack(side="left", padx=(0, theme.px(12)))
        txt = tk.Frame(head, background=theme.FACE)
        txt.pack(side="left")
        tk.Label(txt, text=f"{APP_NAME} {__version__}", font=theme.FONTS["big"]).pack(anchor="w")
        tk.Label(txt, text="Анализ гранулометрии порошков: графики, сводка, отчёт для руководителя.").pack(anchor="w")

        cols = tk.Frame(body, background=theme.FACE)
        cols.pack(fill="both", expand=True)
        g = groupbox(cols, "Открыть данные")
        g.pack(side="left", fill="y", anchor="n", padx=(0, theme.px(12)))
        for icon, text, cmd in (("open", "Открыть файлы…", on_open_files),
                                ("open_dir", "Открыть папку…", on_open_folder),
                                ("sample", "Открыть примеры", on_open_examples)):
            ttk.Button(g, text="  " + text, image=theme.load_icon(self, icon, 2 * theme.icon_px()),
                       compound="left", style="Big.TButton", command=cmd).pack(fill="x", pady=(0, theme.px(8)))
        tk.Label(g, text="Понимает экспорт прибора Fritsch (.xls)\nи таблицы Excel / CSV / TXT:\n"
                         "столбец размеров + накопленная доля\nили доли по интервалам.",
                 justify="left").pack(anchor="w", pady=(theme.px(8), 0))

        side = tk.Frame(cols, background=theme.FACE)
        side.pack(side="left", fill="both", expand=True, anchor="n")
        # «Знаете ли вы…?» — как в окне приветствия Windows 95
        tip = groupbox(side, "Знаете ли вы…?")
        tip.pack(fill="x", pady=(0, theme.px(10)))
        tk.Label(tip, image=theme.load_icon(self, "bulb", 2 * theme.icon_px())).pack(side="left", anchor="n",
                                                                                     padx=(0, theme.px(10)))
        box = tk.Frame(tip, background=theme.FIELD, relief="sunken", borderwidth=2)
        box.pack(side="left", fill="both", expand=True)
        self.tip = tk.Label(box, background=theme.FIELD, justify="left", anchor="nw", wraplength=theme.px(520),
                            padx=theme.px(8), pady=theme.px(8), height=3)
        self.tip.pack(fill="both", expand=True)
        ttk.Button(tip, text="Следующий совет", command=self.next_tip).pack(side="left", anchor="s",
                                                                            padx=(theme.px(10), 0))
        import random

        self._tip_i = random.randrange(len(TIPS))
        self.next_tip(advance=False)
        box.bind("<Configure>", lambda e: self.tip.configure(wraplength=max(200, e.width - theme.px(20))))

        r = groupbox(side, "Последние файлы (двойной щелчок — открыть)")
        r.pack(fill="both", expand=True)
        frame, self.recent = scrolled(r, tk.Listbox, height=10, relief="flat", borderwidth=0,
                                      activestyle="none", font=theme.FONTS["ui"])
        frame.pack(fill="both", expand=True)
        self.recent.bind("<Double-Button-1>", self._open_selected)
        self.recent.bind("<Return>", self._open_selected)
        self._paths: list[str] = []

    def next_tip(self, advance=True):
        if advance:
            self._tip_i = (self._tip_i + 1) % len(TIPS)
        self.tip.configure(text=TIPS[self._tip_i])

    def set_recent(self, paths: list[str]):
        self.recent.delete(0, "end")
        self._paths = list(paths)
        if not paths:
            self.recent.insert("end", "  (пока пусто)")
            return
        for p in paths:
            pp = Path(p)
            self.recent.insert("end", f"  {pp.name}    —    {pp.parent}")

    def _open_selected(self, _e=None):
        sel = self.recent.curselection()
        if sel and sel[0] < len(self._paths):
            self.on_open_recent(self._paths[sel[0]])
