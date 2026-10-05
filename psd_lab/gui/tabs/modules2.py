"""Вкладки М6 (Упаковка) и М9 (Кинетика помола)."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from ...core import deconv, kinetics, packing
from ...core.plots import draw_kinetics, draw_packing
from .. import theme
from ..widgets import NoteBox, PanelTitle, ReadoutBar, Table, groupbox
from .modules import _empty, c
from .plot_panel import PlotPanel


# ==================================================================== М6
class PackingTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, background=theme.FACE)
        self.app = app
        ctl = tk.Frame(self, background=theme.FACE)
        ctl.pack(fill="x", pady=theme.px(4))
        tk.Label(ctl, text="Плотность упаковки монофракции φ₀:").pack(side="left", padx=(theme.px(4), theme.px(4)))
        self.phi0 = tk.Entry(ctl, width=6)
        self.phi0.insert(0, f"{app.st.packing_phi0:g}".replace(".", ","))
        self.phi0.pack(side="left")
        self.phi0.bind("<Return>", lambda e: self.on_phi0())
        ttk.Button(ctl, text="Пересчитать", command=self.on_phi0, default="active").pack(side="left", padx=theme.px(8))
        tk.Label(ctl, text="(случайная плотная упаковка сфер ≈ 0,60–0,64)", foreground=theme.SHADOW).pack(side="left")

        self.read = ReadoutBar(self, "Оценка для выбранного образца")
        self.read.pack(fill="x")
        self.read.set_fields(["d мелк., мкм", "d крупн., мкм", "r", "Мелкой, %", "φ образца", "ε образца, %",
                              "Мелкой в опт., %", "φ опт.", "ε опт., %"])
        NoteBox(self, packing.ASSUMPTIONS, bold=True).pack(side="bottom", fill="x", padx=theme.px(2), pady=theme.px(2))
        NoteBox(self, packing.SOURCE, title="Модель:").pack(side="bottom", fill="x", padx=theme.px(2))
        pw = ttk.PanedWindow(self, orient="vertical")
        pw.pack(fill="both", expand=True)
        self.plot = PlotPanel(pw, "Пористость слоя от доли мелкой популяции", on_save=self.save_png)
        pw.add(self.plot, weight=3)
        g = groupbox(pw, "Все выбранные двухмодальные образцы")
        pw.add(g, weight=1)
        self.table = Table(g, [("Образец", 22, "w"), ("r", 7, "e"), ("Мелкой, %", 10, "e"), ("φ образца", 10, "e"),
                               ("Мелкой в оптимуме, %", 18, "e"), ("φ опт.", 8, "e")], height=4)
        self.table.pack(fill="both", expand=True)

    def on_phi0(self):
        try:
            v = float(self.phi0.get().replace(",", "."))
            if not 0.3 <= v <= 0.74:
                raise ValueError
        except ValueError:
            messagebox.showerror("Упаковка", "φ₀ — число от 0,3 до 0,74 (0,74 — предел для сфер).", parent=self)
            return
        self.app.st.packing_phi0 = v
        self.refresh()

    def refresh(self):
        phi0 = self.app.st.packing_phi0
        rows = []
        self.app.busy(True)
        try:
            for s in self.app.enabled_samples():
                e = packing.estimate(deconv.fit(s), phi0)
                if e.applicable:
                    rows.append((s.label, c(e.r, 3), c(100 * e.x_fine), c(e.phi, 3), c(100 * e.x_opt), c(e.phi_opt, 3)))
            self.table.fill(rows)
            s = self.app.current
            if s is None:
                _empty(self.plot, "Выберите образец слева")
                self.read.set_values(["—"] * 9)
                return
            e = packing.estimate(deconv.fit(s), phi0)
        finally:
            self.app.busy(False)
        if e.applicable:
            self.read.set_values([c(e.d_fine, 1), c(e.d_coarse, 1), c(e.r, 3), c(100 * e.x_fine), c(e.phi, 3),
                                  c(100 * (1 - e.phi)), c(100 * e.x_opt), c(e.phi_opt, 3), c(100 * (1 - e.phi_opt))])
        else:
            self.read.set_values(["—"] * 9)
        self._draw = lambda fig, fs=1.0: draw_packing(fig, e, font_scale=fs)
        self._name = f"упаковка_{s.name}"
        self._draw(self.plot.figure, 0.9)
        self.plot.set_title(f"Пористость слоя от доли мелкой популяции — {s.label}")
        self.plot.draw()

    def save_png(self):
        if getattr(self, "_draw", None) and self.app.current is not None:
            self.app.save_figure_png(self._draw, self._name)


# ==================================================================== М9
class KineticsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, background=theme.FACE)
        self.app = app
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = tk.Frame(pw, background=theme.FACE)
        pw.add(left, weight=1)
        PanelTitle(left, "Время обработки образцов").pack(fill="x")
        self.table = Table(left, [("Образец", 20, "w"), ("Время, ч", 9, "e")], height=12)
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<Double-Button-1>", lambda e: self.set_time())
        bar = tk.Frame(left, background=theme.FACE)
        bar.pack(fill="x", pady=theme.px(4))
        ttk.Button(bar, text="Задать время…", command=self.set_time).pack(side="left", padx=theme.px(4))
        ttk.Button(bar, text="Убрать", command=self.clear_time).pack(side="left")
        tk.Label(left, text="Время берётся из названия («6ч», «30 мин»),\nего можно задать вручную (двойной щелчок).",
                 justify="left", foreground=theme.SHADOW).pack(anchor="w", padx=theme.px(4))
        right = tk.Frame(pw, background=theme.FACE)
        pw.add(right, weight=3)
        self.notes = NoteBox(right, "", title="Внимание:")
        self.hint = NoteBox(right, "", title="Подсказка:")
        self.old = NoteBox(right, kinetics.OLD_DATA_NOTE, title="Пометка:")
        self.plot = PlotPanel(right, "Кинетика помола", on_save=self.save_png)
        self.plot.pack(fill="both", expand=True)
        self.samples = []
        self._pw, self._sash = pw, False

    def time_of(self, s):
        v = self.app.st.kinetics_times.get(s.label)
        if v == "":
            return None
        return v if v is not None else kinetics.time_from_name(s.name)

    def refresh(self):
        if not self._sash and self.winfo_ismapped():
            self.update_idletasks()
            self._pw.sashpos(0, theme.px(300))
            self._sash = True
        self.samples = self.app.enabled_samples()
        self.table.fill([(s.label, c(self.time_of(s), 2) if self.time_of(s) is not None else "")
                         for s in self.samples])
        pairs = [(s, self.time_of(s)) for s in self.samples]
        res = kinetics.analyse(pairs, self.app.st.windows_tuples)
        self._draw = lambda fig, fs=1.0: draw_kinetics(fig, res, font_scale=fs)
        self._draw(self.plot.figure, 0.9)
        self.plot.draw()
        for nb in (self.notes, self.hint, self.old):
            nb.pack_forget()
        if res.warnings:
            self.notes.set("; ".join(res.warnings) + ".")
            self.notes.pack(fill="x", padx=theme.px(2), pady=theme.px(2), before=self.plot)
        if res.hints:
            self.hint.set(" ".join(res.hints))
            self.hint.pack(fill="x", padx=theme.px(2), pady=theme.px(2), before=self.plot)
        if any(Path(s.file).name.lower().startswith("расчет") for s, t in pairs if t is not None):
            self.old.pack(fill="x", padx=theme.px(2), pady=theme.px(2), before=self.plot)

    def _selected(self):
        sel = self.table.tree.selection()
        return self.samples[self.table.tree.index(sel[0])] if sel else None

    def set_time(self):
        s = self._selected()
        if s is None:
            return
        v = simpledialog.askfloat("Время обработки", f"Время обработки образца «{s.label}», ч:", parent=self,
                                  initialvalue=self.time_of(s) or 0, minvalue=0)
        if v is not None:
            self.app.st.kinetics_times[s.label] = v
            self.refresh()

    def clear_time(self):
        s = self._selected()
        if s is not None:
            self.app.st.kinetics_times[s.label] = ""
            self.refresh()

    def save_png(self):
        if getattr(self, "_draw", None):
            self.app.save_figure_png(self._draw, "кинетика_помола")
