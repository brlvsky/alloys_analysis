"""Командная строка: python -m psd_toolkit ..."""
import argparse

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="psd_toolkit",
        description="Обработка гранулометрии порошков (лазерная дифракция).",
    )
    p.add_argument("--version", action="version", version=__version__)
    p.add_subparsers(dest="command", title="команды (появятся на следующих этапах)")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
