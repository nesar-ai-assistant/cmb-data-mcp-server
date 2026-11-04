"""Chain kernels: pure functions (numpy + getdist), JSON in -> JSON out.

Dispatchable via DISPATCH_KERNELS (tools/chains/__init__.py). On a facility node the
kernel downloads the public chain archive itself (args carry a URL, never a local path),
extracts only the requested chain, and returns marginal statistics as JSON.
"""

from __future__ import annotations

import contextlib
import io
import os
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

# one massive neutrino, sum m_nu = 0.06 eV (Planck/ACT baseline): omega_nu h^2 = 0.06/93.14
OMNUH2_006 = 0.06 / 93.14

CHAINS = {
    "planck_pr3": {
        "url": "https://irsa.ipac.caltech.edu/data/Planck/release_3/ancillary-data/cosmoparams/"
               "COM_CosmoParams_base-plikHM-TTTEEE-lowl-lowE_R3.00.zip",
        "member_prefix": "base/plikHM_TTTEEE_lowl_lowE_lensing/",
        "root": "base_plikHM_TTTEEE_lowl_lowE_lensing",
        "ignore_rows": 0.0,
        "label": "Planck 2018 TT,TE,EE+lowE+lensing",
        "aliases": {"H0": "H0", "omegam": "omegam", "sigma8": "sigma8", "S8": "S8", "ns": "ns",
                    "ombh2": "omegabh2", "omch2": "omegach2", "tau": "tau", "logA": "logA",
                    "theta": "theta"},
    },
    "act_dr6_lite": {
        "url": "https://lambda.gsfc.nasa.gov/data/act/chains/lcdm/actlite_lcdm_camb.tar.gz",
        "member_prefix": "actlite_lcdm_camb/",
        "root": "actlite_lcdm_camb",
        "ignore_rows": 0.3,
        "label": "ACT DR6 (ACT-lite + Sroll2 tau)",
        "aliases": {"H0": "H0", "omegam": "omegam", "sigma8": "sigma8", "S8": "S8", "ns": "ns",
                    "ombh2": "ombh2", "omch2": "omch2", "tau": "tau", "logA": "logA",
                    "theta": "cosmomc_theta"},
    },
    "p_act_lite": {
        "url": "https://lambda.gsfc.nasa.gov/data/act/chains/lcdm/p-actlite_lcdm_camb.tar.gz",
        "member_prefix": "p-actlite_lcdm_camb/",
        "root": "p-actlite_lcdm_camb",
        "ignore_rows": 0.3,
        "label": "P-ACT (Planck ell<1000 + ACT-lite)",
        "aliases": {"H0": "H0", "omegam": "omegam", "sigma8": "sigma8", "S8": "S8", "ns": "ns",
                    "ombh2": "ombh2", "omch2": "omch2", "tau": "tau", "logA": "logA",
                    "theta": "cosmomc_theta"},
    },
}

WANTED_SUFFIXES = (".txt", ".paramnames", ".ranges", ".properties.ini", ".inputparams",
                   ".updated.yaml", ".minimum", ".margestats", ".likestats")


def _download(url: str, dest: Path) -> Path:
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "cmb-data-mcp-server/0.1"})
    with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as fh:
        while True:
            block = r.read(1 << 20)
            if not block:
                break
            fh.write(block)
    tmp.replace(dest)
    return dest


def extract_chain(archive: Path, member_prefix: str, root: str, dest_dir: Path) -> Path:
    """Extract ONE chain (no post-processed/importance-sampled variants). Returns the getdist root."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    def keep(name: str) -> bool:
        base = name.rsplit("/", 1)[-1]
        return (name.startswith(member_prefix) and base.startswith(root)
                and "_post_" not in base and base.endswith(WANTED_SUFFIXES))

    if str(archive).endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for n in z.namelist():
                if keep(n):
                    (dest_dir / n.rsplit("/", 1)[-1]).write_bytes(z.read(n))
    else:
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                if m.isfile() and keep(m.name):
                    (dest_dir / m.name.rsplit("/", 1)[-1]).write_bytes(t.extractfile(m).read())
    first = [p for p in dest_dir.iterdir() if p.name.startswith(root) and p.suffix == ".txt"
             and p.stem[len(root):].lstrip("._").isdigit()]
    if not first:
        raise RuntimeError(f"No chain files for {root!r} found under {member_prefix!r} in {archive}")
    return dest_dir / root


def load_samples(root: str, ignore_rows: float):
    from getdist import loadMCSamples
    with contextlib.redirect_stdout(io.StringIO()):
        s = loadMCSamples(str(root), settings={"ignore_rows": ignore_rows})
    names = [p.name for p in s.getParamNames().names]
    if "omegam" not in names and {"ombh2", "omch2", "H0"} <= set(names):
        h = s.getParams().H0 / 100.0
        om = (s.getParams().ombh2 + s.getParams().omch2 + OMNUH2_006) / h**2
        s.addDerived(om, name="omegam", label=r"\Omega_{\rm m}")
    names = [p.name for p in s.getParamNames().names]
    if "S8" not in names and {"sigma8", "omegam"} <= set(names):
        p = s.getParams()
        s.addDerived(p.sigma8 * np.sqrt(p.omegam / 0.3), name="S8", label=r"S_8")
    return s


def marginal_stats(root: str, params: list[str], ignore_rows: float, aliases: dict | None = None) -> dict:
    """Mean, std, 68%/95% limits, best sample for each parameter (getdist)."""
    s = load_samples(root, ignore_rows)
    aliases = aliases or {}
    available = [p.name for p in s.getParamNames().names]
    ms = s.getMargeStats()
    out, missing = {}, []
    like = s.getLikeStats() if hasattr(s, "getLikeStats") else None
    for p in params:
        name = aliases.get(p, p)
        if name not in available:
            missing.append(p)
            continue
        m = ms.parWithName(name)
        lim68, lim95 = m.limits[0], m.limits[1]
        rec = {"name_in_chain": name, "mean": float(m.mean), "std": float(m.err),
               "lower68": float(lim68.lower), "upper68": float(lim68.upper),
               "lower95": float(lim95.lower), "upper95": float(lim95.upper)}
        if like is not None:
            with contextlib.suppress(Exception):
                rec["best_fit_sample"] = float(like.parWithName(name).bestfit_sample)
        out[p] = rec
    return {"params": out, "missing": missing, "n_samples": int(s.numrows),
            "effective_samples": float(np.sum(s.weights) ** 2 / np.sum(s.weights ** 2)),
            "ignore_rows": ignore_rows, "available_params": available[:80]}


def analyze_chain_kernel(chain: str, params: list[str], ignore_rows: float | None = None,
                         url: str | None = None) -> dict:
    """DISPATCH KERNEL: download + extract one public chain in the job cwd, return getdist stats.

    Args (JSON): chain key in CHAINS ('planck_pr3' | 'act_dr6_lite' | 'p_act_lite'),
    params (short names, e.g. ['H0','omegam','sigma8','S8','ns']), optional ignore_rows,
    optional url override. Files written: chain_stats.json in cwd.
    """
    import json
    cfg = CHAINS[chain]
    work = Path(os.getcwd())
    archive = _download(url or cfg["url"], work / (url or cfg["url"]).rsplit("/", 1)[-1])
    root = extract_chain(archive, cfg["member_prefix"], cfg["root"], work / f"chain_{chain}")
    ir = cfg["ignore_rows"] if ignore_rows is None else ignore_rows
    res = marginal_stats(str(root), params, ir, cfg["aliases"])
    res.update({"chain": chain, "label": cfg["label"], "source_url": url or cfg["url"]})
    (work / "chain_stats.json").write_text(json.dumps(res, indent=1))
    return res
