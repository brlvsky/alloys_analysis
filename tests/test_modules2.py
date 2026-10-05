"""М6 (упаковка), М7 (плотность составов), М9 (кинетика) — предельные случаи и данные проекта."""
from pathlib import Path

import numpy as np
import pytest

from psd_lab.core import density, kinetics, load, packing
from psd_lab.core.deconv import fit
from psd_lab.core.metrics import average_repeats

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


# ---------------------------------------------------------------- М6
@pytest.mark.parametrize("r", [0.01, 0.1, 0.3, 0.7, 1.0])
def test_single_fraction_gives_base_packing(r):
    assert packing.packing_fraction(0.0, r, 0.6) == pytest.approx(0.6)
    assert packing.packing_fraction(1.0, r, 0.6) == pytest.approx(0.6)


def test_infinite_size_ratio_limit():
    # предел Фёрнаса: φ_max = φ0 + (1 − φ0)·φ0 при доле мелкой фракции (1 − φ0)·φ0 / φ_max
    for phi0 in (0.55, 0.60, 0.64):
        x, phi = packing.optimum(1e-9, phi0)
        assert phi == pytest.approx(phi0 + (1 - phi0) * phi0, abs=1e-3)
        assert x == pytest.approx((1 - phi0) * phi0 / (phi0 + (1 - phi0) * phi0), abs=2e-3)


def test_equal_sizes_ideal_mixing():
    x = np.linspace(0, 1, 11)
    assert np.allclose(packing.packing_fraction(x, 1.0, 0.6), 0.6)


def test_packing_grows_with_size_ratio():
    assert packing.optimum(0.5)[1] < packing.optimum(0.2)[1] < packing.optimum(0.05)[1]


def test_packing_estimate_on_data():
    if not (RAW / "TANMB_.xls").exists():
        pytest.skip("нет data/raw")
    ss = {s.name: s for s in average_repeats(load(RAW / "TANMB_.xls")) + average_repeats(load(RAW / "N_C_.xls"))}
    e = packing.estimate(fit(ss["П/С +0,5Y2O3"]))
    assert e.applicable and 0.08 < e.r < 0.15 and e.x_fine == pytest.approx(0.526, abs=0.01)
    assert 0.6 < e.phi <= e.phi_opt < 0.84
    assert not packing.estimate(fit(ss["N/C"])).applicable      # одномодальный — оценка неприменима


# ---------------------------------------------------------------- М7
def test_formula_and_conversion():
    at = density.parse_formula("Ti-43.5Al-4Nb-1Mo-0.1B")
    assert at["Ti"] == pytest.approx(51.4) and at["Al"] == 43.5
    wt = density.at_to_wt(at)
    assert sum(wt.values()) == pytest.approx(100)
    back = density.wt_to_at(wt)
    assert all(back[e] == pytest.approx(at[e]) for e in at)
    with pytest.raises(ValueError):
        density.parse_formula("Ti-43.5Xx")


def test_pure_element_and_ti64():
    assert density.calculate("Ti").rho == pytest.approx(4.506)
    r = density.calculate("Ti-6Al-4V", "wt")
    assert r.rho == pytest.approx(4.43, rel=0.02)          # правило смесей ошибается ~1 % для Ti6Al4V
    assert not r.in_target


def test_tnm_and_additives_and_measured():
    r = density.calculate("Ti-43.5Al-4Nb-1Mo-0.1B", "at")
    assert 3.8 < r.rho < 4.2
    r2 = density.calculate("Ti-43.5Al-4Nb-1Mo-0.1B", "at", {"Y2O3": 1.5})
    assert sum(r2.wt.values()) == pytest.approx(100) and r2.wt["Y2O3"] == pytest.approx(1.5)
    r3 = density.calculate("Ti-43.5Al-4Nb-1Mo-0.1B", "at", measured=4.15)
    assert r3.rho == 4.15 and r3.delta_pct == pytest.approx(100 * (4.15 - 4.43) / 4.43)


# ---------------------------------------------------------------- М9
def test_time_from_name():
    assert [kinetics.time_from_name(n) for n in ("6ч", "10 h", "помол 30 мин", "N/C")] == [6, 10, 0.5, None]


def test_kinetics_old_data_growth_hint():
    if not (RAW / "Расчет.xlsx").exists():
        pytest.skip("нет data/raw")
    ss = load(RAW / "Расчет.xlsx")
    res = kinetics.analyse([(s, kinetics.time_from_name(s.name)) for s in ss])
    assert res.times == [6, 8, 10]
    assert not any(f.ok for f in res.fits.values())             # 3 точки — без подгонки
    assert res.hints and "агломерация" in res.hints[0]          # 8 ч → 10 ч размер вырос


def test_kinetics_fit_synthetic():
    t = np.array([0, 2, 4, 8, 16.0])
    y = kinetics.exp_model(t, 5, 40, 0.3)
    f = kinetics.fit(t, y)
    assert f.ok and f.params[0] == pytest.approx(5, rel=1e-3) and f.params[2] == pytest.approx(0.3, rel=1e-3)
    assert not kinetics.fit(t, [40, 20, 10, 12, 8]).ok          # немонотонно
