"""CMB map tools: fetch/downgrade Planck PR3 SMICA/Commander component-separated maps + masks,
mollview plots, and the map -> power spectrum reduction measure_cmb_power_spectrum."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from pydantic import Field, validate_call

from ..common import ArtifactResult, data_kind, data_cache_dir, mpl, ok, resolve_outdir, save_fig
from . import io as mio
from . import kernels

Component = Literal["smica_nosz", "smica", "commander"]
Split = Literal["full", "hm1", "hm2"]
Nside = Literal[128, 256, 512, 1024]

DISPATCH_KERNELS = {
    "prepare_cmb_map": {
        "function": "maps.kernels.prepare_map_kernel",
        "args_shape": "{'component': 'smica_nosz'|'smica'|'commander', 'split': 'full'|'hm1'|'hm2', "
                      "'nside': 128-1024, 'mask': 'common_int'|'common_pol', 'polarization': bool}",
        "pip_deps": ["numpy", "healpy"],
        "duration_hint_s": 1800,
        "returns": "{'map_file','mask_file' (downgraded RING FITS, muK), 'stats': {rms, fsky}, 'source_urls'}",
    },
    "measure_cmb_power_spectrum": {
        "function": "maps.kernels.measure_power_spectrum_kernel",
        "args_shape": "{'map_file': path, 'map_file2': path|None (cross), 'mask_file': path, "
                      "'beam_fwhm_arcmin': 5.0, 'lmax': int, 'apod_deg': float, 'polarization': bool, "
                      "'bin_width': 30, 'out_stem': str, 'method': 'anafast'|'namaster'}",
        "pip_deps": ["numpy", "healpy"],
        "duration_hint_s": 900,
        "returns": "{'csv' (binned D_ell muK^2 + Knox CV error), 'npz' (unbinned), 'meta': {fsky_w2, "
                   "first_peak_ell, first_peak_D_ell, ...}}; files written to the job cwd",
    },
}


def _prepare(component: str, split: str, nside: int, mask: str, polarization: bool) -> dict:
    from mcp_server.dispatch import remote_site, run_kernel  # lazy: server-only

    args = {"component": component, "split": split, "nside": nside, "mask": mask, "polarization": polarization}
    if remote_site():
        # cache_dir='.' -> products land in the job directory and come back as artifact_files
        res = run_kernel("maps.kernels.prepare_map_kernel", dict(args, cache_dir=".", keep_full_res=False),
                         pip_deps=["numpy", "healpy"], duration=2400)
        out = dict(res["result"], computed_on=res.get("host"))
        fetched = {Path(f).name: f for f in res.get("artifact_files", [])}
        for key in ("map_file", "mask_file"):
            out[key] = fetched.get(Path(out[key]).name, out[key])
        return out
    return dict(kernels.prepare_map_kernel(**args), computed_on="local")


@data_kind("catalog")
@validate_call
def fetch_cmb_map(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the downgraded map/mask FITS + JSON.")],
    component: Annotated[Component, Field(description="smica_nosz (T only, 403 MB download, default), smica "
                                                      "(I/Q/U, 2.0 GB) or commander (I/Q/U, 1.6 GB).")] = "smica_nosz",
    split: Annotated[Split, Field(description="full mission, or half-mission hm1 / hm2 (for noise-free "
                                              "cross-spectra; smica_nosz halves are 201 MB each).")] = "full",
    nside: Annotated[Nside, Field(description="Output HEALPix nside after ud_grade from 2048 (1024 keeps "
                                              "ell<~2000; 512 ell<~1000; 256 for quick looks).")] = 1024,
    mask: Annotated[Literal["common_int", "common_pol"], Field(description="Planck PR3 common mask "
                                                                         "(201 MB at nside 2048).")] = "common_int",
    polarization: Annotated[bool, Field(description="Also keep Q/U (smica / commander only).")] = False,
) -> ArtifactResult:
    """Fetch a Planck PR3 component-separated CMB MAP and its common mask, downgraded.

    Use this to start any map-level analysis (own power spectrum, cutouts, cross-correlation).
    The nside-2048 FITS is downloaded ONCE from IRSA with resumable parallel range requests
    into the data cache, then ud_graded to `nside` (RING, Galactic, muK_CMB); the downgraded
    map and mask are cached so later calls are instant. Planck PR3 SMICA/Commander beam: 5'
    FWHM Gaussian. Returns the map/mask paths (pass to measure_cmb_power_spectrum /
    plot_cmb_map), rms in the mask and fsky. Heavy (first call: minutes of download).
    """
    out = resolve_outdir(output_dir)
    info = mio.MAPS[component]
    r = _prepare(component, split, int(nside), mask, polarization)
    files = []
    for key in ("map_file", "mask_file"):
        src = Path(r[key])
        if src.is_file():
            dst = out / src.name
            if dst.resolve() != src.resolve():
                shutil.copyfile(src, dst)
            r[key] = str(dst)
            files.append(dst)
    jpath = out / f"cmb_map_{component}_{split}_n{nside}.json"
    jpath.write_text(json.dumps(r, indent=1))
    files.append(jpath)
    s = r["stats"]
    size = info["bytes_full"] if split == "full" else info["bytes_hm"]
    return ok(f"Planck PR3 {component} {split} map at nside {nside} (from 2048; source {size / 1e6:.0f} MB) + "
              f"{mask} mask: rms(T) in mask = {s['rms_I_uK_in_mask']:.1f} muK, fsky = {s['fsky_mask']:.3f}.",
              files, map_file=r["map_file"], mask_file=r["mask_file"], nside=int(nside), component=component,
              split=split, beam_fwhm_arcmin=r["beam_fwhm_arcmin"], units=r["units"], coord="Galactic",
              stats=s, source_urls=r["source_urls"], computed_on=r.get("computed_on"),
              note=info["note"], citation="Planck Collaboration 2020, A&A 641, A4 (arXiv:1807.06208)")


fetch_cmb_map.weight = "heavy"


@data_kind("catalog")
@validate_call
def measure_cmb_power_spectrum(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the binned CSV / npz / JSON.")],
    map_file: Annotated[str, Field(min_length=1, description="HEALPix map FITS from fetch_cmb_map (muK).")],
    mask_file: Annotated[str, Field(min_length=1, description="Mask FITS from fetch_cmb_map.")],
    map_file2: Annotated[str | None, Field(description="Optional second map with independent noise (hm2 when "
                                                       "map_file is hm1) -> cross-spectrum without noise bias. "
                                                       "Recommended for ell > 1000.")] = None,
    beam_fwhm_arcmin: Annotated[float, Field(gt=0, le=60, description="Gaussian beam FWHM of the map "
                                                                      "(Planck PR3 SMICA/Commander: 5).")] = 5.0,
    lmax: Annotated[int, Field(ge=50, le=3071, description="Max multipole (<= 2*nside is safe).")] = 2000,
    apod_deg: Annotated[float, Field(ge=0, le=10, description="Mask apodisation FWHM [deg] (0 = binary).")] = 1.0,
    polarization: Annotated[bool, Field(description="Also EE/BB/TE (needs an I/Q/U map).")] = False,
    bin_width: Annotated[int, Field(ge=1, le=200, description="Bin width (30 = PLA TT binning).")] = 30,
    method: Annotated[Literal["anafast", "namaster"], Field(description="anafast pseudo-C_ell / fsky "
                                                                        "(default) or pymaster MASTER if installed.")] = "anafast",
) -> ArtifactResult:
    """Measure the CMB TT (optionally EE/TE/BB) power spectrum FROM A MAP (from map to power spectrum).

    Use this for your own spectrum from Planck maps (instead of the released bandpowers).
    Pseudo-C_ell via healpy anafast of the (apodised) masked map, divided by fsky = <w^2>,
    the Gaussian beam^2 and the HEALPix pixel window^2; monopole/dipole removed. Binned in
    Delta-ell = 30 bins like the PLA TT file; errors are Knox cosmic-variance only (no noise
    term). Auto-spectra carry noise bias (SMICA: noticeable above ell ~ 1000), so pass the
    hm1/hm2 pair for a cross-spectrum. Heavy, dispatchable (set_dispatch). Sanity: first
    peak at ell ~ 220 with D_ell ~ 5700-5800 muK^2; within a few % of Planck TT at 30<ell<1500.
    """
    from mcp_server.dispatch import remote_site, run_kernel  # lazy: server-only

    out = resolve_outdir(output_dir)
    stem = Path(map_file).stem + ("_x_" + Path(map_file2).stem if map_file2 else "") + f"_cl_l{lmax}"
    args = {"map_file": str(Path(map_file).expanduser().resolve()),
            "map_file2": str(Path(map_file2).expanduser().resolve()) if map_file2 else None,
            "mask_file": str(Path(mask_file).expanduser().resolve()), "beam_fwhm_arcmin": beam_fwhm_arcmin,
            "lmax": lmax, "apod_deg": apod_deg, "polarization": polarization, "bin_width": bin_width,
            "out_stem": stem, "method": method}
    if method == "namaster":
        try:
            import pymaster  # noqa: F401
        except ImportError:
            raise RuntimeError("pymaster (NaMaster) is not installed (no macOS x86_64 wheel; `pip install "
                               "pymaster` on Linux); use method='anafast'.") from None
    site = remote_site()
    if site:
        # the node cannot see local paths: describe the maps (from the FITS headers written by
        # fetch_cmb_map) and let the kernel download + downgrade them itself.
        rargs = dict(args, map_spec=_spec_from_header(map_file, mask_file),
                     map_spec2=_spec_from_header(map_file2, mask_file) if map_file2 else None,
                     map_file=None, map_file2=None, mask_file=None)
        res = run_kernel("maps.kernels.measure_power_spectrum_kernel", rargs, pip_deps=["numpy", "healpy"],
                         duration=2400)
        payload, host = res["result"], res.get("host", site)
        files = [Path(f) for f in res.get("artifact_files", [])]
        for f in files:
            if f.is_file():
                shutil.copyfile(f, out / f.name)
        files = [out / f.name for f in files]
    else:
        import os
        cwd = os.getcwd()
        os.chdir(out)
        try:
            payload = kernels.measure_power_spectrum_kernel(**args)
        finally:
            os.chdir(cwd)
        host = "local"
        files = [Path(payload["csv"]), Path(payload["npz"]), out / f"{stem}.json"]
    meta = payload["meta"]
    cmp = _compare_planck_binned(out / f"{stem}.csv")
    png = _plot_vs_planck(out / f"{stem}.csv", out, stem, meta)
    if png:
        files.append(png)
    return ok(f"Pseudo-C_ell ({meta.get('estimator', 'auto')}, nside {meta['nside']}, fsky_w2 {meta['fsky_w2']:.3f}): "
              f"first peak ell = {meta['first_peak_ell']:.0f}, D_ell = {meta['first_peak_D_ell']:.0f} muK^2. "
              + (f"Vs released Planck TT bandpowers (30<ell<1500): median ratio {cmp['median_ratio']:.3f}, "
                 f"rms deviation {cmp['rms_frac_dev']:.3f}." if cmp else ""),
              files, csv=str(out / f"{stem}.csv"), computed_on=host, produces="summary_statistic",
              comparison_with_planck_tt_bandpowers=cmp, **meta,
              columns="ell_min, ell_max, ell, D_ell_TT[, D_ell_EE, D_ell_BB, D_ell_TE], err_TT_cv (muK^2)",
              caveats="Pseudo-C_ell/fsky is approximate (no mode-coupling inversion); residual foregrounds and "
                      "noise (auto) not modelled; errors are Knox cosmic variance only.")


measure_cmb_power_spectrum.weight = "heavy"


def _plot_vs_planck(csv_path: Path, out: Path, stem: str, meta: dict) -> Path | None:
    """Measured D_ell^TT vs the released Planck PR3 TT bandpowers, with ratio panel."""
    from ..spectra.data import load_spectrum

    if not csv_path.is_file():
        return None
    a = np.genfromtxt(csv_path, delimiter=",", names=True)
    plt = mpl()
    fig, (ax, axr) = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True, gridspec_kw={"height_ratios": [3, 1.3]})
    ax.errorbar(a["ell"], a["D_ell_TT"], a["err_TT_cv"], fmt="o", ms=3, color="C3",
                label=f"this measurement ({meta.get('estimator', '').split(' ')[0]}, nside {meta['nside']})")
    try:
        rec = load_spectrum("planck_pr3", "TT", True)
        ax.errorbar(rec["ell"], rec["dl"], rec["err_lo"], fmt="s", ms=2.5, color="k", alpha=0.6,
                    label="Planck PR3 released TT bandpowers")
        n = min(len(a), len(rec["ell"]))
        axr.plot(a["ell"][:n], a["D_ell_TT"][:n] / rec["dl"][:n], "o", ms=3, color="C3")
    except Exception:  # noqa: BLE001
        pass
    axr.axhline(1, color="k", lw=0.8)
    axr.axhspan(0.95, 1.05, color="0.85", zorder=0)
    axr.set_ylim(0.8, 1.3)
    axr.set_ylabel("ratio")
    axr.set_xlabel(r"$\ell$")
    ax.set_ylabel(r"$D_\ell^{TT}\ [\mu{\rm K}^2]$")
    ax.set_xlim(0, a["ell_max"].max() + 30)
    ax.legend(fontsize=9)
    ax.set_title(f"Pseudo-$C_\\ell$ from the Planck PR3 map, $f_{{sky}}$={meta['fsky_w2']:.2f}")
    return save_fig(fig, out, f"{stem}_vs_planck")


def _spec_from_header(map_file: str, mask_file: str) -> dict:
    """prepare_map_kernel kwargs reconstructed from a fetch_cmb_map FITS (for remote dispatch)."""
    import healpy as hp

    _, h = hp.read_map(map_file, h=True)
    h = dict(h)
    if "COMP" not in h:
        raise ValueError(f"{map_file} was not written by fetch_cmb_map; remote dispatch needs a Planck map "
                         "spec. Run locally (set_dispatch('local')) for arbitrary maps.")
    mask = Path(mask_file).stem.split("mask_")[-1].rsplit("_n", 1)[0]
    if mask not in mio.MASKS:
        mask = "common_int"
    return {"component": h["COMP"], "split": h["SPLIT"], "nside": int(h["NSIDE"]), "mask": mask}


def _compare_planck_binned(csv_path: Path) -> dict | None:
    """Ratio of the measured spectrum to the released PLA TT bandpowers (bundled), 30<ell<1500."""
    from ..spectra.data import load_spectrum

    try:
        a = np.genfromtxt(csv_path, delimiter=",", names=True)
        rec = load_spectrum("planck_pr3", "TT", True)
    except Exception:  # noqa: BLE001 - comparison is best effort
        return None
    n = min(len(a), len(rec["ell"]))
    if n == 0 or not np.allclose(a["ell_min"][:n], np.arange(30, 30 + 30 * n, 30)):
        return None
    ratio = a["D_ell_TT"][:n] / rec["dl"][:n]
    m = (rec["ell"][:n] > 30) & (rec["ell"][:n] < 1500)
    return {"median_ratio": float(np.median(ratio[m])), "rms_frac_dev": float(np.sqrt(np.mean((ratio[m] - 1) ** 2))),
            "max_abs_frac_dev": float(np.max(np.abs(ratio[m] - 1))), "n_bins": int(m.sum()),
            "reference": "Planck PR3 COM_PowerSpect_CMB-TT-binned_R3.01 (released bandpowers)"}


@data_kind("catalog")
@validate_call
def plot_cmb_map(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the PNG.")],
    map_file: Annotated[str, Field(min_length=1, description="HEALPix map FITS (from fetch_cmb_map).")],
    mask_file: Annotated[str | None, Field(description="Optional mask: masked pixels shown grey.")] = None,
    field: Annotated[int, Field(ge=0, le=2, description="0 = I/T, 1 = Q, 2 = U.")] = 0,
    vmax: Annotated[float, Field(gt=0, description="Colour scale +-vmax in muK.")] = 300.0,
    smooth_fwhm_arcmin: Annotated[float, Field(ge=0, le=600, description="Extra Gaussian smoothing for "
                                                                         "display (0 = none).")] = 0.0,
    title: Annotated[str | None, Field(description="Plot title (default from the file name).")] = None,
) -> ArtifactResult:
    """Mollweide (Galactic) PNG of a HEALPix CMB map, with the mask greyed out.

    Use after fetch_cmb_map to show the component-separated CMB map. Reports the pixel rms inside the mask.
    """
    import healpy as hp

    out = resolve_outdir(output_dir)
    plt = mpl()
    m = hp.read_map(map_file, field=field).astype(float)
    if smooth_fwhm_arcmin > 0:
        m = hp.smoothing(m, fwhm=np.radians(smooth_fwhm_arcmin / 60.0), iter=1)
    good = m != hp.UNSEEN
    if mask_file:
        mk = hp.read_map(mask_file)
        if hp.get_nside(mk) != hp.get_nside(m):
            mk = hp.ud_grade(mk, hp.get_nside(m))
        good &= mk > 0.5
    rms = float(np.std(m[good]))
    shown = np.where(good, m, hp.UNSEEN)
    fig = plt.figure(figsize=(10, 5.6))
    label = "T" if field == 0 else "QU"[field - 1]
    hp.mollview(shown, fig=fig.number, min=-vmax, max=vmax, cmap="RdBu_r", unit=r"$\mu$K$_{\rm CMB}$",
                title=title or f"{Path(map_file).stem} ({label})", badcolor="0.75", bgcolor="white")
    hp.graticule(dpar=30, dmer=60, alpha=0.3)
    path = save_fig(fig, out, f"map_{Path(map_file).stem}_{label}")
    return ok(f"Mollview of {Path(map_file).name} ({label}): rms {rms:.1f} muK over {good.mean():.3f} of the sky.",
              [path], rms_uK=rms, fraction_shown=float(good.mean()), vmax=vmax)


def cached_maps() -> list[str]:
    """Downgraded maps already in the cache (offline helper for tests/skills)."""
    d = data_cache_dir() / "planck_pr3_maps"
    return sorted(str(p) for p in d.glob("*_n*.fits")) if d.is_dir() else []


__all__ = ["fetch_cmb_map", "measure_cmb_power_spectrum", "plot_cmb_map"]
