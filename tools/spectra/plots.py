"""Spectrum plots: multi-experiment D_ell overlay with LCDM + residual panel; lensing C_L^phiphi."""

from __future__ import annotations

from typing import Annotated, Literal

import numpy as np
from pydantic import Field, validate_call

from ..common import ArtifactResult, mpl, ok, resolve_outdir, save_fig
from ..common import tier
from ._shared import get_theory
from .data import LABELS, binned_theory, load_spectrum

COLORS = {"planck_pr3": "#2ca02c", "act_dr6": "#ff7f0e", "spt3g_d1": "#1f77b4", "spt3g_2018": "#9467bd",
          "planck_pr3_lensing": "#2ca02c", "act_dr6_lensing": "#ff7f0e", "spt3g_d1_lensing": "#1f77b4"}
MARKERS = {"planck_pr3": "o", "act_dr6": "s", "spt3g_d1": "D", "spt3g_2018": "^",
           "planck_pr3_lensing": "o", "act_dr6_lensing": "s", "spt3g_d1_lensing": "D"}
YLABEL = {"TT": r"$\mathcal{D}_\ell^{TT}\ [\mu{\rm K}^2]$", "TE": r"$\mathcal{D}_\ell^{TE}\ [\mu{\rm K}^2]$",
          "EE": r"$\mathcal{D}_\ell^{EE}\ [\mu{\rm K}^2]$", "BB": r"$\mathcal{D}_\ell^{BB}\ [\mu{\rm K}^2]$"}

ExpName = Literal["planck_pr3", "act_dr6", "spt3g_d1", "spt3g_2018"]


@tier(2)
@validate_call
def plot_cmb_spectra(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the PNG.")],
    datasets: Annotated[list[ExpName], Field(min_length=1, description="Experiments to overlay.")] = ["planck_pr3"],  # noqa: B006
    spectrum: Annotated[Literal["TT", "TE", "EE", "BB"], Field(description="Spectrum to plot.")] = "TT",
    show_theory: Annotated[bool, Field(description="Overlay best-fit LCDM.")] = True,
    theory_file: Annotated[str | None, Field(description="Theory CSV (compute_lcdm_theory_spectrum); default "
                                                         "= bundled Planck 2018 best fit.")] = None,
    residual_panel: Annotated[bool, Field(description="Add a (data - theory) panel below.")] = True,
    log_x: Annotated[bool, Field(description="Logarithmic ell axis.")] = False,
    log_y: Annotated[bool, Field(description="Logarithmic D_ell axis (TT/EE high-ell damping tail).")] = False,
    ell_max: Annotated[float, Field(ge=0, description="Upper ell limit for the x axis (0 = auto).")] = 0,
) -> ArtifactResult:
    """Plot D_ell bandpowers with error bars for one or more experiments + LCDM + residuals.

    Use to reproduce the Planck 2018 TT/TE/EE figure (datasets=['planck_pr3']) or the
    SPT-3G D1 / ACT DR6 / Planck overlay (Camphuis+25 Fig.1: ['planck_pr3','act_dr6','spt3g_d1'],
    log_y=True for TT/EE). Residuals are D_ell - theory with the same errors.
    """
    out = resolve_outdir(output_dir)
    plt = mpl()
    theory, tsrc = get_theory(theory_file)
    rows = 2 if residual_panel and show_theory else 1
    fig, axes = plt.subplots(rows, 1, figsize=(9, 6.5 if rows == 2 else 4.8), sharex=True, squeeze=False,
                             gridspec_kw={"height_ratios": [3, 1.2][:rows]})
    ax = axes[0, 0]
    summary = {}
    xmax = 0.0
    for ds in datasets:
        rec = load_spectrum(ds, spectrum, True)
        yerr = np.vstack([rec["err_lo"], rec["err_hi"]])
        ax.errorbar(rec["ell"], rec["dl"], yerr=yerr, fmt=MARKERS[ds], ms=3, lw=0.8, color=COLORS[ds],
                    mfc="none" if ds != datasets[0] else COLORS[ds], label=LABELS[ds], alpha=0.9)
        xmax = max(xmax, float(rec["ell"].max()))
        if rows == 2:
            model = binned_theory(rec, theory, spectrum)
            axes[1, 0].errorbar(rec["ell"], rec["dl"] - model, yerr=yerr, fmt=MARKERS[ds], ms=3, lw=0.8,
                                color=COLORS[ds], mfc="none" if ds != datasets[0] else COLORS[ds])
        summary[ds] = {"n": int(len(rec["ell"])), "ell_range": [float(rec["ell"].min()), float(rec["ell"].max())]}
    xmax = ell_max or xmax * 1.03
    if show_theory:
        L = theory["ell"]
        m = (L >= 2) & (L <= xmax)
        ax.plot(L[m], theory[spectrum][m], "k-", lw=1, label=r"$\Lambda$CDM (" + tsrc.split(" (")[0] + ")")
        if rows == 2:
            axes[1, 0].axhline(0, color="k", lw=0.8)
            axes[1, 0].set_ylabel(r"$\Delta\mathcal{D}_\ell$")
    if log_y:
        ax.set_yscale("log")
    if log_x:
        ax.set_xscale("log")
    ax.set_xlim(2 if log_x else 0, xmax)
    ax.set_ylabel(YLABEL[spectrum])
    ax.legend(frameon=False, fontsize=9)
    axes[-1, 0].set_xlabel(r"$\ell$")
    fig.tight_layout()
    path = save_fig(fig, out, f"cmb_{spectrum}_{'_'.join(datasets)}")
    return ok(f"Plotted {spectrum} for {', '.join(LABELS[d] for d in datasets)}"
              f"{' with ' + tsrc if show_theory else ''}.", [path], spectrum=spectrum, datasets=summary,
              theory=tsrc if show_theory else None)


@tier(2)
@validate_call
def plot_lensing_spectrum(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the PNG.")],
    datasets: Annotated[list[Literal["planck_pr3", "act_dr6", "spt3g_d1"]],
                        Field(min_length=1, description="Experiments with lensing bandpowers.")] = ["planck_pr3", "act_dr6", "spt3g_d1"],  # noqa: B006
    theory_file: Annotated[str | None, Field(description="Theory CSV; default = Planck 2018 best fit PP.")] = None,
) -> ArtifactResult:
    """Plot CMB lensing-potential bandpowers [L(L+1)]^2 C_L^phiphi/2pi for Planck/ACT/SPT.

    Shows Planck PR3 (8<=L<=400), ACT DR6 baseline (40<=L<=763) and SPT-3G D1 GMV bandpowers
    with the LCDM prediction, and reports each dataset's amplitude A_lens = best-fit scaling of
    the theory (full covariance) with its error.
    """
    out = resolve_outdir(output_dir)
    plt = mpl()
    theory, tsrc = get_theory(theory_file)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    amps = {}
    for ds in datasets:
        rec = load_spectrum(ds, "PP")
        key = ds if ds.endswith("_lensing") else ds + "_lensing"
        xerr = None
        if "ell_min" in rec:
            xerr = np.vstack([rec["ell"] - rec["ell_min"], rec["ell_max"] - rec["ell"]])
        ax.errorbar(rec["ell"], rec["dl"] * 1e7, yerr=rec["err_lo"] * 1e7, xerr=xerr, fmt=MARKERS[key], ms=4,
                    lw=0.9, color=COLORS[key], label=LABELS[key])
        model = binned_theory(rec, theory, "PP")
        m = np.isfinite(model)
        cinv = np.linalg.inv(rec["cov"][np.ix_(m, m)]) * rec.get("hartlap", 1.0)
        mod = model[m]
        f = float(mod @ cinv @ mod)
        amps[ds] = {"A_lens": float(mod @ cinv @ rec["dl"][m]) / f, "sigma": float(1 / np.sqrt(f)),
                    "n_bins": int(m.sum())}
    L = theory["ell"]
    m = (L >= 2) & (L <= 2000)
    ax.plot(L[m], theory["PP"][m] * 1e7, "k-", lw=1, label=r"$\Lambda$CDM (" + tsrc.split(" (")[0] + ")")
    ax.set_xscale("log")
    ax.set_xlim(7, 2000)
    ax.set_xlabel(r"$L$")
    ax.set_ylabel(r"$10^7\,[L(L+1)]^2 C_L^{\phi\phi}/2\pi$")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    path = save_fig(fig, out, f"lensing_{'_'.join(datasets)}")
    txt = "; ".join(f"{LABELS[d]} A_lens={a['A_lens']:.3f}+-{a['sigma']:.3f}" for d, a in amps.items())
    return ok(f"Lensing bandpowers vs {tsrc}: {txt}.", [path], amplitudes=amps, theory=tsrc,
              caveat=("SPT-3G D1 amplitude is indicative: candl's systematics emulator + M_L response "
                      "corrections are not applied (Phase 2), which biases A_lens low (~0.93)."))
