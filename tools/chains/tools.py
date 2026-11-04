"""MCMC chain tools: fetch a public chain, getdist marginal stats (heavy, dispatchable),
triangle plots, and a whisker comparison of H0 / S8 / Om / ns / sigma8 across experiments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from pydantic import Field, validate_call

from ..common import BUNDLED_DATA, ArtifactResult, data_cache_dir, fetch_file, mpl, ok, resolve_outdir, save_fig
from . import kernels
from .published import PUBLISHED

Chain = Literal["planck_pr3", "act_dr6_lite", "p_act_lite"]
DEFAULT_PARAMS = ["H0", "omegam", "sigma8", "S8", "ns", "ombh2", "omch2", "tau", "logA"]
LATEX = {"H0": r"$H_0$ [km/s/Mpc]", "omegam": r"$\Omega_{\rm m}$", "sigma8": r"$\sigma_8$", "S8": r"$S_8$",
         "ns": r"$n_s$"}

DISPATCH_KERNELS = {
    "analyze_chain": {
        "function": "chains.kernels.analyze_chain_kernel",
        "args_shape": "{'chain': 'planck_pr3'|'act_dr6_lite'|'p_act_lite', 'params': [short names], "
                      "'ignore_rows': float|None, 'url': str|None}",
        "pip_deps": ["numpy", "scipy", "getdist"],
        "duration_hint_s": 900,
        "returns": "{'params': {name: {mean,std,lower68,upper68,lower95,upper95}}, 'missing', 'n_samples', "
                   "'effective_samples', 'label', 'source_url'}; writes chain_stats.json",
    },
}


def _chain_root(chain: str) -> Path:
    """Download (once) + extract one chain into the data cache; return the getdist root."""
    cfg = kernels.CHAINS[chain]
    dest = data_cache_dir() / "chains" / chain
    root = dest / cfg["root"]
    if any(dest.glob(cfg["root"] + "*.txt")) if dest.is_dir() else False:
        return root
    archive = fetch_file(cfg["url"], subdir="chains", timeout=900)
    return kernels.extract_chain(archive, cfg["member_prefix"], cfg["root"], dest)


@validate_call
def fetch_cmb_chain(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the chain summary JSON.")],
    chain: Annotated[Chain, Field(description="planck_pr3 = Planck 2018 base_plikHM_TTTEEE_lowl_lowE_lensing "
                                              "(65 MB zip); act_dr6_lite / p_act_lite = ACT DR6 LCDM "
                                              "(5-7 MB).")] = "planck_pr3",
) -> ArtifactResult:
    """Download and extract ONE public MCMC chain (never the 11 GB Planck grid).

    Returns the getdist chain root path (pass to analyze_chain / plot_triangle) and the
    parameter list. First call downloads into the cache; later calls are instant.
    """
    out = resolve_outdir(output_dir)
    root = _chain_root(chain)
    s = kernels.load_samples(str(root), kernels.CHAINS[chain]["ignore_rows"])
    names = [p.name for p in s.getParamNames().names]
    files = sorted(str(p) for p in root.parent.glob(root.name + "*"))
    summ = {"chain": chain, "root": str(root), "label": kernels.CHAINS[chain]["label"],
            "source_url": kernels.CHAINS[chain]["url"], "n_samples": int(s.numrows), "params": names}
    path = out / f"chain_{chain}.json"
    path.write_text(json.dumps(summ, indent=1))
    return ok(f"{summ['label']}: {len(files)} files, {s.numrows} samples, {len(names)} parameters. "
              f"Chain root: {root}", [path], chain_root=str(root), chain=chain, label=summ["label"],
              n_samples=int(s.numrows), params=names[:60], source_url=summ["source_url"])


@validate_call
def analyze_chain(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for chain_stats JSON/CSV.")],
    chain: Annotated[Chain, Field(description="Which public chain.")] = "planck_pr3",
    params: Annotated[list[str], Field(min_length=1, description="Short names: H0, omegam, sigma8, S8, ns, "
                                                                 "ombh2, omch2, tau, logA, theta.")] = DEFAULT_PARAMS,  # noqa: B006
    ignore_rows: Annotated[float | None, Field(ge=0, lt=1, description="Burn-in fraction; default per chain "
                                                                       "(Planck 0: pre-removed; ACT 0.3).")] = None,
) -> ArtifactResult:
    """getdist marginal statistics (mean, std, 68/95% limits) for a public CMB chain.

    Heavy: downloads/extracts the chain on first use. With set_dispatch('polaris'|
    'perlmutter') it runs as one facility job (the node downloads the archive itself).
    Sanity check (Planck 2018): H0 67.36+-0.54, omegam 0.3153+-0.0073, sigma8 0.8111+-0.0060.
    """
    from mcp_server.dispatch import remote_site, run_kernel  # lazy: server-only

    out = resolve_outdir(output_dir)
    site = remote_site()
    if site:
        res = run_kernel("chains.kernels.analyze_chain_kernel",
                         {"chain": chain, "params": list(params), "ignore_rows": ignore_rows},
                         pip_deps=["numpy", "scipy", "getdist"], duration=1200)
        payload, host = res["result"], res.get("host", site)
    else:
        cfg = kernels.CHAINS[chain]
        root = _chain_root(chain)
        ir = cfg["ignore_rows"] if ignore_rows is None else ignore_rows
        payload = kernels.marginal_stats(str(root), list(params), ir, cfg["aliases"])
        payload.update({"chain": chain, "label": cfg["label"], "source_url": cfg["url"]})
        host = "local"
    jpath = out / f"chain_stats_{chain}.json"
    jpath.write_text(json.dumps(payload, indent=1))
    cpath = out / f"chain_stats_{chain}.csv"
    with open(cpath, "w") as fh:
        fh.write("param,mean,std,lower68,upper68,lower95,upper95\n")
        for p, r in payload["params"].items():
            fh.write(f"{p},{r['mean']:.6g},{r['std']:.4g},{r['lower68']:.6g},{r['upper68']:.6g},"
                     f"{r['lower95']:.6g},{r['upper95']:.6g}\n")
    txt = ", ".join(f"{p}={r['mean']:.4g}+-{r['std']:.2g}" for p, r in payload["params"].items()
                    if p in ("H0", "omegam", "sigma8", "S8", "ns"))
    return ok(f"{payload['label']} ({payload['n_samples']} samples, computed {host}): {txt}.",
              [jpath, cpath], stats=payload["params"], missing=payload["missing"], computed_on=host,
              n_samples=payload["n_samples"], effective_samples=payload.get("effective_samples"),
              ignore_rows=payload["ignore_rows"], label=payload["label"])


analyze_chain.weight = "heavy"


@validate_call
def plot_triangle(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the PNG.")],
    chains: Annotated[list[Chain], Field(min_length=1, max_length=3, description="1-3 chains to overlay.")] = ["planck_pr3"],  # noqa: B006
    params: Annotated[list[str], Field(min_length=2, max_length=8, description="Short names (see analyze_chain).")] = ["H0", "omegam", "sigma8", "ns"],  # noqa: B006
) -> ArtifactResult:
    """getdist triangle plot (1D marginals + 68/95% 2D contours) for one or more CMB chains.

    Overlay planck_pr3 with act_dr6_lite to show the Planck-vs-ACT LCDM agreement.
    """
    from getdist import plots

    out = resolve_outdir(output_dir)
    mpl()
    samples, labels = [], []
    for c in chains:
        cfg = kernels.CHAINS[c]
        s = kernels.load_samples(str(_chain_root(c)), cfg["ignore_rows"])
        names = {p.name for p in s.getParamNames().names}
        for short in params:
            real = cfg["aliases"].get(short, short)
            if real not in names:
                raise ValueError(f"{short!r} not in chain {c}; available: {sorted(names)[:40]}")
            if real != short:
                s.addDerived(s.samples[:, s.index[real]], name=short, label=s.paramNames.parWithName(real).label)
        s.label = cfg["label"]
        samples.append(s)
        labels.append(cfg["label"])
    g = plots.get_subplot_plotter(width_inch=7)
    g.settings.legend_fontsize = 10
    g.triangle_plot(samples, list(params), filled=True, legend_labels=labels)
    path = save_fig(g.fig, out, f"triangle_{'_'.join(chains)}")
    return ok(f"Triangle plot of {', '.join(params)} for {', '.join(labels)}.", [path], chains=chains,
              params=params)


@validate_call
def compare_parameter_constraints(
    output_dir: Annotated[str, Field(min_length=1, description="Directory for the PNG + CSV.")],
    params: Annotated[list[Literal["H0", "S8", "omegam", "ns", "sigma8"]],
                      Field(min_length=1, description="Parameters for whisker panels.")] = ["H0", "S8", "omegam", "ns"],  # noqa: B006
    chains: Annotated[list[Chain], Field(description="Chains to analyse live with getdist ([] = published "
                                                     "tables only). Planck chain needs a 65 MB download.")] = [],  # noqa: B006
    include_published: Annotated[bool, Field(description="Add the cited published table entries "
                                                         "(Planck, SPT-3G D1, ACT DR6, CMB-SPA, SH0ES, DES, KiDS).")] = True,
    reference: Annotated[str, Field(description="Entry to measure tensions against (n-sigma, Gaussian).")] = "Planck 2018 (TT,TE,EE+lowE+lensing)",
) -> ArtifactResult:
    """Whisker plot of H0, S8, Omega_m, n_s (sigma8) across CMB experiments and late-time probes.

    Every point is either a getdist analysis of a public chain (marked 'chain') or a
    published table value with its citation. Reports the Gaussian tension of each entry vs
    the reference: (x - x_ref) / sqrt(s^2 + s_ref^2) - e.g. SH0ES vs Planck H0 ~ 4.9 sigma.
    """
    out = resolve_outdir(output_dir)
    entries: dict[str, dict] = {}
    if include_published:
        entries.update({k: dict(v, source="published") for k, v in PUBLISHED.items()})
    for c in chains:
        cfg = kernels.CHAINS[c]
        st = kernels.marginal_stats(str(_chain_root(c)), list(params), cfg["ignore_rows"], cfg["aliases"])
        entries[cfg["label"] + " [chain]"] = {
            "params": {p: (r["mean"], r["std"]) for p, r in st["params"].items()}, "kind": "cmb",
            "source": "chain", "citation": f"getdist on {cfg['url']}"}
    if not entries:
        raise ValueError("Nothing to compare: pass chains and/or include_published=True.")
    ref = entries.get(reference)
    plt = mpl()
    fig, axes = plt.subplots(1, len(params), figsize=(3.2 * len(params) + 2.5, 0.42 * len(entries) + 1.5),
                             sharey=True, squeeze=False)
    names = list(entries)
    colors = {"cmb": "#1f77b4", "cmb+bao": "#17becf", "cmb-lensing": "#9467bd", "local": "#d62728", "lss": "#ff7f0e"}
    tensions: dict = {}
    rows = []
    for j, p in enumerate(params):
        ax = axes[0, j]
        for i, n in enumerate(names):
            e = entries[n]
            if p not in e["params"]:
                continue
            mu, sd = e["params"][p]
            ax.errorbar(mu, i, xerr=sd, fmt="s" if e["source"] == "chain" else "o",
                        color=colors.get(e["kind"], "k"), ms=5, capsize=2)
            rows.append((n, p, mu, sd, e["source"], e["citation"]))
            if ref and p in ref["params"] and n != reference:
                r_mu, r_sd = ref["params"][p]
                tensions.setdefault(n, {})[p] = round((mu - r_mu) / np.hypot(sd, r_sd), 2)
        if ref and p in ref["params"]:
            r_mu, r_sd = ref["params"][p]
            ax.axvspan(r_mu - r_sd, r_mu + r_sd, color="0.85", zorder=0)
        ax.set_xlabel(LATEX[p])
        ax.grid(axis="x", alpha=0.3)
    axes[0, 0].set_yticks(range(len(names)))
    axes[0, 0].set_yticklabels(names, fontsize=8)
    axes[0, 0].invert_yaxis()
    fig.tight_layout()
    path = save_fig(fig, out, "parameter_whisker_" + "_".join(params))
    cpath = out / "parameter_whisker.csv"
    with open(cpath, "w") as fh:
        fh.write("entry,param,mean,sigma,source,citation\n")
        for r in rows:
            fh.write(",".join([f'"{r[0]}"', r[1], f"{r[2]:.6g}", f"{r[3]:.4g}", r[4], f'"{r[5]}"']) + "\n")
    key = {n: t for n, t in tensions.items() if any(abs(v) >= 2 for v in t.values())}
    return ok(f"Whisker plot of {', '.join(params)} for {len(entries)} entries. "
              + ("Tensions >= 2 sigma vs reference: " + json.dumps(key) if key else "No >= 2 sigma tensions."),
              [path, cpath], tensions_vs_reference=tensions, reference=reference if ref else None,
              citations={n: e["citation"] for n, e in entries.items()},
              note="Gaussian, uncorrelated n-sigma; asymmetric published errors were symmetrised.")


def bundled_planck_margestats(params: list[str]) -> dict:
    """Parse the bundled Planck margestats (offline check, no download)."""
    path = BUNDLED_DATA / "chains" / "base_plikHM_TTTEEE_lowl_lowE_lensing.margestats"
    out = {}
    for line in path.read_text().splitlines()[3:]:
        f = line.split()
        if len(f) > 3 and f[0].rstrip("*") in params:
            out[f[0].rstrip("*")] = (float(f[1]), float(f[2]))
    return out


__all__ = ["fetch_cmb_chain", "analyze_chain", "plot_triangle", "compare_parameter_constraints"]
