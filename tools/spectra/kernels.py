"""Theory kernels: CAMB LCDM spectra (pure function, JSON in -> JSON out).

camb is an OPTIONAL dependency, imported lazily. Kernel modules import only numpy +
declared pip_deps (here: camb).
"""

from __future__ import annotations

import numpy as np

# Planck 2018 base_plikHM_TTTEEE_lowl_lowE_lensing best fit (.minimum in the PLA chain zip)
PLANCK2018_BESTFIT = {"ombh2": 0.02238280, "omch2": 0.1201075, "cosmomc_theta": 1.040909e-2,
                      "tau": 0.05430842, "logA": 3.044784, "ns": 0.9660499, "mnu": 0.06}


def camb_lcdm_kernel(params: dict | None = None, lmax: int = 3000, lens_potential_accuracy: int = 1) -> dict:
    """DISPATCH KERNEL: lensed TT/TE/EE/BB D_ell [muK^2] and PP ([L(L+1)]^2 C^phiphi/2pi).

    params: any of ombh2, omch2, cosmomc_theta (or H0), tau, logA (or As), ns, mnu;
    missing ones default to the Planck 2018 best fit. Returns lists indexed by ell 0..lmax
    plus derived H0, omegam, sigma8, S8.
    """
    import camb

    p = dict(PLANCK2018_BESTFIT)
    p.update(params or {})
    As = p.get("As", np.exp(p["logA"]) * 1e-10)
    pars = camb.CAMBparams()
    kw = dict(ombh2=p["ombh2"], omch2=p["omch2"], tau=p["tau"], mnu=p["mnu"], omk=0)
    if "H0" in (params or {}):
        pars.set_cosmology(H0=p["H0"], **kw)
    else:
        pars.set_cosmology(cosmomc_theta=p["cosmomc_theta"], **kw)
    pars.InitPower.set_params(As=As, ns=p["ns"])
    pars.set_for_lmax(lmax, lens_potential_accuracy=lens_potential_accuracy)
    pars.WantTransfer = True
    pars.set_matter_power(redshifts=[0.0], kmax=2.0)
    res = camb.get_results(pars)
    cls = res.get_cmb_power_spectra(pars, CMB_unit="muK", lmax=lmax)
    tot = cls["total"]
    pp = cls["lens_potential"][:, 0]   # [L(L+1)]^2 C^phiphi / 2pi
    h = pars.H0 / 100.0
    om = (pars.ombh2 + pars.omch2 + pars.omnuh2) / h**2
    s8 = float(res.get_sigma8_0())
    return {"ell": list(range(lmax + 1)), "TT": tot[:, 0].tolist(), "EE": tot[:, 1].tolist(),
            "BB": tot[:, 2].tolist(), "TE": tot[:, 3].tolist(), "PP": pp.tolist(),
            "derived": {"H0": float(pars.H0), "omegam": float(om), "sigma8": s8,
                        "S8": s8 * float(np.sqrt(om / 0.3))},
            "params": {k: float(v) for k, v in p.items() if isinstance(v, int | float)},
            "camb_version": camb.__version__}
