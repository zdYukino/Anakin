# Independent PHC numerical reference

`generate.py` computes the checked-in `tests/fixtures/phc/*.npz` fixtures with
upstream PHC at commit `f8e75fb94918140e85db9744abf1f3b7667428a1`, after applying
this project's complete historical `phc.patch`. It does not import
`robojudo.motion` or any other project package. Normal tests read the fixtures;
they do not run this script, access the network, or need the reference sources.

The reference resources are the original G1 addons and the pinned H1 YAML/MJCF.
They are not substituted with the internal runtime's resources when generating
expected results. All source, effective patched source, resource, input motion,
and fixture SHA-256 values are in `tests/fixtures/phc/provenance.json`.
Generation validates supplied source/resource hashes against that manifest.

## Coverage and tolerances

The three checked-in motions cover G1 23 DOF (24 base / 27 extended bodies),
G1 29 DOF (30 / 33 bodies), and H1 19 DOF (20 / 23 bodies). The G1 29 and H1
motion inputs contain additional fitted nodes; the reference truncates them
using its original FK implementation. Cached `dof` arrays are not substituted
for axis-angle FK.

Each sample has 16 query batches, totaling 150 queried states:

- Identity heading, no heading alignment, and yaw `0.7` radians each cover
  negative time, time zero, exact/intermediate frames, final/intermediate final
  frames, time beyond the end, per-row XYZ offsets, and 20 future references.
- A derived two-clip input retains the original clip and adds frames `[11:72]`
  translated by `[0.7, -0.2, 0.15]`. A batched query mixes clip IDs and endpoints.
- Loading clip indices `1`, `0`, and `3` checks switching, reloading, and wrapping.

Every queried tensor returned by upstream `get_motion_state` is saved, along
with `get_root_pos_smpl`, the query inputs, selected keys, lengths, frame counts,
and ordered body names. The 17 state fields include complete base/extended
positions, quaternions and velocities, DOF positions/velocities, and metadata.
Singleton `curr_motion_keys` scalars produced by NumPy/PyTorch indexing are
normalized to one-element lists for serialization; their values are retained.

The recorded tolerances are `atol=rtol=3e-5` for pose/metadata and
`atol=rtol=2e-4` for velocities. Tests compare quaternion components and signs,
not only rotation equivalence. The values allow float32 rounding and
differentiation; they must not be enlarged to accommodate a changed convention
or calculation order without investigating the cause.

## Reproduce

Use the project's Python environment. NumPy, SciPy, torch, joblib, PyYAML,
python-box, easydict, and tqdm are already project dependencies. `patch` is the
only additional command used to prepare the reference tree. No PHC clone,
installation, training environment, or graphics window is needed.

Retrieve the source paths listed under `original_source_sha256` in the
manifest from its fixed `source_url_prefix`, preserving their directory
structure under a temporary source directory. Also retrieve
`phc/data/cfg/robot/unitree_h1.yaml` and
`phc/data/assets/robot/unitree_h1/h1.xml` from that same commit. The manifest
includes their exact hashes. Keep the original files and headers intact.

Recover the historical local patch and G1 addon resources from project commit
`3d01ec21f7e3ea590dc97159458eec951431d4d3`. For example, with fresh temporary
directories and a complete source tree at `/tmp/phc-upstream`:

```bash
mkdir -p /tmp/phc-project-baseline
git archive 3d01ec21f7e3ea590dc97159458eec951431d4d3 \
  third_party/patches/phc.patch \
  third_party/patches/phc_addon_g1/phc/data/cfg/robot/unitree_g1_23dof_KungfuBot.yaml \
  third_party/patches/phc_addon_g1/phc/data/cfg/robot/unitree_g1_29dof.yaml \
  third_party/patches/phc_addon_g1/phc/data/assets/robot/unitree_g1/g1_23dof_lock_wrist_fitmotionONLY.xml \
  third_party/patches/phc_addon_g1/phc/data/assets/robot/unitree_g1/g1_29dof_rev_1_0.xml \
  | tar -x -C /tmp/phc-project-baseline
.venv/bin/python scripts/phc_reference/generate.py \
  --source-root /tmp/phc-upstream \
  --patch /tmp/phc-project-baseline/third_party/patches/phc.patch \
  --addon-root /tmp/phc-project-baseline/third_party/patches/phc_addon_g1 \
  --reference-root /tmp/anakin-phc-reference-new
.venv/bin/python -m unittest discover -s tests -p test_phc_reference.py
```

`--reference-root` must be a new directory. An optional `--motion-lib-real`
argument supports a separately downloaded `motion_lib_real.py`; otherwise it
is read from its normal path in `--source-root`. `--output-root` can target a
separate directory for reviewing regeneration before replacing the fixtures.
The hidden worker mode is an internal subprocess boundary, not an alternative
to preparing and verifying the pinned source tree.

## Exact compatibility glue

The pinned source's numerical implementations run unchanged after the local
patch. Import and setup glue in `generate.py` is intentionally confined to its
worker subprocess:

1. Empty package initializers prevent unrelated upstream startup code. An
   import finder rejects every `robojudo` import during reference calculation.
2. Unused `SkeletonMotion` and `SkeletonState` imports are raising sentinels.
   The `SkeletonTree` argument only supplies names/count on this execution path;
   its metadata is the MJCF root-body preorder, using stdlib XML parsing.
3. The unused Hydra CLI decorator returns its function unchanged, and
   `DictConfig` is an unused annotation alias. No Hydra/OmegaConf parser runs.
4. The unavailable lxml setup import uses stdlib ElementTree with a legacy
   `getchildren()` method. This is used only for initial joint/motor enumeration;
   upstream's own FK tree parser and numerical arrays remain unchanged.
5. With `multi_thread=False`, upstream constructs a Manager/Queue but never
   uses that queue. A sentinel replaces this unused service and raises if
   queue operations are attempted. No numerical loader or query is replaced.
6. The upstream `torch.Tensor.numpy` monkeypatches, logging setup, and torch
   thread mutation execute inside the worker and end with that process.

The separate poselib `rotation3d.py` is used only as externally supplied
reference source. Its restrictive NVIDIA header is not assumed to be covered
by PHC's root license. Neither that source nor full skeleton/FBX code is
distributed here. Runtime rotation math is implemented independently and
checked against these numerical results.
