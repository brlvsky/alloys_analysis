"""Графики грансостава: столбики Q, % + накопленная кривая ΣQ, %; сравнительный график.

Никакой перенормировки: кривая рисуется как есть.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import matplotlib
import matplotlib.ticker
from matplotlib.collections import PolyCollection
import numpy as np

from .metrics import d_at
from .model import Sample

BAR_COLOR = "#b0b0b0"
GRID_COLOR = "#aaaaaa"
# Категориальная палитра (фиксированный порядок) + тип линии по файлу — читается и в ч/б.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
LINESTYLES = ["-", "--", ":", "-."]

TEXT = {
    "en": {"x": "Size, μm", "q": "Q, %", "cum": "ΣQ, %", "step": "bin {w:g} μm",
           "logbin": "per 1/{n} decade"},
    "ru": {"x": "Размер, мкм", "q": "Q, %", "cum": "ΣQ, %", "step": "шаг {w:g} мкм",
           "logbin": "на 1/{n} декады"},
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


LOG_PER_DECADE = 10   # логарифмические интервалы столбиков на логарифмической оси


def log_bins(s: Sample, x_lo: float, x_hi: float, per_decade: int = LOG_PER_DECADE):
    """Логарифмические интервалы для лог. оси: (границы, высота столбика — Q, % на 1/per_decade декады).

    Границы кратны декаде (1; 1,26; 1,58; …). Интервал, внутри которого нет ни одной точки сетки прибора
    (мелкие размеры: сетка 0,1 → 1 → 2 мкм), объединяется со следующим — иначе столбики показывали бы
    интерполяцию, а не измерение. Высота = Q в интервале / его ширина в долях декады·per_decade, поэтому
    широкий объединённый столбик не завышается; для обычного интервала высота = Q, %. Без перенормировки:
    Σ высота·ширина = ΣQ(x_hi) − ΣQ(x_lo)."""
    k0 = int(np.floor(np.log10(x_lo) * per_decade + 1e-9))
    k1 = int(np.ceil(np.log10(x_hi) * per_decade - 1e-9))
    grid = 10.0 ** (np.arange(k0, k1 + 1) / per_decade)
    nodes = s.size_um[s.size_um > 0]
    edges = [grid[0]]
    for e in grid[1:-1]:
        # точка сетки у самой границы (2,0 мкм при границе 10^0,3 = 1,995) считается внутри интервала
        if np.any((nodes > edges[-1] * 1.01) & (nodes <= e * 1.01)):
            edges.append(e)
    edges.append(grid[-1])
    edges = np.array(edges)
    q = np.diff(np.interp(edges, s.size_um, s.cum_pct))
    width = np.diff(np.log10(edges)) * per_decade
    return edges, q / width


def x_low(s: Sample) -> float:
    """Левая граница логарифмической оси: степень 10 ниже ~0,3 % кумулятивы (и не ниже первой точки сетки)."""
    first = float(s.size_um[s.size_um > 0][0]) if (s.size_um > 0).any() else 0.1
    d = d_at(s, 0.3)
    base = max(first, d / 1.5 if np.isfinite(d) else first)
    return 10.0 ** math.floor(math.log10(base))


def sample_bins(s: Sample, *, bin_um=None, log_x=False, xmin=None, xmax=None):
    """Столбики графика распределения: (границы, Q, %). Линейная ось — шаг сетки (или bin_um),
    логарифмическая — логарифмические интервалы."""
    if log_x:
        return log_bins(s, xmin or x_low(s), xmax or x_limit(s))
    return binned(s, bin_um or grid_step(s))


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
                font_scale=1.0, log_x=False, xmin=None):
    """Рисует на фигуре столбики Q, % и кривую ΣQ, %. Возвращает (ax, ax2).

    log_x — логарифмическая ось размеров; столбики тогда — доли в логарифмических интервалах
    (10 на декаду), иначе на лог. оси столбики шага 1–2 мкм были бы несопоставимой ширины."""
    t = TEXT[lang]
    width = bin_um or grid_step(s)
    xmax = xmax or x_limit(s)
    xmin = (xmin or x_low(s)) if log_x else 0.0
    edges, q = sample_bins(s, bin_um=bin_um, log_x=log_x, xmin=xmin, xmax=xmax)
    vis = edges[:-1] < xmax
    ymax = ymax or nice_ceil(q[vis].max() * 1.1 if vis.any() else 1)
    fs = 12 * font_scale

    fig.clear()
    ax = fig.add_subplot(111)
    ax.set_facecolor("white")
    # столбики одной коллекцией, а не сотней отдельных прямоугольников: на вид то же самое,
    # но рисуется в разы быстрее (важно для сдвига и масштаба графика в окне)
    x0, x1 = edges[:-1], edges[1:]
    verts = np.stack([np.column_stack([x0, np.zeros_like(q)]), np.column_stack([x0, q]),
                      np.column_stack([x1, q]), np.column_stack([x1, np.zeros_like(q)])], axis=1)
    ax.add_collection(PolyCollection(verts, facecolors=BAR_COLOR, edgecolors="black", linewidths=0.6, zorder=2))
    if log_x:
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(0, ymax)
    ax.grid(True, linestyle="--", color=GRID_COLOR, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    ax2 = ax.twinx()
    keep = s.size_um > 0 if log_x else np.ones(len(s.size_um), bool)
    ax2.plot(s.size_um[keep], s.cum_pct[keep], color="black", linewidth=1.5, zorder=3)
    ax2.set_ylim(0, 100)

    if log_x:
        q_label = f"{t['q']} ({t['logbin'].format(n=LOG_PER_DECADE)})"
        below = float(np.interp(xmin, s.size_um, s.cum_pct))
        if below >= 0.5:   # часть порошка левее оси — не теряем её молча
            txt = (f"мельче {xmin:g} мкм: {below:.1f} %" if lang == "ru" else f"below {xmin:g} μm: {below:.1f} %")
            ax.text(0.01, 0.015, txt.replace(".", ",") if lang == "ru" else txt, transform=ax.transAxes,
                    ha="left", va="bottom", fontsize=fs * 0.8, color="#404040", zorder=6)
    else:
        q_label = t["q"] if abs(width - 1) < 1e-9 else f"{t['q']} ({t['step'].format(w=width)})"
    ax.set_xlabel(t["x"], fontstyle="italic", fontsize=fs)
    ax.set_ylabel(q_label, fontstyle="italic", fontsize=fs)
    ax2.set_ylabel(t["cum"], fontstyle="italic", fontsize=fs)
    ax.tick_params(labelsize=fs * 0.85)
    ax2.tick_params(labelsize=fs * 0.85)
    if show_name:
        # на лог. оси справа обычно крупная мода — подпись слева, чтобы не закрывать столбики
        x_txt, ha = (0.03, "left") if log_x else (0.97, "right")
        ax.text(x_txt, 0.80 if not log_x else 0.95, s.name, transform=ax.transAxes, ha=ha, va="top",
                fontsize=fs * 1.08,
                bbox=dict(boxstyle="square,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.8),
                zorder=5)
    fig.tight_layout()
    return ax, ax2


def plot_sample(s: Sample, path: Path, *, lang="en", bin_um=None, xmax=None, ymax=None,
                show_name=True, log_x=False, xmin=None) -> Path:
    """Сохраняет график образца в PNG (публикационный стиль)."""
    fig = new_figure()
    draw_sample(fig, s, lang=lang, bin_um=bin_um, xmax=xmax, ymax=ymax, show_name=show_name, log_x=log_x,
                xmin=xmin)
    return _save(fig, path)


def _save(fig, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white")
    return path


def common_axes(samples: list[Sample], bin_um=None, xmax=None, log_x=False):
    """Общие пределы осей для группы образцов: (xmax, ymax, xmin); xmin — для логарифмической оси."""
    xm = xmax or max(x_limit(s) for s in samples)
    xlo = min(x_low(s) for s in samples) if log_x else None
    ym = 0.0
    for s in samples:
        edges, q = sample_bins(s, bin_um=bin_um, log_x=log_x, xmin=xlo, xmax=xm)
        sel = edges[:-1] < xm
        if sel.any():
            ym = max(ym, q[sel].max())
    return xm, nice_ceil(ym * 1.1), xlo


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
             xmax=None, independent_axes=False, show_name=True, log_x=True, dist_log=False) -> list[tuple]:
    """PNG по каждому образцу (в подпапке с именем файла) + compare.png.

    Возвращает [(образец или None для compare.png, путь)].
    """
    out = Path(out)
    made = []
    for file, samples in file_groups:
        if not samples:
            continue
        folder = out / safe_filename(Path(file).stem)
        shared = (None, None, None) if independent_axes else common_axes(samples, bin_um, xmax, dist_log)
        used = set()
        for s in samples:
            base = safe_filename(s.label if s.name in used else s.name)
            used.add(s.name)
            made.append((s, plot_sample(s, folder / f"{base}.png", lang=lang, bin_um=bin_um,
                                        xmax=xmax or shared[0], ymax=shared[1], show_name=show_name,
                                        log_x=dist_log, xmin=shared[2])))
    groups = [g for _, g in file_groups if g]
    if groups:
        made.append((None, plot_compare(groups, out / "compare.png", lang=lang, log_x=log_x, xmax=xmax)))
    return made


# ==================================================================== графики модулей М2–М5
SEG_COLORS = {"fine": "#d9d9d9", "sls": "#2a78d6", "both": "#4a3aa7", "gap": "#f2f2f2",
              "ebm": "#eb6834", "coarse": "#808080"}
SEG_TEXT = {"fine": "black", "sls": "white", "both": "white", "gap": "black", "ebm": "white", "coarse": "white"}
POP_COLORS = {"мелкая": "#2a78d6", "крупная": "#eb6834", "средняя": "#1baf7a", "основная": "#2a78d6",
              "субмикронная": "#808080"}


def draw_pair(fig, d, *, lang="ru", log_x=True, font_scale=1.0):
    """Два образца: сверху плотности q3*(ln x) A и B, снизу разность ΔΣQ = ΣQ_B − ΣQ_A, п.п.
    Возвращает (ax_top, ax_bottom)."""
    from .deconv import density_ln

    t = TEXT[lang]
    fs = 12 * font_scale
    fig.clear()
    ax1, ax2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    x_hi = max(x_limit(d.a), x_limit(d.b))
    x_lo = max(min(d_at(d.a, 0.5), d_at(d.b, 0.5)) / 1.5, float(d.grid[0]))
    if not log_x:
        x_lo = 0.0
    # q3* — на общих логарифмических интервалах (12 на декаду): у мелкой сетки прибора (шаг 1–2 мкм)
    # плотность по ln x на крупных размерах «шумит» от округления ΣQ, а так оба образца в одних интервалах
    for s, col, fill, lab in ((d.a, "black", "#c8c8c8", "A"), (d.b, "#2a78d6", None, "B")):
        mid, q = log_density(s, max(x_lo, float(d.grid[0])), x_hi)
        if fill:
            ax1.fill_between(mid, q, step="mid", color=fill, linewidth=0)
        ax1.step(mid, q, where="mid", color=col, linewidth=1.5 if lab == "B" else 1.0,
                 label=f"{lab}: {s.label}")
    ax1.set_ylim(bottom=0)
    ax1.legend(loc="upper left", fontsize=9 * font_scale, frameon=True, edgecolor="black", fancybox=False)
    _style_ax(ax1, fs)
    ax1.tick_params(labelbottom=False)

    delta = d.delta
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.fill_between(d.grid, delta, 0, where=delta >= 0, color="#2a78d6", alpha=0.35, linewidth=0,
                     interpolate=True)
    ax2.fill_between(d.grid, delta, 0, where=delta < 0, color="#eb6834", alpha=0.35, linewidth=0,
                     interpolate=True)
    ax2.plot(d.grid, delta, color="black", linewidth=1.3, label="ΔΣQ = ΣQ(B) − ΣQ(A)")
    from .metrics import REPEAT_TOL

    for yv in (-REPEAT_TOL, REPEAT_TOL):   # полоса разброса повторов
        ax2.axhline(yv, color="#808080", linewidth=0.8, linestyle=":")
    lim = max(5.0, float(np.nanmax(np.abs(delta))) * 1.15)
    ax2.set_ylim(-lim, lim)
    ax2.set_ylabel("ΔΣQ, п.п.", fontstyle="italic", fontsize=fs)
    ax2.set_xlabel(t["x"], fontstyle="italic", fontsize=fs)
    ax2.text(0.995, 0.97, "B мельче ↑", transform=ax2.transAxes, ha="right", va="top", fontsize=8.5 * font_scale,
             color="#1a5fb0")
    ax2.text(0.995, 0.03, "B крупнее ↓", transform=ax2.transAxes, ha="right", va="bottom",
             fontsize=8.5 * font_scale, color="#b04a1a")
    _style_ax(ax2, fs)
    if log_x:
        ax1.set_xscale("log")
        ax1.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax1.set_xlim(x_lo, x_hi)
    ax1.set_ylabel("q3*, % (на ln x)", fontstyle="italic", fontsize=fs)
    fig.tight_layout()
    return ax1, ax2


def log_density(s: Sample, x_lo: float, x_hi: float, per_decade: int = 12):
    """q3*(ln x) = ΔΣQ/Δln x на логарифмических интервалах; возвращает (середины, q)."""
    from .metrics import cum_at

    x_lo = max(x_lo, 1e-3)
    n = max(4, int(np.ceil(np.log10(x_hi / x_lo) * per_decade)))
    edges = np.exp(np.linspace(np.log(x_lo), np.log(x_hi), n + 1))
    c = np.array([cum_at(s, x) for x in edges])
    q = np.diff(c) / np.diff(np.log(edges))
    return np.sqrt(edges[:-1] * edges[1:]), q


def _style_ax(ax, fs):
    ax.grid(True, linestyle="--", color=GRID_COLOR, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=fs * 0.85)


def draw_populations(fig, s: Sample, res, *, lang="ru", font_scale=1.0):
    """q3*(ln x): измеренная плотность (серая заливка), компоненты и их сумма."""
    import numpy as np

    from .deconv import component_pdf_ln, density_ln

    fs = 12 * font_scale
    fig.clear()
    ax = fig.add_subplot(111)
    mid, q = density_ln(s)
    # правый край: где кривая вышла на 99,9 % (дальше — шум округления прибора)
    x_hi = d_at(s, 99.9)
    x_hi = mid[-1] if not np.isfinite(x_hi) else min(mid[-1], x_hi * 1.3)
    keep = mid <= x_hi
    mid, q = mid[keep], q[keep]
    ax.fill_between(mid, q, step="mid", color="#d9d9d9", label="измерено (q3*)", linewidth=0)
    grid = np.exp(np.linspace(np.log(max(mid[0], 0.05)), np.log(x_hi), 600))
    total = np.zeros_like(grid)
    for c in res.components:
        total += component_pdf_ln(grid, c.weight_pct, np.log(c.median_um), c.sigma)
    for p in res.populations:
        y = sum(component_pdf_ln(grid, c.weight_pct, np.log(c.median_um), c.sigma) for c in p.components)
        col = POP_COLORS.get(p.kind, "#1baf7a")
        ax.fill_between(grid, y, color=col, alpha=0.35, linewidth=0)
        ax.plot(grid, y, color=col, linewidth=1.4,
                label=f"{p.kind}: {p.weight_pct:.1f} %, мода {p.mode_um:.3g} мкм".replace(".", ","))
    ax.step(mid, q, where="mid", color="#606060", linewidth=0.6)
    ax.plot(grid, total, color="black", linewidth=1.6, label=f"модель (R² = {res.r2:.4f})".replace(".", ","))
    for p in res.populations[1:]:
        if p.lo_um:
            ax.axvline(p.lo_um, color="#808080", linewidth=1, linestyle=":")
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlim(max(mid[0], 0.1), x_hi)
    ax.set_ylim(0, max(q.max(), total.max()) * 1.12)
    ax.set_xlabel(TEXT[lang]["x"], fontstyle="italic", fontsize=fs)
    ax.set_ylabel("q3* = dQ/d ln x, %", fontstyle="italic", fontsize=fs)
    _style_ax(ax, fs)
    ax.legend(loc="upper left", fontsize=9 * font_scale, frameon=True, edgecolor="black", fancybox=False)
    fig.tight_layout()
    return ax


def draw_tech_bars(fig, samples, sls, ebm, *, font_scale=1.0):
    """Горизонтальные составные полосы: мельче | СЛС | между | СЭЛС | крупнее (в % объёма)."""
    from .windows import segments

    fs = 12 * font_scale
    fig.clear()
    ax = fig.add_subplot(111)
    if not samples:
        ax.axis("off")
        ax.text(0.5, 0.5, "Нет выбранных образцов", ha="center", va="center", color="#808080")
        return ax
    names = [s.label for s in samples]
    seen = set()
    for i, s in enumerate(samples):
        left = 0.0
        for g in segments(s, sls, ebm):
            lab = f"{g.name} {g.label}" if g.role not in seen else None
            seen.add(g.role)
            ax.barh(i, g.pct, left=left, color=SEG_COLORS[g.role], edgecolor="black", linewidth=0.6,
                    height=0.7, label=lab)
            if g.pct >= 6:
                ax.text(left + g.pct / 2, i, f"{g.pct:.0f}", ha="center", va="center",
                        color=SEG_TEXT[g.role], fontsize=8.5 * font_scale)
            left += g.pct
    ax.set_yticks(range(len(names)), names, fontsize=9 * font_scale)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("доля объёма, %", fontstyle="italic", fontsize=fs)
    ax.grid(True, axis="x", linestyle="--", color=GRID_COLOR, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=fs * 0.85)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=6, fontsize=9 * font_scale, frameon=False)
    fig.tight_layout()
    return ax


def draw_sieve(fig, s: Sample, sv, *, lang="ru", font_scale=1.0):
    """Исходная кривая и модель после идеального рассева (подписано, что перенормировано)."""
    fs = 12 * font_scale
    fig.clear()
    ax = fig.add_subplot(111)
    ax.axvspan(sv.lo, sv.hi, color="#2a78d6", alpha=0.10, linewidth=0)
    ax.plot(s.size_um, s.cum_pct, color="black", linewidth=1.5, label="исходный порошок")
    ax.plot(sv.sieved.size_um, sv.sieved.cum_pct, color="#2a78d6", linewidth=2, linestyle="--",
            label=f"после рассева {sv.lo:g}–{sv.hi:g} мкм (модель, перенормировано на 100 %)")
    xm = max(x_limit(s), sv.hi * 1.5)
    ax.set_xlim(0, xm)
    ax.set_ylim(0, 100)
    ax.set_xlabel(TEXT[lang]["x"], fontstyle="italic", fontsize=fs)
    ax.set_ylabel(TEXT[lang]["cum"], fontstyle="italic", fontsize=fs)
    _style_ax(ax, fs)
    ax.legend(loc="lower right", fontsize=9 * font_scale, frameon=True, edgecolor="black", fancybox=False)
    fig.tight_layout()
    return ax


def draw_surface(fig, rows, *, font_scale=1.0):
    """Столбики по фракциям: доля объёма и доля поверхности."""
    import numpy as np

    fs = 12 * font_scale
    fig.clear()
    ax = fig.add_subplot(111)
    x = np.arange(len(rows))
    w = 0.38
    v = [r.volume_pct for r in rows]
    a = [r.surface_pct for r in rows]
    b1 = ax.bar(x - w / 2, v, w, color=BAR_COLOR, edgecolor="black", linewidth=0.6, label="доля объёма")
    b2 = ax.bar(x + w / 2, a, w, color="#2a78d6", edgecolor="black", linewidth=0.6, label="доля поверхности")
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 1, f"{h:.1f}".replace(".", ","), ha="center",
                    va="bottom", fontsize=8.5 * font_scale)
    ax.set_xticks(x, [f"{r.label} мкм" for r in rows], fontsize=9 * font_scale)
    ax.set_ylim(0, 105)
    ax.set_ylabel("%", fontstyle="italic", fontsize=fs)
    _style_ax(ax, fs)
    ax.legend(loc="upper right", fontsize=9 * font_scale, frameon=True, edgecolor="black", fancybox=False)
    fig.tight_layout()
    return ax


def draw_packing(fig, est, *, font_scale=1.0):
    """Пористость слоя от доли мелкой фракции при отношении размеров образца и в пределе r → 0."""
    import numpy as np

    from .packing import packing_fraction

    fs = 12 * font_scale
    fig.clear()
    ax = fig.add_subplot(111)
    if not est.applicable:
        ax.axis("off")
        ax.text(0.5, 0.5, "Оценка неприменима: " + est.reason, ha="center", va="center", color="#808080",
                wrap=True)
        return ax
    x = np.linspace(0, 1, 401)
    eps = 100 * (1 - packing_fraction(x, est.r, est.phi0))
    eps0 = 100 * (1 - packing_fraction(x, 1e-9, est.phi0))
    ax.plot(100 * x, eps0, color="#808080", linestyle="--", linewidth=1.2, label="предел r → 0 (Фёрнас)")
    ax.plot(100 * x, eps, color="#2a78d6", linewidth=2,
            label=f"r = d_мелк/d_крупн = {est.r:.3f}".replace(".", ","))
    ax.plot(100 * est.x_fine, 100 * (1 - est.phi), "o", color="#e34948", markeredgecolor="black", markersize=9,
            label=f"образец: {100 * est.x_fine:.0f} % мелкой, ε = {100 * (1 - est.phi):.1f} %".replace(".", ","))
    ax.plot(100 * est.x_opt, 100 * (1 - est.phi_opt), "^", color="#1baf7a", markeredgecolor="black", markersize=10,
            label=f"оптимум: {100 * est.x_opt:.0f} % мелкой, ε = {100 * (1 - est.phi_opt):.1f} %".replace(".", ","))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100 * (1 - est.phi0) * 1.15)
    ax.set_xlabel("доля мелкой популяции (по объёму), %", fontstyle="italic", fontsize=fs)
    ax.set_ylabel("пористость слоя ε, %", fontstyle="italic", fontsize=fs)
    _style_ax(ax, fs)
    ax.legend(loc="lower right", fontsize=9 * font_scale, frameon=True, edgecolor="black", fancybox=False)
    fig.tight_layout()
    return ax


def draw_kinetics(fig, res, *, font_scale=1.0):
    """d10/d50/d90 от времени (сверху) и доли по окнам (снизу) — две оси, не двойная шкала."""
    import numpy as np

    from .kinetics import exp_model

    fs = 12 * font_scale
    fig.clear()
    if not res.times:
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.5, 0.5, "Назначьте образцам время обработки (слева)", ha="center", va="center", color="#808080")
        return
    ax1 = fig.add_subplot(211)
    ax2 = fig.add_subplot(212, sharex=ax1)
    t = np.array(res.times, float)
    colors = {"d10": "#2a78d6", "d50": "#eb6834", "d90": "#1baf7a"}
    for k, col in colors.items():
        ax1.plot(t, res.d[k], "o-", color=col, linewidth=1.4, markersize=7, markeredgecolor="black", label=k)
        f = res.fits.get(k)
        if f and f.ok:
            tt = np.linspace(t.min(), t.max(), 200)
            ax1.plot(tt, exp_model(tt, *f.params), "--", color=col, linewidth=1)
    for name, ti, y in zip(res.names, t, res.d["d50"]):
        ax1.annotate(name, (ti, y), textcoords="offset points", xytext=(5, 6), fontsize=8.5 * font_scale)
    ax1.set_ylabel("размер, мкм", fontstyle="italic", fontsize=fs)
    _style_ax(ax1, fs)
    ax1.margins(x=0.08, y=0.12)   # точки и подписи «6ч … 10ч» не прилипают к краям
    # легенды обеих осей — справа снаружи, чтобы не закрывать точки
    ax1.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8.5 * font_scale, frameon=False)
    for i, k in enumerate([k for k in res.d if k.startswith("frac:")]):
        ax2.plot(t, res.d[k], "s-", color=SERIES_COLORS[i % len(SERIES_COLORS)], linewidth=1.2, markersize=5,
                 label=k.split(":", 1)[1] + " мкм")
    ax2.set_ylabel("доля, %", fontstyle="italic", fontsize=fs)
    ax2.set_xlabel("время обработки, ч", fontstyle="italic", fontsize=fs)
    _style_ax(ax2, fs)
    ax2.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8.5 * font_scale, frameon=False)
    fig.tight_layout()
    return ax1, ax2
