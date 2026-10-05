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
    import tempfile

    w = MainWindow(root, Settings(), save_settings=False,
                   db_file=Path(tempfile.mkdtemp()) / "тест.sqlite")
    yield w
    root.destroy()


def test_auto_scale():
    from psd_lab.gui.theme import auto_user_scale

    assert auto_user_scale(1920, 1080, 1.0) == 1.0     # Full HD, 100 %
    assert auto_user_scale(2560, 1440, 1.0) == 1.25    # 27″ 1440p, 100 %
    assert auto_user_scale(3840, 2160, 1.5) == 1.25    # 4K, Windows 150 %
    assert auto_user_scale(3840, 2160, 1.0) == 1.5     # 4K, 100 %


def test_welcome_then_load_and_toggle(win):
    if not RAW.exists():
        pytest.skip("нет data/raw")
    win.root.update_idletasks()
    assert win.welcome.winfo_manager() == "pack"       # без файлов — стартовая страница
    win.load_paths([RAW])
    assert win.welcome.winfo_manager() == ""           # после загрузки — график
    assert win.readouts.values[1].cget("text") == "19,64"  # d50 первого образца (N/C)


def test_same_file_other_folder_not_duplicated(win, tmp_path):
    import shutil

    copy = tmp_path / "копия" / "TANMB_.xls"
    copy.parent.mkdir()
    shutil.copy2(RAW / "TANMB_.xls", copy)
    before = len(win.groups)
    win.load_paths([copy])
    assert len(win.groups) == before
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


def test_module_tabs(win):
    from psd_lab.gui.main_window import TABS

    s = next(x for x in win.all_samples() if x.name == "П/С +0,5Y2O3")
    sid = next(k for k, v in win.items.items() if v is s)
    win.tree.selection_set(sid)
    win.root.update()
    for name in ("Популяции", "Технология", "Поверхность"):
        win.nb.select(TABS.index(name))
        win.root.update()
    pops = win.mod_tabs["Популяции"].pops.tree
    assert len(pops.get_children()) == 2                     # мелкая + крупная
    tech = win.mod_tabs["Технология"]
    tech.lo.delete(0, "end"), tech.lo.insert(0, "20")
    tech.on_sieve()
    assert win.st.sieve_window == [20.0, 53.0]
    assert tech.yield_bar.values[0].cget("text") != "—"
    surf = win.mod_tabs["Поверхность"]
    assert "91,9 % поверхности" in surf.headline.cget("text")


def test_database_tab_and_structure(win):
    from psd_lab.core import db
    from psd_lab.gui.dialogs.structure import StructureWindow
    from psd_lab.gui.main_window import TABS

    win.wait_db()
    assert win.db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 16
    win.nb.select(TABS.index("База данных"))
    win.root.update()
    tab = win.mod_tabs["База данных"]
    assert len(tab.blist.tree.get_children()) == 12
    bid = tab.batch_id
    db.insert(win.db, "chem", {"O_ppm": "1100"}, bid)
    tab.changed()
    assert len(tab.panels["chem"].grid_.tree.get_children()) == 1
    w = StructureWindow(win)
    win.root.update()
    keys = [k for k, _ in w.fields]
    w.cy.current(keys.index("chem.O_ppm"))
    w.redraw()
    assert len(w.table.tree.get_children()) == 1      # одна партия с химанализом
    w.destroy()


def test_packing_kinetics_density(win):
    from psd_lab.gui.dialogs.density import DensityWindow
    from psd_lab.gui.main_window import TABS

    s = next(x for x in win.all_samples() if x.name == "П/С +0,5Y2O3")
    sid = next(k for k, v in win.items.items() if v is s)
    win.tree.selection_set(sid)
    win.nb.select(TABS.index("Упаковка"))
    win.root.update()
    assert win.mod_tabs["Упаковка"].read.values[3].cget("text") == "52,6"   # доля мелкой популяции
    win.nb.select(TABS.index("Кинетика"))
    win.root.update()
    k = win.mod_tabs["Кинетика"]
    assert "агломерация" in k.hint.label.cget("text")
    d = DensityWindow(win)
    win.root.update()
    d.measured.insert(0, "4,15")
    d.calc()
    assert d.res.rho == 4.15 and not d.res.in_target              # измеренная 4,15 → −6,3 % — вне цели
    d.batch.set("П/С +0,5Y2O3")
    import tkinter.messagebox as mb

    orig, mb.showinfo = mb.showinfo, lambda *a, **k: None
    try:
        d.save()
    finally:
        mb.showinfo = orig
    row = win.db.execute("SELECT composition, density_measured FROM batches WHERE name='П/С +0,5Y2O3'").fetchone()
    assert "Ti-43.5Al" in row[0] and row[1] == 4.15
    d.destroy()


def test_method_tab_qc(win):
    from psd_lab.gui.main_window import TABS

    win.wait_db()
    s = next(x for x in win.all_samples() if x.name == "П/С +0,5Y2O3")
    sid = next(k for k, v in win.items.items() if v is s)
    win.tree.selection_set(sid)
    win.nb.select(TABS.index("Методика"))
    win.root.update()
    m = win.mod_tabs["Методика"]
    assert "Методика измерения" in m.text.get("1.0", "3.0")
    assert m.score.cget("text") == "QC: 1/5"                         # только автоматический пункт
    m.vars["background"].set(True)
    m.vars["ultrasound"].set(True)
    m.on_change()
    assert m.score.cget("text") == "QC: 3/5"
    tree = win.summary.tree
    qc_col = f"c{len(win.summary.cols) - 1}"
    vals = {tree.set(i, "c0"): tree.set(i, qc_col) for i in tree.get_children()}
    assert vals["П/С +0,5Y2O3"] == "3/5"
