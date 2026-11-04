"""Single source of truth for the datasets this server exposes.

Keys are short dataset ids used by every tool's ``dataset`` argument.
"access" is "bundled" (file in data/), "download" (fetched on first use
into the data cache) or "remote-query" (live service). Every URL below was
downloaded (or for the >200 MB maps, HEAD + range-fetched and the defaults fully
downloaded) during development (2026-11-04).

products are split by kind of data (see docs/CONVENTIONS.md):
catalog = component-separated CMB maps, summary_statistic = bandpowers + covariances,
published_result = published chains / best-fit theory (comparison only).
"""

PLA = "https://irsa.ipac.caltech.edu/data/Planck/release_3/ancillary-data/cosmoparams/"
COBAYA_LENS = ("https://raw.githubusercontent.com/CobayaSampler/planck_supp_data_and_covmats/"
               "master/lensing/2018/")
ACT_SACC = "https://lambda.gsfc.nasa.gov/data/act/pspipe/sacc_files/dr6_data_cmbonly.tar.gz"
ACT_CHAINS = "https://lambda.gsfc.nasa.gov/data/act/chains/lcdm/"
ACT_LENS_TGZ = "https://lambda.gsfc.nasa.gov/data/suborbital/ACT/ACT_dr6/likelihood/data/ACT_dr6_likelihood_v1.2.tgz"
SPT_CANDL = ("https://raw.githubusercontent.com/SouthPoleTelescope/spt_candl_data/main/"
             "spt_candl_data/SPT3G_D1_KK_v0/GMV/")

IRSA_CMB = "https://irsa.ipac.caltech.edu/data/Planck/release_3/all-sky-maps/maps/component-maps/cmb/"
IRSA_MASK = "https://irsa.ipac.caltech.edu/data/Planck/release_3/ancillary-data/masks/"
IRSA_LENS = "https://irsa.ipac.caltech.edu/data/Planck/release_3/all-sky-maps/maps/component-maps/lensing/"

DATASETS: dict[str, dict] = {
    "planck_pr3_maps": {
        "title": "Planck 2018 (PR3) component-separated CMB maps (SMICA, SMICA-noSZ, Commander) + common masks",
        "products": {"catalog": ["SMICA-noSZ T map (full, hm1, hm2)", "SMICA I/Q/U map (full, hm1, hm2)",
                               "Commander I/Q/U map (full, hm1, hm2)", "common temperature / polarisation masks"],
                     "summary_statistic": ["pseudo-C_ell TT (EE/TE/BB) measured from the maps by measure_cmb_power_spectrum"]},
        "access": "download on demand (IRSA, resumable parallel range requests), then ud_grade 2048 -> "
                  "nside 128-1024 and cache the downgraded map; never bulk. Sizes: smica_nosz 403 MB full / "
                  "201 MB per half-mission, smica 2.0 GB, commander 1.6 GB, each mask 201 MB.",
        "units": "muK_CMB (files are K_CMB; tools convert); HEALPix nside 2048 NESTED Galactic in the files, "
                 "RING after downgrading; 5 arcmin Gaussian effective beam",
        "urls": [IRSA_CMB + "COM_CMB_IQU-smica-nosz_2048_R3.00_full.fits",
                 IRSA_CMB + "COM_CMB_IQU-smica-nosz_2048_R3.00_hm1.fits",
                 IRSA_CMB + "COM_CMB_IQU-smica-nosz_2048_R3.00_hm2.fits",
                 IRSA_CMB + "COM_CMB_IQU-smica_2048_R3.00_full.fits",
                 IRSA_CMB + "COM_CMB_IQU-commander_2048_R3.00_full.fits",
                 IRSA_MASK + "COM_Mask_CMB-common-Mask-Int_2048_R3.00.fits",
                 IRSA_MASK + "COM_Mask_CMB-common-Mask-Pol_2048_R3.00.fits"],
        "notes": "No official nside-1024 PR3 SMICA map exists (PR2 had one); smica_nosz (temperature-only, 2 "
                 "columns) is the smallest full-resolution product, so it is the default. Auto-spectra carry "
                 "noise bias at ell >~ 1000; use the hm1 x hm2 cross-spectrum. The Planck lensing MV klm "
                 "(COM_Lensing_4096_R3.00.tgz, 723 MB, HEAD-verified) is listed but no tool reads it yet.",
        "citation": "Planck Collaboration 2020, A&A 641, A4 (arXiv:1807.06208)",
        "tools": ["fetch_cmb_map", "plot_cmb_map", "measure_cmb_power_spectrum"],
    },
    "planck_pr3": {
        "title": "Planck 2018 (PR3) CMB power spectra TT/TE/EE (+ low-ell BB) and the "
                 "base_plikHM_TTTEEE_lowl_lowE_lensing best-fit theory spectrum",
        "products": {"summary_statistic": ["TT", "TE", "EE", "BB (low-ell, ell<30)"],
                     "published_result": ["base_plikHM_TTTEEE_lowl_lowE_lensing best-fit theory TT/TE/EE/BB/PP (comparison only)"]},
        "access": "bundled (binned spectra + best-fit theory + low-ell BB); download (unbinned full spectra)",
        "units": "D_ell = ell(ell+1)C_ell/2pi in muK^2; theory PP column = [L(L+1)]^2 C_L^phiphi/2pi",
        "multipoles": "TT 2-2508, TE/EE 2-1996 (full); binned TT 30-2500, TE/EE 30-2000 (low-ell <30 unbinned)",
        "urls": [PLA + "COM_PowerSpect_CMB-TT-binned_R3.01.txt",
                 PLA + "COM_PowerSpect_CMB-TE-binned_R3.02.txt",
                 PLA + "COM_PowerSpect_CMB-EE-binned_R3.02.txt",
                 PLA + "COM_PowerSpect_CMB-TT-full_R3.01.txt",
                 PLA + "COM_PowerSpect_CMB-TE-full_R3.01.txt",
                 PLA + "COM_PowerSpect_CMB-EE-full_R3.01.txt",
                 PLA + "COM_PowerSpect_CMB-low-ell-BB-full_R3.01.txt",
                 PLA + "COM_PowerSpect_CMB-base-plikHM-TTTEEE-lowl-lowE-lensing-minimum-theory_R3.01.txt"],
        "notes": "Errors are diagonal (asymmetric at ell<30). The binned files' 5th column is the "
                 "Planck best fit binned in the same way. No covariance in these plotting products: "
                 "chi2 from them is diagonal-only (Phase 2: HiLLiPoP/plik for the real likelihood).",
        "citation": "Planck Collaboration 2020, A&A 641, A5 (arXiv:1907.12875); A&A 641, A6 (arXiv:1807.06209)",
        "tools": ["fetch_cmb_spectrum", "plot_cmb_spectra", "compute_cmb_residuals",
                  "compute_lcdm_theory_spectrum"],
    },
    "act_dr6": {
        "title": "ACT DR6 CMB-only (ACT-lite) foreground-marginalised TT/TE/EE bandpowers",
        "products": {"summary_statistic": ["TT", "TE", "EE", "full 135x135 covariance", "bandpower window functions"]},
        "access": "download (287 kB sacc tarball from LAMBDA)",
        "units": "D_ell in muK^2 (CMB-only, foregrounds marginalised), ell 600-6500 in Delta-ell=50 bins",
        "urls": [ACT_SACC,
                 "https://github.com/ACTCollaboration/DR6-ACT-lite (act_dr6_cmbonly likelihood; same data)"],
        "notes": "Model bandpowers = W @ D_ell^theory / (A_act^2 * P_act^{n_E}); the tools use "
                 "A_act=P_act=1 by default. Same sacc as the cobaya act_dr6_cmbonly likelihood v1.0.",
        "citation": "Louis et al. 2025 (ACT DR6 power spectra, arXiv:2503.14452); "
                    "Calabrese et al. 2025 (arXiv:2503.14454)",
        "tools": ["fetch_cmb_spectrum", "plot_cmb_spectra", "compute_cmb_residuals"],
    },
    "spt3g_d1": {
        "title": "SPT-3G D1 (2019+2020 Main field) minimum-variance foreground-cleaned TT/TE/EE bandpowers",
        "products": {"summary_statistic": ["TT", "TE", "EE"]},
        "access": "bundled",
        "units": "D_ell in muK^2; TT 400-3000, TE/EE 400-4000, Delta-ell=50",
        "urls": ["https://pole.uchicago.edu/public/data/camphuis25/spt3gd1_mv_cleaned_bandpowers.zip",
                 "https://github.com/SouthPoleTelescope/spt_candl_data (SPT-lite likelihood: Phase 2)"],
        "notes": "Released 'for plotting purposes only' with diagonal errors; chi2 vs theory is "
                 "indicative (no covariance, no windows, no calibration).",
        "citation": "Camphuis et al. 2025, SPT-3G D1 (arXiv:2506.20707)",
        "tools": ["fetch_cmb_spectrum", "plot_cmb_spectra", "compute_cmb_residuals"],
    },
    "spt3g_2018": {
        "title": "SPT-3G 2018 TT/TE/EE minimum-variance bandpowers",
        "products": {"summary_statistic": ["TT", "TE", "EE"]},
        "access": "bundled",
        "units": "D_ell in muK^2; TT 750-3000, TE/EE 300-3000",
        "urls": ["https://pole.uchicago.edu/public/data/balkenhol22/SPT3G_2018_TTTEEE_MV_bdp.txt"],
        "notes": "Columns per spectrum: ell_eff, D_b, sigma_b (zeros where a spectrum is not measured).",
        "citation": "Balkenhol et al. 2023, PRD 108, 023510 (arXiv:2212.05642)",
        "tools": ["fetch_cmb_spectrum", "plot_cmb_spectra", "compute_cmb_residuals"],
    },
    "planck_pr3_lensing": {
        "title": "Planck 2018 lensing-potential bandpowers (conservative 8<=L<=400, CMB-marginalised)",
        "products": {"summary_statistic": ["PP", "9x9 covariance"]},
        "access": "bundled",
        "units": "[L(L+1)]^2 C_L^phiphi / 2pi (dimensionless)",
        "urls": [COBAYA_LENS + "smicadx12_Dec5_ftl_mv2_ndclpp_p_teb_consext8_bandpowers.dat",
                 COBAYA_LENS + "smicadx12_Dec5_ftl_mv2_ndclpp_p_teb_consext8_CMBmarged_cov.dat"],
        "citation": "Planck Collaboration 2020, A&A 641, A8 (arXiv:1807.06210)",
        "tools": ["fetch_cmb_spectrum", "plot_lensing_spectrum"],
    },
    "act_dr6_lensing": {
        "title": "ACT DR6 lensing convergence bandpowers (MV, profile-hardened; baseline 40<=L<=763)",
        "products": {"summary_statistic": ["PP (as C_L^kk)", "18x18 CMB-marginalised covariance", "bin edges"]},
        "access": "bundled (bandpowers/cov extracted from the 361 MB LAMBDA likelihood tarball)",
        "units": "file: C_L^kk; tools convert to [L(L+1)]^2 C_L^phiphi/2pi = 2 C_L^kk / pi",
        "urls": [ACT_LENS_TGZ, "https://github.com/ACTCollaboration/act_dr6_lenslike"],
        "notes": "Baseline likelihood uses bins 2..11 (act_dr6_lenslike). The binning matrix is "
                 "uniform top-hat; we bundle its edges. Hartlap factor for 796 sims applied in chi2.",
        "citation": "Qu et al. 2024, ApJ 962, 112 (arXiv:2304.05202); Madhavacheril et al. 2024 (arXiv:2304.05203)",
        "tools": ["fetch_cmb_spectrum", "plot_lensing_spectrum"],
    },
    "spt3g_d1_lensing": {
        "title": "SPT-3G D1 GMV lensing bandpowers (17 bins, CMB-marginalised covariance)",
        "products": {"summary_statistic": ["PP (as C_L^kk)", "17x17 covariance", "bandpower windows"]},
        "access": "bundled",
        "units": "file: C_L^kk; tools convert to [L(L+1)]^2 C_L^phiphi/2pi",
        "urls": [SPT_CANDL + "SPT3G_D1_KK_GMV_bdp.txt", SPT_CANDL + "SPT3G_D1_KK_GMV_cov_CMBmarg.txt",
                 SPT_CANDL + "windows/kk_window_functions.txt"],
        "notes": "Bin centres are the window-weighted mean L. Hartlap N_sims=498 (candl yaml). CAVEAT: the candl "
                 "data model applies a multiplicative lensing-systematics emulator and M_L response corrections "
                 "to the THEORY; without them (Phase 2: candl) a raw window comparison gives A_lens~0.93 vs "
                 "Planck 2018 - not the published consistency. Treat SPT lensing chi2/A_lens as indicative.",
        "citation": "SPT-3G D1 lensing (arXiv:2608.31136) via spt_candl_data",
        "tools": ["fetch_cmb_spectrum", "plot_lensing_spectrum"],
    },
    "planck_pr3_chains": {
        "title": "Planck 2018 base_plikHM_TTTEEE_lowl_lowE_lensing MCMC chains (CosmoMC)",
        "products": {"published_result": ["posterior chains", "margestats (bundled)"]},
        "access": "bundled margestats; download (65 MB PLA zip, single-likelihood family, NOT the 11 GB grid)",
        "urls": [PLA + "COM_CosmoParams_base-plikHM-TTTEEE-lowl-lowE_R3.00.zip"],
        "notes": "Chains are already burn-in-removed (getdist ignore_rows=0). "
                 "Expected: H0 67.36+-0.54, Om 0.3153+-0.0073, sigma8 0.8111+-0.0060.",
        "citation": "Planck Collaboration 2020, A&A 641, A6 (arXiv:1807.06209)",
        "tools": ["fetch_cmb_chain", "analyze_chain", "plot_triangle", "compare_with_published_constraints"],
    },
    "act_dr6_chains": {
        "title": "ACT DR6 LCDM chains (Cobaya): ACT-lite and P-ACT-lite (CAMB)",
        "products": {"published_result": ["posterior chains"]},
        "access": "download (5.5 MB / 7.1 MB tarballs from LAMBDA)",
        "urls": [ACT_CHAINS + "actlite_lcdm_camb.tar.gz", ACT_CHAINS + "p-actlite_lcdm_camb.tar.gz"],
        "notes": "No Omega_m column: derived as (ombh2+omch2+0.06 eV nu)/h^2. LAMBDA lists no burn-in "
                 "fraction for these; we use 0.3 (results stable vs 0).",
        "citation": "Louis et al. 2025 (arXiv:2503.14452); Calabrese et al. 2025 (arXiv:2503.14454)",
        "tools": ["fetch_cmb_chain", "analyze_chain", "plot_triangle", "compare_with_published_constraints"],
    },
}
