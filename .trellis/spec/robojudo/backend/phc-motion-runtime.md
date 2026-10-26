# PHC-Format Motion Playback Contract

## 1. Scope / Trigger

Read this contract before modifying `robojudo/motion/`, PHC-backed controllers, `MotionCtrlCfg.PhcCfg`, robot playback resources, or the motion reference fixtures.

The internal runtime supports existing deterministic robot-motion playback for G1 23/29-DOF and H1. It replaces the former PHC/poselib submodule dependency. Training, SMPL generation, mesh height fitting, new retargeting, and random training sampling are outside this API.

## 2. Signatures

Exports from `robojudo.motion`:

```python
load_robot_config(robot_config_file: str | Path) -> dict
SkeletonTree.from_mjcf(path)  # Minimal independently implemented node metadata.
MotionLibReal(motion_lib_cfg)
library.load_motions(
    skeleton_trees, gender_betas, limb_weights,
    random_sample=False, start_idx=0, max_len=-1, target_heading=None,
)
library.get_motion_state(motion_ids, motion_times, offset=None) -> dict
library.get_root_pos_smpl(motion_ids, motion_times) -> dict
```

Use `FixHeightMode.no_fix`. `MotionCtrl` retains its existing PHC-shaped private configuration; changing this implementation must not alter policy observations or controller payloads.

## 3. Contracts

### Input and resources

- Motion files are joblib `.pkl` mappings from clip names to data. Required clip fields are `pose_aa` `(frames, nodes, 3)`, `root_trans_offset` `(frames, 3)`, and finite positive `fps`; both arrays are finite floating point. A directory loader uses PHC's filename-key convention: the name before the first period (`walk.v1.pkl` contains clip key `walk`), not `Path.stem`.
- **Do not use cached `dof`, `root_rot`, or `smpl_joints` as a replacement for reference FK.** The tracked G1 29 sample contains 41 pose nodes and 37 cached DOFs; the configured runtime yields 29 joint references after the established extra-node handling.
- Robot tree order, joint axes, local offsets/rotations, actuator membership, and configured extension nodes define the FK contract. Preserve velocity smoothing and floating-point evaluation order around near-zero angular differences.
- Bundled config basenames are `robot/unitree_g1_29dof.yaml`, `robot/unitree_g1_23dof_KungfuBot.yaml`, and `robot/unitree_h1.yaml`. `load_robot_config` also accepts an explicit YAML path and resolves assets against its YAML directory/assetRoot.
- Resolved `assetRoot`/`assetFileName` paths are absolute and independent of the caller's working directory. Bundle YAML/MJCF under `robojudo/motion/resources/` and declare them in setuptools package data along with `SOURCE.md` and `LICENSE-*`.
- The bundled MJCF models are for kinematics and headless diagnostics; external visual mesh declarations are removed while kinematic body/joint data is preserved. Existing simulation assets retain their separate role.
- Keep user motion paths under `assets/motions/{robot}/phc` or G1's `phc_29`. Those format directory names and upstream-attribution links are not external dependencies.

### Queries and output

- Query IDs index currently loaded clips. Times and IDs are one-dimensional arrays of equal length. Deterministic loading wraps `start_idx` across available clips; batch slots can hold multiple loaded clips.
- Queries clamp to the first/last frame outside the clip interval, interpolate position/DOF/velocity fields linearly, and use established quaternion slerp for rotations. Position offsets affect root/body/extended-body positions, not velocities or rotations.
- Output quaternions (`root_rot`, `rb_rot`, `rg_rot_t`) are xyzw. Configured local extension rotations are wxyz; retained heading conversion follows the pinned PHC version plus the repository's historical scalar-order patch. Do not silently replace it with a different convention.
- Query results preserve `root_pos`, `root_rot`, `root_vel`, `root_ang_vel`, `dof_pos`, `dof_vel`, `motion_aa`, `motion_bodies`, `motion_limb_weights`, `rg_pos`, `rb_rot`, `body_vel`, `body_ang_vel`, `rg_pos_t`, `rg_rot_t`, `body_vel_t`, and `body_ang_vel_t`.
- State tensors are float32 on the configured query device; CPU playback is the required tested route. Clip keys, frame counts, FPS, and lengths remain available to existing callers. `get_root_pos_smpl` returns the reset root reference without a query offset.
- Current controllers expose reference keypoints/velocities and joint references; KungfuBot samples future times, and TWIST builds its existing mimic input. H2H requires an environment with FK data. Its old optional `extra_motion_data=True` frequency/phase hook was not implemented by original MotionLibReal; do not claim new support merely because controller hooks exist.

### Runtime boundaries

Do not import `phc`, external `poselib`, SMPLSim, Isaac Gym, Open3D, Hydra, or mesh-fitting services. Do not modify `torch.Tensor.numpy`, sys.path, global logging configuration, or thread settings, and do not start multiprocessing managers on import/load. Use explicit CPU conversions for NumPy/SciPy computations.

## 4. Validation & Error Matrix

| Condition | Expected behavior |
| --- | --- |
| Missing robot YAML/model or motion path | Actionable `FileNotFoundError` identifying the path |
| Missing robot asset/required config fields; empty/malformed clip mapping | `ValueError` identifying the invalid resource/data |
| Missing pose/translation/FPS; invalid shape/type or nonfinite input | `ValueError` before reference generation |
| Too few frames for velocity computation or too few configured pose nodes | Actionable `ValueError` |
| Query before `load_motions` | `RuntimeError` explaining required initialization |
| Nonfinite query times/offsets or wrong query/offset shape | `ValueError` |
| Query ID outside loaded clip slots | `IndexError` |
| Random sampling, cropping, training filters, mesh height fixing, SMPL beta input | Explicit `NotImplementedError`; no hidden upstream fallback |

## 5. Good / Base / Bad Cases

- **Good:** Load the existing G1 29 sample with `unitree_g1_29dof.yaml`, query intermediate/future times, and receive 29 DOF references and configured augmented body state.
- **Base:** One clip, CPU, no height correction, default heading, time zero. H2H uses real FK with GUI disabled in tests.
- **Bad:** Treat 37 cached G1 DOFs as direct G1 29 targets, switch xyzw/wxyz without a tested boundary conversion, or silently reintroduce PHC installation to make an import pass.

## 6. Tests Required

```bash
uv run --locked --extra sim --extra unitree --inexact python -m unittest discover -s tests -p 'test_phc*.py'
```

- `test_phc_motionlib.py`: analytic FK/rotation/interpolation behavior, empty/malformed pose/translation/FPS input with and without heading, the directory filename-before-first-period rule, all three config/resource variants, and absence of global side effects.
- `test_phc_controllers.py`: upstream imports explicitly blocked; real headless MuJoCo FK for H2H G1/H1; base, KungfuBot future references, TWIST wrist handling, registry imports, playback/reset/switch and output-copy behavior.
- `test_phc_reference.py`: compare committed independent goldens for 48 query batches, 450 states, 864 arrays, and all three variants. These cover headings, offsets, interpolation/time boundaries, future samples, loaded multi-clip IDs, and switching. Initial migration matches every compared array bitwise; fixtures record tolerances to permit platform-specific floating-point variation, not unreviewed mathematical changes.
- Normal tests must not fetch code, require a PHC checkout, or use `/tmp` reference source. `scripts/phc_reference/generate.py` runs the fixed patched upstream in an isolated process only to regenerate fixtures. Keep its source/resource/generator hashes and exact import-only glue in fixture provenance.
- Verify a built wheel includes and resolves all internal YAML/XML/notices independently of the source tree. Recheck existing viewer regressions after environment changes; unrelated optional-module registry failures are reported separately.

## 7. Wrong vs Correct

Wrong:

```python
from phc.utils.motion_lib_real import MotionLibReal
robot_dir = THIRD_PARTY_DIR / "phc"
target_joints = clip["dof"]  # Wrong for the tracked G1 29 fitted sample.
```

Correct:

```python
from robojudo.motion import MotionLibReal, load_robot_config

robot = load_robot_config("robot/unitree_g1_29dof.yaml")
# MotionLibReal computes references from pose_aa + root translation + FPS.
```

Preserve applicable PHC, NVIDIA, PyTorch3D, and Unitree notices and record local extraction/model changes in `robojudo/motion/SOURCE.md`. Do not assume a root project license overrides nested component notices.
