"""CMB server science tests (offline: bundled data only)."""

import numpy as np
import pytest

from tools.chains import tools as C
from tools.spectra import tools as S
from tools.chains import kernels as CK
from tools.chains.published import PUBLISHED
from tools.spectra.data import binned_theory, load_spectrum, theory_dl


def test_planck_binned_tt_bundled(tmp_path):
    r = S.fetch_cmb_spectrum(str(tmp_path), "planck_pr3", "TT")
    assert r.metadata["n_bandpowers"] == 83
    rec = load_spectrum("planck_pr3", "TT")
    peak = rec["ell"][np.argmax(rec["dl"])]
    assert 180 < peak < 260 and 5500 < rec["dl"].max() < 6000


def test_planck_tt_chi2_vs_bestfit(tmp_path):
    r = S.compute_cmb_residuals(str(tmp_path), "planck_pr3", "TT")
    assert r.metadata["n_bandpowers"] == 83
    assert 0.7 < r.metadata["chi2_per_n"] < 1.3


def test_bundled_binned_bestfit_matches_theory_file():
    rec = load_spectrum("planck_pr3", "TT")
    th = binned_theory(rec, theory_dl(), "TT")  # nearest-ell, no edges in the PLA file
    assert np.median(np.abs(th / rec["best_fit"] - 1)) < 0.02


@pytest.mark.parametrize("ds", ["planck_pr3", "act_dr6", "spt3g_d1"])
def test_lensing_bandpowers_and_amplitude(tmp_path, ds):
    rec = load_spectrum(ds, "PP")
    assert rec["cov"].shape == (len(rec["dl"]),) * 2
    assert np.all(rec["dl"][:5] > 1e-8) and np.all(rec["dl"] < 3e-7)


def test_lensing_plot_amplitudes(tmp_path):
    r = S.plot_lensing_spectrum(str(tmp_path))
    a = r.metadata["amplitudes"]
    assert abs(a["planck_pr3"]["A_lens"] - 1) < 0.1
    assert abs(a["act_dr6"]["A_lens"] - 1) < 0.1


def test_spt_spectra_bundled():
    for s, lo, hi in (("TT", 400, 3000), ("TE", 400, 4000), ("EE", 400, 4000)):
        rec = load_spectrum("spt3g_d1", s)
        assert lo < rec["ell"].min() < lo + 50 and hi - 50 < rec["ell"].max() < hi
    assert len(load_spectrum("spt3g_2018", "TT")["ell"]) > 20


def test_spectrum_plot(tmp_path):
    r = S.plot_cmb_spectra(str(tmp_path), ["planck_pr3", "spt3g_d1"], "EE")
    assert r.files[0].endswith(".png")


def test_theory_fallback_or_camb(tmp_path):
    r = S.compute_lcdm_theory_spectrum(str(tmp_path), lmax=2500)
    assert abs(r.metadata["derived"]["H0"] - 67.3) < 0.2


def test_bundled_margestats_sanity():
    m = C.bundled_planck_margestats(["H0", "omegam", "sigma8"])
    assert m["H0"][0] == pytest.approx(67.36, abs=0.01) and m["H0"][1] == pytest.approx(0.54, abs=0.01)
    assert m["omegam"][0] == pytest.approx(0.3153, abs=1e-4) and m["omegam"][1] == pytest.approx(0.0073, abs=1e-4)
    assert m["sigma8"][0] == pytest.approx(0.8111, abs=1e-4) and m["sigma8"][1] == pytest.approx(0.0060, abs=1e-4)


def test_published_whisker(tmp_path):
    r = C.compare_with_published_constraints(str(tmp_path))
    t = r.metadata["tensions_vs_reference"]
    assert 4.5 < t["SH0ES (Cepheid-SN Ia)"]["H0"] < 5.2
    assert all(e["citation"] for e in PUBLISHED.values())


def test_kernels_are_pure():
    import ast
    import pathlib
    for f in ("tools/chains/kernels.py", "tools/spectra/kernels.py", "tools/maps/kernels.py", "tools/maps/io.py"):
        tree = ast.parse(pathlib.Path(f).read_text())
        mods = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
        mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not mods & {"pydantic", "matplotlib", "mcp", "tools"}, (f, mods)
    assert set(CK.CHAINS) == {"planck_pr3", "act_dr6_lite", "p_act_lite"}
