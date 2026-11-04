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
    return theory_dl(), DEFAULT_THEORY_LABEL


DEFAULT_THEORY_LABEL = ("Planck 2018 best-fit LCDM (PLA minimum-theory R3.01; published best fit, "
                        "used only as a reference model)")


def theory_provenance_note(theory_file: str | None) -> str:
    """Label where the reference model came from (own model vs published result)."""
    if theory_file:
        return "user-supplied theory CSV (model computation from your own parameters)"
    return ("default reference model = Planck 2018 published best fit (published result, for comparison only). For your own "
            "analysis pass theory_file from compute_lcdm_theory_spectrum(params=...).")
