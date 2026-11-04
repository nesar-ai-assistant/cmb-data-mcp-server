"""Network tests: downloads (ACT sacc 287 kB, Planck chain 65 MB, ACT chain 5.5 MB)."""

import pytest

from tools.chains import tools as C
from tools.spectra import tools as S

pytestmark = pytest.mark.network


def test_act_dr6_sacc_fetch_and_chi2(tmp_path):
    r = S.fetch_cmb_spectrum(str(tmp_path), "act_dr6", "TE")
    assert r.metadata["n_bandpowers"] == 45 and r.metadata["has_covariance"]
    res = S.compute_cmb_residuals(str(tmp_path), "act_dr6", "TE")
    assert "full covariance" in res.metadata["method"] and res.metadata["chi2_per_n"] < 2


def test_planck_unbinned_download(tmp_path):
    r = S.fetch_cmb_spectrum(str(tmp_path), "planck_pr3", "EE", binned=False)
    assert r.metadata["ell_range"][0] == 2


def test_planck_chain_sanity(tmp_path):
    st = C.analyze_chain(str(tmp_path), "planck_pr3", ["H0", "omegam", "sigma8"]).metadata["stats"]
    assert st["H0"]["mean"] == pytest.approx(67.36, abs=0.02) and st["H0"]["std"] == pytest.approx(0.54, abs=0.01)
    assert st["omegam"]["mean"] == pytest.approx(0.3153, abs=3e-4)
    assert st["omegam"]["std"] == pytest.approx(0.0073, abs=3e-4)
    assert st["sigma8"]["mean"] == pytest.approx(0.8111, abs=3e-4)
    assert st["sigma8"]["std"] == pytest.approx(0.0060, abs=3e-4)


def test_act_chain_and_triangle(tmp_path):
    st = C.analyze_chain(str(tmp_path), "act_dr6_lite", ["H0", "omegam", "S8"]).metadata["stats"]
    assert 65 < st["H0"]["mean"] < 67.5 and 0.30 < st["omegam"]["mean"] < 0.36
    r = C.plot_triangle(str(tmp_path), ["planck_pr3", "act_dr6_lite"], ["H0", "omegam"])
    assert r.files[0].endswith(".png")


def test_planck_pr3_map_urls_head_and_header():
    """Component-separated CMB maps: HEAD sizes match the registry; FITS header (range fetch) is HEALPix nside 2048."""
    from tools.maps import io as mio

    for comp in ("smica_nosz", "smica"):
        assert mio.content_length(mio.map_url(comp)) == mio.MAPS[comp]["bytes_full"]
    assert mio.content_length(mio.map_url("smica_nosz", "hm1")) == mio.MAPS["smica_nosz"]["bytes_hm"]
    assert mio.content_length(mio.mask_url("common_int")) == mio.MASKS["common_int"]["bytes"]
    cards = " ".join(mio.fits_header_cards(mio.map_url("smica_nosz")))
    assert "HEALPIX" in cards and "2048" in cards and "I_STOKES" in cards
