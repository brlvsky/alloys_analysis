"""Подсказки при наведении на графики: что показать в точке курсора.

Каждая функция здесь строит «провайдер» fn(event) → HoverInfo | None для конкретного графика.
event.x, event.y — пиксели matplotlib (от левого нижнего угла фигуры).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class HoverInfo:
    title: str
    rows: list = field(default_factory=list)      # [(цвет или None, текст)]
    vlines: list = field(default_factory=list)    # [(ax, x)]
    points: list = field(default_factory=list)    # [(ax, x, y, цвет)]
    rects: list = field(default_factory=list)     # [(ax, x0, y0, ширина, высота)]


def n(v, nd=1) -> str:
    if v is None or v != v:
        return "—"
    return f"{v:.{nd}f}".replace(".", ",")


def size_fmt(x: float) -> str:
    return n(x, 2 if x < 10 else 1 if x < 100 else 0)


def data_xy(ax, ev):
    """Координаты курсора в данных оси ax, если курсор внутри её области, иначе None."""
    if not ax.bbox.contains(ev.x, ev.y):
        return None
    return ax.transData.inverted().transform((ev.x, ev.y))


def _color(line):
    from matplotlib.colors import to_hex

    return to_hex(line.get_color())


def _curves(ax):
    """Подписанные линии оси (без служебных и одиночных маркеров)."""
    out = []
    for ln in ax.get_lines():
        lab = ln.get_label()
        x = np.asarray(ln.get_xdata(), float)
        if lab.startswith("_") or len(x) < 3:
            continue
        out.append((lab, x, np.asarray(ln.get_ydata(), float), _color(ln)))
    return out


def _interp(x, xs, ys):
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]
    if x < xs[0] or x > xs[-1]:
        return None
    return float(np.interp(x, xs, ys))


# ==================================================================== графики
def distribution(s, ax, ax2, width):
    """Столбики Q и кривая ΣQ: размер, ΣQ в точке, Q в столбике под курсором (столбик подсвечивается)."""
    from ..core.metrics import cum_at
    from ..core.plots import binned

    edges, q = binned(s, width)

    def fn(ev):
        p = data_xy(ax, ev)
        if p is None:
            return None
        x = float(p[0])
        if x < 0 or x > edges[-1]:
            return None
        c = cum_at(s, x)
        i = int(np.clip(np.searchsorted(edges, x, side="right") - 1, 0, len(q) - 1))
        e0, e1 = edges[i], edges[i + 1]
        return HoverInfo(
            f"Размер {size_fmt(x)} мкм",
            [("#000000", f"ΣQ = {n(c)} %  — частиц мельче {size_fmt(x)} мкм"),
             ("#b0b0b0", f"Q = {n(q[i], 2)} %  — в интервале {n(e0, 1)}–{n(e1, 1)} мкм"),
             (None, f"крупнее — {n(100 - c)} %")],
            vlines=[(ax, x)], points=[(ax2, x, c, "#ffff00")], rects=[(ax, e0, 0, e1 - e0, q[i])])
    return fn


def curves(ax, title_fmt=lambda x: f"Размер {size_fmt(x)} мкм", value_fmt=lambda y: f"{n(y)} %",
           extra=None, max_rows=16):
    """Универсальная подсказка по всем подписанным кривым оси (сравнение, рассев, упаковка…)."""
    def fn(ev):
        p = data_xy(ax, ev)
        if p is None:
            return None
        x = float(p[0])
        info = HoverInfo(title_fmt(x), vlines=[(ax, x)])
        for lab, xs, ys, col in _curves(ax):
            y = _interp(x, xs, ys)
            if y is None:
                continue
            info.rows.append((col, f"{lab}: {value_fmt(y)}"))
            info.points.append((ax, x, y, col))
        if extra:
            info.rows += extra(x)
        if not info.rows:
            return None
        if len(info.rows) > max_rows:
            info.rows = info.rows[:max_rows] + [(None, f"… и ещё {len(info.rows) - max_rows}")]
        return info
    return fn


def compare(ax):
    return curves(ax, value_fmt=lambda y: f"ΣQ = {n(y)} %")


def pair(ax1, ax2, d):
    """Два образца: ΣQ обоих и разность в точке курсора (на любой из двух осей)."""
    from ..core.metrics import cum_at

    def fn(ev):
        p = data_xy(ax1, ev) if ax1.bbox.contains(ev.x, ev.y) else data_xy(ax2, ev)
        if p is None:
            return None
        x = float(p[0])
        if x <= 0 or x < d.grid[0] or x > d.grid[-1]:
            return None
        ca, cb = cum_at(d.a, x), cum_at(d.b, x)
        dv = cb - ca
        sign = "+" if dv > 0 else ""
        rows = [("#c8c8c8", f"A: {d.a.label}: ΣQ = {n(ca)} %"),
                ("#2a78d6", f"B: {d.b.label}: ΣQ = {n(cb)} %"),
                ("#000000", f"ΔΣQ = {sign}{n(dv)} п.п." + (" (B мельче)" if dv > 0.05 else
                                                         " (B крупнее)" if dv < -0.05 else ""))]
        return HoverInfo(f"Размер {size_fmt(x)} мкм", rows, vlines=[(ax1, x), (ax2, x)],
                         points=[(ax2, x, dv, "#ffff00")])
    return fn


def populations(ax, s):
    """q3*: измеренная плотность + популяции + модель."""
    from ..core.deconv import density_ln

    mid, q = density_ln(s)

    def extra(x):
        y = _interp(x, mid, q)
        return [] if y is None else [("#d9d9d9", f"измерено: q3* = {n(y)} %")]

    return curves(ax, value_fmt=lambda y: f"{n(y)} %", extra=extra)


def sieve(ax):
    return curves(ax, value_fmt=lambda y: f"ΣQ = {n(y)} %")


def packing(ax):
    return curves(ax, title_fmt=lambda x: f"Доля мелкой популяции {n(x, 0)} %",
                  value_fmt=lambda y: f"пористость {n(y)} %")


def tech_bars(ax, samples, sls, ebm):
    """Составные полосы окон печати: какой сегмент под курсором."""
    from ..core.windows import segments

    segs = [segments(s, sls, ebm) for s in samples]

    def fn(ev):
        p = data_xy(ax, ev)
        if p is None:
            return None
        x, y = float(p[0]), float(p[1])
        i = int(round(y))
        if not 0 <= i < len(samples) or abs(y - i) > 0.4:
            return None
        left = 0.0
        for g in segs[i]:
            if left <= x < left + g.pct or (g is segs[i][-1] and x >= left):
                return HoverInfo(samples[i].label,
                                 [(None, f"{g.name} {g.label} мкм: {n(g.pct)} % объёма")]
                                 + [(None, f"   {h.name} {h.label}: {n(h.pct)} %") for h in segs[i] if h is not g],
                                 rects=[(ax, left, i - 0.35, g.pct, 0.7)])
            left += g.pct
        return None
    return fn


def surface_bars(ax, rows):
    """Столбики «объём / поверхность» по фракциям."""
    def fn(ev):
        p = data_xy(ax, ev)
        if p is None:
            return None
        i = int(round(p[0]))
        if not 0 <= i < len(rows) or abs(p[0] - i) > 0.45:
            return None
        r = rows[i]
        ratio = r.surface_pct / r.volume_pct if r.volume_pct > 0 else None
        return HoverInfo(f"Фракция {r.label} мкм",
                         [("#b0b0b0", f"доля объёма: {n(r.volume_pct)} %"),
                          ("#2a78d6", f"доля поверхности: {n(r.surface_pct)} %"),
                          (None, f"поверхность / объём: ×{n(ratio, 2)}" if ratio else "")],
                         rects=[(ax, i - 0.42, 0, 0.84, max(r.volume_pct, r.surface_pct))])
    return fn


def kinetics(axes, res):
    """Ближайшая по времени точка: размеры (верхняя ось) или доли (нижняя)."""
    t = np.asarray(res.times, float)

    def fn(ev):
        for ax in axes:
            p = data_xy(ax, ev)
            if p is None:
                continue
            j = int(np.argmin(abs(t - p[0])))
            info = HoverInfo(f"{res.names[j]} — {n(t[j], 1)} ч", vlines=[(a, t[j]) for a in axes])
            for lab, xs, ys, col in _curves(ax):
                k = int(np.argmin(abs(xs - t[j])))
                unit = " мкм" if ax is axes[0] else " %"
                info.rows.append((col, f"{lab}: {n(ys[k], 2 if ax is axes[0] else 1)}{unit}"))
                info.points.append((ax, xs[k], ys[k], col))
            return info
        return None
    return fn


def scatter_points(ax, pts, xlabel, ylabel, radius_px=24):
    """Точечный график «структура — свойства»: ближайшая партия к курсору."""
    def fn(ev):
        if not ax.bbox.contains(ev.x, ev.y) or not pts:
            return None
        xy = ax.transData.transform([(p[1], p[2]) for p in pts])
        d = np.hypot(xy[:, 0] - ev.x, xy[:, 1] - ev.y)
        j = int(np.argmin(d))
        if d[j] > radius_px:
            return None
        name, x, y = pts[j]
        return HoverInfo(name, [(None, f"{xlabel}: {x:.4g}".replace(".", ",")),
                                (None, f"{ylabel}: {y:.4g}".replace(".", ","))],
                         points=[(ax, x, y, "#ffff00")])
    return fn
