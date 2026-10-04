"""Тесты чтения и метрик на реальных файлах из data/raw/ (если файлов нет — skip)."""
import datetime as dt
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import norm

from psd_lab.core import load
from psd_lab.core.io_table import load_table
from psd_lab.core.metrics import average_repeats, compute, d43
from psd_lab.core.model import ERROR, INFO, WARN, Sample

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
NC, TANMB, CALC = RAW / "N_C_.xls", RAW / "TANMB_.xls", RAW / "Расчет.xlsx"


def need(*files):
    missing = [f.name for f in files if not f.exists()]
    if missing:
        pytest.skip(f"нет файлов: {missing}")


@pytest.fixture(scope="module")
def raw():
    need(NC, TANMB, CALC)
    return {f.name: load(f) for f in (NC, TANMB, CALC)}


def by_id(samples, meas_id):
    return next(s for s in samples if s.meas_id == meas_id)


def test_counts(raw):
    assert len(raw[NC.name]) == 8
    assert len(raw[TANMB.name]) == 5
    assert len(raw[CALC.name]) == 3
    assert {s.sheet for s in raw[NC.name]} == {"Sheet"}  # Лист1/Лист2/Во! не дают измерений
    assert [s.name for s in raw[CALC.name]] == ["6ч", "8ч", "10ч"]


def test_metadata(raw):
    s = by_id(raw[NC.name], "M4246")
    assert s.name == "N/C"
    assert s.meta["obscuration"] == 15
    assert s.meta["error"] == pytest.approx(0.2213, abs=1e-4)
    assert s.meta["date"].replace(second=0, microsecond=0) == dt.datetime(2020, 10, 26, 18, 13)
    assert s.meta["model"] == "Fraunhofer"
    s = by_id(raw[TANMB.name], "M4322")
    assert s.name == "П/С+1.5 Si"
    assert s.meta["obscuration"] == -37
    assert by_id(raw[TANMB.name], "M4347").meta["obscuration"] == 64


def test_flags(raw):
    allm = raw[NC.name] + raw[TANMB.name]
    for mid in ("M4251", "M4253", "M4322"):
        assert any(lvl == ERROR for lvl, _ in by_id(allm, mid).flags)
    assert any(lvl == WARN for lvl, _ in by_id(allm, "M4347").flags)
    assert [lvl for lvl, _ in by_id(allm, "M4246").flags] == [INFO]  # только TradeOff файла
    # TradeOff: в N_C_.xls различается в ~41 раз (флаг ИНФО), в TANMB_.xls — в 4,9 раза (флага нет)
    assert all(any(lvl == INFO and "TradeOff" in t for lvl, t in s.flags) for s in raw[NC.name])
    assert not any("TradeOff" in t for s in raw[TANMB.name] for _, t in s.flags)


def test_d43_matches_instrument(raw):
    allm = raw[NC.name] + raw[TANMB.name]
    assert len(allm) == 13
    for s in allm:
        assert d43(s) == pytest.approx(s.meta["d43_instrument"], abs=0.3), s.meas_id


REFERENCE = {
    #               d10    d50     d90    D43    <15   15–45 15–53 45–105 >53
    "N/C":          (5.81, 19.64, 60.43, 27.4, 38.5, 43.7, 48.3, 16.2, 13.2),
    "N/C+si":       (4.63, 13.31, 31.89, 16.2, 56.3, 41.1, 42.7, 2.6, 1.1),
    "N/C+C":        (4.11, 11.52, 23.81, 13.9, 66.8, 31.3, 31.4, 1.7, 1.8),
    "N/C+Y2O3":     (6.41, 15.67, 73.75, 27.6, 47.6, 31.2, 34.0, 19.0, 18.4),
    "П/С+1.5 Si":   (4.00, 12.31, 118.67, 33.8, 58.9, 22.6, 22.7, 6.3, 18.4),
    "П/С +0,5Si":   (6.82, 76.40, 147.00, 75.5, 23.9, 7.1, 10.4, 39.7, 65.7),
    "П/С +0,5C":    (4.46, 12.77, 108.80, 34.8, 57.3, 16.9, 17.7, 14.9, 25.1),
    "П/С +0,5Y2O3": (4.97, 21.87, 126.33, 52.5, 41.7, 11.6, 13.8, 28.7, 44.5),
    "П/С +1,5Y2O3": (5.18, 55.25, 138.00, 61.4, 34.2, 12.0, 14.9, 31.0, 50.9),
    "6ч":           (2.09, 6.94, 14.76, 7.8, 90.6, 9.4, 9.4, 0.0, 0.0),
    "8ч":           (1.79, 6.00, 13.16, 6.9, 94.0, 6.0, 6.0, 0.0, 0.0),
    "10ч":          (6.03, 9.14, 13.69, 9.5, 94.9, 5.1, 5.1, 0.0, 0.0),
}


def test_reference_values(raw):
    avg = [s for samples in raw.values() for s in average_repeats(samples)]
    assert sorted(s.name for s in avg) == sorted(REFERENCE)
    for s in avg:
        m = compute(s)
        ref = REFERENCE[s.name]
        got_d = (m["d10"], m["d50"], m["d90"])
        assert got_d == pytest.approx(ref[:3], abs=0.1), s.name
        assert m["d43"] == pytest.approx(ref[3], abs=0.1), s.name
        assert list(m["fractions"].values()) == pytest.approx(ref[4:], abs=0.2), s.name


def test_repeats_agree(raw):
    nc = next(s for s in average_repeats(raw[NC.name]) if s.name == "N/C")
    assert nc.members == ["M4246", "M4247"]
    assert nc.meta["repeat_spread_pp"] <= 0.8
    assert not any("Повторы" in t for _, t in nc.flags)


def test_lognormal_d50():
    d50, sigma = 30.0, 0.5
    x = np.arange(0.5, 500, 0.5)
    s = Sample(name="logn", size_um=x, cum_pct=100 * norm.cdf(np.log(x / d50) / sigma))
    m = compute(s)
    assert m["d50"] == pytest.approx(d50, rel=0.01)
    assert m["d10"] == pytest.approx(d50 * np.exp(-1.2816 * sigma), rel=0.01)


def test_no_renormalisation():
    s = Sample(name="cut", size_um=[10, 20, 30, 40], cum_pct=[20, 50, 70, 78.4])
    m = compute(s)
    assert m["fractions"][">53"] == pytest.approx(21.6)
    assert any(lvl == WARN for lvl, _ in s.flags) is False  # флаги ставит load()/check_quality
    from psd_lab.core.metrics import check_quality
    check_quality(s)
    assert any("78.4" in t for _, t in s.flags)


def test_csv_decimal_comma(tmp_path):
    f = tmp_path / "мой порошок.csv"
    rows = ["Размер;Образец А;Образец Б"] + [
        f"{x};{str(c).replace('.', ',')};{str(c / 100).replace('.', ',')}"
        for x, c in [(1, 2.5), (5, 10.0), (10, 35.5), (20, 70.0), (40, 95.0), (80, 100.0)]
    ]
    f.write_text("\n".join(rows), encoding="utf-8")
    ss = load_table(f)
    assert [s.name for s in ss] == ["Образец А", "Образец Б"]
    for s in ss:
        assert s.cum_pct[-1] == pytest.approx(100)
        assert s.size_um[0] == 0


def test_interval_column(tmp_path):
    f = tmp_path / "q.csv"
    f.write_text("x,Q\n" + "\n".join(f"{x},{q}" for x, q in
                                      [(5, 10), (10, 20), (15, 40), (20, 20), (25, 10)]), encoding="utf-8")
    (s,) = load_table(f)
    assert s.name == "q"
    assert list(s.cum_pct) == [0, 10, 30, 70, 90, 100]
