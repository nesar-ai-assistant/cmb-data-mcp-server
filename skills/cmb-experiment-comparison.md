---
name: cmb-experiment-comparison
description: Planck vs ACT DR6 vs SPT-3G - overlay TT/TE/EE bandpowers (Camphuis+25 Fig. 1), chi2 of each experiment against one common LCDM theory to ell=6600, lensing amplitudes, and a chain-level triangle comparison
---

# Planck vs ACT vs SPT-3G (spectra -> chi2 -> lensing -> parameters)

Use one `output_dir`.

## 1. Common theory to high ell
`compute_lcdm_theory_spectrum(output_dir, lmax=6600)` (camb; ACT's windows reach ell~6500).
Without camb, the bundled Planck theory stops at ell=2508: ACT/SPT bins beyond it are dropped
and the residual tool says so via n_bandpowers.

## 2. Overlay (reproduces SPT-3G D1 paper Fig. 1)
`plot_cmb_spectra(output_dir, ["planck_pr3","act_dr6","spt3g_d1"], "TT", log_y=True, theory_file=<csv>)`,
then `"EE"` (log_y=True) and `"TE"` (linear). Planck dominates ell<1500; ACT/SPT the damping tail.

## 3. chi2 per experiment vs the SAME theory
`compute_cmb_residuals(output_dir, ds, s, theory_file=<csv>)` for ds in
{planck_pr3, act_dr6, spt3g_d1} and s in {TT, TE, EE}. Expected vs Planck 2018 best fit:
- ACT DR6 (full covariance, A_act=P_act=1): TT ~59/45, TE ~47/45, EE ~60/45.
- SPT-3G D1 (diagonal): TT ~44/43, TE ~35/43, EE ~64/72.
ACT TT/EE PTE ~0.07 is expected because calibration/polarisation efficiency are fixed to 1 here.

## 4. Lensing
`plot_lensing_spectrum(output_dir, theory_file=<csv>)`: Planck ~1.01, ACT ~1.02 (+-0.03);
SPT-3G D1 ~0.93 is a known artefact of missing candl corrections (report it as such).

## 5. Parameters
`plot_triangle(output_dir, ["planck_pr3","act_dr6_lite"], ["H0","omegam","sigma8","ns"])` and
`analyze_chain` on both: ACT-lite H0 ~ 66.2 +- 0.8 vs Planck 67.36 +- 0.54 (~1.2 sigma);
P-ACT (`p_act_lite`) H0 ~ 67.6 +- 0.5. Published SPT-3G D1: H0 = 66.66 +- 0.60 (2506.20707).

## Report
Table of chi2/N, PTE and method per experiment and spectrum; lensing amplitudes; parameter
shifts in sigma; all figure paths. Never claim a likelihood-level result (Phase 2).
