# PHC-format robot motion playback

This package provides only the runtime needed by RoboJuDo's `MotionCtrl`,
`MotionH2HCtrl`, `MotionKungfuBotCtrl`, and `MotionTwistCtrl`. It does not install
or impersonate the upstream `phc` or `poselib` Python packages.

## Source and notices

The numerical baseline is [PHC](https://github.com/ZhengyiLuo/PHC) commit
`f8e75fb94918140e85db9744abf1f3b7667428a1`, with RoboJuDo's existing
`phc.patch` heading and translation-dtype changes. The following bounded
components were adapted:

| Local file | Source at the fixed PHC commit | Treatment |
| --- | --- | --- |
| `motion_lib.py` | `phc/utils/motion_lib_base.py`, `motion_lib_real.py` | File/directory loading, deterministic clip selection, metadata and state/root interpolation. Training and SMPL branches removed. |
| `kinematics.py` | `phc/utils/torch_humanoid_batch.py` | FK, extension nodes, linear/angular smoothing and DOF differences retained. MJCF metadata parsing and quaternion finite-difference arithmetic implemented locally. |
| `_quaternion.py` | `phc/utils/torch_utils.py` | Only its spherical interpolation rule retained. Heading extraction uses existing RoboJuDo rotation math and preserves the local patch's wxyz heading result. |
| `_transforms.py` | `phc/utils/rotation_conversions.py` | Only `quaternion_to_matrix`, `_sqrt_positive_part`, `matrix_to_quaternion`, and `axis_angle_to_quaternion` retained; numerical branches unchanged. |
| `skeleton.py` | Local implementation | Stdlib MJCF body-name metadata; no poselib source copied. |
| `robot_config.py` | Local implementation | Bundled or explicit local YAML resource resolution. |

`LICENSE-PHC` retains PHC's BSD 3-Clause Clear notice (Carnegie Mellon
University and NVIDIA). `LICENSE-NVIDIA` retains the distinct NVIDIA
BSD-3-Clause notice from `torch_utils.py`. The extracted conversion helpers
retain their original Facebook attribution and PyTorch3D's BSD license in
`LICENSE-PYTORCH3D`; the complete license was verified from the
[official PyTorch3D v0.7.7 source](https://github.com/facebookresearch/pytorch3d/blob/v0.7.7/LICENSE).
No code with the restrictive nested poselib header is redistributed here.

## Robot resources

The G1 YAML and MJCF sources are the existing RoboJuDo G1 addons present at
RoboJuDo baseline `3d01ec2`, formerly under `third_party/patches/phc_addon_g1/`:

- `unitree_g1_29dof.yaml` and `g1_29dof_rev_1_0.xml`.
- `unitree_g1_23dof_KungfuBot.yaml` and
  `g1_23dof_lock_wrist_fitmotionONLY.xml`. The YAML already attributes its
  ancestry to PBHC-KungfuBot's `humanoidverse/config/robot/g1/g1_23dof_general.yaml`.

The H1 YAML and `h1.xml` are from the fixed PHC commit at
`phc/data/cfg/robot/unitree_h1.yaml` and
`phc/data/assets/robot/unitree_h1/h1.xml`.
`LICENSE-UNITREE` additionally retains Unitree Robotics' BSD-3-Clause notice
for the robot model ancestry, verified from the
[official Unitree ROS source](https://github.com/unitreerobotics/unitree_ros/blob/master/LICENSE).
The pinned PHC tree has no separate `assets/licenses/` files despite the
reference to that directory in its root notice.

Local resource changes are limited to these runtime requirements:

- Trailing whitespace is normalized in bundled YAML and the PHC license;
  configuration values and license wording are unchanged.
- YAML model paths now refer to this package's resources. The unused H1
  fitting-only `urdfFileName` is omitted because the external URDF is not a
  playback resource. G1's retained MJCF-as-URDF alias resolves internally.
- MJCF mesh declarations, geoms referencing meshes, and the unused
  `compiler.meshdir` are removed. Body/joint/actuator order, local translations,
  body quaternions, ranges, inertials and primitive geoms are retained.
  These are kinematics models; their appearance and collisions are not a
  substitute for the simulation models under `assets/robots/`.
- The three existing runtime configs are included. Unused fitting/training
  configs and meshes are outside this package.

## Preserved numerical details

Input `pose_aa`, `root_trans_offset`, and `fps` remain authoritative. Cached
DOF, SMPL or root quaternion arrays are not used instead of FK. Extra fitted
nodes are truncated to the configured augmented tree. Query rotations are
xyzw; internal matrix conversions and MJCF body quaternions use wxyz.

Linear velocities use NumPy gradient followed by a temporal Gaussian with
sigma 2 and nearest-edge padding. Angular velocities use normalized relative
quaternions, the legacy positive-scalar `acos(2*w*w-1)` angle, a zero final
difference, and the same Gaussian. DOF velocity retains the original
penultimate-difference padding. Spherical interpolation retains PHC's
near-identical-pair midpoint rule. Query times clamp to motion endpoints.
The scalar-first heading interpretation and float32 translation rotation
from the old local patch are intentional compatibility behavior.

Only `FixHeightMode.no_fix`, complete clips, and deterministic playback
(`random_sample=False`) are supported. Mesh height correction, random
training sampling/cropping, SMPL beta data, training filters and motion
retargeting remain external. The old robot loader does not load hand poses;
this migration does not add a new optional hand-data interpretation.

Imports and loads do not patch `torch.Tensor.numpy`, create multiprocessing
managers, change the global PyTorch thread count, or add module search paths.

## Reproduction hashes

SHA-256 of original source/resource files before local changes:

| File | SHA-256 |
| --- | --- |
| PHC `motion_lib_real.py` | `bde4fa970e30a23090c0e5040ed7b852ac4d7c54cf1fff96a4c48079fddac24f` |
| PHC `motion_lib_base.py` | `fd6348ecc94e851633351be155c7053ad3c10169c8c1b3f754f5681538e8b804` |
| PHC `torch_humanoid_batch.py` | `49335a9559bc9a79c64ff387cca27bf9dc6f4a0f1e45df8af547c25f4d73b158` |
| PHC `torch_utils.py` | `f242819d509c73df3d53a0c166bafa1e88b5fd2f7cae1ddcd992169a39eedd2e` |
| PHC `rotation_conversions.py` | `53f392f41906b09a210f56d6a2fd99c12b64c1121ed54a0b28d6572c1704cbd1` |
| PHC `unitree_h1.yaml` | `b8c9d16437564e0b82cd2eacb079e8a8348451b06092c53a0be7bb638c22b2c0` |
| PHC `h1.xml` | `ed2b709089c9b1b9825fac3162e23f63b6b20346bb155fe86e8b0376d0b4bc97` |
| G1 `unitree_g1_29dof.yaml` | `5aad8aef0d8eeb9e3c38bf12c3a073349e10281f11cc5ab638332a6276ad6956` |
| G1 `unitree_g1_23dof_KungfuBot.yaml` | `298718afc1d56138ae3228bd4aec449696a24bc00df99cae24db30e1ff8b4e8b` |
| G1 `g1_29dof_rev_1_0.xml` | `165fa7a5275745e45fa25e1bc78010c1055d81bb81c013b3c7bc8b9347a3b9c3` |
| G1 `g1_23dof_lock_wrist_fitmotionONLY.xml` | `e1a4260fe73077afd47518417b2d6609148b086438003d1956656ce133ae5101` |

Numerical fixtures and their isolated pinned-reference reproduction details
live under `tests/fixtures/phc/`. Normal execution and tests do not load the
temporary reference source or access the network.
