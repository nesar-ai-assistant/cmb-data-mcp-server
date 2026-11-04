# Bundled data (total ~350 kB)

Every file was downloaded on 2026-11-04 from the URL shown; files are verbatim unless
noted. Larger products (Planck unbinned spectra, ACT DR6 sacc, all chains) download on
first use into `~/.cache/cosmo-mcp/cmb-data-mcp-server` (override: `$COSMO_MCP_DATA`).

| file | source URL | citation |
|---|---|---|
| `planck_pr3/COM_PowerSpect_CMB-TT-binned_R3.01.txt`, `...-TE-binned_R3.02.txt`, `...-EE-binned_R3.02.txt` | https://irsa.ipac.caltech.edu/data/Planck/release_3/ancillary-data/cosmoparams/ | Planck 2018 V (arXiv:1907.12875) |
| `planck_pr3/COM_PowerSpect_CMB-low-ell-BB-full_R3.01.txt` | same directory | Planck 2018 V |
| `planck_pr3/COM_PowerSpect_CMB-base-plikHM-TTTEEE-lowl-lowE-lensing-minimum-theory_R3.01.txt` | same directory | Planck 2018 VI (arXiv:1807.06209) |
| `planck_pr3_lensing/smicadx12_Dec5_ftl_mv2_ndclpp_p_teb_consext8_bandpowers.dat`, `..._CMBmarged_cov.dat` | https://raw.githubusercontent.com/CobayaSampler/planck_supp_data_and_covmats/master/lensing/2018/ | Planck 2018 VIII (arXiv:1807.06210) |
| `act_dr6_lensing/clkk_bandpowers_act.txt`, `covmat_act_cmbmarg.txt` | extracted from https://lambda.gsfc.nasa.gov/data/suborbital/ACT/ACT_dr6/likelihood/data/ACT_dr6_likelihood_v1.2.tgz (361 MB; file list from github.com/ACTCollaboration/act_dr6_lenslike) | Qu et al. 2024 (arXiv:2304.05202); Madhavacheril et al. 2024 (arXiv:2304.05203) |
| `act_dr6_lensing/act_dr6_lensing_bins.txt` | DERIVED: bin edges/centres of `binning_matrix_act.txt` in the same tarball (uniform top-hat rows, verified); baseline flag = bins 2..11 as in act_dr6_lenslike | as above |
| `spt3g/spt3gd1_mv_cleaned_bandpowers_{TT,TE,EE}.txt` | https://pole.uchicago.edu/public/data/camphuis25/spt3gd1_mv_cleaned_bandpowers.zip ("for plotting purposes only") | Camphuis et al. 2025 (arXiv:2506.20707) |
| `spt3g/SPT3G_2018_TTTEEE_MV_bdp.txt` | https://pole.uchicago.edu/public/data/balkenhol22/SPT3G_2018_TTTEEE_MV_bdp.txt | Balkenhol et al. 2023 (arXiv:2212.05642) |
| `spt3g/SPT3G_D1_KK_GMV_bdp.txt`, `SPT3G_D1_KK_GMV_cov_CMBmarg.txt` | https://raw.githubusercontent.com/SouthPoleTelescope/spt_candl_data/main/spt_candl_data/SPT3G_D1_KK_v0/GMV/ | SPT-3G D1 lensing (arXiv:2608.31136) |
| `spt3g/SPT3G_D1_KK_GMV_windows_sparse.txt` | DERIVED: non-zero entries of `.../GMV/windows/kk_window_functions.txt` (771 kB -> 67 kB) | as above |
| `chains/base_plikHM_TTTEEE_lowl_lowE_lensing.margestats` | from `dist/` in https://irsa.ipac.caltech.edu/data/Planck/release_3/ancillary-data/cosmoparams/COM_CosmoParams_base-plikHM-TTTEEE-lowl-lowE_R3.00.zip | Planck 2018 VI |

Downloaded on demand (also verified): the Planck `COM_PowerSpect_CMB-{TT,TE,EE}-full_R3.01.txt`,
`https://lambda.gsfc.nasa.gov/data/act/pspipe/sacc_files/dr6_data_cmbonly.tar.gz` (ACT DR6
CMB-only sacc v1.0), the 65 MB Planck chain zip above, and
`https://lambda.gsfc.nasa.gov/data/act/chains/lcdm/{actlite,p-actlite}_lcdm_camb.tar.gz`.
