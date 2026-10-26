# Research: Offline policy and configuration deployment audit

- Query: Which current registered configurations/checkpoints have viable local policy/model contracts, and what prerequisites or concrete code defects block official G1 deployment?
- Scope: internal; configuration construction, filesystem/import probes, CPU model loading and one-forward policy inference. No DDS publisher/subscriber, external simulator, GUI, input listener, or Redis worker was started.
- Date: 2026-10-26

## Findings

### Complete registry and checkpoint counts

Fresh `cfg_registry.types` + `ConfigManager(name).get_cfg()` inspection found **25 configurations: 20 G1 and 5 H1**. All config constructors succeed. The configured policies reference **30 unique checkpoint paths**, of which **17 exist and 13 are absent**. This excludes AMO's two required adapter companions from the checkpoint count. Both adapter companions exist and were actually loaded by the AMO policy.

The machine-readable companion `policy-audit.json` records every config, policy role and exact checkpoint path; all unique policy config snapshots; file existence; current network/backend/controller prerequisites; complete ONNX signatures and metadata; TorchScript forward schemas/parameter shapes; offline inference results; and explicit prerequisite/reset probes. It is a point-in-time audit, not a generated deployment claim.

| Config | Pipeline | Current backend | Policy checkpoints / roles |
| --- | --- | --- | --- |
| `g1` | RL | MujocoEnv | Unitree `policy_lstm_1` |
| `g1_real` | RL | UnitreeCppEnv | Unitree `policy_lstm_1` |
| `g1_switch` | Multi | MujocoEnv | Unitree `policy_lstm_1`, AMO |
| `g1_locomimic` | LocoMimic | MujocoEnv | Unitree `policy_lstm_1` + ASAP CR7 |
| `g1_h2h` | RL | MujocoEnv | H2H `h2h` |
| `g1_beyondmimic` | RL | MujocoEnv | BeyondMimic `Jump_wose`, embedded motion |
| `g1_beyondmimic_with_ctrl` | RL | MujocoEnv | BeyondMimic `Dance_wose`, external NPZ |
| `g1_asap` | RL | MujocoEnv | ASAP CR7 |
| `g1_asap_loco` | RL | MujocoEnv | ASAP decoupled locomotion `model_6600` |
| `g1_kungfubot2` | RL | MujocoEnv | KungfuBot `horse_test_43000` |
| `g1_twist` | RL | MujocoEnv | TWIST `twist_general_motion_tracker`, Redis producer required |
| `g1_switch_beyondmimic` | Multi | MujocoEnv | AMO, Violin, Waltz, Dance_wose |
| `g1_protomotions_tracker` | RL | MujocoEnv | `unified_pipeline`, motion path unset |
| `g1_protomotions_tracker_real` | RL | UnitreeCppEnv | `unified_pipeline`, motion path unset |
| `g1_dev` | RL | MujocoEnv, 23-DoF model | Unitree `policy_lstm_1` |
| `g1_locomimic_beyondmimic` | LocoMimic | MujocoEnv | AMO + Dance_wose, Violin, Waltz |
| `g1_locomimic_asap` | LocoMimic | MujocoEnv | ASAP locomotion + CR7, robomimic, kongfu |
| `g1_locomimic_beyondmimic_real` | LocoMimic | UnitreeCppEnv | AMO + Dance_wose, Violin, Waltz |
| `g1_locomimic_asap_real` | LocoMimic | UnitreeCppEnv | ASAP locomotion + CR7, robomimic, kongfu |
| `g1_locomimic_asap_full` | LocoMimic | MujocoEnv | ASAP locomotion + 14 YAML-listed mimic models; only CR7 exists |
| `h1` | RL | MujocoEnv | Unitree `motion` |
| `h1_real` | RL | UnitreeEnv / Python SDK | Unitree `motion` |
| `h1_switch` | Multi | MujocoEnv | Unitree `motion`, Smooth `train_default-14000-jit` |
| `h1_h2h` | RL | MujocoEnv | H2H `h2h_release` |
| `h1_dev` | RL | MujocoEnv | Smooth `train_default-14000-jit` |

Registry authority: `robojudo/config/__init__.py:26` imports G1/H1; `robojudo/utils/module_registry.py:16` enumerates types; `robojudo/config/config_manager.py:14` constructs configs. Multi policy order is defined in `robojudo/config/g1/g1_cfg.py` and `robojudo/config/g1/g1_loco_mimic_cfg.py`. H1 entries are in `robojudo/config/h1/h1_cfg.py` / `h1_custom_cfg.py`.

### Loaded model contracts and actual finite inference

All **17 present unique checkpoints** successfully loaded and executed a forward inference via their real policy class on CPU. There are **18 successful policy variants** because Dance_wose was tested with both embedded-reference and external-reference settings. This proves local file/model/observation dimensional compatibility for the stated inputs; it does **not** prove balance, reference tracking, switching continuity, controller operation or real-time performance.

| Checkpoint / policy | Actual observation contract | Action count | Probe boundary |
| --- | --- | --- | --- |
| G1 Unitree `policy_lstm_1.pt` | 47; LSTM `weight_ih_l0` is 256×47 | 12 | Synthetic upright robot state and neutral Unitree axes |
| AMO `amo_jit.pt` | 1043, plus 25×93 = 2325 extra history inside `get_action()` | 15 | Real adapter JIT and normalization stats loaded; synthetic upright state |
| ASAP CR7 `model_191500.onnx` | `actor_obs` 1×380 | 23 | Real policy history/phase assembly |
| ASAP robomimic `dance_0605.onnx` | `actor_obs` 1×380 | 23 | Same |
| ASAP kongfu `horse_squat.onnx` | `actor_obs` 1×380 | 23 | Same |
| G1 H2H `h2h.pt` | 1821; first linear is 512×1821 | 21 | Three synthetic reference/robot keypoints; no FK/controller claim |
| BeyondMimic Jump_wose | `obs` 1×154, `time_step` 1×1 | 29 | Model-embedded joint/body references + upright state |
| BeyondMimic Dance_wose | `obs` 1×154, `time_step` 1×1 | 29 | Both embedded-reference and synthetic external-reference payload variants |
| BeyondMimic Violin | `obs` 1×160, `time_step` 1×1 | 29 | State estimator fields included |
| BeyondMimic Waltz | `obs` 1×160, `time_step` 1×1 | 29 | State estimator fields included |
| ASAP locomotion `model_6600.onnx` | `actor_obs` 1×500 | 12 | Real command/history assembly |
| KungfuBot `horse_test_43000.onnx` | `actor_obs` 1×877; `future_motion_targets` 1×600; `prop_history` 1×740 | 23 | Actual headless MotionKungfuBotCtrl reference from bundled Horse-stance motion |
| TWIST `twist_general_motion_tracker.pt` | 1155; normalizer mean/std both length1155 | 23 | Actual alternate headless MotionTwistCtrl source; **not the registered Redis source** |
| ProtoMotions `unified_pipeline.onnx` | Eight typed ONNX inputs; effective DOFs29; policy dummy observation length1 | 29 | Explicit bundled seed motion, actual ONNX reference/inference path |
| H1 Unitree `motion.pt` | 41; LSTM `weight_ih_l0` is 256×41 | 10 | Offline H1 state only |
| H1 Smooth `train_default-14000-jit.pt` | 783 including history and privileged padding | 19 | Offline H1 state only |
| H1 H2H `h2h_release.pt` | 1665; first linear is 512×1665 | 19 | Three synthetic keypoints; offline H1 state only |

Unified tracker ONNX inputs are `current_anchor_rot (B,4)`, `current_dof_pos (B,29)`, `current_dof_vel (B,29)`, `current_root_local_ang_vel (B,3)`, `historical_processed_actions (B,1,29)`, `mimic_future_anchor_rot (B,4,4)`, `mimic_future_dof_pos (B,4,29)`, and `mimic_future_dof_vel (B,4,29)`. Its outputs are actions, absolute joint position targets, stiffness targets and damping targets, all `(B,29)`. Config's placeholder1-DoF is replaced by YAML metadata in the policy constructor; treating placeholder1 as a mismatch is wrong (`robojudo/policy/protomotions_tracker_policy.py:55`).

The tracker source `assets/motions/g1/g1_bones_seed_mini.pt`, index0, loads63 source frames at30Hz and resamples104 frames at50Hz. Its policy reports torso_link anchor. The single-step probe uses synthetic torso orientation; it does not certify the reference is physically trackable in the official model.

### Missing prerequisites and deployment implications

1. **Full-ASAP is unavailable as configured**: the first mimic `APT_level1/model_176500.onnx` is missing, so the pipeline cannot even load all models. The complete missing set is APT_level1, jump_forward_level1/2/3, kick_level1/2/3, Kobe_level1, lebron_level1/2, side_jump_level1/2/3. Exact paths are in JSON. CR7 and the locomotion model exist. All14 entries are enumerated by `robojudo/config/g1/asap.yaml` and expanded in `g1_loco_mimic_cfg.py:196` onward.
2. **Both tracker defaults require a motion override**: `robojudo/config/g1/policy/g1_protomotions_tracker_cfg.py:29` sets `motion_path=""`. Actual default-policy construction raises `FileNotFoundError(2, 'No such file or directory')`. Setting the bundled seed path allows initialization and finite inference. This is a recoverable input prerequisite, not an absent tracker model.
3. **Registered TWIST cannot start in this environment**: `import redis` raises `ModuleNotFoundError`. Even after installing it, the registered controller waits for the first externally produced mimic action. `TwistRedisCtrl.__init__` (`robojudo/controller/twist_redis_ctrl.py:21`) starts a worker and loops until first data, so package installation alone is insufficient. The successful alternate MotionTwistCtrl probe is explicitly a different source configuration, not evidence the Redis pipeline is deployed.
4. **H1 is a separate robot target**: all three H1 models have valid offline contracts but are not deployable to the official G1 body by swapping model paths. H1 has distinct joint order/count and configured motor remap (`robojudo/config/h1/env/h1_real_env_cfg.py:34`). `h1_real` uses `UnitreeEnv`, `msg_type="go"`, `eno2`, dummy odometry and an absent `unitree_sdk2py` module. Switching its backend to the current C++ implementation is also insufficient: `UnitreeCppEnv.update()` explicitly raises `NotImplementedError("H1 robot with unitree_cpp not supported yet.")` at `robojudo/environment/unitree_cpp_env.py:123`. It requires an H1 simulator/backend setup and its own runtime validation. Do not label H1 checkpoints permanently unusable merely because this task's G1 simulator is running.
5. **G1 presets need backend overrides to use the external simulator**: simulation configs instantiate in-process MujocoEnv. Existing G1 real presets instantiate native UnitreeCppEnv and default to physical networking / the real odometry topic. Runner overrides must explicitly choose loopback and `rt/sportmodestate`; selecting `--extra unitree` alone does not change a config's backend.
6. **Interactive prerequisites remain separate from model validity**: keyboard presets import pynput, PHC motion controllers default to a GUI, joystick presets require a device, and AMO only consumes joystick/Unitree axes. Offline probes disabled GUI and supplied only deterministic in-memory policy inputs; they do not verify those device paths.

### Concrete reset defect found (reported to parent, no edit made)

At this audit snapshot, `UnitreePolicy.reset()` (`robojudo/policy/unitree_policy.py:22`) resets timestep and Python history only. The included recurrent G1 model exports `reset_memory`, but the policy never calls it. Reproduction: construct UnitreePolicy, run `get_action(np.zeros(47, dtype=np.float32))`, record `model.hidden_state.norm()`, call `policy.reset()`, record again. Both norms are **0.37892550230026245**, instead of the reset clearing recurrent memory. Exported methods are `['forward', 'reset_memory']`.

The exact exported schema is `reset_memory(__torch__.legged_gym.utils.helpers.PolicyExporterLSTM self) -> NoneType`. Both `hidden_state` and `cell_state` have shape `(1,1,64)`. In the same reproduction, cell norm remains0.9165987968444824 and `last_action` norm remains1.3897388423592216 after policy reset. Directly calling `policy.model.reset_memory()` clears both recurrent state tensors but does not clear `last_action`. Any fix must preserve nonrecurrent/WoGait models that do not export `reset_memory`.

```python
import numpy as np
from robojudo.config.g1.policy.g1_unitree_policy_cfg import G1UnitreePolicyCfg
from robojudo.policy.unitree_policy import UnitreePolicy

p = UnitreePolicy(G1UnitreePolicyCfg(), "cpu")
p.get_action(np.zeros(47, dtype=np.float32))
before = (p.model.hidden_state.norm().item(), p.model.cell_state.norm().item())
p.reset()
after = (p.model.hidden_state.norm().item(), p.model.cell_state.norm().item())
print(before, after, p.model.reset_memory.schema)
```

Other actual inference-then-reset probes demonstrate retained action/history state in several classes. These are reproducibility concerns, not demonstrated causes of any physical failure:

| Policy | last_action norm after reset | History norm(s) after reset | Observation |
| --- | --- | --- | --- |
| AMO |0.9683723449707031 | proprio2.222004160637251; extra2.222004160637251 | All unchanged from before reset |
| H2H G1 |4.087591156889568 |1.1329165900453573 | All unchanged; reset is no-op |
| TWIST |6.747728004656276 |0.009604686356149273 | All unchanged |
| H1 Smooth |1.9296625293226581 |1.8062647232265066 | All unchanged |
| ASAP CR7 |0 |0 | Correctly cleared from nonzero values |
| ASAP locomotion |0 |0 | Correctly cleared from nonzero values |

These probes used DOF velocity0.01 and base angular velocity `[0.01,0.02,0.03]`, so the history test observes actual nonzero state rather than a vacuous all-zero buffer. Full values are under `other_reset_probes` in JSON.

This is an evidenced reproducibility issue across pipeline self-check/reset or policy switches, not an input/output-shape blocker. A root implementation fix should be owned by the affected policy and covered by an actual state reset regression; the research agent changed no runtime file.

### Method and commands

The probes used existing `.venv/bin/python`, with local modules only. Config-only inventory imported `cfg_registry` and ConfigManager, enumerated all25 names and their policy/policies/loco_policy+mimic_policies roles, and checked actual `Path.is_file()` values. Direct model inspection used `torch.jit.load(..., map_location='cpu')` and `onnxruntime.InferenceSession(..., providers=['CPUExecutionProvider'])`. Signature-only ONNX sessions used one intra/inter-op thread; actual policy sessions retained repository defaults.

Real policy probes constructed the policy class directly, without pipeline/environment constructors. State inputs used policy-default DOF positions, zero velocities, identity xyzw quaternion and finite base/torso positions; neutral Unitree axes were supplied where consumed. H2H used three synthetic hand/head points. Kungfu/TWIST reference controllers were constructed with `motion_ctrl_gui=False` and no external simulator/environment; their internal deterministic motion loaders and pure reference generation ran without device threads. External Dance used a synthetic default-reference payload solely to verify dimensions. Tracker used the explicit bundled path. Each result and any override is stored under `offline_inference` in JSON.

## Files found

- `robojudo/config/{g1,h1}/`: complete registered pipeline/default asset declarations.
- `robojudo/policy/policy_cfgs.py`: checkpoint path conventions and model/history settings.
- `robojudo/policy/{unitree_policy,amo_policy,asap_policy,beyondmimic_policy,h2h_student_policy,kungfubot_policy,twist_policy,protomotions_tracker_policy}.py`: actual observation/inference and initialization contracts.
- `robojudo/controller/twist_redis_ctrl.py`: missing optional redis import and externally dependent first-data wait.
- `robojudo/config/g1/ctrl/g1_motion_ctrl_cfg.py`: actual existing PHC-format reference paths.
- `robojudo/tools/dof.py:37`: name-based subset adaptation. A23- or12-action G1 policy can target a29-DoF environment when untouched joints receive a valid default template; action count alone is not incompatibility.
- `assets/models/g1/protomotions_tracker/unified_pipeline.yaml`: effective tracker29-DoF order and ONNX semantic mapping.

## External references

None required. Conclusions concern current local checked-out code/assets and executed probes. No network request, package install or checkpoint download was performed.

## Related specs

- `.trellis/spec/robojudo/backend/index.md`: CodeGraph-first, concurrent edit preservation, checks and dependency boundaries.
- `.trellis/spec/robojudo/backend/phc-motion-runtime.md`: deterministic internal reference generation; CPU playback and rotation/resource contracts.

## Caveats / Not Found

- **No floating-base runtime, DDS transport, sustained balance, motion accuracy, switching continuity, hardware deployment or real-time execution was tested by this subtask.** Those results must come from the main integration run.
- No dimensional incompatibility was found among the17 present configured checkpoints under the stated reference and motion overrides. Missing files/modules/producer data are prerequisites, not inferred model defects.
- No claim is made that neutral input causes zero command in every policy: H1 Smooth printed nonzero mapped neutral commands. This is current policy behavior and must be handled when designing movement tests.
- Audit source line anchors are from the inspected snapshot and may shift as the parent fixes runtime issues. JSON captures the actual tested parameter/config values.
