"""Распознавание таблиц разной формы: экспорты разных приборов и таблицы, набранные руками.

Во всех файлах — одно и то же логнормальное распределение (d50 = 30 мкм, σg = 1,6) в разной записи;
проверяется, что программа находит его и восстанавливает d50.
"""
import math

import numpy as np
import pytest

from psd_lab.core import load
from psd_lab.core.metrics import d_at

D50, SG = 30.0, 1.6


def Q(x):
    """Накопленная «мельче x», %."""
    from scipy.stats import norm

    x = np.asarray(x, float)
    with np.errstate(divide="ignore"):
        return 100 * norm.cdf(np.log(np.maximum(x, 1e-12) / D50) / math.log(SG))


LASER = np.round(np.geomspace(0.5, 300, 60), 3)          # «лазерная» сетка
SIEVES = [500, 300, 212, 150, 106, 75, 53, 45, 38, 25]    # сита, мкм (по убыванию)


def xlsx(path, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Лист1"
    for r in rows:
        ws.append(list(r))
    wb.save(path)
    return path


def csv(path, rows, sep=";"):
    path.write_text("\n".join(sep.join("" if v is None else str(v) for v in r) for r in rows), encoding="utf-8")
    return path


def one(path, d50=D50, rel=0.03):
    ss = load(path)
    assert len(ss) == 1, [s.name for s in ss]
    s = ss[0]
    assert d_at(s, 50) == pytest.approx(d50, rel=rel), s.meta.get("import_notes")
    return s


def retained(sieves):
    """Доли по ситам (остаток на сите — частицы крупнее сита и мельче предыдущего) + поддон."""
    q = Q(sieves)                    # sieves по убыванию
    top = 100 - q[0]
    out = [top] + [q[i - 1] - q[i] for i in range(1, len(sieves))]
    return out, q[-1]                # остатки на ситах, поддон


# ---------------------------------------------------------------- лазерные экспорты разных приборов
def test_title_rows_and_metadata(tmp_path):
    rows = [["Отчёт по гранулометрии"], ["Прибор: что-то", None, "Дата", "01.02.2024"], [],
            ["Размер, мкм", "ΣQ, %", "Q, %"]]
    prev = 0
    for x in LASER:
        rows.append([x, round(float(Q(x)), 3), round(float(Q(x)) - prev, 3)])
        prev = float(Q(x))
    rows += [[], ["Оператор", "Иванов"]]
    s = one(xlsx(tmp_path / "отчёт.xlsx", rows))
    assert s.meta["distribution"] == "cum"


def test_horiba_like_csv(tmp_path):
    rows = [["Sample", "Порошок 1"], ["Diameter(µm)", "q(%)", "Undersize(%)"]]
    prev = 0
    for x in LASER:
        rows.append([x, f"{float(Q(x)) - prev:.4f}", f"{float(Q(x)):.4f}"])
        prev = float(Q(x))
    one(csv(tmp_path / "horiba.csv", rows, sep=","))


def test_microtrac_like_descending(tmp_path):
    """Microtrac пишет от крупных к мелким: Size(um) | %Chan | %Pass."""
    xs = LASER[::-1]
    rows = [["Size(um)", "%Chan", "%Pass"]]
    for i, x in enumerate(xs):
        nxt = xs[i + 1] if i + 1 < len(xs) else 0
        rows.append([x, round(float(Q(x) - Q(nxt)), 4), round(float(Q(x)), 4)])
    s = one(xlsx(tmp_path / "microtrac.xlsx", rows))
    assert any("убыванию" in n for n in s.meta["import_notes"])


def test_malvern_like_rows(tmp_path):
    """Malvern: одна строка — одно измерение; в заголовке границы классов (на одну больше, чем долей)."""
    edges = np.round(np.geomspace(0.4, 400, 51), 4)
    head = ["Sample Name", "Measurement Date", "Obscuration"] + list(edges)
    rows = [head]
    for name in ("Партия А", "Партия Б"):
        q = np.diff(Q(edges))
        q = q / q.sum() * 100           # доли в классах (сумма 100)
        rows.append([name, "12.03.2024 10:00", 12.5] + [round(float(v), 5) for v in q] + [None])
    ss = load(xlsx(tmp_path / "malvern.xlsx", rows))
    assert [s.name for s in ss] == ["Партия А", "Партия Б"]
    for s in ss:
        assert d_at(s, 50) == pytest.approx(D50, rel=0.03)
        assert any("боком" in n for n in s.meta["import_notes"])


def test_sympatec_like(tmp_path):
    rows = [["x0/µm", "Q3/%", "q3lg"]]
    for x in LASER:
        rows.append([x, round(float(Q(x)), 3), 0.0])
    one(csv(tmp_path / "helos.txt", rows, sep="\t"))


def test_density_only(tmp_path):
    """Только плотность q3lg (dQ/dlg x) — интегрируется."""
    from scipy.stats import norm

    xs = np.geomspace(1, 300, 80)
    q3lg = 100 * norm.pdf(np.log10(xs / D50) / math.log10(SG)) / math.log10(SG)
    rows = [["x, мкм", "q3lg"]] + [[round(float(x), 4), round(float(v), 5)] for x, v in zip(xs, q3lg)]
    s = one(xlsx(tmp_path / "плотность.xlsx", rows), rel=0.05)
    assert s.meta["distribution"] == "density"


# ---------------------------------------------------------------- таблицы, набранные руками
def test_text_numbers_and_percent(tmp_path):
    rows = [["размер", "проход"]] + [[str(x).replace(".", ","), f"{float(Q(x)):.2f} %".replace(".", ",")]
                                     for x in LASER]
    one(xlsx(tmp_path / "текстом.xlsx", rows))


def test_fractions_of_one(tmp_path):
    rows = [["x", "F"]] + [[x, round(float(Q(x)) / 100, 5)] for x in LASER]
    s = one(xlsx(tmp_path / "доли.xlsx", rows))
    assert any("×100" in n for n in s.meta["import_notes"])


def test_millimetres(tmp_path):
    rows = [["Размер, мм", "Q, %"]] + [[round(x / 1000, 6), round(float(Q(x)), 3)] for x in LASER]
    s = one(xlsx(tmp_path / "мм.xlsx", rows))
    assert any("мм" in n for n in s.meta["import_notes"])


def test_residue_cumulative(tmp_path):
    rows = [["Сито, мкм", "Остаток, %"]] + [[x, round(100 - float(Q(x)), 3)] for x in sorted(SIEVES)]
    s = one(xlsx(tmp_path / "остаток.xlsx", rows), rel=0.08)
    assert s.meta["distribution"] == "residue"


def test_sieve_retained_with_pan(tmp_path):
    ret, pan = retained(SIEVES)
    rows = [["Сито, мкм", "Остаток на сите, %"]] + [[x, round(float(r), 3)] for x, r in zip(SIEVES, ret)]
    rows.append(["Поддон", round(float(pan), 3)])
    s = one(xlsx(tmp_path / "рассев.xlsx", rows), rel=0.08)
    assert s.meta["distribution"] == "sieve"
    # ΣQ на сите 45 мкм = поддон + остатки на ситах мельче 45
    assert np.interp(45, s.size_um, s.cum_pct) == pytest.approx(float(Q(45)), abs=0.05)


def test_mesh_numbers(tmp_path):
    mesh = [35, 50, 70, 100, 140, 200, 270, 325, 400, 500]       # = SIEVES в мкм по ASTM E11
    ret, pan = retained(SIEVES)
    rows = [["Mesh", "Retained, %"]] + [[m, round(float(r), 3)] for m, r in zip(mesh, ret)]
    rows.append(["Pan", round(float(pan), 3)])
    s = one(xlsx(tmp_path / "mesh.xlsx", rows), rel=0.08)
    assert any("ASTM E11" in n for n in s.meta["import_notes"])


def test_fraction_ranges_text(tmp_path):
    bounds = [0, 20, 45, 63, 100, 150, 250]
    rows = [["Фракция, мкм", "Доля, %"]]
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        lab = f"<{hi}" if lo == 0 else f"{lo}–{hi}"
        rows.append([lab, round(float(Q(hi) - Q(lo)), 3)])
    rows.append([">250", round(float(100 - Q(250)), 3)])
    # d50 по 6 классам — линейная интерполяция между 20 и 45 мкм: 32,5 вместо 30 — это грубость таблицы
    s = one(xlsx(tmp_path / "фракции.xlsx", rows), rel=0.12)
    assert s.meta["distribution"] == "ranges"


def test_sieve_notation_minus_plus(tmp_path):
    rows = [["Класс", "мас. %"], ["+150", round(float(100 - Q(150)), 3)],
            ["-150+106", round(float(Q(150) - Q(106)), 3)], ["-106+63", round(float(Q(106) - Q(63)), 3)],
            ["-63+45", round(float(Q(63) - Q(45)), 3)], ["-45+20", round(float(Q(45) - Q(20)), 3)],
            ["-20", round(float(Q(20)), 3)]]
    one(xlsx(tmp_path / "классы.xlsx", rows), rel=0.12)


def test_pairs_with_different_grids(tmp_path):
    """У каждого образца свой столбец размеров: x | ΣQ | x | ΣQ (разные сетки)."""
    g1, g2 = LASER, np.round(np.geomspace(1, 250, 40), 3)
    rows = [["x, мкм", "Образец 1", "x, мкм", "Образец 2"]]
    for i in range(max(len(g1), len(g2))):
        r = []
        for g, k in ((g1, 1.0), (g2, 2.0)):
            if i < len(g):
                r += [g[i], round(float(Q(g[i] / k)), 3)]
            else:
                r += [None, None]
        rows.append(r)
    ss = load(xlsx(tmp_path / "пары.xlsx", rows))
    assert [s.name for s in ss] == ["Образец 1", "Образец 2"]
    assert d_at(ss[0], 50) == pytest.approx(30, rel=0.03)
    assert d_at(ss[1], 50) == pytest.approx(60, rel=0.03)


def test_two_tables_stacked(tmp_path):
    rows = [["Партия 7"], ["Размер, мкм", "ΣQ, %"]] + [[x, round(float(Q(x)), 3)] for x in LASER]
    rows += [[], [], ["Партия 8"], ["Размер, мкм", "ΣQ, %"]] + [[x, round(float(Q(x / 2)), 3)] for x in LASER]
    ss = load(xlsx(tmp_path / "две.xlsx", rows))
    assert len(ss) == 2
    assert sorted(round(d_at(s, 50)) for s in ss) == [30, 60]


def test_many_samples_one_axis_and_junk(tmp_path):
    rows = [["Размер", "А-1", "А-2", "Примечание", "Б-1"]]
    for x in LASER:
        rows.append([x, round(float(Q(x)), 3), round(float(Q(x * 1.1)), 3), "ок", round(float(Q(x / 1.5)), 3)])
    ss = load(xlsx(tmp_path / "много.xlsx", rows))
    assert [s.name for s in ss] == ["А-1", "А-2", "Б-1"]


def test_nothing_found(tmp_path):
    rows = [["Просто текст"], [1, 2], [3, 4]]
    assert load(xlsx(tmp_path / "пусто.xlsx", rows)) == []


def test_passing_and_retained_same_sample(tmp_path):
    rows = [["Size, um", "% Passing", "% Retained"]] + [[x, round(float(Q(x)), 3), round(100 - float(Q(x)), 3)]
                                                        for x in LASER]
    s = one(xlsx(tmp_path / "pass_ret.xlsx", rows))
    assert any("та же кривая" in n for n in s.meta["import_notes"])


def test_lower_upper_size_columns(tmp_path):
    """Beckman-подобная таблица: нижняя и верхняя граница канала + доля в канале."""
    edges = np.round(np.geomspace(0.4, 400, 61), 4)
    rows = [["Channel Diameter (Lower)", "Channel Diameter (Upper)", "Volume %"]]
    for lo, hi in zip(edges[:-1], edges[1:]):
        rows.append([lo, hi, round(float(Q(hi) - Q(lo)), 5)])
    one(xlsx(tmp_path / "beckman.xlsx", rows))


def test_manual_recipe(tmp_path):
    """Ручной импорт: таблица, которую автомат не понимает (размеры через строку с пропусками)."""
    rows = [["Мой журнал"], ["d", None, "проба 1"]]
    for x in LASER[::3]:
        rows.append([x, "мкм", round(float(Q(x)), 2)])
    rows[5][2] = "нет"                       # опечатка в одной строке — в рецепте её можно не брать
    p = xlsx(tmp_path / "журнал.xlsx", rows)
    recipe = {"sheet": "Лист1", "orient": "cols", "axis": 0, "r0": 6, "r1": len(rows) - 1, "data": [2],
              "kind": "cum", "unit": "um", "names": {"2": "Проба 1"}}
    (s,) = load(p, recipe)
    assert s.name == "Проба 1" and d_at(s, 50) == pytest.approx(D50, rel=0.05)
    assert any("ручной" in n for n in s.meta["import_notes"])
    with pytest.raises(ValueError):
        load(p, dict(recipe, r0=2))          # в выбранных строках есть текст — понятная ошибка
