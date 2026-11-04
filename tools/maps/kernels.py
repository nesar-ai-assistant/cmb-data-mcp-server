"""Map kernels: pure functions (numpy + healpy), JSON in -> JSON out, files to cwd.

prepare_map_kernel             download a Planck PR3 CMB map (+ common mask) and downgrade it (cached FITS)
measure_power_spectrum_kernel  masked pseudo-C_ell (healpy anafast) with fsky, beam and pixel-window
                               correction, binned like the PLA Planck TT bandpowers -> D_ell [muK^2]

Imports ONLY numpy / healpy (declared pip_deps) and the stdlib+numpy sibling io module.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

try:  # package import (server) or flat import (facility node with tools/ on sys.path)
    from . import io as mio
except ImportError:  # pragma: no cover
    from maps import io as mio  # type: ignore

K_TO_UK = 1e6


def cache_root(cache_dir: str | None = None) -> Path:
    if cache_dir:
        p = Path(cache_dir)
    else:
        root = os.environ.get("COSMO_MCP_DATA")
        base = Path(root).expanduser() if root else Path.home() / ".cache" / "cosmo-mcp"
        p = base / "cmb-data-mcp-server"
    p = p / "planck_pr3_maps"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _hp():
    import healpy as hp
    return hp


def _ud(hp, m, nside, nested):
    return hp.ud_grade(m, nside, order_in="NESTED" if nested else "RING", order_out="RING")


def prepare_map_kernel(component: str = "smica_nosz", split: str = "full", nside: int = 1024,
                       mask: str = "common_int", polarization: bool = False, n_conn: int = 8,
                       cache_dir: str | None = None, keep_full_res: bool = True) -> dict:
    """DISPATCH KERNEL: download one Planck PR3 CMB map (+ common mask) and downgrade it.

    Writes cached RING-ordered FITS at ``nside``: map in muK (I, or I/Q/U) and the mask
    (pixel average of the nside-2048 mask, in [0,1]). Returns paths + summary stats.
    The full-resolution download is resumable; downgraded products are reused if present.
    """
    hp = _hp()
    if component not in mio.MAPS:
        raise ValueError(f"unknown component {component!r}; choose from {list(mio.MAPS)}")
    info = mio.MAPS[component]
    if polarization and not info["pol"]:
        raise ValueError(f"{component} is temperature-only; use 'smica' or 'commander' for Q/U")
    if split not in ("full", "hm1", "hm2"):
        raise ValueError("split must be full | hm1 | hm2")
    cache = cache_root(cache_dir)
    tag = f"{component}_{split}_n{nside}{'_iqu' if polarization else ''}"
    out_map = cache / f"{tag}.fits"
    out_mask = cache / f"mask_{mask}_n{nside}.fits"
    downloaded = []
    if not out_map.is_file():
        url = mio.map_url(component, split)
        src = mio.download_ranges(url, cache / url.rsplit("/", 1)[-1], n_conn=n_conn)
        downloaded.append(url)
        cols = ["I_STOKES"] + (["Q_STOKES", "U_STOKES"] if polarization else [])
        data, hdr = mio.read_healpix_columns(src, cols)
        nested = hdr.get("ORDERING", "NESTED").upper().startswith("NEST")
        maps = []
        for c in cols:
            m = data[c].astype(np.float64)
            bad = np.logical_or(~np.isfinite(m), m < -1e29)
            m[bad] = hp.UNSEEN
            m[~bad] *= K_TO_UK
            maps.append(_ud(hp, m, nside, nested))
        hp.write_map(str(out_map), maps if polarization else maps[0], overwrite=True, dtype=np.float32,
                     column_units="uK_CMB", extra_header=[("SRCFILE", url.rsplit("/", 1)[-1][:60]),
                                                          ("COMP", component), ("SPLIT", split)])
        if not keep_full_res:
            src.unlink(missing_ok=True)
    if not out_mask.is_file():
        url = mio.mask_url(mask)
        src = mio.download_ranges(url, cache / url.rsplit("/", 1)[-1], n_conn=n_conn)
        downloaded.append(url)
        field = mio.MASKS[mask]["field"]
        data, hdr = mio.read_healpix_columns(src, [field])
        nested = hdr.get("ORDERING", "NESTED").upper().startswith("NEST")
        hp.write_map(str(out_mask), _ud(hp, data[field].astype(np.float64), nside, nested),
                     overwrite=True, dtype=np.float32)
    m = np.atleast_2d(hp.read_map(str(out_map), field=None))
    mk = hp.read_map(str(out_mask))
    good = np.logical_and(mk > 0.999, m[0] != hp.UNSEEN)
    stats = {"rms_I_uK_in_mask": float(np.std(m[0][good])), "mean_I_uK_in_mask": float(np.mean(m[0][good])),
             "fsky_mask": float(np.mean(mk)), "fsky_binary": float(np.mean(mk > 0.999)),
             "n_unseen": int(np.sum(m[0] == hp.UNSEEN))}
    return {"map_file": str(out_map), "mask_file": str(out_mask), "nside": nside, "component": component,
            "split": split, "polarization": polarization, "mask": mask, "downloaded": downloaded,
            "beam_fwhm_arcmin": info["beam_fwhm_arcmin"], "units": "muK_CMB (thermodynamic)",
            "coord": "Galactic", "ordering": "RING", "stats": stats,
            "source_urls": [mio.map_url(component, split), mio.mask_url(mask)]}


def apodize_mask(mask: np.ndarray, apod_deg: float) -> np.ndarray:
    """Smooth a [0,1] mask with a Gaussian of FWHM ``apod_deg`` and re-zero the masked region.

    Simple 'C1-like' apodisation with healpy only: binary-threshold, smooth, then multiply by
    the binary mask so no masked (foreground) pixel gets weight.
    """
    hp = _hp()
    binary = (mask > 0.5).astype(float)
    if apod_deg <= 0:
        return binary
    sm = hp.smoothing(binary, fwhm=np.radians(apod_deg), iter=1)
    return np.clip(sm, 0, 1) * binary


def pla_tt_bins(lmin: int = 30, lmax: int = 2500, width: int = 30) -> list[list[int]]:
    """Delta-ell=30 bins [30-59], [60-89], ... matching the PLA COM_PowerSpect_CMB-TT-binned file."""
    return [[lo, min(lo + width - 1, lmax)] for lo in range(lmin, lmax + 1, width)]


def measure_power_spectrum_kernel(map_file: str | None = None, mask_file: str | None = None,
                                  beam_fwhm_arcmin: float = 5.0,
                                  lmax: int = 2000, apod_deg: float = 1.0, polarization: bool = False,
                                  bin_width: int = 30, lmin_bin: int = 30, remove_monopole_dipole: bool = True,
                                  out_stem: str = "cmb_pseudo_cl", method: str = "anafast",
                                  map_file2: str | None = None, map_spec: dict | None = None,
                                  map_spec2: dict | None = None) -> dict:
    """DISPATCH KERNEL: binned D_ell from a HEALPix CMB map and a mask.

    Pseudo-C_ell: C_ell = anafast(m * w) / (fsky_w2 * B_ell^2 * p_ell^2), with
    fsky_w2 = <w^2> (the standard f_sky correction for a smooth apodised mask w), B_ell the
    Gaussian beam of the map (5' FWHM for Planck PR3 SMICA/Commander) and p_ell the
    HEALPix pixel window of the map nside. Monopole/dipole are removed outside the mask
    first. method='namaster' uses pymaster's mode-coupling inversion instead (if installed).
    map_file2: a second map with independent noise (e.g. the hm2 half-mission map when
    map_file is hm1) -> CROSS-spectrum, which has no noise bias. Use it whenever the
    measurement must hold beyond ell ~ 1000, where the SMICA auto-spectrum is noise-dominated.
    map_spec / map_spec2: prepare_map_kernel kwargs (component, split, nside, mask) instead of
    paths - used on a facility node, which then downloads + downgrades the maps itself.
    Writes <out_stem>.csv (binned) and <out_stem>_unbinned.npz to cwd.
    """
    hp = _hp()
    if map_spec:
        prep = prepare_map_kernel(**map_spec, polarization=polarization, cache_dir=os.getcwd())
        map_file, mask_file = prep["map_file"], prep["mask_file"]
    if map_spec2:
        map_file2 = prepare_map_kernel(**map_spec2, polarization=polarization, cache_dir=os.getcwd())["map_file"]
    if not map_file or not mask_file:
        raise ValueError("give map_file + mask_file, or map_spec")
    fld = (0, 1, 2) if polarization else 0
    maps = np.atleast_2d(hp.read_map(map_file, field=fld))
    maps2 = np.atleast_2d(hp.read_map(map_file2, field=fld)) if map_file2 else None
    if polarization and maps.shape[0] < 3:
        raise ValueError("polarization=True needs an I/Q/U map (prepare with polarization=True)")
    nside = hp.get_nside(maps[0])
    if maps2 is not None and hp.get_nside(maps2[0]) != nside:
        raise ValueError("map_file and map_file2 must have the same nside")
    lmax = int(min(lmax, 3 * nside - 1))
    mask = hp.read_map(mask_file)
    if hp.get_nside(mask) != nside:
        mask = hp.ud_grade(mask, nside)
    unseen = np.zeros(maps.shape[1], bool)
    for m in list(maps) + (list(maps2) if maps2 is not None else []):
        unseen |= (m == hp.UNSEEN) | ~np.isfinite(m)
    mask = np.where(unseen, 0.0, mask)
    w = apodize_mask(mask, apod_deg)
    maps = np.where(unseen, 0.0, maps)
    if maps2 is not None:
        maps2 = np.where(unseen, 0.0, maps2)
    if remove_monopole_dipole:
        maps[0] = _rm_dipole(hp, maps[0], w)
        if maps2 is not None:
            maps2[0] = _rm_dipole(hp, maps2[0], w)
    bl = hp.gauss_beam(np.radians(beam_fwhm_arcmin / 60.0), lmax=lmax, pol=polarization)
    pw = hp.pixwin(nside, pol=polarization, lmax=lmax)
    fsky_w2 = float(np.mean(w**2))
    fsky_w4 = float(np.mean(w**4))
    ell = np.arange(lmax + 1)
    if method == "namaster":
        cl = _namaster_cls(maps, w, bl, pw, lmax, polarization, nside, maps2)
    else:
        m1 = maps * w if polarization else maps[0] * w
        m2 = None if maps2 is None else (maps2 * w if polarization else maps2[0] * w)
        raw = hp.anafast(m1, map2=m2, lmax=lmax, pol=polarization, iter=3)
        raw = np.atleast_2d(raw)
        cl = {"TT": raw[0] / fsky_w2}
        if polarization:
            cl["EE"], cl["BB"], cl["TE"] = raw[1] / fsky_w2, raw[2] / fsky_w2, raw[3] / fsky_w2
    b_t = bl[:, 0] if bl.ndim == 2 else bl
    p_t = pw[0] if polarization else pw
    tf = {"TT": (b_t * p_t) ** 2}
    if polarization:
        b_e, p_e = bl[:, 1], pw[1]
        tf.update({"EE": (b_e * p_e) ** 2, "BB": (b_e * p_e) ** 2, "TE": b_t * p_t * b_e * p_e})
    fac = ell * (ell + 1) / (2 * np.pi)
    dl = {k: np.where(tf[k] > 0, v / np.where(tf[k] > 0, tf[k], 1) * fac, 0.0) if method != "namaster"
          else v * fac for k, v in cl.items()}
    bins = pla_tt_bins(lmin_bin, lmax, bin_width)
    rows = []
    for lo, hi in bins:
        sl = slice(lo, hi + 1)
        lc = ell[sl]
        wts = 2 * lc + 1
        row = {"ell_min": lo, "ell_max": hi, "ell": float(np.sum(lc * wts) / np.sum(wts))}
        for k, v in dl.items():
            row[f"D_ell_{k}"] = float(np.sum(v[sl] * wts) / np.sum(wts))
        # Knox-formula Gaussian error (cosmic variance on the cut sky; no noise term)
        dtt = row["D_ell_TT"]
        nmodes = np.sum(wts) * fsky_w2**2 / fsky_w4
        row["err_TT_cv"] = float(dtt * np.sqrt(2.0 / nmodes))
        rows.append(row)
    keys = list(rows[0])
    csv_path = Path(f"{out_stem}.csv")
    with open(csv_path, "w") as fh:
        fh.write(",".join(keys) + "\n")
        for r in rows:
            fh.write(",".join(f"{r[k]:.8g}" for k in keys) + "\n")
    npz_path = Path(f"{out_stem}_unbinned.npz")
    np.savez(npz_path, ell=ell, **{f"D_ell_{k}": v for k, v in dl.items()})
    btt = np.array([r["D_ell_TT"] for r in rows])
    bell = np.array([r["ell"] for r in rows])
    sel = (bell > 100) & (bell < 400)
    ipk = int(np.argmax(np.where(sel, btt, -np.inf)))
    meta = {"nside": int(nside), "lmax": lmax, "fsky_w2": fsky_w2, "fsky_w4": fsky_w4,
            "fsky_binary": float(np.mean(mask > 0.5)), "apod_deg": apod_deg, "beam_fwhm_arcmin": beam_fwhm_arcmin,
            "method": method, "estimator": "cross (map1 x map2)" if map_file2 else "auto (includes noise bias)",
            "n_bins": len(rows), "first_peak_ell": float(bell[ipk]),
            "first_peak_D_ell": float(btt[ipk]), "spectra": sorted(dl)}
    Path(f"{out_stem}.json").write_text(json.dumps(meta, indent=1))
    return {"csv": str(csv_path.resolve()), "npz": str(npz_path.resolve()), "meta": meta}


def _rm_dipole(hp, tmap: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Fit and subtract monopole + dipole using only pixels with weight > 0.5."""
    m = tmap.copy()
    bad = w <= 0.5
    m[bad] = hp.UNSEEN
    m = np.asarray(hp.remove_dipole(m), dtype=float)
    m[bad] = 0.0
    return m


def _namaster_cls(maps, w, bl, pw, lmax, polarization, nside, maps2=None):  # pragma: no cover - optional dep
    import pymaster as nmt

    b_t = (bl[:, 0] if bl.ndim == 2 else bl) * (pw[0] if polarization else pw)
    f0 = nmt.NmtField(w, [maps[0]], beam=b_t, lmax=lmax)
    f1 = f0 if maps2 is None else nmt.NmtField(w, [maps2[0]], beam=b_t, lmax=lmax)
    b = nmt.NmtBin.from_nside_linear(nside, 1)
    cl00 = nmt.compute_full_master(f0, f1, b)[0]
    ells = b.get_effective_ells().astype(int)
    out = np.zeros(lmax + 1)
    keep = ells <= lmax
    out[ells[keep]] = cl00[: keep.sum()]
    return {"TT": out}
