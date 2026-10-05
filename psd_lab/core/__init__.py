"""Ядро PSD-Lab: чтение файлов, метрики, графики, отчёты. Не зависит от GUI."""
from __future__ import annotations

from pathlib import Path

SUPPORTED = (".xls", ".xlsx", ".xlsm", ".csv", ".txt", ".tsv", ".dat")


def load(path) -> list:
    """Читает файл: сначала как экспорт Fritsch, иначе как произвольную таблицу.

    Если в книге есть экспорт прибора, остальные листы (ручные расчёты) не читаются.
    """
    from .io_fritsch import load_fritsch
    from .io_table import load_table
    from .metrics import check_file, check_quality

    path = Path(path)
    samples = []
    if path.suffix.lower() in (".xls", ".xlsx", ".xlsm"):
        samples = load_fritsch(path)
    if not samples:
        samples = load_table(path)
    for s in samples:
        check_quality(s)
    check_file(samples)
    return samples


def file_sha1(path) -> str:
    """Отпечаток содержимого файла: один и тот же файл из разных папок узнаётся по нему."""
    import hashlib

    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expand_paths(paths) -> list[Path]:
    """Файлы и папки → список поддерживаемых файлов (временные файлы Excel ~$ пропускаются)."""
    import glob

    out = []
    for p in paths:
        if any(ch in str(p) for ch in "*?[") and not Path(p).exists():  # Windows не раскрывает маски
            out.extend(Path(m) for m in sorted(glob.glob(str(p))) if Path(m).is_file())
            continue
        p = Path(p)
        if p.is_dir():
            out.extend(sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED
                              and not f.name.startswith("~$")))
        elif p.exists():
            out.append(p)
    return out
