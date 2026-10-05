"""Тесты графиков: файлы создаются, столбики не перенормированы."""
from pathlib import Path

import numpy as np
import pytest

from psd_lab.core import load
from psd_lab.core.metrics import average_repeats
from psd_lab.core.model import Sample
from psd_lab.core.plots import binned, nice_ceil, plot_all

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def test_binned_no_renormalisation():
    s = Sample(name="cut", size_um=[1, 2, 3, 4], cum_pct=[10, 40, 70, 78.4])
    edges, q = binned(s, 1)
    assert q.sum() == pytest.approx(78.4)
    edges, q = binned(s, 2)
    assert list(edges) == [0, 2, 4]
    assert list(q) == pytest.approx([40, 38.4])


def test_binned_non_multiple_width():
    s = Sample(name="lin", size_um=np.arange(1, 11), cum_pct=np.arange(1, 11) * 10.0)
    edges, q = binned(s, 2.5)
    assert list(q) == pytest.approx([25, 25, 25, 25])


def test_nice_ceil():
    assert nice_ceil(117) == 120
    assert nice_ceil(23) == 25
    assert nice_ceil(0.9) == 1


def test_plot_all(tmp_path):
    files = [RAW / "N_C_.xls", RAW / "TANMB_.xls", RAW / "Расчет.xlsx"]
    if not all(f.exists() for f in files):
        pytest.skip("нет исходных файлов")
    groups = [(f, average_repeats(load(f))) for f in files]
    made = plot_all(groups, tmp_path, lang="ru")
    assert len(made) == 13  # 12 образцов + compare.png
    assert (tmp_path / "compare.png").exists()
    assert (tmp_path / "Расчет" / "6ч.png").exists()
    assert all(p.stat().st_size > 10_000 for _, p in made)


def test_log_bins_conserve_and_merge():
    """Лог. интервалы: без перенормировки (сумма = разность ΣQ на краях), интервалы без точек прибора
    объединены; для обычных интервалов высота = Q, %."""
    import numpy as np

    from psd_lab.core import load
    from psd_lab.core.metrics import average_repeats, cum_at
    from psd_lab.core.plots import LOG_PER_DECADE, log_bins, x_limit, x_low

    raw = Path(__file__).resolve().parent.parent / "data" / "raw"
    if not (raw / "TANMB_.xls").exists():
        pytest.skip("нет исходных файлов")
    for s in average_repeats(load(raw / "TANMB_.xls")) + average_repeats(load(raw / "Расчет.xlsx")):
        e, h = log_bins(s, x_low(s), x_limit(s))
        w = np.diff(np.log10(e)) * LOG_PER_DECADE
        assert (h * w).sum() == pytest.approx(cum_at(s, e[-1]) - cum_at(s, e[0]), abs=1e-9)
        nodes = s.size_um[s.size_um > 0]
        for a, b in zip(e[:-1], e[1:]):      # в каждом интервале есть точка прибора
            assert np.any((nodes > a * 1.01) & (nodes <= b * 1.01))
        assert e[1] == pytest.approx(2.0, rel=0.01)   # сетка 0,1 → 2 мкм: первый интервал объединён


def test_draw_sample_log_axis():
    import matplotlib

    matplotlib.use("Agg")
    from psd_lab.core import load
    from psd_lab.core.metrics import average_repeats
    from psd_lab.core.plots import draw_sample, new_figure

    raw = Path(__file__).resolve().parent.parent / "data" / "raw"
    if not (raw / "Расчет.xlsx").exists():
        pytest.skip("нет исходных файлов")
    s = average_repeats(load(raw / "Расчет.xlsx"))[0]          # 6ч: сетка с 1 мкм
    fig = new_figure()
    ax, ax2 = draw_sample(fig, s, lang="ru", log_x=True)
    assert ax.get_xscale() == "log" and ax.get_xlim()[0] == pytest.approx(1.0)
    assert "1/10 декады" in ax.get_ylabel()
    assert any("мельче 1 мкм" in t.get_text() for t in ax.texts)   # то, что левее оси, подписано
