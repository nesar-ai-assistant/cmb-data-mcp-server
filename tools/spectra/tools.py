"""CMB power-spectrum tools: fetch, LCDM theory, residuals/chi2 (plots live in .plots)."""

from __future__ import annotations

import json
from typing import Annotated, Literal

import numpy as np
from pydantic import Field, validate_call

from ..common import ArtifactResult, ok, param_slug, resolve_outdir
from . import kernels
from ._shared import get_theory, write_csv
from .data import LABELS, binned_theory, load_spectrum, theory_dl
from .plots import plot_cmb_spectra, plot_lensing_spectrum

Dataset = Literal["planck_pr3", "act_dr6", "spt3g_d1", "spt3g_2018"]
Spectrum = Literal["TT", "TE", "EE", "BB", "PP"]

DISPATCH_KERNELS = {
    "camb_lcdm": {
        "function": "spectra.kernels.camb_lcdm_kernel",
        "args_shape": "{'params': {ombh2, omch2, cosmomc_theta|H0, tau, logA|As, ns, mnu} (missing -> "
                      "Planck 2018 best fit), 'lmax': int, 'lens_potential_accuracy': int}",
        "pip_deps": ["numpy", "camb"],
        "duration_hint_s": 300,
        "returns": "{'ell', 'TT','TE','EE','BB' (D_ell muK^2), 'PP' ([L(L+1)]^2 C^phiphi/2pi), "
                   "'derived': {H0, omegam, sigma8, S8}, 'params', 'camb_version'}",
    },
}


@validate_call
def fetch_cmb_spectrum(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the tidy CSV.")],
    dataset: Annotated[Dataset, Field(description="planck_pr3 | act_dr6 | spt3g_d1 | spt3g_2018.")] = "planck_pr3",
    spectrum: Annotated[Spectrum, Field(description="TT, TE, EE, BB (Planck low-ell only) or PP (lensing).")] = "TT",
    binned: Annotated[bool, Field(description="Planck only: True = PLA binned (ell>=30, bundled); "
                                              "False = unbinned 2<=ell (downloaded).")] = True,
) -> ArtifactResult:
    """Fetch one public CMB bandpower spectrum and write it as a tidy CSV.

    Use this first for any spectrum task. Columns: ell, D_ell, err_lo, err_hi (+ ell_min,
    ell_max when bins are known; + planck_best_fit for Planck binned). Units: D_ell =
    ell(ell+1)C_ell/2pi in muK^2; PP is [L(L+1)]^2 C_L^phiphi/2pi (ACT/SPT C^kk converted).
    If the dataset ships a covariance (ACT DR6, all lensing) it is saved as <stem>_cov.npy.
    """
    out = resolve_outdir(output_dir)
    rec = load_spectrum(dataset, spectrum, binned)
    stem = f"{dataset}_{spectrum}{'' if (binned or dataset != 'planck_pr3') else '_unbinned'}"
    cols = {"ell": rec["ell"], "D_ell": rec["dl"], "err_lo": rec["err_lo"], "err_hi": rec["err_hi"]}
    if "ell_min" in rec:
        cols["ell_min"], cols["ell_max"] = rec["ell_min"], rec["ell_max"]
    if "best_fit" in rec:
        cols["planck_best_fit"] = rec["best_fit"]
    files = [write_csv(out / f"{stem}.csv", cols)]
    if "cov" in rec:
        np.save(out / f"{stem}_cov.npy", rec["cov"])
        files.append(out / f"{stem}_cov.npy")
    snr = float(np.sqrt(np.sum((rec["dl"] / rec["err_lo"]) ** 2)))
    return ok(f"{LABELS.get(dataset, dataset)} {spectrum}: {len(rec['ell'])} bandpowers, "
              f"ell {rec['ell'].min():.0f}-{rec['ell'].max():.0f}, diagonal S/N {snr:.0f}.",
              files, dataset=dataset, spectrum=spectrum, n_bandpowers=int(len(rec["ell"])),
              ell_range=[float(rec["ell"].min()), float(rec["ell"].max())],
              has_covariance="cov" in rec, has_window="window" in rec, note=rec.get("note", ""),
              units="muK^2 D_ell" if spectrum != "PP" else "[L(L+1)]^2 C_L^phiphi / 2pi")


def _compute_theory(params: dict | None, lmax: int) -> tuple[dict, str]:
    """camb if importable (or on the dispatch site), else the bundled Planck best-fit file."""
    from mcp_server.dispatch import remote_site, run_kernel  # lazy: server-only

    site = remote_site()
    if site:
        res = run_kernel("spectra.kernels.camb_lcdm_kernel", {"params": params or {}, "lmax": lmax},
                         pip_deps=["numpy", "camb"], duration=600)
        return res["result"], f"camb on {res.get('host', site)}"
    try:
        import camb  # noqa: F401
    except ImportError:
        if params:
            raise RuntimeError("camb is not installed, so only the bundled Planck 2018 best-fit spectrum is "
                               "available (call without params), or `pip install camb` / set_dispatch.") from None
        th = theory_dl()
        n = min(lmax, len(th["ell"]) - 1)
        payload = {k: th[k][: n + 1].tolist() for k in ("TT", "TE", "EE", "BB", "PP")}
        payload["ell"] = list(range(n + 1))
        payload["derived"] = {"H0": 67.32, "omegam": 0.3158, "sigma8": 0.8120,
                              "note": "Planck 2018 best-fit (.minimum) values, Table 1 of arXiv:1807.06209"}
        payload["params"] = dict(kernels.PLANCK2018_BESTFIT)
        return payload, "bundled Planck 2018 best-fit theory (camb not installed)"
    return kernels.camb_lcdm_kernel(params=params, lmax=lmax), "camb (local)"


@validate_call
def compute_lcdm_theory_spectrum(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the theory CSV.")],
    params: Annotated[dict[str, float] | None, Field(description="LCDM parameters: ombh2, omch2, cosmomc_theta "
                      "(or H0), tau, logA (or As), ns, mnu. Missing -> Planck 2018 best fit. Requires camb.")] = None,
    lmax: Annotated[int, Field(ge=100, le=9000, description="Maximum multipole (ACT needs ~6500).")] = 3000,
) -> ArtifactResult:
    """Compute a lensed LCDM TT/TE/EE/BB + lensing-potential theory spectrum to CSV.

    Uses camb (optional dependency, lazily imported; or a facility node via set_dispatch).
    Without camb and without params it falls back to the bundled Planck 2018 best-fit
    theory file (ell<=2508) - say so when reporting. Pass the CSV as theory_file to
    plot_cmb_spectra / compute_cmb_residuals / plot_lensing_spectrum.
    """
    out = resolve_outdir(output_dir)
    payload, source = _compute_theory(params, lmax)
    stem = f"lcdm_theory_{param_slug(params or {'planck': 2018})}_l{len(payload['ell']) - 1}"
    cols = {k: payload[k] for k in ("ell", "TT", "TE", "EE", "BB", "PP")}
    path = write_csv(out / f"{stem}.csv", cols)
    (out / f"{stem}.json").write_text(json.dumps({"derived": payload["derived"], "params": payload.get("params"),
                                                  "source": source}, indent=1))
    d = payload["derived"]
    return ok(f"LCDM theory to ell={len(payload['ell']) - 1} from {source}: H0={d['H0']:.2f}, "
              f"Om={d['omegam']:.4f}, sigma8={d['sigma8']:.4f}.", [path, out / f"{stem}.json"],
              source=source, derived=d, lmax=len(payload["ell"]) - 1,
              columns="ell, TT/TE/EE/BB D_ell [muK^2], PP [L(L+1)]^2 C^phiphi/2pi")


compute_lcdm_theory_spectrum.weight = "heavy"


@validate_call
def compute_cmb_residuals(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the residual CSV.")],
    dataset: Annotated[Literal["planck_pr3", "act_dr6", "spt3g_d1", "spt3g_2018", "planck_pr3_lensing",
                               "act_dr6_lensing", "spt3g_d1_lensing"],
                       Field(description="Spectrum dataset (lensing datasets use spectrum PP).")] = "planck_pr3",
    spectrum: Annotated[Spectrum, Field(description="TT, TE, EE, BB or PP.")] = "TT",
    theory_file: Annotated[str | None, Field(description="Theory CSV from compute_lcdm_theory_spectrum; "
                                                         "default = bundled Planck 2018 best fit.")] = None,
    ell_min: Annotated[float, Field(ge=0, description="Drop bandpowers below this ell.")] = 0,
    ell_max: Annotated[float, Field(ge=0, description="Drop bandpowers above this ell (0 = no cut).")] = 0,
    binned: Annotated[bool, Field(description="Planck: binned (True) or unbinned (False).")] = True,
) -> ArtifactResult:
    """chi2 of one experiment's bandpowers against an LCDM theory spectrum, plus residuals.

    Uses the full covariance when the release has one (ACT DR6 TT/TE/EE block, all lensing
    datasets, with Hartlap factors) and the bandpower windows when available; otherwise the
    diagonal errors (Planck/SPT plotting products: chi2 is INDICATIVE, correlations ignored;
    Planck unbinned uses the mean of the asymmetric errors). Reports chi2, N, PTE.
    """
    from scipy import stats

    out = resolve_outdir(output_dir)
    if dataset.endswith("_lensing"):
        spectrum = "PP"
    rec = load_spectrum(dataset, spectrum, binned)
    theory, tsrc = get_theory(theory_file)
    model = binned_theory(rec, theory, spectrum)
    m = np.isfinite(model) & (rec["ell"] >= ell_min)
    if ell_max:
        m &= rec["ell"] <= ell_max
    if not m.any():
        raise ValueError("No bandpowers left after the ell cuts / theory range.")
    resid = rec["dl"] - model
    sig = 0.5 * (rec["err_lo"] + rec["err_hi"])
    if "cov" in rec:
        c = rec["cov"][np.ix_(m, m)]
        r = resid[m]
        chi2 = float(r @ np.linalg.solve(c, r)) * float(rec.get("hartlap", 1.0))
        method = "full covariance" + (f" (Hartlap {rec['hartlap']:.3f})" if rec.get("hartlap", 1.0) != 1.0 else "")
    else:
        chi2 = float(np.sum((resid[m] / sig[m]) ** 2))
        method = "diagonal errors (no released covariance; indicative only)"
    n = int(m.sum())
    pte = float(stats.chi2.sf(chi2, n))
    stem = f"residuals_{dataset}_{spectrum}"
    path = write_csv(out / f"{stem}.csv", {"ell": rec["ell"][m], "D_ell": rec["dl"][m], "theory": model[m],
                                            "residual": resid[m], "sigma": sig[m],
                                            "pull": resid[m] / sig[m]})
    return ok(f"{LABELS.get(dataset, dataset)} {spectrum} vs {tsrc}: chi2={chi2:.1f} for N={n} "
              f"(chi2/N={chi2 / n:.2f}, PTE={pte:.3f}) using {method}.", [path],
              dataset=dataset, spectrum=spectrum, chi2=chi2, n_bandpowers=n, chi2_per_n=chi2 / n, pte=pte,
              method=method, theory=tsrc, max_abs_pull=float(np.max(np.abs(resid[m] / sig[m]))),
              caveat=("Theory has fixed nuisance/calibration (A_act=P_act=1 for ACT); not a likelihood "
                      "evaluation - Phase 2 adds HiLLiPoP/LoLLiPoP/candl/act_dr6_lenslike."))


__all__ = ["fetch_cmb_spectrum", "plot_cmb_spectra", "compute_cmb_residuals", "compute_lcdm_theory_spectrum",
           "plot_lensing_spectrum"]
