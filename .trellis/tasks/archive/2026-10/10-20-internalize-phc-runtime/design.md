# Internal PHC Runtime Design

## Architecture and boundaries

Introduce an internal, explicitly scoped runtime under `robojudo/motion/`, with a PHC-compatible loader, robot kinematics, necessary rotation helpers, and packaged YAML/MJCF resources. This is an internal implementation, not a top-level `phc` or `poselib` compatibility package.

The controllers retain their names, configuration fields (including `phc.robot_config_file`), external motion paths, output contracts, and playback behavior. Redirect `MotionCtrlCfg.PhcCfg` to one internal resource resolver and redirect `MotionCtrl` imports to the internal runtime. Keep the familiar YAML basenames so existing configuration overrides continue to work.

```text
Existing PHC-format .pkl + internal robot YAML/MJCF
  -> bounded loader + forward kinematics + velocity computation
  -> loaded tensors and motion metadata
  -> time/index interpolation with heading/position alignment
  -> existing MotionCtrl and its H2H/KungfuBot/TWIST derivatives
  -> unchanged policy observations and action generation
```

Reuse existing project rotation helpers where conventions match. `robojudo/utils/motion_utils.py` is a ProtoMotions loader with another format; it is evidence for an internal deployment-runtime pattern, not a substitute for PHC semantics.

## Runtime contract

- Preserve the operations controllers actually call: deterministic clip loading by index, current clip keys and length, root position query for reset, and batched state queries by motion index/time/offset.
- Preserve the queried fields used by each controller: `root_pos`, `root_rot`, `root_vel`, `root_ang_vel`, `dof_pos`, `dof_vel`, `rg_pos_t`, `rg_rot_t`, `body_vel_t`, plus other currently consumed metadata established by the final caller audit.
- Input source of truth is the current loader's `root_trans_offset`, `pose_aa`, and `fps` path. Do not silently replace FK-derived state with cached `dof`, `root_rot`, or `smpl_joints` fields: the checked-in G1 29 sample has extra fitted entries.
- Preserve truncation of extra fitted pose nodes to the configured kinematic tree, augmented body transforms, float32 query outputs, existing quaternion component order at every boundary, velocity smoothing, and frame blending/clipping.
- Preserve position-offset behavior and the existing reset's XY recentering. Test heading behavior from the pinned version plus the local scalar-order/dtype patch; do not silently correct it while refactoring.
- The internal implementation may simplify PHC's broad API. Keep that simplification behind `MotionCtrl`; policy/controller consumers must not need a new input schema.
- Existing hand passthrough remains where supported; upstream raw source and the checked-in samples do not establish an implemented hand-loading feature, so do not promise new hands support.

## Kinematics and resources

1. Preserve the effective G1 addon YAML/MJCF for the current G1 23/29-DOF configurations.
2. Retrieve `robot/unitree_h1.yaml` and its required kinematic XML from the pinned source during implementation. The active H1 controller must remain supported.
3. Resolve paths internally, validate required files, and report clear config errors rather than returning an empty robot config when resources are absent.
4. Avoid full poselib transplantation: current `MotionLibReal` only uses the skeleton-tree names/count on this execution path; `Humanoid_Batch` already parses MJCF and computes FK. Use minimal internal metadata and existing/permitted math functions instead of importing full FBX/SMPL/serialization machinery.
5. Kinematic parsing does not need graphics meshes under the current `FixHeightMode.no_fix` path. Keep body/joint/actuator/offset data exact. Retain an appropriate full MJCF when another current consumer needs to load it through MuJoCo; audit `robojudo/tools/kinematics.py:173` before choosing resource reuse. Do not substitute the simulation model solely because its filename matches.

## Dependencies and side effects

Use the existing NumPy, PyTorch, SciPy, joblib, PyYAML, and config helpers where needed. Prefer stdlib XML parsing if it preserves the required MJCF contract, avoiding `lxml`, Hydra/OmegaConf, Open3D, numpy-stl, Isaac Gym, SMPLSim, and external poselib at runtime.

Remove runtime-unnecessary PHC behavior: `sys.path` mutation, process-wide `torch.Tensor.numpy` patching, unconditional `logging.basicConfig`, thread-count mutation, and `mp.Manager()` creation when loading deterministically without worker processes. Explicit tensor-to-CPU conversion must preserve output math. Baseline runs with those side effects happen only in an isolated reference-generation process.

Do not add a fake uv dependency removal: the current root project has no PHC entry. Adjust requirements/uv metadata only if the final internal runtime needs an actual dependency change. If dynamic dependencies change, refresh root metadata when regenerating the lock. Keep the `sim` and `unitree` extras and source pins intact.

The existing setuptools configuration lists only `robojudo`; verify that new internal modules/resources are included in the supported installation route and make a targeted discovery/package-data correction if needed. A general packaging redesign is outside scope.

## Provenance and licensing boundary

Record the fixed PHC commit, applied patch/addon provenance, extracted files/functions, local modifications, and fixture-generation process in the internal runtime's source notice. Keep PHC's BSD-3-Clause-Clear notice and any separate required notices for copied utilities/assets.

Inspected poselib files have restrictive NVIDIA headers, and a separate `poselib/LICENSE` was not found at the guessed location. Do not infer permission from the root license or copy them wholesale. Prefer the minimal internal metadata/existing utilities described above. Resolve provenance for every copied nested component before adding it; replace an unnecessary dependency rather than expanding the import tree.

## Validation and migration

- Build an isolated pinned+patched reference harness in temporary storage and produce compact golden results for the checked-in G1 23/29 and H1 samples. Fetch only reference source/resources; do not initialize or depend on the old submodule for delivery.
- Test reference positions/angles/velocities with recorded tolerances, including interpolation, clipping, headings, offsets, batches, and a two-clip fixture. Use analytic rotation/FK cases as an independent check of conventions, not a replacement for meaningful baseline comparison.
- Test controllers with GUI disabled. H2H needs an environment exposing real FK/kinematic data; use a headless environment/fixture rather than pretending `env=None` is supported.
- Only after runtime compatibility passes, remove the PHC gitlink, `.gitmodules` stanza, installer entry and active patch/addon wiring, stale Trellis package registration, and obsolete documentation. Retain/migrate useful attribution and fitting-only resource documentation; no stale link should remain to a deleted asset.
- Keep normal tests independent of network or `/tmp` reference source; record any mechanical baseline import-compatibility glue and avoid changing reference math.
- Search executable/config/install paths for external PHC requirements. Do not require deleting motion directories named `phc` or source-attribution links.

## Risks, deferred details, and rollback

- Quaternion conventions, smoothed angular velocities, and extra fitted nodes can cause plausible-looking numerical drift; the reference gate is mandatory.
- H1 resource closure, the four required rotation-conversion helpers, and fixture/tolerance selection are resolved. Runtime resources and original hashes are documented in `robojudo/motion/SOURCE.md`; independent reference provenance is in `tests/fixtures/phc/provenance.json`.
- Numerical baseline generation and controller execution passed. See `research/implementation-validation.md` for the full result and the unchanged optional-module limitations. The original unsupported H2H frequency/phase hook remains outside this migration.
- Do not delete or reset a user's initialized/modified PHC checkout during cleanup. Remove tracked links after preserving local work, if any.
- Keep the removal stage separate from runtime extraction so it can be reverted independently. The fixed source commit and local patch history remain sufficient to reproduce the original baseline.
