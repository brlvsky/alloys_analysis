"""Анализ → Структура — свойства: точечный график двух числовых полей базы с регрессией."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...core import db
from ...core.plots import GRID_COLOR
from .. import hover, theme
from ..tabs.plot_panel import PlotPanel
from ..widgets import NoteBox, Table, center_on


def draw_structure(fig, pts, xlabel, ylabel, font_scale=1.0):
    import numpy as np

    fs = 12 * font_scale
    fig.clear()
    ax = fig.add_subplot(111)
    if not pts:
        ax.axis("off")
        ax.text(0.5, 0.5, "Нет партий, у которых заполнены оба поля", ha="center", va="center", color="#808080")
        return None
    x = np.array([p[1] for p in pts])
    y = np.array([p[2] for p in pts])
    ax.scatter(x, y, s=46 * font_scale, color="#2a78d6", edgecolor="black", linewidth=0.7, zorder=3)
    reg = db.regression(x, y)
    if reg.slope is not None:
        xx = np.linspace(x.min(), x.max(), 50)
        ax.plot(xx, reg.slope * xx + reg.intercept, color="black", linewidth=1.2, linestyle="--", zorder=2)
    text = (f"n = {reg.n}; R² = {reg.r2:.3f}".replace(".", ",") if reg.r2 is not None
            else f"n = {reg.n}: мало точек для R² (нужно ≥ 3)")
    ax.set_title(text, fontsize=10 * font_scale, loc="left")   # над графиком — не закрывает точки
    ax.margins(0.1)
    ax.set_xlabel(xlabel, fontstyle="italic", fontsize=fs)
    ax.set_ylabel(ylabel, fontstyle="italic", fontsize=fs)
    ax.grid(True, linestyle="--", color=GRID_COLOR, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=fs * 0.85)
    fig.tight_layout()
    _place_labels(fig, ax, pts, 8.5 * font_scale)
    return reg


# варианты положения подписи относительно точки (смещение в пунктах, выравнивание)
_SPOTS = [((6, 5), "left"), ((6, -13), "left"), ((-6, 5), "right"), ((-6, -13), "right"),
          ((6, 17), "left"), ((6, -25), "left"), ((-6, 17), "right"), ((-6, -25), "right")]


def _place_labels(fig, ax, pts, fontsize):
    """Подписи партий без наложения: для каждой точки берётся первое свободное место из _SPOTS."""
    try:
        renderer = fig.canvas.get_renderer()
    except AttributeError:
        renderer = None
    placed = []
    for name, xi, yi in pts:
        ann = None
        for off, ha in _SPOTS:
            if ann is not None:
                ann.remove()
            ann = ax.annotate(name, (xi, yi), textcoords="offset points", xytext=off, ha=ha, fontsize=fontsize)
            if renderer is None:
                break
            bb = ann.get_window_extent(renderer).expanded(1.05, 1.1)
            if not any(bb.overlaps(o) for o in placed):
                break
        else:
            ann.remove()   # всё занято — ставим на исходное место
            ann = ax.annotate(name, (xi, yi), textcoords="offset points", xytext=_SPOTS[0][0], fontsize=fontsize)
        if renderer is not None:
            placed.append(ann.get_window_extent(renderer))


class StructureWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Структура — свойства")
        self.configure(background=theme.FACE)
        self.geometry(f"{theme.px(980)}x{theme.px(700)}")
        self.transient(app.root)
        top = tk.Frame(self, background=theme.FACE, padx=theme.px(6), pady=theme.px(6))
        top.pack(fill="x")
        self.fields = db.property_fields(app.db)
        labels = [lab for _, lab in self.fields]
        keys = [k for k, _ in self.fields]
        tk.Label(top, text="Ось X:").pack(side="left")
        self.cx = ttk.Combobox(top, values=labels, state="readonly", width=30, font=theme.FONTS["ui"])
        self.cx.current(keys.index("psd.d50"))
        self.cx.pack(side="left", padx=(theme.px(4), theme.px(16)))
        tk.Label(top, text="Ось Y:").pack(side="left")
        self.cy = ttk.Combobox(top, values=labels, state="readonly", width=30, font=theme.FONTS["ui"])
        self.cy.current(keys.index("psd.ssa_m2_g"))
        self.cy.pack(side="left", padx=theme.px(4))
        for cb in (self.cx, self.cy):
            cb.bind("<<ComboboxSelected>>", lambda e: self.redraw())
        ttk.Button(top, text="Закрыть", command=self.destroy).pack(side="right")
        NoteBox(self, "по каждой партии берётся среднее всех её записей (измерений, режимов печати, испытаний); "
                      "линия — линейная регрессия; R² показывается только при n ≥ 3. Корреляция ≠ причинность.").pack(
            side="bottom", fill="x", padx=theme.px(4), pady=theme.px(4))
        self.table = Table(self, [("Партия", 24, "w"), ("X", 12, "e"), ("Y", 12, "e")], height=5)
        self.table.pack(side="bottom", fill="x", padx=theme.px(4))
        self.plot = PlotPanel(self, "", on_save=self.save)
        self.plot.pack(fill="both", expand=True, padx=theme.px(2))
        center_on(self, app.root)
        self.after(50, self.redraw)

    def keys(self):
        return self.fields[self.cx.current()], self.fields[self.cy.current()]

    def redraw(self):
        (kx, lx), (ky, ly) = self.keys()
        pts = db.xy(self.app.db, kx, ky)
        self._draw = lambda fig, fs=1.0: draw_structure(fig, pts, lx, ly, fs)
        self._draw(self.plot.figure, 0.9)
        ax = self.plot.figure.axes[0] if pts else None
        self.plot.set_hover(hover.scatter_points(ax, pts, lx, ly) if ax is not None else None)
        self.plot.set_title(f"{ly}  от  {lx}")
        self.plot.draw()
        f = lambda v: f"{v:.4g}".replace(".", ",")  # noqa: E731
        self.table.fill([(n, f(a), f(b)) for n, a, b in pts])

    def save(self):
        (_, lx), (_, ly) = self.keys()
        self.app.save_figure_png(self._draw, f"структура-свойства {ly} от {lx}")

