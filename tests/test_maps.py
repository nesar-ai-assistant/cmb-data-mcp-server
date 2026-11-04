"""Component-separated CMB map tools: offline tests (synthetic HEALPix maps, FITS reader) + the reference run.

The real Planck maps are NOT downloaded here (CI is offline); network tests for the IRSA
URLs live in tests/test_network.py, and the reference hm1 x hm2 measurement from the real
SMICA-noSZ maps is checked in as tests/data/smica_nosz_hm1xhm2_n1024_cl.csv.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

hp = pytest.importorskip("healpy")

from tools.maps import io as mio  # noqa: E402
from tools.maps import kernels as MK  # noqa: E402
from tools.maps import tools as MT  # noqa: E402
from tools.spectra.data import load_spectrum, theory_dl  # noqa: E402

DATA = Path(__file__).parent / "data"


def _synthetic(tmp_path, nside=256, fwhm_arcmin=5.0, seed=3, nested_planck_format=False):
    """Gaussian CMB sky from the bundled Planck best-fit TT, beam- and pixel-window-convolved."""
    th = theory_dl()
    ell = np.arange(3 * nside)
    dl = np.interp(ell, th["ell"], th["TT"], left=0, right=0)
    cl = np.where(ell > 1, dl * 2 * np.pi / np.maximum(ell * (ell + 1), 1), 0.0)
    np.random.seed(seed)
    m = hp.synfast(cl, nside, fwhm=np.radians(fwhm_arcmin / 60), pixwin=True, new=True)
    # galactic-like cut: |b| < 20 deg masked
    theta, _ = hp.pix2ang(nside, np.arange(hp.nside2npix(nside)))
    mask = (np.abs(np.pi / 2 - theta) > np.radians(20)).astype(float)
    mf, kf = tmp_path / "map.fits", tmp_path / "mask.fits"
    hp.write_map(str(mf), m, overwrite=True, dtype=np.float32)
    hp.write_map(str(kf), mask, overwrite=True, dtype=np.float32)
    return mf, kf, ell, dl


def test_pseudo_cl_recovers_input_spectrum(tmp_path):
    mf, kf, ell, dl = _synthetic(tmp_path)
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        r = MK.measure_power_spectrum_kernel(str(mf), str(kf), 5.0, lmax=500, apod_deg=2.0, out_stem="syn")
    finally:
        os.chdir(cwd)
    a = np.genfromtxt(r["csv"], delimiter=",", names=True)
    truth = np.array([np.average(dl[int(lo):int(hi) + 1], weights=2 * ell[int(lo):int(hi) + 1] + 1)
                      for lo, hi in zip(a["ell_min"], a["ell_max"], strict=True)])
    pull = (a["D_ell_TT"] - truth) / a["err_TT_cv"]
    assert np.abs(np.median(a["D_ell_TT"] / truth - 1)) < 0.03
    assert np.std(pull) < 2.0
    assert 180 < r["meta"]["first_peak_ell"] < 260 and 5000 < r["meta"]["first_peak_D_ell"] < 6500
    assert abs(r["meta"]["fsky_binary"] - (1 - np.sin(np.radians(20)))) < 0.02


def test_cross_spectrum_removes_noise_bias(tmp_path):
    mf, kf, ell, dl = _synthetic(tmp_path, nside=128)
    m = hp.read_map(str(mf))
    rng = np.random.default_rng(1)
    noise = 60.0  # muK per pixel: dominates ell > ~200 at nside 128
    for i in (1, 2):
        hp.write_map(str(tmp_path / f"h{i}.fits"), m + rng.normal(0, noise, m.size), overwrite=True,
                     dtype=np.float32)
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        auto = MK.measure_power_spectrum_kernel(str(tmp_path / "h1.fits"), str(kf), lmax=300, out_stem="a")
        cross = MK.measure_power_spectrum_kernel(str(tmp_path / "h1.fits"), str(kf), lmax=300, out_stem="x",
                                                 map_file2=str(tmp_path / "h2.fits"))
    finally:
        os.chdir(cwd)
    A = np.genfromtxt(auto["csv"], delimiter=",", names=True)
    X = np.genfromtxt(cross["csv"], delimiter=",", names=True)
    hi = A["ell"] > 200
    truth = np.interp(X["ell"], ell, dl)
    assert np.median(A["D_ell_TT"][hi] / truth[hi]) > 1.3      # noise-biased
    assert abs(np.median(X["D_ell_TT"][hi] / truth[hi]) - 1) < 0.15
    assert cross["meta"]["estimator"].startswith("cross")


def test_fits_reader_matches_healpy_and_downgrade(tmp_path):
    """read_healpix_columns on a Planck-format (NESTED, multi-column) table + prepare-style ud_grade."""
    from astropy.io import fits

    nside = 64
    npix = hp.nside2npix(nside)
    rng = np.random.default_rng(0)
    i_k, inp = (rng.normal(0, 1e-4, npix).astype(np.float32), rng.normal(0, 1, npix).astype(np.float32))
    cols = [fits.Column("I_STOKES", "E", array=i_k), fits.Column("I_STOKES_INP", "E", array=inp)]
    hdu = fits.BinTableHDU.from_columns(cols)
    hdu.header.update({"PIXTYPE": "HEALPIX", "ORDERING": "NESTED", "NSIDE": nside})
    path = tmp_path / "planck_like.fits"
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(path)
    data, hdr = mio.read_healpix_columns(path, ["I_STOKES"])
    assert hdr["ORDERING"] == "NESTED" and int(hdr["NSIDE"]) == nside
    np.testing.assert_array_equal(data["I_STOKES"], i_k)
    ring = MK._ud(hp, data["I_STOKES"].astype(float) * 1e6, 32, True)
    ref = hp.ud_grade(hp.reorder(i_k.astype(float) * 1e6, n2r=True), 32)
    np.testing.assert_allclose(ring, ref, rtol=1e-5)


def test_prepare_kernel_offline_from_cached_file(tmp_path, monkeypatch):
    """prepare_map_kernel with the full-res file already in cache: no network, correct units/ordering."""
    from astropy.io import fits

    nside = 64
    npix = hp.nside2npix(nside)
    cache = tmp_path / "planck_pr3_maps"
    cache.mkdir()
    t_k = np.full(npix, 1e-4, np.float32)
    for name, cols in ((mio.MAPS["smica_nosz"]["full"], [("I_STOKES", t_k), ("I_STOKES_INP", t_k)]),
                       (mio.MASKS["common_int"]["file"], [("TMASK", np.ones(npix, np.float32))])):
        hdu = fits.BinTableHDU.from_columns([fits.Column(n, "E", array=a) for n, a in cols])
        hdu.header.update({"PIXTYPE": "HEALPIX", "ORDERING": "NESTED", "NSIDE": nside})
        fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(cache / name)
    monkeypatch.setattr(mio, "content_length", lambda url, timeout=60: (_ for _ in ()).throw(AssertionError))
    r = MK.prepare_map_kernel("smica_nosz", "full", 32, "common_int", cache_dir=str(tmp_path))
    assert abs(r["stats"]["mean_I_uK_in_mask"] - 100.0) < 1e-3
    assert r["stats"]["fsky_mask"] == pytest.approx(1.0)
    m, h = hp.read_map(r["map_file"], h=True)
    assert dict(h)["ORDERING"] == "RING" and hp.get_nside(m) == 32
    assert MT._spec_from_header(r["map_file"], r["mask_file"]) == {
        "component": "smica_nosz", "split": "full", "nside": 32, "mask": "common_int"}


def test_reference_run_on_real_planck_maps():
    """Checked-in output of measure_cmb_power_spectrum on the real SMICA-noSZ hm1 x hm2 maps."""
    a = np.genfromtxt(DATA / "smica_nosz_hm1xhm2_n1024_cl.csv", delimiter=",", names=True)
    meta = json.loads((DATA / "smica_nosz_hm1xhm2_n1024_cl.json").read_text())
    assert 215 < meta["first_peak_ell"] < 235 and 5600 < meta["first_peak_D_ell"] < 5850
    rec = load_spectrum("planck_pr3", "TT")
    n = min(len(a), len(rec["ell"]))
    ratio = a["D_ell_TT"][:n] / rec["dl"][:n]
    sel = (rec["ell"][:n] > 30) & (rec["ell"][:n] < 1500)
    assert np.sqrt(np.mean((ratio[sel] - 1) ** 2)) < 0.07
    assert np.max(np.abs(ratio[sel] - 1)) < 0.12


def test_plot_cmb_map(tmp_path):
    mf, kf, *_ = _synthetic(tmp_path, nside=64)
    r = MT.plot_cmb_map(str(tmp_path), str(mf), str(kf))
    assert r.metadata["data_kind"] == "catalog"
    assert 50 < r.metadata["rms_uK"] < 200
    assert Path(r.files[0]).stat().st_size > 20_000


def test_map_registry_urls_are_irsa_pr3():
    for comp in mio.MAPS:
        for split in ("full", "hm1", "hm2"):
            assert mio.map_url(comp, split).startswith(mio.CMB_DIR) and "R3.00" in mio.map_url(comp, split)
    assert set(MT.DISPATCH_KERNELS) == {"prepare_cmb_map", "measure_cmb_power_spectrum"}
    assert MT.fetch_cmb_map.weight == MT.measure_cmb_power_spectrum.weight == "heavy"
