"""Калькулятор шихты (версия 1.1): состав → навески по загрузкам барабана.

Термины:
* компонент — элемент (Ti) или соединение (CeO2), отвешиваемое как отдельный порошок;
* x — «мольные» доли компонентов, %: для элемента это ат.%, для соединения — мол.% формульных единиц
  (CeO2 считается одной частицей с M = M(Ce) + 2·M(O)); w — массовые доли компонентов, мас.%;
* перевод: wᵢ = xᵢ·Mᵢ / Σ xⱼ·Mⱼ и обратно; внутри — без округлений (округление только в fmt_*).

Добавки: «за счёт» компонента (по умолчанию основы) — его доля уменьшается на то же количество в тех же
единицах; «сверх» — остальные компоненты уменьшаются пропорционально. Порядок, если добавок несколько и
они вводятся вместе: сначала все добавки в ат.%/мол.% (за счёт, затем сверх), потом в мас.% (за счёт, затем
сверх) — внутри одной группы добавки не зависят от порядка.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from .elements import is_element, masses, normalize_name, parse_formula

SUM_TOL = 0.01                # допуск суммы состава, п.п.
OXYGEN_WARN_WT = 0.2          # порог предупреждения по кислороду из оксидов, мас.% (ориентир, не норматив)
LIGATURE_TOL = 0.005          # допустимое отклонение состава при подборе по заданной лигатуре, п.п.
ROUNDING_WARN_REL = 0.02      # предупреждать, если округление массовой доли может дать ошибку > 2 %

ASSUMPTIONS = ("идеальное смешение компонентов; потерь сверх заданного запаса нет; чистота порошков — по "
               "паспорту (примеси не учитываются, навеска только пересчитывается на содержание основного "
               "компонента); атомные массы — IUPAC (сокращённые значения, если не переопределены).")

UNITS = {"at": "ат.%", "wt": "мас.%", "mol": "мол.%"}


class ChargeError(ValueError):
    """Ошибка ввода — текст понятен пользователю."""


# ==================================================================== компоненты и состав
def check_component(name: str) -> str:
    """Нормализованное имя компонента; неизвестный элемент — ошибка."""
    n = normalize_name(name)
    try:
        parse_formula(n)
    except ValueError as e:
        raise ChargeError(str(e)) from e
    return n


def is_compound(name: str) -> bool:
    return not is_element(normalize_name(name))


def molar(name: str, m: dict) -> float:
    return sum(k * m[el] for el, k in parse_formula(normalize_name(name)).items())


@dataclass
class Composition:
    """Состав в единицах ввода: values — {компонент: %}, basis — "at" или "wt";
    decimals — сколько знаков после запятой было у каждого числа (для предупреждения об округлении)."""
    values: dict
    basis: str = "at"
    base: str | None = None
    decimals: dict = field(default_factory=dict)
    text: str = ""


_PART = re.compile(r"^(\d+(?:[.,]\d+)?)?\s*([A-Z][A-Za-z0-9()₀-₉]*)$")


def parse_composition(text: str, basis: str = "at") -> Composition:
    """«50Ti-44Al-4.9Nb-1Mo-0.1B» (все доли) или «Ti-44Al-4,9Nb-1Mo-0,1B» (Ti — основа, остаток до 100)."""
    if basis not in ("at", "wt"):
        raise ChargeError("единицы состава — ат.% или мас.%")
    t = (text or "").strip()
    if not t:
        raise ChargeError("состав не задан")
    # разделители — «-», «–», «—», «;»; пробелы между частями без дефиса («50Ti 44Al») тоже делят,
    # а пробел между числом и элементом («50 Ti») — нет
    parts = []
    for chunk in re.split(r"[-–—;]", t):
        parts += [re.sub(r"\s+", "", q) for q in re.split(r"\s+(?=\d)", chunk.strip()) if q.strip()]
    vals: dict[str, float] = {}
    dec: dict[str, int] = {}
    base = None
    for p in parts:
        m = _PART.match(p.strip())
        if not m:
            raise ChargeError(f"не понял «{p}»: ожидается число и элемент, например 44Al или 4,9Nb")
        num, comp = m.group(1), check_component(m.group(2))
        if num is None:
            if base is not None:
                raise ChargeError(f"основа указана дважды: «{base}» и «{comp}» — у остальных нужны числа")
            base = comp
            continue
        v = float(num.replace(",", "."))
        vals[comp] = vals.get(comp, 0.0) + v
        dec[comp] = len(num.replace(",", ".").split(".")[1]) if "." in num.replace(",", ".") else 0
    return _finish(vals, basis, base, dec, t)


def composition_from_table(rows, basis: str | None = None) -> Composition:
    """Таблица [(компонент, количество, единицы)]; количество None/«ост.» — основа (остаток до 100)."""
    vals, dec, base = {}, {}, None
    units = set()
    for comp, amount, unit in rows:
        if not str(comp or "").strip():
            continue
        c = check_component(str(comp))
        if unit in ("at", "wt"):
            units.add(unit)
        if amount is None or str(amount).strip().lower() in ("", "ост", "ост.", "остальное", "основа", "bal"):
            if base is not None:
                raise ChargeError("основа (остаток до 100) может быть только одна")
            base = c
            continue
        try:
            v = float(str(amount).replace(",", "."))
        except ValueError as e:
            raise ChargeError(f"{c}: «{amount}» — не число") from e
        u = unit or basis
        if u not in ("at", "wt"):
            raise ChargeError(f"{c}: укажите единицы — ат.% или мас.%")
        units.add(u)
        vals[c] = vals.get(c, 0.0) + v
        s = str(amount).replace(",", ".")
        dec[c] = len(s.split(".")[1]) if "." in s else 0
    if len(units) > 1:
        raise ChargeError("в одной таблице состава — одни единицы: все ат.% или все мас.%")
    return _finish(vals, (units.pop() if units else basis or "at"), base, dec, "")


def _finish(vals, basis, base, dec, text) -> Composition:
    for c, v in vals.items():
        if v < 0:
            raise ChargeError(f"{c}: отрицательное количество")
    total = sum(vals.values())
    if base is not None:
        rest = 100.0 - total
        if rest <= 0:
            raise ChargeError(f"сумма легирующих {total:g} % ≥ 100 % — для основы {base} ничего не остаётся")
        vals = {base: rest, **{k: v for k, v in vals.items() if k != base}}
    elif abs(total - 100.0) > SUM_TOL + 1e-9:
        raise ChargeError(f"сумма = {total:.4g} %, а должна быть 100 ± {SUM_TOL:g} % "
                          f"(или укажите основу без числа, например «Ti-44Al-…»)")
    if not vals:
        raise ChargeError("состав пуст")
    return Composition(vals, basis, base, dec, text)


# ==================================================================== перевод ат.% ↔ мас.%
def to_wt(x: dict, m: dict) -> dict:
    s = sum(v * molar(c, m) for c, v in x.items())
    return {c: 100.0 * v * molar(c, m) / s for c, v in x.items()}


def to_at(w: dict, m: dict) -> dict:
    s = sum(v / molar(c, m) for c, v in w.items())
    return {c: 100.0 * (v / molar(c, m)) / s for c, v in w.items()}


def sum_xm(x: dict, m: dict) -> float:
    """Σ xᵢ·Mᵢ (контрольная величина ручного расчёта)."""
    return sum(v * molar(c, m) for c, v in x.items())


def rounding_warnings(comp: Composition, m: dict) -> list[str]:
    """Округлённые массовые доли малых компонентов: 0,03 % бора вместо 0,0262 % — это +15 % бора."""
    if comp.basis != "wt":
        return []
    out = []
    for c, v in comp.values.items():
        if c == comp.base or v >= 1.0 or v <= 0:
            continue
        half = 0.5 * 10 ** (-comp.decimals.get(c, 0))
        rel = half / v
        if rel > ROUNDING_WARN_REL:
            out.append(f"{c} {_n(v)} мас.% задан с точностью ±{_n(half)} (до ±{rel * 100:.0f} % от навески {c}): "
                       f"если это округлённое значение, навеска будет неточной — задайте состав в ат.% "
                       f"или массовую долю с большим числом знаков")
    return out


# ==================================================================== добавки и варианты
@dataclass
class Additive:
    component: str
    amount: float
    unit: str | None              # at | wt | mol (для соединений — mol или wt, обязательно явно)
    mode: str = "instead"         # instead — «за счёт» компонента; over — «сверх»
    instead_of: str | None = None # за счёт чего (по умолчанию — основа)

    def label(self) -> str:
        u = UNITS.get(self.unit or "", "?")
        how = "сверх" if self.mode == "over" else f"за счёт {self.instead_of}" if self.instead_of else "за счёт основы"
        return f"+{_n(self.amount)} {u} {self.component} ({how})"


def check_additive(a: Additive, base: str | None) -> Additive:
    c = check_component(a.component)
    if a.unit not in ("at", "wt", "mol"):
        if is_compound(c):
            raise ChargeError(f"{c}: выберите единицы явно — мол.% (формульных единиц) или мас.%. "
                              f"Это разные смеси: 1,2 мол.% CeO₂ ≈ 4,8 мас.%, а 1,2 мас.% — в четыре раза меньше.")
        raise ChargeError(f"{c}: выберите единицы — ат.% или мас.%")
    if is_compound(c) and a.unit == "at":
        raise ChargeError(f"{c}: «ат.%» для соединения не определён — выберите мол.% (формульных единиц) или мас.%")
    if a.amount is None or a.amount <= 0:
        raise ChargeError(f"{c}: количество добавки должно быть больше 0")
    if a.mode not in ("instead", "over"):
        raise ChargeError(f"{c}: способ ввода — «за счёт» или «сверх»")
    instead = a.instead_of or base
    if a.mode == "instead" and not instead:
        raise ChargeError(f"{c}: укажите, за счёт какого компонента вводится добавка")
    return Additive(c, float(a.amount), "at" if (a.unit == "mol" and not is_compound(c)) else a.unit, a.mode,
                    check_component(instead) if instead else None)


def apply_additives(x0: dict, adds: list[Additive], m: dict) -> dict:
    """Базовый состав (x, %) + добавки → новый x. Ошибка, если «за счёт» компонента не хватает."""
    x = dict(x0)
    molar_adds = [a for a in adds if a.unit in ("at", "mol")]
    wt_adds = [a for a in adds if a.unit == "wt"]
    for a in [a for a in molar_adds if a.mode == "instead"]:
        _take(x, a, "ат.%/мол.%")
    over = [a for a in molar_adds if a.mode == "over"]
    if over:
        k = (100.0 - sum(a.amount for a in over)) / 100.0
        if k <= 0:
            raise ChargeError("добавки «сверх» в сумме ≥ 100 %")
        x = {c: v * k for c, v in x.items()}
        for a in over:
            x[a.component] = x.get(a.component, 0.0) + a.amount
    if wt_adds:
        w = to_wt(x, m)
        for a in [a for a in wt_adds if a.mode == "instead"]:
            _take(w, a, "мас.%")
        over = [a for a in wt_adds if a.mode == "over"]
        if over:
            k = (100.0 - sum(a.amount for a in over)) / 100.0
            if k <= 0:
                raise ChargeError("добавки «сверх» в сумме ≥ 100 %")
            w = {c: v * k for c, v in w.items()}
            for a in over:
                w[a.component] = w.get(a.component, 0.0) + a.amount
        x = to_at(w, m)
    return x


def _take(d: dict, a: Additive, unit: str):
    have = d.get(a.instead_of, 0.0)
    if a.amount > have + 1e-12:
        raise ChargeError(f"добавка {a.component} {_n(a.amount)} {unit} за счёт {a.instead_of}: "
                          f"{a.instead_of} в составе только {_n(have)} {unit}")
    d[a.instead_of] = have - a.amount
    if d[a.instead_of] <= 1e-15:
        d.pop(a.instead_of)
    d[a.component] = d.get(a.component, 0.0) + a.amount


@dataclass
class Variant:
    name: str
    x: dict                       # компоненты, ат.% / мол.%
    w: dict                       # компоненты, мас.%
    elements_at: dict             # элементы (с разложением соединений), ат.%
    elements_wt: dict             # элементы, мас.%
    oxygen: dict                  # {соединение: вклад O, мас.%}
    additives: list = field(default_factory=list)
    flags: list = field(default_factory=list)          # [(уровень, текст)]
    density: object = None        # density.DensityResult | None
    density_note: str = ""

    @property
    def oxygen_total(self) -> float:
        return sum(self.oxygen.values())


def make_variant(name: str, x: dict, m: dict, adds=(), o_warn: float = OXYGEN_WARN_WT) -> Variant:
    w = to_wt(x, m)
    el_w, el_x, oxy = {}, {}, {}
    for c, wc in w.items():
        f = parse_formula(c)
        mc = molar(c, m)
        for el, n in f.items():
            share = wc * n * m[el] / mc
            el_w[el] = el_w.get(el, 0.0) + share
            el_x[el] = el_x.get(el, 0.0) + x[c] * n
            if el == "O" and is_compound(c):
                oxy[c] = oxy.get(c, 0.0) + share
    sx = sum(el_x.values())
    el_x = {k: 100.0 * v / sx for k, v in el_x.items()}
    v = Variant(name, x, w, el_x, el_w, oxy, list(adds))
    if oxy and v.oxygen_total > o_warn:
        v.flags.append(("WARN", f"кислород из оксидов {_n(v.oxygen_total)} мас.% > {_n(o_warn)} %: кислород в оксиде при "
                                f"плавлении или помоле может частично перейти в матрицу и охрупчить сплав; "
                                f"проверить требования к O"))
    _density(v)
    return v


def _density(v: Variant):
    """Оценка плотности варианта моделью М7 (правило смесей) и Δ к Ti6Al4V."""
    from . import density

    missing = [c for c in v.w if density.component_density(c) is None]
    if missing:
        v.density_note = "нет справочной плотности для " + ", ".join(missing) + " — оценка плотности не делается"
        return
    rho = 1.0 / sum((wc / 100.0) / density.component_density(c) for c, wc in v.w.items())
    v.density = density.DensityResult(v.elements_at, v.w, rho, None)


def variants(comp: Composition, adds: list[Additive], mode: str = "each", overrides: dict | None = None,
             o_warn: float = OXYGEN_WARN_WT) -> list[Variant]:
    """Базовый состав + варианты: each — каждая добавка отдельно, all — все вместе, both — и то и другое."""
    m = masses(overrides)
    x0 = comp.values if comp.basis == "at" else to_at(comp.values, m)
    checked = [check_additive(a, comp.base or _largest(comp.values)) for a in adds]
    out = [make_variant("Базовый состав", dict(x0), m, (), o_warn)]
    if mode in ("each", "both"):
        for a in checked:
            out.append(make_variant(a.label(), apply_additives(x0, [a], m), m, [a], o_warn))
    if mode in ("all", "both") and len(checked) > (1 if mode == "both" else 0):
        out.append(make_variant("Все добавки вместе", apply_additives(x0, checked, m), m, checked, o_warn))
    return out


def _largest(vals: dict) -> str:
    return max(vals, key=vals.get)


# ==================================================================== загрузки
@dataclass
class LoadPlan:
    target_g: float
    capacity_g: float
    reserve_pct: float
    mode: str                     # full | equal
    n: int
    per_load_g: float
    made_g: float
    balls_ratio: float | None = None

    @property
    def reserve_g(self) -> float:
        return self.target_g * self.reserve_pct / 100.0

    @property
    def excess_g(self) -> float:
        """Избыток сверх нужной массы с запасом (только у «полных загрузок»)."""
        return self.made_g - self.target_g * (1 + self.reserve_pct / 100.0)

    @property
    def balls_g(self) -> float | None:
        return None if not self.balls_ratio else self.per_load_g * self.balls_ratio

    @property
    def note(self) -> str:
        if self.mode == "equal" and self.per_load_g < self.capacity_g - 1e-9:
            return ("загрузка неполная — чтобы сохранить режим помола, пропорционально уменьшите массу шаров "
                    "(соотношение шары : порошок)")
        return ""


def plan_loads(target_g: float, capacity_g: float, reserve_pct: float = 0.0, mode: str = "full",
               balls_ratio: float | None = None) -> LoadPlan:
    if capacity_g is None or capacity_g <= 0:
        raise ChargeError("ёмкость барабана должна быть больше 0 г")
    if target_g is None or target_g <= 0:
        raise ChargeError("нужная масса смеси должна быть больше 0 г")
    if reserve_pct < 0:
        raise ChargeError("запас на потери не может быть отрицательным")
    if balls_ratio is not None and balls_ratio < 0:
        raise ChargeError("соотношение шары : порошок не может быть отрицательным")
    need = target_g * (1 + reserve_pct / 100.0)
    n = max(1, math.ceil(need / capacity_g - 1e-9))
    if mode == "full":
        return LoadPlan(target_g, capacity_g, reserve_pct, mode, n, capacity_g, n * capacity_g, balls_ratio)
    if mode == "equal":
        return LoadPlan(target_g, capacity_g, reserve_pct, mode, n, need / n, need, balls_ratio)
    raise ChargeError("режим загрузок — «полные» или «равные»")


def weigh(w: dict, mass_g: float, purity: dict | None = None) -> dict:
    """Навески на массу mass_g: m = mass·w/100 / (чистота/100)."""
    out = {}
    for c, wc in w.items():
        p = (purity or {}).get(c, 100.0)
        if not p or p <= 0 or p > 100:
            raise ChargeError(f"{c}: чистота должна быть от 0 до 100 %")
        out[c] = mass_g * wc / 100.0 / (p / 100.0)
    return out


def purchase(w: dict, plan: LoadPlan, purity: dict | None = None) -> dict:
    """Итого на закупку: N × навеска одной загрузки."""
    return {c: plan.n * g for c, g in weigh(w, plan.per_load_g, purity).items()}


# ==================================================================== лигатура
@dataclass
class LigatureResult:
    lig_pct: float                       # доля лигатуры в шихте, мас.%
    lig_comp: dict                       # состав лигатуры, мас.%
    pure: dict                           # чистые компоненты, мас.% шихты
    result: dict = field(default_factory=dict)      # получившийся состав, мас.%
    deviation: dict = field(default_factory=dict)   # отклонение от цели, п.п.
    flags: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(lv == "ERROR" for lv, _ in self.flags)


def ligature_computed(w: dict, pure: set) -> LigatureResult:
    """Расчётная лигатура: всё, что не вводится чистым, — в лигатуру."""
    pure = {normalize_name(p) for p in pure}
    unknown = pure - set(w)
    if unknown:
        raise ChargeError("чистыми отмечены компоненты, которых нет в составе: " + ", ".join(sorted(unknown)))
    lig = {c: v for c, v in w.items() if c not in pure}
    if not lig:
        raise ChargeError("все компоненты отмечены чистыми — лигатуры нет")
    tot = sum(lig.values())
    return LigatureResult(tot, {c: 100.0 * v / tot for c, v in lig.items()}, {c: w[c] for c in w if c in pure},
                          dict(w), {c: 0.0 for c in w})


def ligature_given(w: dict, lig_comp: dict, pure: set | None = None, tol: float = LIGATURE_TOL) -> LigatureResult:
    """Заданная лигатура (мас.%): сколько её и каких чистых компонентов взять — неотрицательные наименьшие
    квадраты (scipy.optimize.nnls). pure — какие компоненты можно добавлять чистыми (по умолчанию — те,
    которых нет в лигатуре). Из точных решений выбирается то, где лигатуры больше."""
    from scipy.optimize import nnls

    lig = {normalize_name(k): float(v) for k, v in lig_comp.items() if v}
    s = sum(lig.values())
    if abs(s - 100.0) > 0.5:
        raise ChargeError(f"состав лигатуры в сумме {s:.3g} %, а должен быть 100 %")
    lig = {k: 100.0 * v / s for k, v in lig.items()}
    pure = {normalize_name(p) for p in (pure if pure is not None else set(w) - set(lig))}
    comps = sorted(set(w) | set(lig))
    cols = ["__lig__"] + sorted(pure)
    A = np.array([[lig.get(c, 0.0) / 100.0] + [1.0 if c == p else 0.0 for p in cols[1:]] for c in comps])
    b = np.array([w.get(c, 0.0) / 100.0 for c in comps])
    # баланс массы (доли в сумме 1) и слабое предпочтение «больше лигатуры» среди точных решений
    A = np.vstack([A * 100, np.ones(len(cols)) * 10, [1e-4] + [0.0] * (len(cols) - 1)])
    b = np.concatenate([b * 100, [10.0], [1e-4]])
    f, _ = nnls(A, b)
    res = {c: 100.0 * (f[0] * lig.get(c, 0.0) / 100.0 + sum(f[i] for i, p in enumerate(cols) if i and p == c))
           for c in comps}
    dev = {c: res[c] - w.get(c, 0.0) for c in comps}
    out = LigatureResult(100.0 * f[0], lig, {p: 100.0 * f[i] for i, p in enumerate(cols) if i and f[i] > 1e-12},
                         res, dev)
    worst = max(dev, key=lambda c: abs(dev[c]))
    if abs(dev[worst]) > tol:
        over = [c for c in comps if dev[c] > tol]
        why = ("в лигатуре " + ", ".join(over) + " больше, чем нужно по составу, а убрать лишнее нельзя"
               if over else "не хватает компонентов, которые можно добавить чистыми")
        out.flags.append(("ERROR", f"точно попасть в состав нельзя: {why}; наибольшее отклонение — {worst} "
                                   f"{dev[worst]:+.4f} п.п. Добавьте чистые компоненты или проверьте состав лигатуры"))
    return out


# ==================================================================== вывод
def _n(v: float) -> str:
    return f"{v:.6g}".replace(".", ",")


def fmt_pct(v: float) -> str:
    """Проценты: не меньше 4 значащих цифр для компонентов < 1 %, иначе 2 знака после запятой."""
    if v is None or v != v:
        return "—"
    if abs(v) < 1.0 and v != 0:
        digits = 4 - int(math.floor(math.log10(abs(v)))) - 1
        return f"{v:.{max(digits, 2)}f}".replace(".", ",")
    return f"{v:.2f}".replace(".", ",")


def fmt_g(v: float) -> str:
    """Граммы: 0,001 г для навесок < 1 г (аналитические весы), 0,01 г для остальных."""
    if v is None or v != v:
        return "—"
    return (f"{v:.3f}" if abs(v) < 1.0 else f"{v:.2f}").replace(".", ",")


def balance_accuracy(g: float) -> str:
    """Точность весов для бланка навесок."""
    return "0,001 г (аналитические)" if g < 1.0 else "0,01 г"


# ==================================================================== рецепт шихты целиком
@dataclass
class Recipe:
    """Всё, что задаёт пользователь на вкладке «Шихта» (и что сохраняется в JSON и в базу)."""
    alloy: str = ""                               # название сплава / партии
    composition: str = ""                         # строка состава
    basis: str = "at"                             # единицы состава: at | wt
    additives: list = field(default_factory=list) # [Additive]
    mode: str = "each"                            # each | all | both
    target_g: float = 1500.0
    capacity_g: float = 200.0
    reserve_pct: float = 0.0
    load_mode: str = "full"                       # full | equal
    balls_ratio: float | None = None
    purity: dict = field(default_factory=dict)    # {компонент: чистота, %}
    ligature_mode: str = "none"                   # none | computed | given
    pure_components: list = field(default_factory=list)   # что вводится чистым
    ligature_comp: dict = field(default_factory=dict)     # заданный состав лигатуры, мас.%
    mass_overrides: dict = field(default_factory=dict)    # переопределённые атомные массы
    oxygen_warn_wt: float = OXYGEN_WARN_WT
    notes: str = ""

    def to_json(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "additives"}
        d["additives"] = [{"component": a.component, "amount": a.amount, "unit": a.unit, "mode": a.mode,
                           "instead_of": a.instead_of} for a in self.additives]
        d["version"] = "1.1"
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Recipe":
        d = dict(d or {})
        d.pop("version", None)
        adds = [Additive(a.get("component", ""), float(a.get("amount") or 0), a.get("unit"),
                         a.get("mode", "instead"), a.get("instead_of")) for a in d.pop("additives", [])]
        known = {f for f in cls.__dataclass_fields__ if f != "additives"}
        unknown = set(d) - known
        if unknown:
            raise ChargeError("в файле рецепта незнакомые поля: " + ", ".join(sorted(unknown)))
        return cls(additives=adds, **d)


@dataclass
class Result:
    """Результат расчёта рецепта."""
    recipe: Recipe
    variants: list                                 # [Variant]; variants[0] — базовый состав
    plan: LoadPlan
    warnings: list = field(default_factory=list)   # предупреждения о вводе (округление мас.% и т. п.)
    ligature: object = None                        # LigatureResult | None

    @property
    def main(self) -> Variant:
        """Вариант, по которому считаются навески: последний (с добавками), иначе базовый."""
        return self.variants[-1]

    def loads(self, variant: Variant | None = None) -> dict:
        return weigh((variant or self.main).w, self.plan.per_load_g, self.recipe.purity)

    def purchase(self, variant: Variant | None = None) -> dict:
        return purchase((variant or self.main).w, self.plan, self.recipe.purity)


def calculate(recipe: Recipe) -> Result:
    """Полный расчёт по рецепту: варианты состава, загрузки, лигатура, предупреждения."""
    m = masses(recipe.mass_overrides)
    comp = parse_composition(recipe.composition, recipe.basis)
    warns = rounding_warnings(comp, m)
    vs = variants(comp, recipe.additives, recipe.mode, recipe.mass_overrides, recipe.oxygen_warn_wt)
    plan = plan_loads(recipe.target_g, recipe.capacity_g, recipe.reserve_pct, recipe.load_mode,
                      recipe.balls_ratio)
    lig = None
    w = vs[-1].w
    if recipe.ligature_mode == "computed":
        lig = ligature_computed(w, set(recipe.pure_components))
    elif recipe.ligature_mode == "given":
        lig = ligature_given(w, recipe.ligature_comp, set(recipe.pure_components) or None)
    for c, p in (recipe.purity or {}).items():
        if p and p < 100:
            warns.append(f"{c}: чистота {_n(p)} % — навеска увеличена в {100 / p:.4f} раза; "
                         f"примеси не учитываются")
    return Result(recipe, vs, plan, warns, lig)


EXAMPLE = Recipe(
    alloy="Пример: 50Ti-44Al-4,9Nb-1Mo-0,1B (задание коллеги)",
    composition="50Ti-44Al-4.9Nb-1Mo-0.1B", basis="at",
    additives=[Additive("C", 0.5, "at", "instead", "Ti"), Additive("Si", 0.5, "at", "instead", "Ti"),
               Additive("CeO2", 1.2, "mol", "instead", "Ti")],
    mode="both", target_g=1500.0, capacity_g=200.0, load_mode="full",
    ligature_mode="computed", pure_components=["Al"],
    notes="Задание: перевести состав в мас.% на 200 г; посчитать операции для 1,5 кг при барабане 200 г; "
          "пересчитать с добавками 0,5 ат.% C (за счёт Ti), 0,5 Si, 1,2 CeO₂.")
