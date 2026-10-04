"""Дымовой тест окна: загрузка, флажки, переименование, усреднение, экспорт (нужен дисплей)."""
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


@pytest.fixture(scope="module")
def win():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея для Tk")
    root.withdraw()
    from psd_lab.core.settings import Settings
    from psd_lab.gui import theme
    from psd_lab.gui.main_window import MainWindow

    theme.apply(root)
    w = MainWindow(root, Settings(), save_settings=False)
    yield w
    root.destroy()


def test_load_and_toggle(win):
    if not RAW.exists():
        pytest.skip("нет data/raw")
    win.load_paths([RAW])
    assert len(win.all_samples()) == 12
    assert len(win.summary.tree.get_children()) == 12
    sid = next(iter(win.items))
    win.toggle_item(sid)
    assert len(win.enabled_samples()) == 11
    assert len(win.summary.tree.get_children()) == 11
    win.toggle_item("f0")   # файл N_C_: часть включена → выключить все
    assert len(win.enabled_samples()) == 8
    win.set_all_enabled(True)
    assert len(win.enabled_samples()) == 12
    assert "Флаги: 3" in win.status.cells[2].cget("text")


def test_average_toggle_and_rename(win):
    win.v_avg.set(False)
    win.on_view_option()
    assert len(win.all_samples()) == 16
    win.v_avg.set(True)
    win.on_view_option()
    s = next(x for x in win.all_samples() if x.name == "N/C")
    win.apply_rename(s, "TANMB исходный")
    names = [x.name for x in win.all_samples()]
    assert "TANMB исходный" in names and "N/C" not in names
    renamed = next(x for x in win.all_samples() if x.name == "TANMB исходный")
    assert renamed.members == ["M4246", "M4247"]  # повторы по-прежнему усреднены


def test_exports(win, tmp_path):
    win.export_xlsx(tmp_path / "Сводка.xlsx")
    win.export_html(tmp_path / "отчёт.html", ask_open=False)
    win.export_png_all(tmp_path / "png")
    assert (tmp_path / "Сводка.xlsx").exists()
    assert "TANMB исходный" in (tmp_path / "отчёт.html").read_text(encoding="utf-8")
    assert len(list((tmp_path / "png").rglob("*.png"))) == 13
