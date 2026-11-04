"""Loaders: every public CMB spectrum -> one tidy record (pure numpy; no pydantic/mpl).

Unified record (dict of numpy arrays + metadata):
    ell, dl, err_lo, err_hi  (D_ell muK^2 for TT/TE/EE/BB; for PP: [L(L+1)]^2 C_L^phiphi / 2pi)
    cov (optional, same units squared), ell_min/ell_max (optional bin edges),
    window (optional, (nbin, n_ell) with window_ell), best_fit (optional, Planck binned BF).
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import numpy as np

from ..common import BUNDLED_DATA, data_cache_dir, fetch_file, get_cached
from ..registry import ACT_SACC, COBAYA_LENS, PLA

SPECTRA = ("TT", "TE", "EE", "BB", "PP")
PRIMARY = ("planck_pr3", "act_dr6", "spt3g_d1", "spt3g_2018")
LENSING = {"planck_pr3": "planck_pr3_lensing", "act_dr6": "act_dr6_lensing",
           "spt3g_d1": "spt3g_d1_lensing", "planck_pr3_lensing": "planck_pr3_lensing",
           "act_dr6_lensing": "act_dr6_lensing", "spt3g_d1_lensing": "spt3g_d1_lensing"}
LABELS = {"planck_pr3": "Planck PR3", "act_dr6": "ACT DR6", "spt3g_d1": "SPT-3G D1",
          "spt3g_2018": "SPT-3G 2018", "planck_pr3_lensing": "Planck PR3", "act_dr6_lensing": "ACT DR6",
          "spt3g_d1_lensing": "SPT-3G D1"}
THEORY_FILE = "COM_PowerSpect_CMB-base-plikHM-TTTEEE-lowl-lowE-lensing-minimum-theory_R3.01.txt"
KK_TO_PP = 2.0 / np.pi   # [L(L+1)]^2 C^phiphi / 2pi = (4 C^kk) / 2pi


def _rec(ell, dl, lo, hi=None, **extra) -> dict:
    ell = np.asarray(ell, float)
    r = {"ell": ell, "dl": np.asarray(dl, float), "err_lo": np.asarray(lo, float),
         "err_hi": np.asarray(lo if hi is None else hi, float)}
    r.update(extra)
    return r


# ------------------------------------------------------------------ Planck PR3
def _planck(spectrum: str, binned: bool) -> dict:
    if spectrum == "BB":
        p = fetch_file(PLA + "COM_PowerSpect_CMB-low-ell-BB-full_R3.01.txt", subdir="planck_pr3")
        a = np.loadtxt(p)
        return _rec(a[:, 0], a[:, 1], a[:, 2], note="Planck low-ell (2<=ell<=29) BB only; consistent with zero.")
    if binned:
        name = {"TT": "COM_PowerSpect_CMB-TT-binned_R3.01.txt",
                "TE": "COM_PowerSpect_CMB-TE-binned_R3.02.txt",
                "EE": "COM_PowerSpect_CMB-EE-binned_R3.02.txt"}[spectrum]
        a = np.loadtxt(fetch_file(PLA + name, subdir="planck_pr3"))
        # PLA binned products start at ell=30 (Delta-ell=30 bins); the 5th column is the
        # Planck best fit binned identically. Low-ell points: binned=False (download).
        return _rec(a[:, 0], a[:, 1], a[:, 2], a[:, 3], best_fit=a[:, 4],
                    note="Planck PR3 binned (ell>=30). Use binned=False for the unbinned 2<=ell spectrum.")
    a = np.loadtxt(fetch_file(PLA + f"COM_PowerSpect_CMB-{spectrum}-full_R3.01.txt", subdir="planck_pr3"))
    return _rec(a[:, 0], a[:, 1], a[:, 2], a[:, 3])


def theory_dl() -> dict:
    """Planck 2018 best-fit (plikHM TTTEEE+lowl+lowE+lensing) theory, indexed by ell (0..2508)."""
    def load():
        a = np.loadtxt(fetch_file(PLA + THEORY_FILE, subdir="planck_pr3"))
        n = int(a[-1, 0]) + 1
        out = {"ell": np.arange(n)}
        for j, s in enumerate(("TT", "TE", "EE", "BB", "PP"), start=1):
            v = np.zeros(n)
            v[a[:, 0].astype(int)] = a[:, j]
            out[s] = v
        return out
    return get_cached("planck_theory", load)


# ------------------------------------------------------------------ ACT DR6
def act_sacc_path() -> Path:
    dest = data_cache_dir() / "act_dr6" / "dr6_data_cmbonly.fits"
    if dest.is_file():
        return dest
    tgz = fetch_file(ACT_SACC, subdir="act_dr6")
    with tarfile.open(tgz) as t:
        member = next(m for m in t.getmembers() if m.name.endswith("dr6_data_cmbonly.fits"))
        data = t.extractfile(member).read()
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest


def _act(spectrum: str) -> dict:
    if spectrum not in ("TT", "TE", "EE"):
        raise ValueError("ACT DR6 CMB-only provides TT, TE, EE (lensing: spectrum='PP').")

    def load():
        import contextlib
        import warnings

        import sacc
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
            warnings.simplefilter("ignore")
            s = sacc.Sacc.load_fits(str(act_sacc_path()))
        cov = s.covariance.covmat
        out = {}
        for pol, dt, tr in (("TT", "cl_00", ("dr6_cmb_s0", "dr6_cmb_s0")),
                            ("TE", "cl_0e", ("dr6_cmb_s0", "dr6_cmb_s2")),
                            ("EE", "cl_ee", ("dr6_cmb_s2", "dr6_cmb_s2"))):
            ell, dl, ind = s.get_ell_cl(dt, *tr, return_ind=True)
            w = s.get_bandpower_windows(ind)
            c = cov[np.ix_(ind, ind)]
            out[pol] = _rec(ell, dl, np.sqrt(np.diag(c)), cov=c, window=np.asarray(w.weight).T,
                            window_ell=np.asarray(w.values), sacc_index=np.asarray(ind))
        out["_full_cov"] = cov
        return out
    return get_cached("act_dr6", load)[spectrum]


# ------------------------------------------------------------------ SPT-3G
def _spt_d1(spectrum: str) -> dict:
    if spectrum not in ("TT", "TE", "EE"):
        raise ValueError("SPT-3G D1 bandpowers: TT, TE, EE (lensing: spectrum='PP').")
    a = np.loadtxt(BUNDLED_DATA / "spt3g" / f"spt3gd1_mv_cleaned_bandpowers_{spectrum}.txt")
    return _rec(a[:, 0], a[:, 1], a[:, 2], ell_min=a[:, 0] - 25, ell_max=a[:, 0] + 25)


def _spt_2018(spectrum: str) -> dict:
    if spectrum not in ("TT", "TE", "EE"):
        raise ValueError("SPT-3G 2018 bandpowers: TT, TE, EE.")
    a = np.loadtxt(BUNDLED_DATA / "spt3g" / "SPT3G_2018_TTTEEE_MV_bdp.txt")
    j = {"TT": 2, "TE": 5, "EE": 8}[spectrum]
    m = a[:, j + 2] > 0
    return _rec(a[m, j], a[m, j + 1], a[m, j + 2], ell_min=a[m, 0], ell_max=a[m, 1])


# ------------------------------------------------------------------ lensing
def _lensing(dataset: str) -> dict:
    d = LENSING[dataset]
    if d == "planck_pr3_lensing":
        b = np.loadtxt(fetch_file(COBAYA_LENS + "smicadx12_Dec5_ftl_mv2_ndclpp_p_teb_consext8_bandpowers.dat",
                                  subdir="planck_pr3_lensing"))
        cov = np.loadtxt(fetch_file(COBAYA_LENS + "smicadx12_Dec5_ftl_mv2_ndclpp_p_teb_consext8_CMBmarged_cov.dat",
                                    subdir="planck_pr3_lensing"))
        return _rec(b[:, 3], b[:, 4], np.sqrt(np.diag(cov)), cov=cov, ell_min=b[:, 1], ell_max=b[:, 2],
                    hartlap=1.0)
    if d == "act_dr6_lensing":
        root = BUNDLED_DATA / "act_dr6_lensing"
        y = np.loadtxt(root / "clkk_bandpowers_act.txt") * KK_TO_PP
        cov = np.loadtxt(root / "covmat_act_cmbmarg.txt") * KK_TO_PP**2
        bins = np.loadtxt(root / "act_dr6_lensing_bins.txt")
        m = bins[:, 4] > 0
        nbin = int(m.sum())
        return _rec(bins[m, 3], y[m], np.sqrt(np.diag(cov)[m]), cov=cov[np.ix_(m, m)],
                    ell_min=bins[m, 1], ell_max=bins[m, 2], hartlap=(796 - nbin - 2.0) / (796 - 1.0),
                    note="ACT DR6 baseline bins (40<=L<=763).")
    root = BUNDLED_DATA / "spt3g"
    y = np.loadtxt(root / "SPT3G_D1_KK_GMV_bdp.txt") * KK_TO_PP
    cov = np.loadtxt(root / "SPT3G_D1_KK_GMV_cov_CMBmarg.txt") * KK_TO_PP**2
    w = np.loadtxt(root / "SPT3G_D1_KK_GMV_windows_sparse.txt")
    nb = len(y)
    lmax = int(w[:, 1].max())
    win = np.zeros((nb, lmax + 1))
    win[w[:, 0].astype(int), w[:, 1].astype(int)] = w[:, 2]
    L = np.arange(lmax + 1)
    centre = (win * L).sum(1) / win.sum(1)
    lo = np.array([L[np.nonzero(r)[0][0]] for r in win])
    hi = np.array([L[np.nonzero(r)[0][-1]] for r in win])
    return _rec(centre, y, np.sqrt(np.diag(cov)), cov=cov, ell_min=lo, ell_max=hi,
                window=win, window_ell=L, window_kind="kk", hartlap=(498 - nb - 2.0) / (498 - 1.0))


# ------------------------------------------------------------------ dispatcher
def load_spectrum(dataset: str, spectrum: str, binned: bool = True) -> dict:
    """One spectrum from one experiment as a tidy record."""
    spectrum = spectrum.upper()
    if spectrum not in SPECTRA:
        raise ValueError(f"spectrum must be one of {SPECTRA}")
    if spectrum == "PP" or dataset in ("planck_pr3_lensing", "act_dr6_lensing", "spt3g_d1_lensing"):
        if dataset not in LENSING:
            raise ValueError(f"No lensing bandpowers for {dataset!r}; use one of planck_pr3, act_dr6, spt3g_d1.")
        rec = _lensing(dataset)
    elif dataset == "planck_pr3":
        rec = _planck(spectrum, binned)
    elif dataset == "act_dr6":
        rec = _act(spectrum)
    elif dataset == "spt3g_d1":
        rec = _spt_d1(spectrum)
    elif dataset == "spt3g_2018":
        rec = _spt_2018(spectrum)
    else:
        raise ValueError(f"Unknown spectrum dataset {dataset!r}. Use one of {PRIMARY} (or *_lensing).")
    return dict(rec)


def binned_theory(rec: dict, theory: dict, spectrum: str) -> np.ndarray:
    """Theory D_ell (dict indexed by ell) in the record's bandpowers.

    Uses the bandpower window if present (ACT sacc; SPT lensing in C^kk), else the top-hat
    mean of D_ell over [ell_min, ell_max], else D_ell at the nearest integer ell.
    """
    t = np.asarray(theory[spectrum], float)
    if "window" in rec:
        L = np.asarray(rec["window_ell"]).astype(int)
        W = np.asarray(rec["window"])
        # a bin is predictable only if its whole window support lies within the theory range
        support_max = np.array([L[np.nonzero(r)[0][-1]] if np.any(r) else 0 for r in W])
        ok_bins = support_max < len(t)
        keep = L < len(t)
        out = W[:, keep] @ t[L[keep]]   # windows act linearly (SPT kk windows: same factor cancels)
        out[~ok_bins] = np.nan
        return out
    if "ell_min" in rec:
        out = []
        for a, b in zip(rec["ell_min"], rec["ell_max"], strict=True):
            a, b = int(np.ceil(a)), int(np.floor(b))
            b = min(b, len(t) - 1)
            out.append(t[a:b + 1].mean() if b >= a else np.nan)
        return np.array(out)
    idx = np.clip(np.rint(rec["ell"]).astype(int), 0, len(t) - 1)
    return t[idx]
