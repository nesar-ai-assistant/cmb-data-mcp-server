---
name: reproduce-planck-tt-spectrum
description: Reproduce the Planck 2018 TT (and TE/EE) power-spectrum figure with the best-fit LCDM curve and residual panel, check chi2 against the PLA best fit, and optionally recompute the theory with camb
---

# Reproduce the Planck 2018 TT spectrum (Planck 2018 I, Fig. 1 / VI, Fig. 1)

Use one `output_dir`. All bundled: no network unless you ask for unbinned data.

## 1. Data
`fetch_cmb_spectrum(output_dir, "planck_pr3", "TT", binned=True)`.
Expect 83 bandpowers, ell 47.7-2499 (Delta-ell=30 bins from ell=30), first bin
D_ell = 1479 +- 51 muK^2, first peak near ell ~ 220 at ~5700-5800 muK^2.
For the low-ell plateau (2<=ell<30, asymmetric errors) add
`fetch_cmb_spectrum(output_dir, "planck_pr3", "TT", binned=False)` (170 kB download).

## 2. Plot
`plot_cmb_spectra(output_dir, ["planck_pr3"], "TT", show_theory=True, residual_panel=True)`.
Repeat with `"TE"` and `"EE"`. For the paper's hybrid look use `log_x=True` on the unbinned data.

## 3. chi2 vs the best fit
`compute_cmb_residuals(output_dir, "planck_pr3", "TT")` -> chi2 ~ 82.7 for 83 (PTE ~ 0.49);
TE ~ 78 / 66; EE ~ 75 / 66. These use DIAGONAL errors (the PLA plotting files carry no
covariance), so read them as "consistent", not as a likelihood. Check `max_abs_pull` < ~3.

## 4. Theory from scratch (optional, needs camb)
`compute_lcdm_theory_spectrum(output_dir)` (Planck best-fit params by default; pass e.g.
`params={"ns": 0.95}` to explore) -> derived H0 ~ 67.31, Om ~ 0.316, sigma8 ~ 0.812.
Then `compute_cmb_residuals(..., theory_file=<csv>)`: chi2 should move by < ~1 vs step 3
for the default parameters (camb vs CAMB-2018 accuracy settings).

## Report
Figure path, number of bandpowers, chi2/N per spectrum (state "diagonal"), theory source.
For a real likelihood use Phase 2 (HiLLiPoP/plik) - not available here.
