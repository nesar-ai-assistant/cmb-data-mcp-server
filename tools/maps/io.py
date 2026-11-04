"""Planck PR3 map products: registry of verified IRSA URLs + a resumable, parallel
HTTP range downloader (the files are 0.2-2 GB) + header probing (pure python).

Kept import-light (stdlib + numpy) so maps.kernels can use it on a facility node.
"""

from __future__ import annotations

import os
import threading
import time
import urllib.request
from pathlib import Path

IRSA = "https://irsa.ipac.caltech.edu/data/Planck/release_3/"
CMB_DIR = IRSA + "all-sky-maps/maps/component-maps/cmb/"
MASK_DIR = IRSA + "ancillary-data/masks/"
LENS_DIR = IRSA + "all-sky-maps/maps/component-maps/lensing/"

# Sizes are the HTTP Content-Length values seen on 2026-11-04 (HEAD requests); columns are
# from the FITS headers (range-fetched). All maps are HEALPix nside 2048, NESTED, Galactic, K_CMB.
MAPS: dict[str, dict] = {
    "smica_nosz": {
        "full": "COM_CMB_IQU-smica-nosz_2048_R3.00_full.fits", "bytes_full": 402661440,
        "hm1": "COM_CMB_IQU-smica-nosz_2048_R3.00_hm1.fits", "hm2": "COM_CMB_IQU-smica-nosz_2048_R3.00_hm2.fits",
        "bytes_hm": 201335040, "fields": ["I_STOKES", "I_STOKES_INP"], "pol": False,
        "beam_fwhm_arcmin": 5.0,
        "note": "SMICA with thermal SZ deprojected; temperature only. Smallest official full-res CMB map (403 MB).",
    },
    "smica": {
        "full": "COM_CMB_IQU-smica_2048_R3.00_full.fits", "bytes_full": 2013312960,
        "hm1": "COM_CMB_IQU-smica_2048_R3.00_hm1.fits", "hm2": "COM_CMB_IQU-smica_2048_R3.00_hm2.fits",
        "bytes_hm": 603990720,
        "fields": ["I_STOKES", "Q_STOKES", "U_STOKES", "TMASK", "PMASK", "I_STOKES_INP", "Q_STOKES_INP",
                   "U_STOKES_INP", "TMASKINP", "PMASKINP"], "pol": True, "beam_fwhm_arcmin": 5.0,
        "note": "SMICA I/Q/U (+ confidence masks). Full file is 2.0 GB.",
    },
    "commander": {
        "full": "COM_CMB_IQU-commander_2048_R3.00_full.fits", "bytes_full": 1610660160,
        "hm1": "COM_CMB_IQU-commander_2048_R3.00_hm1.fits", "hm2": "COM_CMB_IQU-commander_2048_R3.00_hm2.fits",
        "bytes_hm": 603990720, "fields": None, "pol": True, "beam_fwhm_arcmin": 5.0,
        "note": "Commander I/Q/U. Full file is 1.6 GB.",
    },
}
MASKS: dict[str, dict] = {
    "common_int": {"file": "COM_Mask_CMB-common-Mask-Int_2048_R3.00.fits", "bytes": 201335040,
                   "field": "TMASK", "note": "PR3 common temperature mask (fsky ~0.78)"},
    "common_pol": {"file": "COM_Mask_CMB-common-Mask-Pol_2048_R3.00.fits", "bytes": 201335040,
                   "field": "PMASK", "note": "PR3 common polarisation mask"},
}
LENSING_TGZ = LENS_DIR + "COM_Lensing_4096_R3.00.tgz"   # 723 MB (MV klm + mask + N0); HEAD-verified


def map_url(component: str, split: str = "full") -> str:
    return CMB_DIR + MAPS[component][split]


def mask_url(mask: str) -> str:
    return MASK_DIR + MASKS[mask]["file"]


def _req(url: str, start: int | None = None, end: int | None = None, method: str = "GET"):
    h = {"User-Agent": "cosmo-mcp-server/0.1"}
    if start is not None:
        h["Range"] = f"bytes={start}-{'' if end is None else end}"
    return urllib.request.Request(url, headers=h, method=method)


def content_length(url: str, timeout: float = 60.0) -> int:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(_req(url, method="HEAD"), timeout=timeout) as r:
                return int(r.headers["Content-Length"])
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def fits_header_cards(url: str, nbytes: int = 8640) -> list[str]:
    """Range-fetch the first ``nbytes`` of a FITS file and return its header cards (all HDUs)."""
    with urllib.request.urlopen(_req(url, 0, nbytes - 1), timeout=60) as r:
        blob = r.read()
    cards = [blob[i:i + 80].decode("ascii", "replace") for i in range(0, len(blob), 80)]
    return [c.rstrip() for c in cards if c.strip() and c.isprintable()]


def download_ranges(url: str, dest: Path, n_conn: int = 6, chunk: int = 32 * 2**20,
                    timeout: float = 120.0, progress=None) -> Path:
    """Resumable parallel range download of ``url`` to ``dest`` (atomic rename at the end).

    The IRSA server gives ~0.8 MB/s per connection, so 6 connections cut a 400 MB map to a
    few minutes. Completed chunks are tracked in ``<dest>.part.done`` so an interrupted run
    resumes where it stopped.
    """
    dest = Path(dest)
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = content_length(url)
    part = dest.with_suffix(dest.suffix + ".part")
    donef = Path(str(part) + ".done")
    if not part.exists() or part.stat().st_size != total:
        with open(part, "wb") as fh:
            fh.truncate(total)
        donef.write_text("")
    done = {int(x) for x in donef.read_text().split()} if donef.exists() else set()
    todo = [s for s in range(0, total, chunk) if s not in done]
    lock = threading.Lock()
    errors: list[Exception] = []
    state = {"bytes": len(done) * chunk, "t0": time.time()}

    def worker():
        while True:
            with lock:
                if not todo or errors:
                    return
                s = todo.pop(0)
            e = min(s + chunk, total) - 1
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(_req(url, s, e), timeout=timeout) as r:
                        data = r.read()
                    if len(data) != e - s + 1:
                        raise OSError(f"short read {len(data)} != {e - s + 1}")
                    with lock:
                        fd = os.open(part, os.O_WRONLY)
                        try:
                            os.pwrite(fd, data, s)
                        finally:
                            os.close(fd)
                        with open(donef, "a") as fh:
                            fh.write(f"{s}\n")
                        state["bytes"] += len(data)
                        if progress:
                            progress(state["bytes"], total)
                    break
                except Exception as exc:  # noqa: BLE001 - retried, then surfaced
                    if attempt == 4:
                        with lock:
                            errors.append(exc)
                        return
                    time.sleep(3 * (attempt + 1))

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, n_conn))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise RuntimeError(f"Download of {url} incomplete ({errors[0]}); rerun to resume from {part}.")
    part.replace(dest)
    donef.unlink(missing_ok=True)
    return dest


def read_healpix_columns(path: Path, columns: list[str]) -> tuple[dict, dict]:
    """Read named float32 columns of a Planck HEALPix BINTABLE without astropy/healpy.

    Returns ({column: np.ndarray}, header_dict). Pure numpy memmap, so a 2 GB SMICA file
    is read column-by-column without loading every field.
    """
    import numpy as np

    with open(path, "rb") as fh:
        # skip primary HDU header
        hdr, off = _read_header(fh, 0)
        hdr, data_off = _read_header(fh, off)
    nrow, width = int(hdr["NAXIS2"]), int(hdr["NAXIS1"])
    names, forms = [], []
    for i in range(1, int(hdr["TFIELDS"]) + 1):
        names.append(hdr[f"TTYPE{i}"].strip())
        forms.append(hdr[f"TFORM{i}"].strip())
    if any(f not in ("1E", "E") for f in forms):
        raise ValueError(f"unexpected column formats {forms} in {path}")
    rec = np.memmap(path, dtype=np.dtype([(n, ">f4") for n in names]), mode="r", offset=data_off, shape=(nrow,))
    assert rec.dtype.itemsize == width
    out = {}
    for c in columns:
        if c not in names:
            raise KeyError(f"{c} not in {names}")
        out[c] = np.asarray(rec[c], dtype=np.float32)
    return out, hdr


def _read_header(fh, offset: int) -> tuple[dict, int]:
    fh.seek(offset)
    hdr: dict = {}
    while True:
        block = fh.read(2880)
        if len(block) < 2880:
            raise ValueError("truncated FITS header")
        for i in range(0, 2880, 80):
            card = block[i:i + 80].decode("ascii", "replace")
            key = card[:8].strip()
            if key == "END":
                return hdr, fh.tell()
            if card[8:10] == "= ":
                val = card[10:].split("/")[0].strip().strip("'").strip()
                hdr[key] = val

