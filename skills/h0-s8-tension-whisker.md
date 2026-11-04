---
name: h0-s8-tension-whisker
description: TIER 3 (comparison only) - build the H0 / S8 / Omega_m / n_s whisker plot across Planck, ACT, SPT-3G, CMB-SPA, SH0ES, DES Y3 and KiDS from public chains + cited tables and quantify the Hubble and S8 tensions in sigma
---

# H0 and S8 tension whisker (TIER 3: comparison only)

Every number here is a published inference product (chains, cited tables). Use this recipe
to put YOUR tier-1/2 results (e.g. from `planck-map-to-power-spectrum` or a fit to the
bandpowers) in context. Never use these constraints as measurements or priors in a fit.

Use one `output_dir`.

## 1. Live chains (ground truth for the CMB rows)
`analyze_chain(output_dir, "planck_pr3", params=["H0","S8","omegam","ns","sigma8"])`
-> H0 67.36 +- 0.54, S8 0.832 +- 0.013, omegam 0.3153 +- 0.0073, ns 0.9649 +- 0.0042.
`analyze_chain(output_dir, "act_dr6_lite", ...)` -> H0 ~ 66.2 +- 0.8, S8 ~ 0.87 +- 0.02
(Omega_m derived from ombh2+omch2+0.06 eV nu; S8 from sigma8).

## 2. Whisker
`compare_with_published_constraints(output_dir, params=["H0","S8","omegam","ns"],
chains=["planck_pr3","act_dr6_lite"], include_published=True)`.
Chain rows are squares, published rows circles; the grey band is the reference (Planck).

## 3. Expected tensions vs Planck 2018 (Gaussian, uncorrelated)
- SH0ES H0 73.04 +- 1.04 -> +4.9 sigma.
- KiDS-1000 S8 0.766 -> -3.1 sigma; DES Y3 S8 0.776 +- 0.017 -> -2.6 sigma.
- SPT-3G D1 / ACT DR6 / CMB-SPA H0 all within ~1 sigma of Planck.

## Report
The PNG + CSV, the tension table from `metadata.tensions_vs_reference`, and the citation
for every row (`metadata.citations`). State the caveats: asymmetric errors symmetrised,
correlations between CMB datasets ignored, KiDS/DES priors differ from the CMB analyses.
