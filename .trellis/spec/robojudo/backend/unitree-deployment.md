# Unitree Deployment Contract

## 1. Scope / Trigger

Read before modifying `UnitreeCppEnv`, Unitree policy reset, pipeline initialization, or the official-simulator runner. These boundaries join live SDK feedback, FK, reference controllers, policy state and external simulation. Read the PHC playback contract as well when changing motion reference fields.

The official G1 simulator remains an external C++ executable. `scripts/run_unitree_policy.py` uses the actual deployment pipeline and native SDK backend; it does not implement substitute dynamics or a mock SDK. Keep physical-robot defaults and submodule revisions unchanged when adding simulator-only overrides.

## 2. Signatures

```python
UnitreeCppEnv(cfg_env: UnitreeEnvCfg, device="cpu")
env.update()  # materializes measured robot/sport state and optional FK
env.get_data()  # Box with dof/base/torso/FK fields
env.step(pd_target, hand_pose=None)
UnitreePolicy.reset()  # episode state, previous action and optional JIT memory
```

```bash
.venv/bin/python scripts/run_unitree_policy.py --headless -c g1_real \
  --duration 30 --command 0.3 0 0 --summary logs/unitree_policy/run.json \
  --log logs/unitree_policy/run.jsonl
```

The runner accepts normalized three-axis commands, repeatable `--event TIME:ACTION`, tracker `--motion-path`/`--motion-index`, and optional screenshots. Actions are `[COMMAND]` (with optional comma suffix), `button:NAME`, or `axes:VX,VY,YAW`. Consult parser help for the full interface. Exit statuses are 0 (runtime criteria passed), 1 (runtime/configuration failure), and 130 (interrupted).

## 3. Contracts

### Ready state and coordinate conventions

- A successfully constructed `UnitreeCppEnv` must expose the first actual feedback snapshot before controller construction. `RlPipeline` creates `CtrlManager` before its first reset; H2H reads `env.fk_info` during pipeline self-check.
- Native `self_check()` precedes this initial `update()`. Do not expose the base class's zero DOFs or identity quaternion as if they were measured feedback.
- When `update_with_fk=True`, every update stores the complete result of `env.fk()` in `_fk_info` as well as torso position/quaternion/angular velocity. `Environment.fk()` only returns a result; it does not cache it. When FK is disabled, these optional fields may remain `None`.
- SDK IMU quaternions are wxyz; framework outputs are xyzw. IMU gyroscope is body-local. UNITREE sport-state velocity is world-frame and the backend rotates it into the body frame. Preserve name-based DOF adaptation for policy subsets.
- The G1 runner uses HG LowCmd/LowState on `rt/lowcmd`/`rt/lowstate`, native DDS domain 0, network interface `lo`, and `rt/sportmodestate` for simulation odometry. The hardware default `rt/odommodestate` must remain unchanged.
- Registered H1 configs require their own model/backend/message mapping. Do not deploy H1 checkpoints on the G1 body because an action dimension happens to fit.
- When a simulator-only adapter changes a 23-joint source environment to the native 29-joint body, use the native body's FK configuration; do not pass 29 measured joints into the source's 23-joint FK. Preserve an explicitly disabled FK setting and keep the source policy/DOF adapters unchanged.

### Episode reset and initialization

- `UnitreePolicy.reset()` clears `timestep`, `last_action`, Python history, and an exported callable `model.reset_memory()` if present. Feedforward exports without that method remain supported. Actual recurrent output must replay identically after reset.
- SDK startup can take about 5 seconds waiting for absent simulator MotionSwitcher RPC services. Fallen startup samples do not establish policy failure. The runner loads the pipeline, publishes a finite adapted initial target, resets its owned simulator, and requires fresh upright feedback with a reset tick before starting measurement.
- Reset heading alignment only after the new world's measured feedback is acknowledged. A tracker can otherwise retain heading computed from pre-reset pipeline dry runs.
- Official `main.cc` replaces GLFW's key callback; Space is not a reliable pause control in this build. BackSpace has an explicit upstream reset handler. Match the window's PID to the owned simulator before injecting an event on a desktop display.
- Floating-base balance evidence must use an unconstrained scene without welds or elastic support. Simulator reset startup is separate from the lifted physical robot's `prepare()` workflow.

### Reference playback and evidence

- `BeyondMimicCtrl` starts with `playing=False`. H2H motion playback also starts paused. Stable inference at reference frame zero is evidence of pose holding only; dynamic playback needs the real controller command and advancing reference time/frame evidence.
- LocoMimic selection and entering mimic are separate events. A delivered event count does not prove that its consumer executed or completed the requested transition. Use actual active-policy IDs/names and motion progress.
- An active legacy policy receiving `[MOTION_FADE_IN]` resumes reference/controller callbacks without another nominal-pose blend. `[MOTION_RESET]`, fade-in after an actual blend-out, and tracker default-pose handling retain their separate existing transitions. Test these branches independently.
- Intentional pipeline blend-in may run a 50 Hz inner control loop inside one outer `step()`. Measure actual target-update gaps rather than rejecting a continuously controlled blend solely for a long outer-call duration. Never compress later steps into a catch-up burst after that blocking operation.
- Validate every emitted target, including initialization, for 29 finite values before native actuation. Position-limit excursions are measured, not silently clipped by the runner; use the current policy's limits after switches.
- Require advancing valid LowState ticks, sufficient simulated duration, posture/height criteria, live processes and active backend. A slow simulator or finite model output alone does not establish a successful closed loop. Preserve both failure and success evidence.
- Target-gap statistics cover measured control, excluding initial preload/reset startup. State/posture snapshots are sampled at outer-step boundaries; an intentional inner blend checks target gaps on each emission but does not sample every internal target's posture. Do not claim a stronger monitoring scope.

## 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Wrong robot, malformed axes/event/time, colliding log destinations | Reject before the requested trial |
| Missing model, tracker motion, optional controller dependency | Nonzero result identifying the missing prerequisite |
| Startup reset not acknowledged, non-upright initial feedback | Fail initialization; do not label the policy unstable |
| Invalid/nonfinite PD target, including initial preload | Reject before publishing it |
| Frozen/backwards tick, insufficient simulated duration | Fail the measured run |
| Excessive tilt, low pelvis, disabled backend, exited simulator/Xvfb | Fail and retain the runtime evidence |
| Continuous target publication during intentional blend | Continue monitoring without a false frame-time failure |
| Prolonged target-update gap | Fail instead of replaying catch-up commands |
| Constructor raises after native env creation | Own simulator/Xvfb still close; CLI process exit releases native threads. Do not claim a generic partial-construction shutdown API exists. |

## 5. Good / Base / Bad Cases

- **Base:** Unitree policy, normalized neutral input, floating G1, fresh reset and 30 seconds of advancing feedback.
- **Good:** Nonzero locomotion command, then a real LocoMimic transition and automatic/commanded return with reference progress and active-policy evidence.
- **Bad:** Call a suspended joint test balance validation, count a paused Dance reference as full playback, or treat a missing external Redis producer as a failed checkpoint.

## 6. Tests Required

```bash
.venv/bin/python -m unittest \
  tests.test_unitree_cpp_initial_state tests.test_unitree_policy_reset \
  tests.test_pipeline_motion_resume tests.test_unitree_policy_runner tests.test_unitree_mujoco_launcher \
  tests.test_unitree_mujoco_runner tests.test_unitree_remote
```

- Initial-state tests mock only the native feedback boundary, run real headless FK, compare torso pose with an independent bare MuJoCo oracle, and have actual `MotionH2HCtrl` consume first/updated snapshots. No DDS or GUI is required.
- Reset tests use the included real G1 recurrent JIT and verify hidden/cell/action clearing and deterministic multi-frame replay; also cover exports without reset memory.
- Runner tests cover input overlays/reference preservation, malformed arguments, finite preload, reset acknowledgment/alignment, own-window selection, switched limits, stale/slowed feedback, actual control gaps/blends and cleanup. Meaningful live trials remain necessary for physical stability and switching claims.
- Current focused selection and removed-test rationale: [Testing](../../../../docs/testing.md). Preserve independent PHC suites when motion code/data change. RC packet tests are memory-only; independent native CRC and real RC/hardware acceptance remain gaps.
- Run pinned Ruff 0.12.7 lint/format and scoped whitespace checks. No standalone root type checker is configured.

## 7. Wrong vs Correct

Wrong:

```python
fk_info = self.fk()  # Only setting torso fields leaves env.fk_info unavailable.
# A successful self_check alone does not populate measured Python fields.
```

Correct:

```python
self.self_check()
self.update()  # Before controller construction.
# In update(), when FK is enabled:
fk_info = self.fk()
self._fk_info = fk_info.copy()
```

Wrong: report `events_consumed=1` and finite actions as proof that a reference motion played.

Correct: inspect the reference controller's increasing time/frame, the active policy and the returned/completed motion state, together with advancing state and posture evidence.
