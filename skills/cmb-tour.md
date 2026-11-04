---
name: cmb-tour
description: Five-minute all-local tour of the CMB Data server - one call per family (Planck/ACT/SPT spectra, residual chi2, lensing, LCDM theory, Planck chain stats, whisker comparison) with the numbers to expect
---

# CMB Data server tour (local, < 5 min)

Use one `output_dir` (e.g. `output/tour`). Everything runs locally; the first chain call
downloads 65 MB once (cached in `~/.cache/cosmo-mcp/cmb-data-mcp-server`).

## 1. Discover
`list_cmb_datasets()` -> 9 datasets (planck_pr3, act_dr6, spt3g_d1, spt3g_2018, three lensing
sets, planck_pr3_chains, act_dr6_chains). `describe_cmb_dataset("act_dr6")` for units/URLs.

## 2. Spectra
- `fetch_cmb_spectrum(output_dir, "planck_pr3", "TT")` -> 83 bandpowers, ell 48-2499,
  diagonal S/N ~846 (bundled; no network).
- `fetch_cmb_spectrum(output_dir, "act_dr6", "EE")` -> 45 bandpowers, ell 600-6126, with
  a 45x45 `_cov.npy` (287 kB download from LAMBDA on first use).
- `plot_cmb_spectra(output_dir, ["planck_pr3","act_dr6","spt3g_d1"], "TT", log_y=True)`
  -> three-experiment overlay with the Planck 2018 best fit and a residual panel.

## 3. chi2 vs LCDM
`compute_cmb_residuals(output_dir, "planck_pr3", "TT")` -> chi2 ~ 82.7 / 83 (diagonal;
indicative). `compute_cmb_residuals(output_dir, "act_dr6", "TE")` -> full covariance,
chi2 ~ 31 / 33 within ell<=2508 (the bundled theory stops there; see step 5 for full range).

## 4. Lensing
`plot_lensing_spectrum(output_dir)` -> Planck A_lens ~ 1.01 +- 0.03, ACT DR6 ~ 1.02 +- 0.03
vs Planck 2018 LCDM. SPT-3G D1 comes out ~0.93 because candl's systematics/response
corrections are not applied - say so when reporting (Phase 2).

## 5. Theory
`compute_lcdm_theory_spectrum(output_dir, lmax=6600)` -> camb if installed
(H0 ~ 67.31, Om ~ 0.316, sigma8 ~ 0.812 at the Planck best fit); without camb it falls back
to the bundled Planck best-fit file (ell<=2508). Pass the CSV as `theory_file` to steps 2-4.

## 6. Chains
`analyze_chain(output_dir, "planck_pr3")` -> **H0 = 67.36 +- 0.54, omegam = 0.3153 +- 0.0073,
sigma8 = 0.8111 +- 0.0060** (Planck 2018 Table 2; if these differ, stop - the chain is wrong).

## 7. Compare
`compare_parameter_constraints(output_dir)` -> whisker PNG + CSV; SH0ES vs Planck H0 ~ 4.9 sigma,
KiDS S8 ~ -3.1 sigma, DES Y3 S8 ~ -2.6 sigma.

Report: the files, the three Planck sanity numbers, the A_lens values, and the tensions.
