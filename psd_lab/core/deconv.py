"""М2. Популяции частиц: разложение накопленной кривой на смесь 1–3 логнормальных компонент.

    Q(x) = Σ wᵢ · Φ((ln x − ln mᵢ) / σᵢ),   Σ wᵢ = 1

mᵢ — медиана компоненты (мкм), σ_g = exp(σᵢ) — геометрическое стандартное отклонение.
Подгонка — scipy.optimize.least_squares по точкам накопленной кривой (x > 0), несколько
стартов; число компонент — по минимуму BIC = n·ln(RSS/n) + k·ln(n), k = 3K − 1.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares
from scipy.special import ndtr

from .model import Sample

MIN_SHOWN_PCT = 3.0       # компоненты меньше 3 % отдельно не показываются
SUBMICRON_UM = 1.0        # медиана < 1 мкм — «субмикронная» компонента (вероятный артефакт Фраунгофера)
SIGMA_BOUNDS = (0.08, 1.6)


@dataclass
class Component:
    weight_pct: float
    median_um: float
    sigma: float                 # σ в ln-шкале
    kind: str = ""               # «субмикронная», «мелкая», «средняя», «крупная», «основная»
    shown: bool = True

    @property
    def sigma_g(self) -> float:
        return float(np.exp(self.sigma))


@dataclass
class Population:
    """Популяция = группа компонент между провалами плотности смеси q3*(ln x)."""
    weight_pct: float
    mode_um: float               # положение максимума плотности
    lo_um: float | None          # границы по провалам (None — край)
    hi_um: float | None
    components: list = field(default_factory=list)
    kind: str = ""               # «мелкая», «крупная», «средняя», «основная», «субмикронная»


@dataclass
class DeconvResult:
    components: list[Component]
    r2: float
    k: int
    bic: dict = field(default_factory=dict)       # K → BIC
    x: np.ndarray | None = None                   # сетка (мкм, x > 0)
    cum_data: np.ndarray | None = None            # ΣQ, %
    cum_fit: np.ndarray | None = None             # ΣQ модели, %

    populations: list = field(default_factory=list)

    @property
    def visible(self) -> list[Component]:
        return [c for c in self.components if c.shown]

    @property
    def main(self) -> list[Component]:
        """Компоненты без субмикронной — «настоящие» популяции порошка."""
        return [c for c in self.components if c.kind != "субмикронная"]

    @property
    def main_populations(self) -> list[Population]:
        return [p for p in self.populations if p.kind != "субмикронная"]

    def fine(self) -> Population | None:
        """Мелкая популяция (если распределение многомодальное)."""
        main = self.main_populations
        return main[0] if len(main) >= 2 else None

    def coarse(self) -> Population | None:
        main = self.main_populations
        return main[-1] if len(main) >= 2 else None

    @property
    def bimodal(self) -> bool:
        return self.fine() is not None


def mixture_cdf(x, weights, ln_m, sig):
    z = (np.log(x)[:, None] - np.asarray(ln_m)[None, :]) / np.asarray(sig)[None, :]
    return ndtr(z) @ np.asarray(weights)


def component_pdf_ln(x, w, ln_m, sig):
    """Плотность по ln x (q3*), в долях на единицу ln x."""
    z = (np.log(x) - ln_m) / sig
    return w * np.exp(-0.5 * z * z) / (sig * np.sqrt(2 * np.pi))


def density_ln(s: Sample):
    """Экспериментальная q3*(ln x): ΔQ/Δln x в середине (геометрической) интервала, %."""
    x, c = s.size_um, s.cum_pct
    sel = x > 0
    x, c = x[sel], c[sel]
    lx = np.log(x)
    dq = np.diff(c)
    dlx = np.diff(lx)
    mid = np.exp((lx[:-1] + lx[1:]) / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        q = np.where(dlx > 0, dq / dlx, 0.0)
    return mid, q


# ---------------------------------------------------------------- подгонка
def _unpack(p, k):
    # веса через softmax (k−1 свободных), ln m, ln σ
    a = np.concatenate([[0.0], p[: k - 1]])
    w = np.exp(a - a.max())
    w /= w.sum()
    ln_m = p[k - 1: 2 * k - 1]
    sig = np.exp(p[2 * k - 1: 3 * k - 1])
    return w, ln_m, sig


def _pack(w, ln_m, sig):
    w = np.clip(np.asarray(w, float), 1e-6, None)
    a = np.log(w / w[0])[1:]
    return np.concatenate([a, ln_m, np.log(sig)])


def _starts(x, y, k, rng):
    """Стартовые точки: медианы из пиков q3* и квантилей + случайные."""
    lx = np.log(x)
    dq = np.diff(y)
    mid = (lx[:-1] + lx[1:]) / 2
    q = np.where(np.diff(lx) > 0, dq / np.diff(lx), 0)
    peaks = [mid[i] for i in range(1, len(q) - 1) if q[i] >= q[i - 1] and q[i] >= q[i + 1] and q[i] > 0.02 * q.max()]
    peaks = sorted(peaks, key=lambda v: -q[np.argmin(abs(mid - v))])[:5]
    quant = [lx[np.searchsorted(y, p)] if np.searchsorted(y, p) < len(lx) else lx[-1] for p in (0.1, 0.3, 0.5, 0.7, 0.9)]
    cands = sorted(set(np.round(peaks[:3] + quant[::2] + [np.log(0.5)], 3)))
    starts = []
    for combo in itertools.combinations(cands, k):
        starts.append((np.full(k, 1 / k), np.array(combo), np.full(k, 0.5)))
    starts = starts[:12]
    for _ in range(3):
        m = np.sort(rng.uniform(np.log(max(x[0], 0.1)), lx[-1], k))
        starts.append((rng.dirichlet(np.ones(k)), m, rng.uniform(0.2, 0.9, k)))
    return starts


def _fit_k(x, y, k, rng):
    lo_m, hi_m = np.log(max(x[0], 0.05)) - 1, np.log(x[-1]) + 1
    lb = np.concatenate([np.full(k - 1, -12), np.full(k, lo_m), np.full(k, np.log(SIGMA_BOUNDS[0]))])
    ub = np.concatenate([np.full(k - 1, 12), np.full(k, hi_m), np.full(k, np.log(SIGMA_BOUNDS[1]))])

    def resid(p):
        w, ln_m, sig = _unpack(p, k)
        return mixture_cdf(x, w, ln_m, sig) - y

    best = None
    for w0, m0, s0 in _starts(x, y, k, rng):
        p0 = np.clip(_pack(w0, np.clip(m0, lo_m + 1e-3, hi_m - 1e-3), np.clip(s0, *SIGMA_BOUNDS)), lb + 1e-9, ub - 1e-9)
        try:
            r = least_squares(resid, p0, bounds=(lb, ub), method="trf", x_scale="jac", max_nfev=200)
        except ValueError:
            continue
        rss = float(np.sum(r.fun ** 2))
        if best is None or rss < best[0]:
            best = (rss, r.x)
    return best


_CACHE: dict = {}


def fit(s: Sample, max_k: int = 3) -> DeconvResult:
    key = (s.size_um.tobytes(), s.cum_pct.tobytes(), max_k)
    if key in _CACHE:
        return _CACHE[key]
    sel = s.size_um > 0
    x = s.size_um[sel]
    y = np.clip(s.cum_pct[sel] / 100.0, 0, None)
    # точки после выхода кривой на плато не несут информации и перевешивают подгонку
    top = np.nonzero(y >= y.max() - 1e-9)[0]
    last = min(len(x), (top[0] + 3) if len(top) else len(x))
    x, y = x[:last], y[:last]
    n = len(x)
    rng = np.random.default_rng(12345)
    tss = float(np.sum((y - y.mean()) ** 2))
    fits, bic = {}, {}
    for k in range(1, max_k + 1):
        if 3 * k - 1 >= n - 2:
            break
        b = _fit_k(x, y, k, rng)
        if b is None:
            continue
        rss, p = b
        fits[k] = (rss, p)
        bic[k] = n * np.log(max(rss, 1e-12) / n) + (3 * k - 1) * np.log(n)
    k_best = min(bic, key=bic.get)
    rss, p = fits[k_best]
    w, ln_m, sig = _unpack(p, k_best)
    order = np.argsort(ln_m)
    comps = [Component(float(w[i] * 100), float(np.exp(ln_m[i])), float(sig[i])) for i in order]
    _classify(comps)
    res = DeconvResult(comps, r2=1 - rss / tss if tss > 0 else 1.0, k=k_best, bic=bic,
                       x=x, cum_data=y * 100, cum_fit=mixture_cdf(x, w, ln_m, sig) * 100)
    res.populations = populations(comps, x[0], x[-1])
    _CACHE[key] = res
    return res


VALLEY_DEPTH = 0.6   # провал считается разделом популяций, если плотность в нём < 60 % меньшего из соседних пиков


def populations(comps: list[Component], x_min: float, x_max: float) -> list[Population]:
    """Группирует компоненты в популяции по провалам плотности смеси q3*(ln x)."""
    grid = np.exp(np.linspace(np.log(max(min(x_min, 0.05), 0.01)), np.log(x_max * 3), 1200))
    dens = sum(component_pdf_ln(grid, c.weight_pct, np.log(c.median_um), c.sigma) for c in comps)
    peaks = [i for i in range(1, len(dens) - 1) if dens[i] >= dens[i - 1] and dens[i] > dens[i + 1]]
    peaks = [i for i in peaks if dens[i] > 0.01 * dens.max()]
    # провалы между соседними пиками; слабые провалы — склеиваем пики
    cuts = []
    merged = [peaks[0]] if peaks else []
    for p in peaks[1:]:
        a = merged[-1]
        v = a + int(np.argmin(dens[a:p + 1]))
        if dens[v] < VALLEY_DEPTH * min(dens[a], dens[p]):
            cuts.append(grid[v])
            merged.append(p)
        elif dens[p] > dens[a]:
            merged[-1] = p
    bounds = [None] + cuts + [None]
    pops = []
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        members = [c for c in comps if (lo is None or c.median_um >= lo) and (hi is None or c.median_um < hi)]
        if not members:
            continue
        sel = np.ones_like(grid, bool)
        if lo is not None:
            sel &= grid >= lo
        if hi is not None:
            sel &= grid < hi
        mode = float(grid[sel][np.argmax(dens[sel])])
        pops.append(Population(sum(c.weight_pct for c in members), mode, lo, hi, members))
    for p in pops:
        if p.mode_um < SUBMICRON_UM and p.weight_pct < 10:
            p.kind = "субмикронная"
    main = [p for p in pops if p.kind != "субмикронная"]
    if len(main) == 1:
        main[0].kind = "основная"
    elif main:
        main[0].kind = "мелкая"
        main[-1].kind = "крупная"
        for p in main[1:-1]:
            p.kind = "средняя"
    return pops


def _classify(comps: list[Component]) -> None:
    for c in comps:
        c.shown = c.weight_pct >= MIN_SHOWN_PCT
        if c.median_um < SUBMICRON_UM:
            c.kind = "субмикронная"
    main = [c for c in comps if c.kind != "субмикронная" and c.shown]
    if len(main) == 1:
        main[0].kind = "основная"
    elif len(main) >= 2:
        main.sort(key=lambda c: c.median_um)
        main[0].kind = "мелкая"
        main[-1].kind = "крупная"
        for c in main[1:-1]:
            c.kind = "средняя"
    for c in comps:
        if not c.kind:
            c.kind = "малая (< 3 %)"


def window_share(c: Component, lo: float | None, hi: float | None) -> float:
    """Доля объёма компоненты (в % от самой компоненты), попадающая в окно [lo, hi)."""
    ln_m = np.log(c.median_um)
    a = 0.0 if not lo else float(ndtr((np.log(lo) - ln_m) / c.sigma))
    b = 1.0 if hi is None else float(ndtr((np.log(hi) - ln_m) / c.sigma))
    return 100 * (b - a)
