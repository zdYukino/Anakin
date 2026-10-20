# Current-State Evidence for PHC Runtime Migration

Inspected on 2026-10-20. Parent baseline `3d01ec2` (`release`), initially clean. This is planning research; no runtime implementation or numerical parity result is claimed.

This document preserves the pre-migration evidence. Final implementation and validation results are in [implementation-validation.md](./implementation-validation.md).

Concurrent-work note: by the final planning check, `docs/controller.md`, `docs/environment.md`, `docs/policy.md`, and `docs/unitree_setup.md` had working-tree modifications from other work. This planning task did not edit those files. Preserve and incorporate their latest content during implementation; the anchors below describe the inspected baseline.

## 1. Repository consumers and environment

CodeGraph was consulted before source searches, as required by AGENTS.md. Follow-up repository searches covered `robojudo`, docs, installation config, uv metadata, local patches, and task/spec metadata.

| Evidence | Current behavior | Migration consequence |
| --- | --- | --- |
| `.gitmodules:5`; `git ls-tree HEAD third_party/phc` | Gitlink `f8e75fb94918140e85db9744abf1f3b7667428a1`, currently uninitialized | Fixed source baseline; remove link after validation |
| `robojudo/controller/motion_ctrl.py:11` | Imports `FixHeightMode`, `MotionLibReal`, `SkeletonTree` | Replace external imports with internal bounded runtime |
| `robojudo/controller/motion_ctrl.py:28` | Creates tree from MJCF; configures `no_fix`, `min_length=-1`, `max_length=-1`, `im_eval=False`, `multi_thread=False`, and fixed heading | Training, mesh fitting, and worker services are unnecessary on this path |
| `robojudo/controller/motion_ctrl.py:100` | Deterministic clip selection, current keys/length, reset | Preserve motion selection and metadata |
| `robojudo/controller/motion_ctrl.py:137` | Batched motion/time query with positional offset and cache | Preserve all caller-used result fields; do not fix unrelated cache behavior |
| `robojudo/controller/motion_ctrl.py:172` | Exposes selected body positions/velocities and DOF references | Numerical compatibility affects policy input |
| `robojudo/controller/motion_ctrl.py:199` | Time advances with play ratio; fade/reset/previous/next events | Preserve controller behavior |
| `robojudo/controller/motion_h2h_ctrl.py:17` | Inherits base; requires a real FK-capable environment and compares current/reference keypoints | Headless tests still need an FK environment |
| `robojudo/controller/motion_kungfubot_ctrl.py:43` | Queries 20 future sample times from step 1 to 95 at 0.02 s | Batched interpolation/endpoint handling matter |
| `robojudo/controller/motion_twist_ctrl.py:35` | Converts current reference into TWIST mimic observation, including G1 wrist padding | Preserve existing DOF shape/convention |
| `robojudo/controller/ctrl_cfgs.py:63` | Keeps public nested `PhcCfg` fields; reads submodule YAML and rewrites asset paths; silently leaves empty config if file absent | Redirect resource resolution and make missing resource errors explicit |
| `robojudo/config/g1/ctrl/g1_motion_ctrl_cfg.py:5` | G1 29 YAML and `phc_29` path for base/H2H; G1 23 KungfuBot YAML and `phc` path for KungfuBot/TWIST | Both G1 variants remain supported |
| `robojudo/config/h1/ctrl/h1_motion_ctrl_cfg.py:4` | Uses `robot/unitree_h1.yaml` with H1 PHC motion | H1 resource closure is required |
| `robojudo/tools/kinematics.py:173` | Diagnostic reads `cfg.phc.robot_config` model path | Audit model reuse beyond MotionLib alone |
| `submodule_cfg.yaml:22` | Installs PHC, `phc.patch`, G1 addons, and extra `third_party/phc/poselib` package | Retire external installation after resources migrate |
| `.trellis/config.yaml:165` | Registers PHC as a submodule package | Remove obsolete live registration; historical records can remain |
| `pyproject.toml`, `requirements.txt`, `uv.lock` | No PHC/poselib dependency; current optional extras are sim, unitree, dev | Do not invent a lock entry to remove; declare only necessary actual changes |
| `pyproject.toml` setuptools section | Packages explicitly lists only `robojudo` | Check new internal subpackage/resource distribution |
| `README.md:123`, `README.md:130`, `docs/policy.md:84`, `:92`, `:177`, `:202` | Say PHC submodule is needed; fitting link targets submodule | Update behavior docs and replace stale links |
| `docs/controller.md:136` | Uses an outdated `assets/resources/motions` path | Correct migration docs to actual per-config motion paths |

Current `.venv` has torch/NumPy/SciPy/joblib/PyYAML but no `phc`, `poselib`, `lxml`, Hydra, or OmegaConf. The absence is verified using module-spec inspection, not a successful current controller run.

`tests/test_full_imports.py` exercises every registry and can fail for unrelated uninstalled optional modules. The existing regression test uses unittest; no root mypy/type-check command is configured. The shared cross-layer and reuse guides contain real conventions; PHC backend/frontend spec indexes are unfilled templates.

## 2. Checked-in motion samples

Loaded with the existing `.venv/bin/python` and joblib, without PHC/poselib. All three files are real tracked binary data, not LFS pointer text, and contain one clip each.

| File under `assets/motions/` | Bytes | Frames / FPS | `pose_aa` | `dof` | `root_trans_offset` |
| --- | ---: | --- | --- | --- | --- |
| `g1/phc/kungfubot/Horse-stance_pose.pkl` | 165363 | 210 / 30 | `(210, 27, 3)` float32 | `(210, 23)` float32 | `(210, 3)` float32 |
| `g1/phc_29/singles/0-KIT_6_WalkInCounterClockwiseCircle05_1_poses.pkl` | 227924 | 231 / 30 | `(231, 41, 3)` float32 | `(231, 37)` float32 | `(231, 3)` float64 |
| `h1/phc/singles/0-KIT_572_punch_right01_poses.pkl` | 114356 | 158 / 30 | `(158, 25, 3)` float32 | `(158, 19)` float32 | `(158, 3)` float64 |

Each also has `root_rot` and `smpl_joints`; the G1 23 file additionally has `contact_mask`. None of these three samples has `hand_pose`.

Important: G1 "29-DOF" motion data has 37 cached DOF values and 41 fitted pose nodes. The current runtime derives references through FK and truncates extra nodes according to the configured tree. Loading cached `dof` arrays directly would change semantics.

Existing G1 addon XML files contain mesh references but the addons intentionally omit 29-DOF meshes. Do not pull large meshes just to run FK with height correction disabled. Existing `assets/robots/g1` and `assets/robots/h1` models can only be reused after semantic comparison.

## 3. Fixed upstream dependency path

Reference source URL prefix:

`https://raw.githubusercontent.com/ZhengyiLuo/PHC/f8e75fb94918140e85db9744abf1f3b7667428a1/`

Fetched individual files into `/tmp` for inspection; PHC was not initialized in this repository. Future implementation must retrieve/reproduce reference material independently; `/tmp` is not a delivery dependency.

| Fixed upstream file | Findings |
| --- | --- |
| `phc/utils/motion_lib_real.py` | Subclasses MotionLibBase; constructs Humanoid_Batch; loads root translation/axis-angle/FPS; deterministic selection and batched state interpolation |
| `phc/utils/motion_lib_base.py` | joblib file/directory loading, metadata, root query, time clipping/blending; also imports unused training/skeleton branches |
| `phc/utils/torch_humanoid_batch.py` | MJCF tree parsing, configured extension nodes, FK, smoothed linear/angular velocities; imports Hydra/mesh packages beyond current runtime need |
| `phc/utils/torch_utils.py`, `pytorch3d_transforms.py`, `flags.py` | Rotation interpolation/heading helpers and global flags; isolate only required helpers with verified notices |
| `poselib/poselib/skeleton/skeleton3d.py` | Broad skeleton/FBX/serialization stack; avoid wholesale transplantation |
| `poselib/poselib/core/rotation3d.py` | Quaternion helpers used by angular velocity; prefer existing/permitted equivalents rather than unclear-license copying |

The fixed upstream `torch_humanoid_batch.py` also imports `phc.utils.rotation_conversions`; retrieve that helper's required subset/provenance during implementation. H1's correct YAML basename is `unitree_h1.yaml`; a guessed `h1.yaml` URL was absent. Guessed upstream `setup.py` and `poselib/LICENSE` URLs were also absent; no conclusion about other license locations follows from those 404s.

Current runtime needs only the skeleton tree's names/count from the `SkeletonTree` argument on the MotionLibReal path, not all of SkeletonState/SkeletonMotion. The already-present FK parser offers a way to avoid external poselib entirely.

### Behavior to retain

- `torch_humanoid_batch.py:156` truncates input poses to its configured parent count before FK.
- `torch_humanoid_batch.py:175` converts internal rotation matrices/quaternions to xyzw output and calculates extended body state.
- `torch_humanoid_batch.py:253` uses NumPy gradient and Gaussian smoothing for linear velocity; `:263` computes and smooths angular velocity.
- `motion_lib_real.py:371` loads `root_trans_offset` and `pose_aa`; `:405` aligns target heading before FK.
- `motion_lib_base.py:522` supplies reset root positions; `:549` clips phase/blend to endpoints, including negative time.
- `third_party/patches/phc.patch:27` changes the SciPy heading quaternion interpretation to `scalar_first=True`; adjacent changes normalize translation dtype to float32.

### Side effects not to transplant

- Both motion-lib files patch global `torch.Tensor.numpy` during import; related helpers can also affect sys.path/logging.
- MotionLibReal creates `mp.Manager()` and changes torch thread count even when `multi_thread=False`.
- The current PHC patch removes SMPL parser, Isaac Gym, Open3D, and STL imports/mesh loads and redirects rotation helpers to poselib. Internalization should eliminate those now-unneeded package boundaries rather than restoring them.

The current upstream source has no hand-pose loader field; controller `.get('hand_pose')` hooks alone do not establish an implemented hand input contract.

## 4. Provenance notes

PHC's fixed root LICENSE is BSD 3-Clause Clear and specifically points to asset licenses. `torch_utils.py` retains an NVIDIA BSD-style header; `pytorch3d_transforms.py` has a Facebook BSD-style attribution. Inspected poselib files carry separate restrictive NVIDIA headers. Avoid copying them on the assumption that the root notice overrides nested notices. This task plans verified provenance per included component and a minimal internal replacement for unnecessary poselib functionality.

Source SHA-256 values useful for reproducing the fixed reference:

| Path | SHA-256 |
| --- | --- |
| `phc/utils/motion_lib_real.py` | `bde4fa970e30a23090c0e5040ed7b852ac4d7c54cf1fff96a4c48079fddac24f` |
| `phc/utils/motion_lib_base.py` | `fd6348ecc94e851633351be155c7053ad3c10169c8c1b3f754f5681538e8b804` |
| `phc/utils/torch_humanoid_batch.py` | `49335a9559bc9a79c64ff387cca27bf9dc6f4a0f1e45df8af547c25f4d73b158` |
| `phc/utils/torch_utils.py` | `f242819d509c73df3d53a0c166bafa1e88b5fd2f7cae1ddcd992169a39eedd2e` |
| `phc/utils/pytorch3d_transforms.py` | `74ace5e1da74b1bb023198b33747ac0da79065e3413b6766dd5d498989464a5c` |
| `LICENSE` | `aeb976a86efd6b8afb707fceaf36e1d77d2faad027f7fe7a00fc8c062074f0f9` |

## 5. Remaining implementation investigations

- Reproduce a working pinned+patched numerical reference in an isolated process; no numerical baseline was generated during planning.
- Retrieve H1 config/model and exact required rotation helper subset; validate all resource paths.
- Select and record tolerances, compact reference outputs, and the minimal internal runtime file decomposition.
- Verify setuptools subpackage/resource inclusion for the new code and decide whether any dependency change is necessary. Current evidence favors existing dependencies plus stdlib XML.
- Keep any pre-existing controller cache/timing defects separate from this compatibility migration.

These investigations do not change the agreed outcome: existing PHC-backed G1/H1 motion execution must work without the original submodule.
