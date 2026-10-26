# Research: Additional local policy assets outside registered defaults

- Query: Cover eight local G1/H1 model assets outside the30 unique checkpoints referenced by current registered pipeline defaults, without implying unregistered assets cannot work.
- Scope: internal; code/file/config/registry inspection and finite CPU offline inference for existing WoGait/Smooth policies. No DDS, external simulator, GUI, input listener or native environment was started.
- Date: 2026-10-26

## Findings

All eight files exist. **None is selected by any current registered `-c` configuration default.** This is a routing/coverage statement, not proof of model incompatibility. The JSON companion records exact paths, sizes, current registry/dependency observations and the two successful inference results.

| Local asset | Current implementation/config routing | Executed evidence / classification |
| --- | --- | --- |
| `assets/models/g1/unitree/policy_wo_gait.pt` | Existing `UnitreeWoGaitPolicy` runtime registry entry and `G1UnitreeWoGaitPolicyCfg`; `g1_cfg.py:54` shows a commented alternative, while active policy remains Unitree LSTM | **Offline inference passed**, observation480 → actions29, all finite, maximum absolute processed action0.1033492237. Not run in official simulator; requires explicitly selecting this policy in a pipeline config |
| `assets/models/g1/smooth/for_test-2000-jit.pt` | Existing `SmoothPolicy` registry entry and `G1SmoothPolicyCfg`; imported by G1 config modules but absent from every active default | **Offline inference passed**, observation853 → actions21, all finite, maximum absolute processed action0.2129460424. Not run in official simulator; requires config selection and subset/default-pose integration |
| `assets/models/g1/gmt/pretrained.pt` | `GMTPolicy` registration is commented out; target `.gmt_policy` module absent; no matching active config factory found | Local asset present; **no enabled framework implementation/config route; not inferred or closed-loop tested** |
| `assets/models/g1/hugwbc/Jun26_20-12-44_3000_g1int.pt` | `HugWbcPolicy` registration is commented out; target `.hugwbc_policy` module absent; no matching config found | Same: asset present, integration unavailable in current framework, model validity untested |
| `assets/models/g1/hugwbc/g1_waist_interrupt_full-test_collision_pos_root-py@_model_55000.pt` | Same HugWBC routing gap | Same |
| `assets/models/g1/hugwbc/g1int.pt` | Same HugWBC routing gap | Same |
| `assets/models/h1/hugwbc/h1int old.pt` | Same HugWBC routing gap, plus separate H1 target requirements | Same; not evidence that checkpoint cannot deploy with future H1 integration |
| `assets/models/h1/hugwbc/h1int.pt` | Same HugWBC routing gap, plus separate H1 target requirements | Same |

The two existing policy probes used their real `PolicyCfg` factories and real policy classes, loaded their included JIT models, built observations from default DOF positions/identity xyzw quaternion/zero velocity and neutral Unitree axes, and executed actual `get_action()`. No model or runtime code was modified. Their model shapes corroborate the observed contracts: WoGait first layer512×480, final29×128; Smooth real policy853 inputs, final21×128.

G1 Smooth's neutral axes produce commands **`[-0.5, 0, -0.5]`**, due to its declared command map. A future official-simulator trial must account for this rather than treating neutral axes as standstill. WoGait neutral commands are `[0,0,0]`. Both are offline-compatible, **not yet approved as stable deployment results**.

### Code-backed routing and prerequisites

- `robojudo/policy/__init__.py:27` enables UnitreeWoGaitPolicy; `:28` enables SmoothPolicy. `:31` and `:32` contain commented GMTPolicy/HugWbcPolicy registrations.
- `robojudo/config/g1/policy/g1_unitree_policy_cfg.py:112` defines G1UnitreeWoGaitPolicyCfg,29-DoF joint order/defaults and five-frame grouped history.
- `robojudo/config/g1/policy/g1_smooth_policy_cfg.py:61` defines G1SmoothPolicyCfg,21 joints, the local checkpoint name, control gains, period and nonzero neutral command map.
- `robojudo/config/g1/g1_cfg.py:53` actively selects the LSTM policy; the next line's WoGait alternative is commented. G1SmoothPolicyCfg imports in main/custom/loco-mimic config modules are not active selections.
- Actual filesystem checks confirm `robojudo/policy/gmt_policy.py`, `robojudo/policy/hugwbc_policy.py`, `robojudo/policy/hilo/` and `robojudo/policy/gmt/` **do not exist**. The `hilo`/`gmt` Ruff exclusion paths in `pyproject.toml:47` are stale exclusions, not implementations.
- There are no current code references to these GMT/HugWBC checkpoint filenames or an active Hilo factory. Source search covered `robojudo/` with ignored files included. No Hilo asset was identified in this eight-file set.
- Current module probes: torch, onnxruntime and zmq are installed; omegaconf, hydra, redis and unitree_sdk2py are absent. **No authoritative GMT/HugWBC runtime exists here to establish which external packages/services those six assets would need**, so their unavailable routing must not be reduced to an invented dependency-install recipe. WoGait/Smooth probes required no missing package or external service.

## Files found

- `research/additional-assets.json`: all eight exact asset paths; two actual forward-inference contracts; dependency and absent-runtime-path probes.
- Source files listed above: current policy registry, unselected supported policy factories, and commented unsupported routes.
- `README.md:70` and `:95`: existing documentation also states GMT/HugWBC are not enabled; code/filesystem evidence independently confirms the statement.

## External references

None required. This audit used only local source/assets and the installed environment. No downloads, training imports or dependency troubleshooting were attempted.

## Related specs

- `.trellis/spec/robojudo/backend/index.md`: CodeGraph-first and preservation boundaries.
- Task PRD/design: distinguish absent integration from model incompatibility, and offline finite inference from physical closed-loop success.

## Caveats / Not Found

- Exact coverage: eight additional checkpoint assets, separate from the30 registered-default checkpoint paths. AMO companion adapter files remain companions rather than additional strategy rows.
- The six GMT/HugWBC assets were not loaded or inferred because current framework policy semantics/config mappings are absent; their tensor validity and deployability with a future integration remain **unverified**.
- No new CLI/config registration, runtime change or source edit was made. Only the owned research Markdown/JSON files were written.
