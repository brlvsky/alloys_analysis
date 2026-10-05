"""М2–М5: популяции, окна СЛС/СЭЛС, выход годного, удельная поверхность."""
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import norm

from psd_lab.core import load
from psd_lab.core.deconv import fit
from psd_lab.core.metrics import average_repeats, d32
from psd_lab.core.model import Sample
from psd_lab.core.surface import fine_shares, shares, ssa_m2_g
from psd_lab.core.windows import frac, requirements_check, segments, sieve

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
WINDOWS = [[None, 15], [15, 45], [15, 53], [45, 105], [53, None]]


@pytest.fixture(scope="module")
def samples():
    if not (RAW / "TANMB_.xls").exists():
        pytest.skip("нет data/raw")
    out = {}
    for f in ("N_C_.xls", "TANMB_.xls", "Расчет.xlsx"):
        for s in average_repeats(load(RAW / f)):
            out[s.name] = s
    return out


# ---------------------------------------------------------------- М2
FINE_PS = {"П/С+1.5 Si": 82, "П/С +0,5Si": 29, "П/С +0,5C": 74, "П/С +0,5Y2O3": 52, "П/С +1,5Y2O3": 44}


@pytest.mark.parametrize("name,expected", FINE_PS.items())
def test_fine_population_ps(samples, name, expected):
    r = fit(samples[name])
    assert r.bimodal
    assert r.fine().weight_pct == pytest.approx(expected, abs=5)
    assert 5 < r.fine().mode_um < 20          # мода мелкой популяции ~10 мкм


def test_r2_all(samples):
    for s in samples.values():
        assert fit(s).r2 > 0.995, s.name


def test_nc_y2o3_coarse_component(samples):
    r = fit(samples["N/C+Y2O3"])
    assert 12 <= r.coarse().weight_pct <= 25


def test_synthetic_mixture():
    x = np.arange(0.5, 400, 0.5)
    cum = 100 * (0.3 * norm.cdf(np.log(x / 8) / 0.35) + 0.7 * norm.cdf(np.log(x / 80) / 0.3))
    r = fit(Sample(name="смесь", size_um=x, cum_pct=cum))
    assert r.r2 > 0.9999
    assert r.fine().weight_pct == pytest.approx(30, abs=1.5)
    assert r.fine().mode_um == pytest.approx(8, rel=0.1)
    assert r.coarse().mode_um == pytest.approx(80, rel=0.1)


# ---------------------------------------------------------------- М3 / М4
def test_segments_sum_to_100(samples):
    for s in samples.values():
        for sls, ebm in (((15, 45), (45, 105)), ((15, 53), (45, 150)), ((20, 63), (45, 105))):
            assert sum(g.pct for g in segments(s, sls, ebm)) == pytest.approx(100, abs=1e-6)


def test_sieve(samples):
    s = samples["N/C"]
    r = sieve(s, 15, 53)
    assert r.yield_pct == pytest.approx(48.3, abs=0.2)           # = доля 15–53 из эталонной таблицы
    assert r.yield_pct + r.fines_pct + r.coarse_pct == pytest.approx(100, abs=1e-6)
    assert r.grams_per_kg() == pytest.approx(10 * r.yield_pct)
    assert r.sieved.cum_pct[-1] == pytest.approx(100)              # модель рассева — перенормирована
    assert frac(r.sieved, None, 15) == pytest.approx(0, abs=1e-9)
    after = {row.name: row.ok for row in requirements_check(r.sieved)}
    assert after["d10, мкм"] and after["d90, мкм"]


def test_requirements_fail_for_fine_powder(samples):
    ok = {r.name: r.ok for r in requirements_check(samples["6ч"])}
    assert not ok["d10, мкм"] and not ok["d50, мкм"] and not ok["Мельче 15 мкм, %"]
    assert ok["d90, мкм"]   # d90 = 14,8 мкм ≤ 53 — формально проходит


# ---------------------------------------------------------------- М5
def test_ssa_formula(samples):
    s = samples["N/C"]
    assert ssa_m2_g(s, 4.0) == pytest.approx(6 / (4.0 * d32(s)))
    assert ssa_m2_g(s, 2.0) == pytest.approx(2 * ssa_m2_g(s, 4.0))


def test_surface_shares(samples):
    for s in samples.values():
        rows = shares(s, WINDOWS)
        assert sum(r.volume_pct for r in rows) == pytest.approx(100, abs=1e-6)
        assert sum(r.surface_pct for r in rows) == pytest.approx(100, abs=1e-6)
    v, a = fine_shares(samples["П/С +0,5Y2O3"])
    assert v == pytest.approx(41.7, abs=0.2) and a > 2 * v       # мелочь даёт непропорционально много поверхности


def test_monodisperse_surface():
    # почти монодисперсный порошок 30 мкм: SSA ≈ 6/(ρ·30)
    s = Sample(name="mono", size_um=[29.9, 30.1], cum_pct=[0, 100])
    assert ssa_m2_g(s, 4.0) == pytest.approx(6 / (4.0 * 30), rel=0.01)
