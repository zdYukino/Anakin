# Journal - zdyukino (Part 1)

> AI development session journal
> Started: 2026-10-18

---



## Session 1: MuJoCo viewer compatibility and uv pin
<!-- trellis-session: v=2 fp=edc8e60ff862f11d -->

**Date**: 2026-10-20
**Task**: MuJoCo viewer compatibility and uv pin
**Package**: third_party/mujoco_viewer
**Branch**: `release`

### Summary

Fixed camera drag/scroll and double-click selection for MuJoCo 3.16.0, preserved legacy camera dispatch and replayable viewer patch, pinned/refreshed uv dependency metadata, committed the approved uv setup and fix batch. Six native regression tests and independent review passed. Desktop GUI was not exercised; unrelated .gitattributes left untracked.

### Git Commits

| Hash | Message |
|------|---------|
| `dde491d` | build: configure uv environment for simulation |
| `ec39201` | fix: support MuJoCo 3.16 mouse callbacks and pin engine |

### Testing

- [OK] Six native MuJoCo callback regressions passed, including pre-commit rerun.
- [OK] Independent review: Ruff check/format, uv lock and metadata checks, pristine patch reproduction passed.

### Status

[OK] **Completed**


## Session 2: Publish fork improvements and update submodule sources
<!-- trellis-session: v=2 fp=10bb0cb00fc23104 -->

**Date**: 2026-10-20
**Task**: Publish fork improvements and update submodule sources
**Package**: third_party/mujoco_viewer
**Branch**: `release`

### Summary

Published current viewer and Unitree improvements to zdYukino fork anakin-improvements branches; parent release commit records exact SSH URLs and gitlinks, removes duplicate patch application and updates install docs. Original upstream remotes and validated source baselines preserved. No parent push; unrelated .archify/ and .gitattributes remain untracked.

### Main Changes

- Viewer fork commit a16a799; Unitree fork commit 6f995d6; parent commit 6a77265.

### Git Commits

| Hash | Message |
|------|---------|
| `6a77265` | build: use forked submodules with integrated fixes |

### Testing

- [OK] Independent remote refs and SSH clean clones matched source hashes; 6 clone-imported native viewer regressions passed.
- [OK] Native Unitree import, TOML build setting, uv lock offline/metadata, staged URL/gitlink assertions and whitespace checks passed.

### Status

[OK] **Completed**


## Session 3: Internalize PHC motion runtime
<!-- trellis-session: v=2 fp=eb26c59850c21ce4 -->

**Date**: 2026-10-20
**Task**: Internalize PHC motion runtime
**Package**: robojudo
**Branch**: `feat/internalize-phc-runtime`

### Summary

Internalized PHC-format motion playback for G1 23/29 DOF and H1; removed the original PHC gitlink and install links, committed the reviewed migration, and archived the task while preserving existing document translations.

### Main Changes

- Bundled minimal runtime, robot YAML/MJCF, source/license notices, and controller/config integration; packaged internal resources without PHC/poselib installation.
- Added independent pinned-reference fixtures and controller/runtime tests; retained original motion paths and other submodule pins.
- Recorded executable Trellis contracts; committed only task-specific English documentation edits while preserving four translated working copies.

### Git Commits

| Hash | Message |
|------|---------|
| `0ff914f74ec9489c53320f40f4352dc1f543071d` | feat: internalize PHC motion runtime and remove submodule |

### Testing

- [OK] 25 PHC tests and 6 MuJoCo viewer regressions passed; 864 independent reference arrays across 48 batches were bitwise equal.
- [OK] Ruff 0.12.7 lint/format and compile checks passed; locked offline uv sync and final wheel/resource verification passed.
- [OK] Final staged whitespace cleanup preserved parsed YAML values and license wording; archive context manifests validated.
- [OK] Broad import checks retain existing limitations: no X display, optional redis missing, and optional unitree_sdk2py missing; PHC controllers and UnitreeCppEnv import.

### Status

[OK] **Completed**

### Next Steps

- No migration work remains; existing document translations are left for their original work.
