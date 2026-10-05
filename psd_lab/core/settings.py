"""Настройки программы (settings.json) и папка данных.

Портативный режим: папка PSD-Lab-data рядом с exe (при запуске из исходников — в корне
проекта). Если туда писать нельзя — %APPDATA%\\PSD-Lab (или ~/.psd-lab вне Windows).
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

DATA_DIR_NAME = "PSD-Lab-data"


def app_base_dir() -> Path:
    """Папка программы: рядом с exe или корень проекта при запуске из исходников."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    """Где лежат встроенные ресурсы (assets/, docs/): в exe — _MEIPASS."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", app_base_dir()))
    return Path(__file__).resolve().parents[2]


def _writable(d: Path) -> bool:
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def data_dir() -> Path:
    portable = app_base_dir() / DATA_DIR_NAME
    if _writable(portable):
        return portable
    if os.name == "nt" and os.environ.get("APPDATA"):
        alt = Path(os.environ["APPDATA"]) / "PSD-Lab"
    else:
        alt = Path.home() / ".psd-lab"
    alt.mkdir(parents=True, exist_ok=True)
    return alt


@dataclass
class Settings:
    lang: str = "en"                 # подписи осей на экспортных графиках: en / ru
    bin_um: float | None = None      # ширина столбика, мкм (None — шаг сетки)
    xmax: float | None = None        # предел X, мкм (None — по d99)
    independent_axes: bool = False   # свои оси у каждого образца
    show_name: bool = True           # название образца в рамке
    average: bool = True             # усреднять повторы
    compare_log: bool = True         # логарифмическая ось X на сравнении
    windows: list = field(default_factory=lambda: [[None, 15], [15, 45], [15, 53], [45, 105], [53, None]])
    density_g_cm3: float = 4.0       # плотность материала для удельной поверхности
    sls_windows: list = field(default_factory=lambda: [[15, 45], [15, 53], [20, 63]])   # М3, мкм
    ebm_windows: list = field(default_factory=lambda: [[45, 105], [45, 150]])
    sls_index: int = 0               # выбранное окно СЛС для полос
    ebm_index: int = 0
    sieve_window: list = field(default_factory=lambda: [15, 53])                         # М4
    packing_phi0: float = 0.60       # М6: плотность случайной упаковки монофракции
    kinetics_times: dict = field(default_factory=dict)   # М9: {подпись образца: часы}
    requirements: dict = field(default_factory=lambda: {"d10_min": 15.0, "d50_min": 25.0,
                                                         "d50_max": 35.0, "d90_max": 53.0})
    splash: bool = True              # заставка при запуске
    show_log: bool = True            # панель «Журнал»
    ui_scale: float = 0              # масштаб интерфейса: 0 — авто, иначе 1.0…2.0
    toolbar_labels: bool = True      # подписи под кнопками тулбара
    geometry: str = ""               # размер и положение окна ("" — развернуть на весь экран)
    zoomed: bool = True              # окно развёрнуто
    reopen_session: bool = True      # открывать файлы прошлого сеанса
    session_files: list = field(default_factory=list)
    recent_files: list = field(default_factory=list)
    last_dir: str = ""

    @property
    def windows_tuples(self) -> list[tuple]:
        return [tuple(w) for w in self.windows]

    @property
    def sls(self) -> tuple:
        return tuple(self.sls_windows[min(self.sls_index, len(self.sls_windows) - 1)])

    @property
    def ebm(self) -> tuple:
        return tuple(self.ebm_windows[min(self.ebm_index, len(self.ebm_windows) - 1)])

    def add_recent(self, path, limit=8) -> None:
        p = str(path)
        if p in self.recent_files:
            self.recent_files.remove(p)
        self.recent_files.insert(0, p)
        del self.recent_files[limit:]

    # -------------------------------------------------------------- файл
    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or data_dir() / "settings.json"
        s = cls()
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return s
        known = {f.name for f in fields(cls)}
        for k, v in raw.items():
            if k in known:
                setattr(s, k, v)
        return s

    def save(self, path: Path | None = None) -> None:
        path = Path(path or data_dir() / "settings.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")


def parse_windows(text: str) -> list[list]:
    """'<15; 15-45; >53' → [[None, 15], [15, 45], [53, None]]."""
    out = []
    for part in text.replace(",", ".").split(";"):
        part = part.strip().replace("–", "-").replace(" ", "")
        if not part:
            continue
        if part.startswith("<"):
            out.append([None, float(part[1:])])
        elif part.startswith(">"):
            out.append([float(part[1:]), None])
        else:
            lo, hi = part.split("-")
            lo, hi = float(lo), float(hi)
            if hi <= lo:
                raise ValueError(f"окно {part}: верхняя граница должна быть больше нижней")
            out.append([lo, hi])
    if not out:
        raise ValueError("не задано ни одного окна")
    return out


def format_windows(windows) -> str:
    parts = []
    for lo, hi in windows:
        if lo is None:
            parts.append(f"<{hi:g}")
        elif hi is None:
            parts.append(f">{lo:g}")
        else:
            parts.append(f"{lo:g}-{hi:g}")
    return "; ".join(parts)
