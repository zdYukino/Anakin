# Internalize PHC Motion Runtime

## Goal

Run existing PHC-backed motion controllers from this repository without cloning or installing PHC or external poselib. Once the internal runtime is validated, remove the original submodule and its active install/environment links.

The user authorized task creation and this migration scope, then approved the final planning summary on 2026-10-20 with “开始实现”. Implementation and acceptance evidence are recorded in `research/implementation-validation.md`.

## Background

The facts below describe the pre-migration baseline used for compatibility and dependency-removal verification.

- Parent baseline: `3d01ec2` on `release`; the worktree was clean before task creation.
- PHC is an uninitialized gitlink pinned to `f8e75fb94918140e85db9744abf1f3b7667428a1` (`.gitmodules:5`, `git ls-tree HEAD third_party/phc`).
- `robojudo/controller/motion_ctrl.py:11` imports PHC MotionLib and poselib; `MotionH2HCtrl`, `MotionKungfuBotCtrl`, and `MotionTwistCtrl` inherit this runtime.
- `robojudo/controller/ctrl_cfgs.py:73` resolves robot configs and model resources within `third_party/phc`. Both G1 and H1 have active configurations.
- `submodule_cfg.yaml:22` installs PHC, poselib, the local PHC patch, and G1 addons. `.trellis/config.yaml:165` also registers the external PHC package.
- `pyproject.toml` and `uv.lock` contain no PHC/poselib source or dependency. The local patch's PHC package metadata adds `lxml` and `hydra-core`, which are absent from the current uv environment.
- Three real PHC-format motion samples are tracked in this repository: G1 23-DOF, G1 29-DOF, and H1. Detailed evidence, shapes, source references, and migration hazards are in `research/current-state.md`.

## Requirements

- **R1 — Self-contained runtime:** Existing PHC-backed controllers must load compatible existing motion files without a PHC clone, a separately installed `phc`/`poselib`, or network access during execution.
- **R2 — Behavioral compatibility:** Preserve supported motion loading/query behavior, controller data keys and shapes, body/joint ordering, quaternion conventions, velocity calculation, interpolation, offsets, playback/reset/switch behavior, and supported optional hand data. Preserve existing G1 23/29-DOF and H1 configurations and motion file paths. No motion conversion is required from users.
- **R3 — Complete resources and provenance:** Bundle the minimum runtime source and robot YAML/MJCF resources needed by those configurations, integrating required existing patches/addons. Keep source versions and applicable license notices. Do not assume PHC's root license covers every nested file.
- **R4 — Remove original dependency after validation:** Remove the PHC gitlink/registration, installer entry, active PHC patch/addon installation, runtime paths, stale Trellis package registration, and any actual uv/package links to the original checkout. The remaining submodules and their pinned versions must stay intact. Historical/source attribution references to PHC are allowed and required where appropriate.
- **R5 — Reproducible environment and useful diagnostics:** Use the current Python 3.11 CPU uv environment, declaring only required dependencies. Missing or incompatible motion/config input must produce actionable errors. Runtime imports must not mutate global PyTorch methods or spawn multiprocessing services.
- **R6 — Evidence and documentation:** Add numerical compatibility and controller-level smoke coverage, and update installation/policy/controller documentation to explain the internal runtime and remaining motion/model prerequisites.

## Acceptance Criteria

- [x] **AC1 (R1, R5):** Import all four PHC-backed controller classes and load their representative motions with PHC/poselib imports explicitly blocked and `third_party/phc` absent; no network or graphics window is needed.
- [x] **AC2 (R2, R6):** Compare reference output against the pinned, locally patched baseline on all three checked-in samples. Cover original frame times, between-frame times, start/end/out-of-range times, position offsets, nontrivial heading alignment, batched future queries, and clip switching. Record tolerances and reference-generation provenance. Optional hands are checked only where the existing loader actually supports them.
- [x] **AC3 (R2, R3):** G1 23/29-DOF and H1 configs resolve internal resources; controller data keys/shapes are preserved. Multi-clip loading is covered with a derived fixture, since each checked-in sample currently contains one clip.
- [x] **AC4 (R4):** `.gitmodules`, gitlinks, `submodule_cfg.yaml`, live runtime config, and Trellis package registration no longer require PHC. uv metadata/lock contain no original-PHC checkout dependency; retained source links and `phc` motion-format folder names remain valid.
- [x] **AC5 (R3, R5):** Fresh uv resolution and locked sync work with the existing sim/unitree extras; copied source/resources include their applicable notices. No temporary baseline checkout participates in runtime or normal tests.
- [x] **AC6 (R6):** Targeted numerical/controller tests and relevant existing regression checks pass. Docs describe the migration, supported configs, and separately supplied motions/policy models. Any unrelated optional-module test limitations are reported accurately.

## Out of Scope

- PHC training, evaluation, recovery-policy reproduction, random/adaptive training sampling, SMPL body generation, mesh-based height fitting, raw-human/video conversion, and new retargeting workflows.
- Adding robot variants, changing policy observations/actions, implementing missing hand features, fixing unrelated controller timing/cache bugs, or changing unrelated submodules.
- Downloading full motion datasets, new policy checkpoints, or extra meshes when kinematic queries do not require them.
- A general wheel-packaging overhaul, GUI redesign, real-robot execution, and new CUDA support. CPU compatibility is required; available accelerator paths must not be intentionally broken, but new GPU guarantees are outside this task.
