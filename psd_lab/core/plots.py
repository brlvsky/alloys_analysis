"""Графики грансостава: столбики Q, % + накопленная кривая ΣQ, %; сравнительный график.

Никакой перенормировки: кривая рисуется как есть.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import matplotlib
import matplotlib.ticker
import numpy as np

from .metrics import d_at
from .model import Sample

BAR_COLOR = "#b0b0b0"
GRID_COLOR = "#aaaaaa"
# Категориальная палитра (фиксированный порядок) + тип линии по файлу — читается и в ч/б.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
LINESTYLES = ["-", "--", ":", "-."]

TEXT = {
    "en": {"x": "Size, μm", "q": "Q, %", "cum": "ΣQ, %", "step": "bin {w:g} μm"},
    "ru": {"x": "Размер, мкм", "q": "Q, %", "cum": "ΣQ, %", "step": "шаг {w:g} мкм"},
}

matplotlib.rcParams["font.family"] = "DejaVu Sans"


# ---------------------------------------------------------------- вспомогательное
def nice_ceil(x: float) -> float:
    """Округление вверх до «красивого» числа: 1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8 × 10^k."""
    if x <= 0 or not np.isfinite(x):
        return 1.0
    k = 10 ** math.floor(math.log10(x))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if x <= m * k + 1e-9:
            return m * k
    return 10 * k


def grid_step(s: Sample) -> float:
    """Основной шаг сетки (медиана разностей размеров), округлённый."""
    d = np.diff(s.size_um)
    d = d[d > 0]
    return float(np.round(np.median(d), 6)) if len(d) else 1.0


def binned(s: Sample, width: float):
    """Границы интервалов шириной width от 0 и доля Q, % в каждом.

    Значения берутся интерполяцией накопленной кривой; при ширине, кратной шагу
    сетки, это просто разности исходных точек.
    """
    top = s.size_um[-1]
    edges = np.arange(0.0, top + width * 0.5, width)
    if edges[-1] < top - 1e-9:
        edges = np.append(edges, edges[-1] + width)
    cum = np.interp(edges, s.size_um, s.cum_pct)
    return edges, np.diff(cum)


def x_limit(s: Sample) -> float:
    d99 = d_at(s, 99)
    if not np.isfinite(d99):
        d99 = s.size_um[-1]
    return nice_ceil(d99)


def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip(" .")
    return name or "sample"


# ---------------------------------------------------------------- один образец
def new_figure(dpi=200):
    """Фигура публикационного стиля 10×6 дюймов, белый фон (без pyplot — годится и для GUI)."""
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10, 6), dpi=dpi)
    fig.patch.set_facecolor("white")
    return fig


def draw_sample(fig, s: Sample, *, lang="en", bin_um=None, xmax=None, ymax=None, show_name=True,
                font_scale=1.0):
    """Рисует на фигуре столбики Q, % и кривую ΣQ, %. Возвращает (ax, ax2)."""
    t = TEXT[lang]
    width = bin_um or grid_step(s)
    edges, q = binned(s, width)
    xmax = xmax or x_limit(s)
    ymax = ymax or nice_ceil(q[edges[1:] <= xmax + width].max() * 1.1 if len(q) else 1)
    fs = 12 * font_scale

    fig.clear()
    ax = fig.add_subplot(111)
    ax.set_facecolor("white")
    ax.bar(edges[:-1], q, width=width, align="edge", color=BAR_COLOR, edgecolor="black",
           linewidth=0.6, zorder=2)
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.grid(True, linestyle="--", color=GRID_COLOR, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    ax2 = ax.twinx()
    ax2.plot(s.size_um, s.cum_pct, color="black", linewidth=1.5, zorder=3)
    ax2.set_ylim(0, 100)

    q_label = t["q"] if abs(width - 1) < 1e-9 else f"{t['q']} ({t['step'].format(w=width)})"
    ax.set_xlabel(t["x"], fontstyle="italic", fontsize=fs)
    ax.set_ylabel(q_label, fontstyle="italic", fontsize=fs)
    ax2.set_ylabel(t["cum"], fontstyle="italic", fontsize=fs)
    ax.tick_params(labelsize=fs * 0.85)
    ax2.tick_params(labelsize=fs * 0.85)
    if show_name:
        ax.text(0.97, 0.80, s.name, transform=ax.transAxes, ha="right", va="top", fontsize=fs * 1.08,
                bbox=dict(boxstyle="square,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.8),
                zorder=5)
    fig.tight_layout()
    return ax, ax2


def plot_sample(s: Sample, path: Path, *, lang="en", bin_um=None, xmax=None, ymax=None,
                show_name=True) -> Path:
    """Сохраняет график образца в PNG (публикационный стиль)."""
    fig = new_figure()
    draw_sample(fig, s, lang=lang, bin_um=bin_um, xmax=xmax, ymax=ymax, show_name=show_name)
    return _save(fig, path)


def _save(fig, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white")
    return path


def common_axes(samples: list[Sample], bin_um=None, xmax=None):
    """Общие пределы осей X и Y для группы образцов."""
    xm = xmax or max(x_limit(s) for s in samples)
    ym = 0.0
    for s in samples:
        w = bin_um or grid_step(s)
        edges, q = binned(s, w)
        sel = edges[:-1] < xm
        if sel.any():
            ym = max(ym, q[sel].max())
    return xm, nice_ceil(ym * 1.1)


# ---------------------------------------------------------------- сравнение
def draw_compare(fig, groups: list[list[Sample]], *, lang="en", log_x=True, xmax=None, font_scale=1.0):
    """Накопленные кривые. Цвет — номер образца в группе (файле), тип линии — группа."""
    t = TEXT[lang]
    fs = 12 * font_scale
    fig.clear()
    ax = fig.add_subplot(111)
    all_s = [s for g in groups for s in g]
    if not all_s:
        ax.text(0.5, 0.5, "Нет выбранных образцов", ha="center", va="center", transform=ax.transAxes)
        return ax
    xm = xmax or max(x_limit(s) for s in all_s)
    for gi, grp in enumerate(groups):
        ls = LINESTYLES[gi % len(LINESTYLES)]
        for si, s in enumerate(grp):
            x, y = s.size_um, s.cum_pct
            if log_x:
                x, y = x[x > 0], y[x > 0]
            ax.plot(x, y, color=SERIES_COLORS[si % len(SERIES_COLORS)], linestyle=ls,
                    linewidth=1.6, label=s.label)
    if log_x:
        ax.set_xscale("log")
        xmin = min(s.size_um[s.size_um > 0][0] for s in all_s)
        ax.set_xlim(max(xmin, 0.1), xm)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    else:
        ax.set_xlim(0, xm)
    ax.set_ylim(0, 100)
    ax.grid(True, which="major", linestyle="--", color=GRID_COLOR, linewidth=0.6)
    ax.set_xlabel(t["x"], fontstyle="italic", fontsize=fs)
    ax.set_ylabel(t["cum"], fontstyle="italic", fontsize=fs)
    ax.tick_params(labelsize=fs * 0.85)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=9 * font_scale)
    fig.tight_layout()
    return ax


def plot_compare(groups: list[list[Sample]], path: Path, *, lang="en", log_x=True, xmax=None) -> Path:
    fig = new_figure()
    draw_compare(fig, groups, lang=lang, log_x=log_x, xmax=xmax)
    return _save(fig, path)


# ---------------------------------------------------------------- всё сразу
def plot_all(file_groups: list[tuple[Path, list[Sample]]], out: Path, *, lang="en", bin_um=None,
             xmax=None, independent_axes=False, show_name=True, log_x=True) -> list[tuple]:
    """PNG по каждому образцу (в подпапке с именем файла) + compare.png.

    Возвращает [(образец или None для compare.png, путь)].
    """
    out = Path(out)
    made = []
    for file, samples in file_groups:
        if not samples:
            continue
        folder = out / safe_filename(Path(file).stem)
        shared = (None, None) if independent_axes else common_axes(samples, bin_um, xmax)
        used = set()
        for s in samples:
            base = safe_filename(s.label if s.name in used else s.name)
            used.add(s.name)
            made.append((s, plot_sample(s, folder / f"{base}.png", lang=lang, bin_um=bin_um,
                                        xmax=xmax or shared[0], ymax=shared[1], show_name=show_name)))
    groups = [g for _, g in file_groups if g]
    if groups:
        made.append((None, plot_compare(groups, out / "compare.png", lang=lang, log_x=log_x, xmax=xmax)))
    return made
