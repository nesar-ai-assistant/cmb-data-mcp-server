"""Shared helpers for the spectra tool modules (theory selection, CSV I/O)."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .data import theory_dl


def write_csv(path: Path, columns: dict) -> Path:
    keys = list(columns)
    n = len(next(iter(columns.values())))
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(keys)
        for i in range(n):
            w.writerow([f"{float(columns[k][i]):.8g}" for k in keys])
    return path


def read_theory_csv(path: str) -> dict:
    """Theory CSV written by compute_lcdm_theory_spectrum -> dict of arrays indexed by ell."""
    a = np.genfromtxt(path, delimiter=",", names=True)
    ell = a["ell"].astype(int)
    out = {"ell": np.arange(ell.max() + 1)}
    for s in ("TT", "TE", "EE", "BB", "PP"):
        if s in a.dtype.names:
            v = np.zeros(ell.max() + 1)
            v[ell] = a[s]
            out[s] = v
    return out


def get_theory(theory_file: str | None) -> tuple[dict, str]:
    if theory_file:
        return read_theory_csv(theory_file), f"theory CSV {Path(theory_file).name}"
    return theory_dl(), "Planck 2018 best-fit LCDM (PLA minimum-theory R3.01)"
