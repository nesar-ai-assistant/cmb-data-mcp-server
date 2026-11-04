---
name: hpc-dispatch-handoff
description: Run this server's heavy kernels (Planck map download + downgrade, pseudo-C_ell from maps, getdist chain analysis with on-node chain download, camb LCDM spectra) on ALCF Polaris or NERSC Perlmutter through the hep-genesis IRI engine - client-side pack export (hosted) or server-side set_dispatch (own machine)
---

# HPC dispatch handoff

This server holds NO facility credentials, project, workdir or environment
settings. All facility access goes through IRI (job submission) and Globus /
the IRI filesystem API (staging) via the hep-genesis engine; nothing here
writes batch scripts or opens SSH sessions. Tool names `set_dispatch`,
`get_dispatch`, `auth_status`, `export_dispatch_pack` are a cross-server
convention matched by the hep-genesis harness.

## Client-side (hosted servers - recommended)
1. `export_dispatch_pack` -> the client saves `files` locally (do NOT echo
   their contents) and reads `kernels`: each has `function`, `args_shape`,
   `pip_deps`, `duration_hint_s`, `returns`.
2. On the client's facility server call
   `run_pack_kernel(pack=<saved>/tools, function=<kernel function>,
   args={...}, pip_deps=<kernel pip_deps>, duration>=duration_hint_s,
   artifact_dir=<run dir>)`.
3. Long or parallel jobs: `wait=False`, then `find_dispatched_jobs` /
   `collect_dispatched_job(record=...)`.

## Server-side (server runs on the user's own machine)
1. `auth_status` -> IRI + transfer tokens must be "available".
2. `set_dispatch("perlmutter" | "polaris")`. Heavy tools now run each call
   as one facility job; light tools stay local. `set_dispatch("local")` to undo.
3. Never blind-retry a failed dispatch: surface the error. A walltime
   rejection may be resubmitted ONCE with a shorter duration.

## This server's kernels
| key | function | pip_deps | hint | heavy tool |
|---|---|---|---|---|
| `analyze_chain` | `chains.kernels.analyze_chain_kernel` | numpy, scipy, getdist | 900 s | `analyze_chain` |
| `camb_lcdm` | `spectra.kernels.camb_lcdm_kernel` | numpy, camb | 300 s | `compute_lcdm_theory_spectrum` |
| `prepare_cmb_map` | `maps.kernels.prepare_map_kernel` | numpy, healpy | 1800 s | `fetch_cmb_map` |
| `measure_cmb_power_spectrum` | `maps.kernels.measure_power_spectrum_kernel` | numpy, healpy | 900 s | `measure_cmb_power_spectrum` |

Map kernels: on a node pass `map_spec={"component": "smica_nosz", "split": "hm1", "nside": 1024,
"mask": "common_int"}` (and `map_spec2` with `"split": "hm2"` for the cross) instead of
local paths. The node downloads the 201 MB IRSA files with resumable range requests and
downgrades them in the job directory. Sanity check: first peak ell ~ 225, D_ell ~ 5706 muK^2.

Example (client-side): `run_pack_kernel(pack=<saved>/tools,
function="chains.kernels.analyze_chain_kernel", args={"chain": "planck_pr3",
"params": ["H0","omegam","sigma8","S8","ns"]}, pip_deps=["numpy","scipy","getdist"],
duration=1200)`. The node downloads the 65 MB Planck zip itself (args carry no local
paths) and writes `chain_stats.json`. Sanity check: H0 67.36 +- 0.54.
