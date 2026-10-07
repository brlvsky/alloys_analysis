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
    win.export_docx(tmp_path / "отчёт.docx", ask_open=False)
    win.export_png_all(tmp_path / "png")
    assert (tmp_path / "Сводка.xlsx").exists()
    assert "TANMB исходный" in (tmp_path / "отчёт.html").read_text(encoding="utf-8")
    assert (tmp_path / "отчёт.docx").stat().st_size > 100_000
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


def test_hover_tooltips(win):
    from psd_lab.core.metrics import cum_at
    from psd_lab.gui.main_window import TABS

    s = next(x for x in win.all_samples() if x.name == "П/С +0,5Y2O3")
    sid = next(k for k, v in win.items.items() if v is s)
    win.tree.selection_set(sid)
    win.nb.select(TABS.index("Распределение"))
    win.root.update()
    info = win.dist.hover_at(win.dist.figure.axes[0], 30, 2)
    want = f"{cum_at(s, 30):.1f}".replace(".", ",")
    assert info is not None and info.title.startswith("Размер 30")
    assert any(want in text for _, text in info.rows)
    assert info.rects and info.points                     # подсвечен столбик и точка на кривой
    win.nb.select(TABS.index("Сравнение"))
    win.root.update()
    info = win.cmp.hover_at(win.cmp.figure.axes[0], 20, 50)
    assert info is not None and len(info.rows) == len(win.enabled_samples())
    win.dist.hide_hover()
    win.cmp.hide_hover()


def test_pan_freezes_layout(win):
    """Сдвиг графика: на время перетаскивания раскладка «замораживается» (без tight layout на каждом
    кадре), после отпускания — снова tight; столбики — одна коллекция, а не сотни прямоугольников."""
    from matplotlib.backend_bases import MouseButton, MouseEvent
    from matplotlib.layout_engine import TightLayoutEngine

    if not win.all_samples():
        win.load_paths([RAW])
    win.nb.select(0)
    win.root.update()
    p = win.dist
    p.draw()
    p.canvas.draw()
    ax = p.figure.axes[0]
    assert len(ax.patches) == 0 and len(ax.collections) == 1
    c = p.canvas
    x, y = ax.bbox.x0 + ax.bbox.width / 2, ax.bbox.y0 + ax.bbox.height / 2
    p.pan()
    try:
        c.callbacks.process("button_press_event", MouseEvent("button_press_event", c, x, y, MouseButton.LEFT))
        assert not isinstance(p.figure.get_layout_engine(), TightLayoutEngine)
        x0 = ax.get_xlim()[0]
        c.callbacks.process("motion_notify_event", MouseEvent("motion_notify_event", c, x + 40, y,
                                                              MouseButton.LEFT, buttons={MouseButton.LEFT}))
        assert p._hover_drawn is False
        c.callbacks.process("button_release_event", MouseEvent("button_release_event", c, x + 40, y,
                                                               MouseButton.LEFT))
        assert ax.get_xlim()[0] != x0                       # график сдвинулся
        assert isinstance(p.figure.get_layout_engine(), TightLayoutEngine)
    finally:
        p.pan()
        p.home()


def test_compare_pair(win):
    """Сравнение «до и после»: два образца, разность кривых, таблица разницы, сохранение выбора."""
    if not win.all_samples():
        win.load_paths([RAW])
    win.nb.select(1)
    win.v_cmp_mode.set("pair")
    win.on_cmp_mode()
    win.root.update()
    labels = [s.label for s in win.all_samples()]
    a = next(x for x in labels if x.startswith("N/C (") or x.startswith("TANMB исходный"))
    b = next(x for x in labels if x.startswith("N/C+Y2O3"))
    win.cb_a.set(a)
    win.cb_b.set(b)
    win.on_pair_change()
    assert win.st.compare_pair == [a, b]
    assert win.pair_panel.winfo_manager() == "pack"
    rows = [win.pair_table.tree.item(i, "values") for i in win.pair_table.tree.get_children()]
    d50 = next(r for r in rows if r[0].startswith("d50"))
    assert d50[1] == "19,64" and d50[2] == "15,67" and d50[3] == "−3,97"
    assert "наибольшее расхождение" in win.pair_note.label.cget("text")
    ax1, ax2 = win.cmp.figure.axes[:2]
    info = win.cmp.hover_at(ax2, 20, 0)
    assert info is not None and "ΔΣQ" in info.rows[-1][1]
    win.swap_pair()
    assert win.st.compare_pair == [b, a]
    win.v_cmp_mode.set("all")
    win.on_cmp_mode()
    assert win.pair_panel.winfo_manager() == ""


def test_drag_and_drop(win, tmp_path):
    """Перетаскивание: tkdnd подключается, пути с пробелами и кириллицей разбираются, файл открывается."""
    import shutil

    from psd_lab.gui import dnd

    import time

    t0 = time.time()
    while not win.dnd and time.time() - t0 < 2:   # подключается через after(50) после старта окна
        win.root.update()
        time.sleep(0.02)
    assert win.dnd, "расширение tkdnd не загрузилось"
    assert dnd.enable.failed == [], "не все виджеты (в т.ч. главное окно) приняли перетаскивание"
    src = tmp_path / "папка с пробелом" / "Расчет копия.xlsx"
    src.parent.mkdir()
    shutil.copy2(RAW / "Расчет.xlsx", src)
    data = "{" + str(src) + "} {" + str(tmp_path / "нет такого.csv") + "}"
    paths = dnd.parse_paths(win.root, data)
    assert paths[0] == src and len(paths) == 2
    before = len(win.groups)
    win.on_drop([src.parent])          # папка целиком
    win.root.update()
    assert len(win.groups) >= before   # тот же файл (SHA-1) не дублируется, новый — добавляется


def test_help_window(win):
    """F1: руководство из README с оглавлением; раздел разработчика не показывается."""
    w = win.help("Флаги")
    win.root.update()
    titles = [w.toc.get(i).strip() for i in range(w.toc.size())]
    assert any("Флаги качества" in t for t in titles)
    assert not any("разработчика" in t for t in titles)
    assert w.toc.curselection()                      # раздел «Флаги» выделен
    assert len(w.text.image_names()) >= 3            # значки флагов в тексте
    assert win.help() is w                           # второе окно не создаётся
    w.destroy()


def test_distribution_log_axis(win):
    """Вид → Логарифмическая ось X распределения: ось и подсказка работают, настройка сохраняется."""
    if not win.all_samples():
        win.load_paths([RAW])
    win.nb.select(0)
    win.v_dlog.set(True)
    win.on_view_option()
    win.root.update()
    try:
        assert win.st.dist_log
        ax = win.dist.figure.axes[0]
        assert ax.get_xscale() == "log"
        info = win.dist.hover_at(ax, 10, 1)
        assert info is not None and info.title.startswith("Размер 10")
        assert any("ΣQ" in r[1] for r in info.rows)
    finally:
        win.v_dlog.set(False)
        win.on_view_option()
    assert win.dist.figure.axes[0].get_xscale() == "linear"


def test_import_wizard(win, tmp_path):
    """Мастер импорта: автопредложение, ручной выбор, рецепт запоминается и используется при открытии."""
    import openpyxl

    from psd_lab.gui.dialogs.import_wizard import ImportWizard

    f = tmp_path / "журнал.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Мой журнал"])
    ws.append(["d", "ед.", "проба 1"])
    for x, q in [(1, 2), (3, 9), (5, 20), (10, 45), (20, 75), (40, 95), (80, 100)]:
        ws.append([x, "мкм", q])
    wb.save(f)
    w = ImportWizard(win.root, f)
    win.root.update()
    assert w.cb_axis.current() == 0 and w.sp_r0.get() == "3"      # ось найдена сама
    w.lb_data.selection_clear(0, "end")
    w.lb_data.selection_set(2)
    w.update_preview()
    assert w.samples and "d50" in w.result_label.cget("text")
    w.on_ok()
    samples, recipe = w.result
    assert recipe["axis"] == 0 and recipe["data"] == [2] and len(samples) == 1
    # ошибка в настройке — понятный текст, а не падение
    w2 = ImportWizard(win.root, f, dict(recipe, r0=0))
    win.root.update()
    assert "Пока не получается" in w2.result_label.cget("text")
    w2.destroy()


def _hover(widget, x, y, wait=0.9):
    import time

    widget.event_generate("<Motion>", x=x, y=y, warp=False)
    t0 = time.time()
    while time.time() - t0 < wait:
        widget.update()
        time.sleep(0.02)


def test_section_help_on_hover(win):
    """Подержать мышь над вкладкой / полем результата / заголовком сводки — всплывает пояснение."""
    win.root.deiconify()
    win.root.update()
    nb = win.nb
    y = 8
    xs = [x for x in range(2, nb.winfo_width(), 4) if nb.identify(x, y) not in ("", "client")]
    x_cmp = next(x for x in xs if nb.index(f"@{x},{y}") == 1)
    _hover(nb, x_cmp, y)
    tip = win.tab_help
    assert tip.visible
    texts = [w.cget("text") for w in tip._tip.winfo_children()[0].winfo_children()]
    assert texts[0] == "Сравнение образцов"
    _hover(nb, 2, nb.winfo_height() - 5)          # ушли с вкладок — окошко пропадает
    assert not tip.visible

    from psd_lab.gui.help_texts import metric

    assert metric("d10, мкм")[0] == "d10" and metric("15–53 мкм, %")[0] == "Доля 15–53 мкм"
    win.root.withdraw()


def test_charge_tab(win, tmp_path):
    """Вкладка «Шихта»: пример считается, добавка и загрузки меняют результат, экспорт и база работают."""
    from psd_lab.core import db
    from psd_lab.core.charge import Additive

    ch = win.mod_tabs["Шихта"]
    win.nb.select(TABS_INDEX := [win.nb.tab(i, "text").strip() for i in range(win.nb.index("end"))].index("Шихта"))
    win.root.update()
    assert ch.result is not None, ch.msg.cget("text")
    assert ch.result.plan.n == 8 and len(ch.result.variants) == 5
    rows = [ch.t_var.tree.item(i, "values") for i in ch.t_var.tree.get_children()]
    assert rows[0][0] == "Базовый состав" and rows[0][1] == "57,91"          # Ti, мас.%
    # навески показываются по выбранному варианту
    ch.v_variant.set("Базовый состав")
    ch._show(ch.result)
    loads = {r[0]: r[1] for r in (ch.t_load.tree.item(i, "values") for i in ch.t_load.tree.get_children())}
    assert loads["Ti"] == "115,82" and loads["B"] == "0,052"

    # ошибка ввода — красным, без падения
    ch.e_cap.delete(0, "end")
    ch.e_cap.insert(0, "0")
    ch.recalc()
    assert ch.result is None and "ёмкость" in ch.msg.cget("text")
    ch.e_cap.delete(0, "end")
    ch.e_cap.insert(0, "200")
    ch.recalc()
    assert ch.result is not None

    # экспорт
    from psd_lab.core import charge_report

    x = charge_report.write_xlsx(ch.result, tmp_path / "Шихта.xlsx", variant=ch._chosen(ch.result))
    assert x.stat().st_size > 5000
    # рецепт в файл и обратно
    p = tmp_path / "рецепт.json"
    import json

    p.write_text(json.dumps(ch.recipe().to_json(), ensure_ascii=False), encoding="utf-8")
    ch._adds.clear()
    ch._fill_adds()
    ch.recalc()
    assert len(ch.result.variants) == 1
    ch.open_recipe(p)
    assert len(ch.result.variants) == 5 and ch.adds.tree.get_children()

    # сохранение в карточку партии
    bid = db.get_or_create_batch(win.db, "Тестовая партия")
    rid = db.charge_save(win.db, ch.recipe().to_json(), "из теста", bid)
    win.mod_tabs["База данных"].batch_id = bid
    win.mod_tabs["База данных"]._fill_charges()
    assert win.mod_tabs["База данных"].charge_ids == [rid]
    _ = Additive
