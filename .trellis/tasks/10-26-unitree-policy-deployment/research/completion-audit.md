# Completion audit

Date: 2026-10-26. Baseline HEAD: `379be5f`. Work was interrupted by approval/session changes; the restored live integration interval began at approximately 08:39 UTC and final audit continued past 09:39 UTC (over one hour of this resumed work, within four hours). Earlier approval downtime is not represented as test execution.

## Requirement evidence

| Requirement | Authoritative evidence | Result |
| --- | --- | --- |
| Run the real deployment framework against the official simulator | `scripts/run_unitree_policy.py` resolves the real pipeline and original policy, uses `G1RealEnvCfg`/`UnitreeCppEnv`, `is_sim=False`, native `unitree_cpp`, HG DDS domain0 on `lo`. Formal run command vectors and summaries are exported in `docs/data/unitree_policy_results_2026-10-26.json`. | Proven |
| Achieve normal policy operation on the floating robot | Unitree60s/3000controls; full external Dance145s/7186controls/reference0→6573; H2H45s/2236controls with advancing complete reference; tracker reaches103 and default-pose hold; actual LocoMimic returns and Multi active-policy transitions. Screenshots show actual official MuJoCo windows. | Proven for the reported scenarios |
| Demonstrate actual physics/feedback rather than a suspended bench test | Official source commit `1eb6642e3f3fdfb7fb13a9794fd6a2dd93ea0e7d` is clean; delivered evidence fingerprints the binary/scene/model and verifies one floating joint,29motors,zero welds and disabled elastic band. Advancing LowState ticks, state/target logs, measured posture and action counts are retained. | Proven |
| Report deployable and unavailable policies in docs | Chinese report covers all25registered names and30unique configured checkpoints; all20G1names were actually attempted.17present checkpoints have real finite CPU-policy inference;13missing models are listed. Runtime failure, missing prerequisites, partial paths and H1 not tested on its own robot are distinguished. | Proven |
| Resolve required integration gaps | Initial measured state/FK caching; recurrent policy reset; active-playback resume without nominal-pose reblend; native29FK for23-joint source adaptation; fresh-world heading alignment and runner telemetry/cleanup. Owner regressions exercise actual reference-controller callbacks and independent FK oracle. | Proven |
| Reproducible operation and quantitative evidence | Report commands match the CLI;44formal trials (27criterion passes including limited-scope/snapshot runs) total854.714measured simulation seconds. Raw summaries/JSONL hashes, final delivered-source hashes, model hashes, actual command vectors and progress are exported. Diagnostic reblend bypass is excluded from formal certification. | Proven |
| Quality and preservation |85tests passed, including affected suites and complete PHC analytic/reference/controller checks. Ruff0.12.7 lint/format and compile/whitespace checks passed for8task Python files. No dependency/lock/submodule/checkpoint change. Existing unrelated dirty files retained; no commit/stage/reset performed. | Proven |

## Current failures and explicit limits

- Current-code independent Jump and CR7 finish their motions, then fall during the standalone completion/default-pose return path. Their combined-model counterparts are not substituted as proof for these standalone configs.
- Kongfu fails mid-motion (latest trial low-pelvis threshold); KungfuBot2 loses stability near/after its reference end. No unsupported claim about their exact dynamics root cause is made.
- TWIST lacks Redis and an actual external producer; full-ASAP lacks13checkpoints. Tracker requires an explicit motion. H1 has offline evidence only and requires its own scene/backend (Python SDK is absent).
- Command-gap measurement excludes initial preload/reset startup. Posture/state sampling is at outer-loop boundaries during preserved intentional inner blends. Partial pipeline construction has no generic explicit environment-shutdown API; owned simulator/Xvfb close and CLI exit releases native threads. These bounds are documented rather than hidden.
- Finite-duration simulation success does not certify physical hardware or untested motions/controller devices. Physical robot defaults and lifted `prepare()` were preserved.

## Final integrity checks

Parent checked every exported summary/JSONL fingerprint, all delivered-source fingerprints, passing result stages/exit codes, report/spec links and whitespace. Native checker independently reviews the final report/data artifact set; its outcome is recorded in `research/review.md`.

The final breadth audit also covers8additional checkpoint files outside registered defaults: WoGait and G1Smooth passed real CPU-policy inference but have no selected registered pipeline; six GMT/HugWBC files lack the current implementation/config route and remain unverified. Their exact files, implementation boundaries and fingerprints are included in the public report/data. Thus the report does not silently omit unregistered project assets or label untested models permanently incompatible.

No owned simulator, Xvfb or policy process remains after the trials. Implementation/docs/spec changes remain in the worktree; commit/archive workflow is pending a separately requested commit decision and is not a missing deployment deliverable.
