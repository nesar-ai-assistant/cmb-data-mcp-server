---
name: planck-map-to-power-spectrum
description: Tier 1 -> tier 2 - download the Planck PR3 SMICA-noSZ half-mission maps + common mask, downgrade to nside 1024, plot the map, and measure the TT power spectrum yourself (pseudo-C_ell hm1 x hm2 cross, beam/pixel-window/fsky corrected), then validate it against the released Planck bandpowers
---

# Planck map -> your own TT power spectrum (tier 1 -> tier 2)

Use one `output_dir`. First run downloads 2 x 201 MB half-mission maps + a 201 MB mask from
IRSA (~2-3 min each at ~1 MB/s, resumable); the downgraded nside-1024 maps are cached in
`~/.cache/cosmo-mcp/cmb-data-mcp-server/planck_pr3_maps`, so reruns are instant.
Both heavy tools dispatch (`set_dispatch("perlmutter")`): the node downloads the maps itself.

## 1. Tier-1 maps
```
h1 = fetch_cmb_map(output_dir, component="smica_nosz", split="hm1", nside=1024)
h2 = fetch_cmb_map(output_dir, component="smica_nosz", split="hm2", nside=1024)
```
Expect rms(T) in the mask ~107.5 / 107.4 muK, fsky (common_int) = 0.779, 0 UNSEEN pixels.
The full-mission map (`split="full"`, 403 MB) gives rms 106.9 muK.
Use smica_nosz (temperature only) unless you need Q/U: `smica` is 2.0 GB, `commander` 1.6 GB.

## 2. Look at it
`plot_cmb_map(output_dir, h1.metadata["map_file"], h1.metadata["mask_file"])` -> Mollweide PNG,
galactic plane and point-source holes greyed out, +-300 muK scale.

## 3. Measure the spectrum (tier 1 -> tier 2)
```
measure_cmb_power_spectrum(output_dir, map_file=h1.metadata["map_file"],
    map_file2=h2.metadata["map_file"], mask_file=h1.metadata["mask_file"],
    beam_fwhm_arcmin=5.0, lmax=2000, apod_deg=1.0)
```
Cross-spectrum hm1 x hm2: no noise bias. Reference run (2026-11-04, ~50 s on a laptop):
- fsky_w2 = 0.752 (1 deg apodised common mask), 66 Delta-ell = 30 bins, ell 30-2009.
- **First peak: ell = 225, D_ell = 5706 muK^2** (released Planck bin: 5793).
- Ratio to the released Planck TT bandpowers, 30 < ell < 1500: **median 1.023, rms 4.7 %,
  max 10 %**. Within +-4 % for 100 < ell < 1000; ell ~ 48 at -6.5 %; ell 1000-1500 at +4 to +10 %;
  above ell ~ 1500 it rises (+18 % at 1575, +58 % at 1935) from residual foregrounds and point
  sources that the Planck likelihood models and SMICA + common mask does not remove.
- The full-mission AUTO spectrum (no `map_file2`) is noise-biased: +3 % at ell ~ 600 but +27 %
  at ell ~ 1500. Always use the cross for ell > 1000.

If your numbers differ from these by more than ~2 %, check the beam (5'), the nside (pixel
window is applied for the map nside) and that the mask is the common_int one.

## 4. Fit your own spectrum (tier 2)
Feed the CSV (columns ell_min, ell_max, ell, D_ell_TT, err_TT_cv) to a theory comparison:
`compute_lcdm_theory_spectrum(output_dir, params={...})` then compare by eye, or with
`plot_cmb_spectra`. Errors are Knox cosmic-variance only (no noise, no mode coupling), so
chi2 values from this CSV are indicative. Restrict to 30 < ell < 1500.

## 5. Compare with published (tier 3, comparison only)
Only at the end: the Planck 2018 best-fit theory (`plot_cmb_spectra` default curve) or
`analyze_chain(output_dir, "planck_pr3")`. Do not use them as priors for step 4.

## Report
Map files and rms, the spectrum CSV + PNG, first-peak position/height, the ratio statistics
vs the released bandpowers, and the caveats (pseudo-C_ell/fsky, Knox errors, foreground
residuals at high ell).
