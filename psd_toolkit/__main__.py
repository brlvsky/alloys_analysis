"""Командная строка: python -m psd_toolkit ..."""
import argparse
import sys

from . import __version__, expand_paths, load


def cmd_metrics(args) -> int:
    from .metrics import average_repeats, compute

    files = expand_paths(args.paths)
    if not files:
        print("Не найдено ни одного файла.", file=sys.stderr)
        return 1
    for f in files:
        samples = load(f)
        if args.average:
            samples = average_repeats(samples)
        print(f"\n=== {f.name}: образцов {len(samples)}")
        if not samples:
            continue
        frac_names = list(compute(samples[0])["fractions"])
        head = f"{'Образец':<28}{'d10':>8}{'d50':>8}{'d90':>8}{'span':>7}{'D43':>8}{'D32':>7}"
        head += "".join(f"{n:>9}" for n in frac_names)
        print(head)
        for s in samples:
            m = compute(s)
            line = f"{s.label[:27]:<28}{m['d10']:8.2f}{m['d50']:8.2f}{m['d90']:8.2f}{m['span']:7.2f}"
            line += f"{m['d43']:8.2f}{m['d32']:7.2f}" + "".join(f"{v:9.1f}" for v in m["fractions"].values())
            print(line)
            for lvl, text in s.flags:
                print(f"    [{lvl}] {text}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="psd_toolkit",
        description="Обработка гранулометрии порошков (лазерная дифракция).",
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", title="команды")

    m = sub.add_parser("metrics", help="таблица d10/d50/d90, D[4,3], долей и флагов")
    m.add_argument("paths", nargs="+", help="файлы или папки (например data/raw)")
    m.add_argument("--average", action=argparse.BooleanOptionalAction, default=True,
                   help="усреднять повторы с одинаковым названием (по умолчанию да)")
    m.set_defaults(func=cmd_metrics)
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # кириллица в консоли Windows
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
