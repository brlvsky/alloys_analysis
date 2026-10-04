"""Запуск PSD-Lab.

    python -m psd_lab                          — окно программы
    python -m psd_lab --batch data/raw --out out   — обработать папку без окна
    python -m psd_lab --selftest               — самопроверка окна со скриншотами
"""
import argparse
import sys
from pathlib import Path

from . import APP_NAME, __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="PSD-Lab",
        description=f"{APP_NAME} {__version__} — анализ гранулометрии порошков (лазерная дифракция).",
    )
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    p.add_argument("files", nargs="*", help="файлы или папки, которые открыть сразу")
    p.add_argument("--batch", metavar="ПАПКА", help="обработать папку без окна: графики, summary.xlsx, report.html")
    p.add_argument("--out", metavar="ПАПКА", default=None, help="куда сложить результаты (по умолчанию out)")
    p.add_argument("--lang", choices=["en", "ru"], help="язык подписей осей на графиках")
    p.add_argument("--bin", type=float, help="ширина столбика, мкм (по умолчанию шаг сетки)")
    p.add_argument("--xmax", type=float, help="предел оси X, мкм")
    p.add_argument("--no-average", action="store_true", help="не усреднять повторы")
    p.add_argument("--selftest", action="store_true",
                   help="загрузить data/raw, пройти по вкладкам, сохранить скриншоты в out/screens и закрыться")
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # кириллица в консоли Windows
    args = build_parser().parse_args(argv)

    if args.batch:
        from .core.report import run_batch
        from .core.settings import Settings

        st = Settings()
        if args.lang:
            st.lang = args.lang
        st.bin_um, st.xmax = args.bin, args.xmax
        st.average = not args.no_average
        out = Path(args.out or "out")
        lines = []

        def log(msg):
            # у exe без консоли print не виден — журнал дублируется в out/batch_log.txt
            print(msg)
            lines.append(msg)

        res = run_batch(Path(args.batch), out, st, log=log)
        out.mkdir(parents=True, exist_ok=True)
        (out / "batch_log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 0 if res.samples else 1

    from .gui.main_window import run_gui

    return run_gui(files=args.files, selftest=args.selftest, out=args.out)


if __name__ == "__main__":
    raise SystemExit(main())
