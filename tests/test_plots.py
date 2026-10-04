"""Тесты графиков: файлы создаются, столбики не перенормированы."""
from pathlib import Path

import numpy as np
import pytest

from psd_toolkit import load
from psd_toolkit.metrics import average_repeats
from psd_toolkit.model import Sample
from psd_toolkit.plots import binned, nice_ceil, plot_all

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
    assert all(p.stat().st_size > 10_000 for p in made)
