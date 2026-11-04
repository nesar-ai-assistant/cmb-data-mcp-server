"""Published parameter constraints (mean, 1-sigma) with citations - every number copied from
the cited paper/table (checked against arXiv HTML / abstracts on 2026-11-04).

Used by compare_with_published_constraints when a chain is not requested/available.
"""

PUBLISHED: dict[str, dict] = {
    "Planck 2018 (TT,TE,EE+lowE+lensing)": {
        "params": {"H0": (67.36, 0.54), "omegam": (0.3153, 0.0073), "sigma8": (0.8111, 0.0060),
                   "S8": (0.832, 0.013), "ns": (0.9649, 0.0042)},
        "kind": "cmb",
        "citation": "Planck Collaboration 2020, A&A 641, A6, Table 2 col. 'TT,TE,EE+lowE+lensing' (arXiv:1807.06209)",
    },
    "SPT-3G D1 (T&E + lensing)": {
        "params": {"H0": (66.66, 0.60), "omegam": (0.3246, 0.0091), "sigma8": (0.8158, 0.0058),
                   "ns": (0.951, 0.011)},
        "kind": "cmb",
        "citation": "Camphuis et al. 2025, Table 1 col. 'SPT-3G D1' (arXiv:2506.20707)",
    },
    "ACT DR6 (T&E + lensing)": {
        "params": {"H0": (66.51, 0.64), "omegam": (0.330, 0.010), "sigma8": (0.8171, 0.0055),
                   "ns": (0.9682, 0.0069)},
        "kind": "cmb",
        "citation": "Camphuis et al. 2025, Table 1 col. 'ACT DR6' (arXiv:2506.20707)",
    },
    "CMB-SPA (SPT+Planck+ACT)": {
        "params": {"H0": (67.19, 0.38), "omegam": (0.3175, 0.0055), "sigma8": (0.8137, 0.0037),
                   "ns": (0.9679, 0.0033)},
        "kind": "cmb",
        "citation": "Camphuis et al. 2025, Table 1 col. 'CMB-SPA' (arXiv:2506.20707)",
    },
    "P-ACT-LB (+lensing+DESI DR1 BAO)": {
        "params": {"H0": (68.22, 0.36), "sigma8": (0.813, 0.005), "ns": (0.974, 0.003)},
        "kind": "cmb+bao",
        "citation": "Louis et al. 2025, abstract (arXiv:2503.14452)",
    },
    "ACT DR6 lensing + BAO": {
        "params": {"H0": (68.3, 1.1), "sigma8": (0.819, 0.015), "S8": (0.840, 0.028)},
        "kind": "cmb-lensing",
        "citation": "Madhavacheril et al. 2024, abstract (arXiv:2304.05203)",
    },
    "SH0ES (Cepheid-SN Ia)": {
        "params": {"H0": (73.04, 1.04)},
        "kind": "local",
        "citation": "Riess et al. 2022, ApJL 934, L7 (arXiv:2112.04510)",
    },
    "DES Y3 3x2pt": {
        "params": {"S8": (0.776, 0.017), "omegam": (0.339, 0.0315)},
        "kind": "lss",
        "citation": "DES Collaboration 2022, PRD 105, 023520, abstract (arXiv:2105.13549); Om error symmetrised",
    },
    "KiDS-1000 3x2pt": {
        "params": {"S8": (0.766, 0.017)},
        "kind": "lss",
        "citation": "Heymans et al. 2021, A&A 646, A140, abstract (arXiv:2007.15632); +0.020/-0.014 symmetrised",
    },
}
