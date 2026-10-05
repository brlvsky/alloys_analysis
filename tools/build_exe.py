"""Сборка PSD-Lab через PyInstaller (one-folder, без консоли) + самопроверка + zip.

Запуск: python tools/build_exe.py   (обычно через build_exe.bat)

Шаги:
  1. PyInstaller → dist/PSD-Lab/ (PSD-Lab.exe, иконка, версия в свойствах файла);
  2. рядом с exe кладутся примеры (data/raw → dist/PSD-Lab/examples);
  3. копия программы в папку с кириллицей и пробелом в пути, там запускается --selftest;
  4. архив dist/PSD-Lab-<версия>-win64.zip (без папки PSD-Lab-data).
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psd_lab import APP_NAME, PROJECT, __version__  # noqa: E402

DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_DIR = DIST / APP_NAME
IS_WIN = sys.platform == "win32"
EXE = APP_DIR / (f"{APP_NAME}.exe" if IS_WIN else APP_NAME)


def step(msg):
    print(f"\n=== {msg}", flush=True)


def version_file() -> Path:
    """Файл версии для свойств exe (вкладка «Подробно» в проводнике)."""
    nums = [int(x) for x in __version__.split(".")] + [0, 0, 0, 0]
    v = tuple(nums[:4])
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v}, prodvers={v}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041904B0', [
      StringStruct('CompanyName', 'Учебный научный проект'),
      StringStruct('FileDescription', '{APP_NAME} — анализ гранулометрии порошков'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', '{APP_NAME}'),
      StringStruct('OriginalFilename', '{APP_NAME}.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{__version__}'),
      StringStruct('Comments', 'Проект: {PROJECT}')])]),
    VarFileInfo([VarStruct('Translation', [0x0419, 1200])])
  ]
)
"""
    p = BUILD / "version_info.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def run_pyinstaller():
    import PyInstaller.__main__

    sep = os.pathsep
    args = [
        str(ROOT / "tools" / "launcher.py"),
        "--name", APP_NAME,
        "--onedir", "--windowed", "--noconfirm", "--clean",
        "--distpath", str(DIST), "--workpath", str(BUILD / "pyinstaller"), "--specpath", str(BUILD),
        "--icon", str(ROOT / "assets" / "app.ico"),
        "--add-data", f"{ROOT / 'assets'}{sep}assets",
        "--hidden-import", "matplotlib.backends.backend_tkagg",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "scipy.special.cython_special",
        "--hidden-import", "scipy.optimize",
        "--hidden-import", "scipy.stats",
        "--exclude-module", "pytest",
        "--exclude-module", "pandas",   # в коде программы не используется (−22 МБ)
        "--exclude-module", "IPython",
        "--exclude-module", "PyQt5", "--exclude-module", "PyQt6",
        "--exclude-module", "PySide2", "--exclude-module", "PySide6",
    ]
    docs = ROOT / "psd_lab" / "docs"
    if docs.is_dir() and any(docs.iterdir()):
        args += ["--add-data", f"{docs}{sep}psd_lab/docs"]
    if IS_WIN:
        args += ["--version-file", str(version_file())]
    PyInstaller.__main__.run(args)


def fix_docx_paths():
    """python-docx открывает шаблоны по пути «docx/parts/../templates/…». В сборке модули лежат в архиве,
    папки docx/parts нет, и такой путь не открывается (ошибка при создании колонтитула отчёта Word).
    Создаём пустую папку — путь становится рабочим."""
    for base in (APP_DIR / "_internal" / "docx", APP_DIR / "docx"):
        if (base / "templates").is_dir():
            (base / "parts").mkdir(exist_ok=True)
            print(f"docx: создана папка {base / 'parts'}")


def copy_examples():
    src = ROOT / "data" / "raw"
    dst = APP_DIR / "examples"
    if dst.exists():
        shutil.rmtree(dst)
    files = [f for f in src.iterdir() if f.is_file() and not f.name.startswith(".")] if src.is_dir() else []
    if files:
        dst.mkdir(parents=True)
        for f in files:
            shutil.copy2(f, dst / f.name)
    print(f"Примеры: {len(files)} файл(ов) → {dst}")


def selftest_from_cyrillic_path() -> bool:
    """Копия программы в «Проверка кириллицы\\PSD-Lab» и запуск exe --selftest оттуда."""
    test_root = BUILD / "Проверка кириллицы и пробелов"
    if test_root.exists():
        shutil.rmtree(test_root)
    app_copy = test_root / APP_NAME
    shutil.copytree(APP_DIR, app_copy)
    exe = app_copy / EXE.name
    out = test_root / "результаты"
    cmd = [str(exe), "--selftest", "--out", str(out)]
    env = dict(os.environ)
    if not IS_WIN and not env.get("DISPLAY"):
        if shutil.which("xvfb-run"):
            cmd = ["xvfb-run", "-a", "-s", "-screen 0 1400x900x24"] + cmd
        else:
            print("Нет дисплея — самопроверка окна пропущена")
            return True
    t0 = time.time()
    r = subprocess.run(cmd, cwd=str(test_root), env=env, timeout=600)
    log = out / "screens" / "selftest.txt"
    text = log.read_text(encoding="utf-8") if log.exists() else "(нет selftest.txt)"
    print(text)
    shots = list((out / "screens").glob("*.png")) if (out / "screens").exists() else []
    ok = r.returncode == 0 and "SELFTEST: OK" in text and len(shots) >= 10
    print(f"Самопроверка exe из папки «{test_root.name}»: {'OK' if ok else 'ОШИБКА'} "
          f"(код {r.returncode}, скриншотов {len(shots)}, {time.time() - t0:.0f} с)")
    if ok:
        dst = ROOT / "out" / "screens_exe"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(out / "screens", dst)
        print(f"Скриншоты собранной программы: {dst}")
    return ok


def make_zip() -> Path:
    junk = APP_DIR / "PSD-Lab-data"
    if junk.exists():
        shutil.rmtree(junk)
    arch = "win64" if IS_WIN else f"{platform.system().lower()}-{platform.machine().lower()}"
    base = DIST / f"{APP_NAME}-{__version__}-{arch}"
    z = shutil.make_archive(str(base), "zip", root_dir=DIST, base_dir=APP_NAME)
    print(f"Архив: {z} ({Path(z).stat().st_size / 1e6:.0f} МБ)")
    return Path(z)


def main() -> int:
    step(f"Сборка {APP_NAME} {__version__} (Python {platform.python_version()}, {platform.system()})")
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)
    run_pyinstaller()
    if not EXE.exists():
        print(f"ОШИБКА: не найден {EXE}")
        return 1
    fix_docx_paths()
    copy_examples()
    step("Самопроверка собранной программы (путь с кириллицей и пробелами)")
    if not selftest_from_cyrillic_path():
        print("ОШИБКА: самопроверка не прошла — архив не создаётся")
        return 1
    step("Архив")
    make_zip()
    step(f"ГОТОВО: {EXE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
