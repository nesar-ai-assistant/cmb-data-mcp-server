---
name: cmb-tour
description: Tour of the CMB Data server by data tier - Planck PR3 map (tier 1) -> your own TT spectrum and released Planck/ACT/SPT bandpowers (tier 2) -> your own LCDM fit/chi2 -> compare with published chains (tier 3, comparison only), with the numbers to expect
---

# CMB Data server tour (tier 1 -> tier 2 -> own fit -> compare)

Use one `output_dir` (e.g. `output/tour`). Steps 2-4 are local and bundled; step 1 downloads
~600 MB once (cached in `~/.cache/cosmo-mcp/cmb-data-mcp-server`); step 6 downloads 65 MB.

## 0. Discover
`list_cmb_datasets()` -> 10 datasets; with tier-1/2/3 products: 1/8/3.
`list_cmb_datasets(tier=1)` -> `planck_pr3_maps`. `describe_cmb_dataset("planck_pr3_maps")`
for URLs, file sizes, units.

## 1. Tier 1: a Planck map
`m = fetch_cmb_map(output_dir, "smica_nosz", "full", nside=1024)` -> 403 MB download, then
cached; rms(T) in the common mask = 106.9 muK, fsky = 0.779.
`plot_cmb_map(output_dir, m.metadata["map_file"], m.metadata["mask_file"])` -> Mollweide PNG.

## 2. Tier 1 -> tier 2: your own spectrum
Fetch `split="hm1"` and `"hm2"` too, then
`measure_cmb_power_spectrum(output_dir, map_file=<hm1>, map_file2=<hm2>, mask_file=<mask>)`
-> first peak ell = 225, D_ell = 5706 muK^2; within 4.7 % rms of the released Planck TT
bandpowers at 30 < ell < 1500 (full recipe: `planck-map-to-power-spectrum`).

## 3. Tier 2: released bandpowers
- `fetch_cmb_spectrum(output_dir, "planck_pr3", "TT")` -> 83 bandpowers, ell 48-2499,
  diagonal S/N ~846 (bundled; no network).
- `fetch_cmb_spectrum(output_dir, "act_dr6", "EE")` -> 45 bandpowers, ell 600-6126, with
  a 45x45 `_cov.npy` (287 kB download from LAMBDA on first use).
- `plot_cmb_spectra(output_dir, ["planck_pr3","act_dr6","spt3g_d1"], "TT", log_y=True)`.
- Lensing: `plot_lensing_spectrum(output_dir)` -> Planck A_lens ~ 1.01 +- 0.03, ACT DR6
  ~ 1.02 +- 0.03. SPT-3G D1 comes out ~0.93 because candl's corrections are not applied.

## 4. Your own model and chi2 (tier 2)
`compute_lcdm_theory_spectrum(output_dir, params={"H0": 67.5, "ombh2": 0.0224, ...}, lmax=6600)`
-> camb with YOUR parameters (H0 ~ 67.31, sigma8 ~ 0.812 at Planck-like values). Then
`compute_cmb_residuals(output_dir, "act_dr6", "TE", theory_file=<csv>)` -> full-covariance chi2
(~31 / 33). Without `theory_file` the reference curve is the PUBLISHED Planck best fit (tier 3):
fine for a quick look, but report it as such (`metadata.theory_provenance`).
Planck TT vs best fit: chi2 ~ 82.7 / 83 (diagonal; indicative).

## 5-6. Compare with published (tier 3, comparison only)
`analyze_chain(output_dir, "planck_pr3")` -> **H0 = 67.36 +- 0.54, omegam = 0.3153 +- 0.0073,
sigma8 = 0.8111 +- 0.0060** (Planck 2018 Table 2; if these differ, stop - the chain is wrong).
`compare_with_published_constraints(output_dir)` -> whisker PNG + CSV; SH0ES vs Planck
H0 ~ 4.9 sigma, KiDS S8 ~ -3.1 sigma, DES Y3 S8 ~ -2.6 sigma. These are published inference
products: compare your step-4 numbers against them; never feed them into step 4.

Report: map rms, your first-peak numbers and ratio to the released bandpowers, chi2 values,
A_lens, and (last, labelled tier 3) the published constraints and tensions.
