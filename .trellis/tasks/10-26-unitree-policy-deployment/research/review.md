# Deployment runner review

Scope: `scripts/run_unitree_policy.py`, `tests/test_unitree_policy_runner.py`,
`robojudo/policy/unitree_policy.py`, and `tests/test_unitree_policy_reset.py`.
Reviewed against the task PRD/design/execution plan and RoboJuDo backend specs.
No DDS, simulator, X server, keyboard listener or device thread was started by
this review. Live integration evidence is owned by the parent session.

## Fixed findings

- **Initialization bypassed target validation.** The preload in `start_control`
  called the native backend before the closed-loop command monitor was installed.
  It now requires 29 finite target values before native actuation. A regression
  supplies NaNs and proves no command was sent.
- **Tracker alignment referred to the old simulator episode.** Pipeline dry runs
  can initialize `ProtoMotionsTrackerPolicy._heading_offset` against the fallen
  pre-reset world. Its normal motion reset deliberately retains that value.
  `start_control` now calls the existing policy `reset_alignment` hook only after
  fresh, upright post-reset feedback is validated. A regression verifies the
  hook sees the acknowledged new episode tick.
- **Limit reporting retained the first policy's limits.** `CommandRecorder`
  now reads the environment's current limits for every target so subsequent
  policy switches are evaluated against their active configuration. A regression
  changes limits after recorder creation and checks the second target is counted.
- **Desktop reset could select another MuJoCo window.** `SimulatorWindow` now
  matches the GLFW `_NET_WM_PID` property to the child process it started, in
  addition to the window title. A regression presents an unrelated viewer first
  and proves only the owned window is selected.
- **Touched policy had an existing Ruff F841 finding.** Renamed unused `ry` to
  `_ry` without changing controller input behavior.

The parent's Unitree LSTM reset fix was also verified: exported hidden/cell
memory and `last_action` are cleared, replaying four observations after reset
produces bitwise identical actions, and a nonrecurrent export needs no reset hook.

## Verification

- `python -m unittest tests.test_unitree_policy_runner tests.test_unitree_policy_reset`:
  **26 tests passed** (24 runner and 2 policy reset).
- Combined runner/reset/official launcher/state monitor suites:
  **42 tests passed**; output is in ignored
  `logs/unitree_policy/review-tests.log`.
- Ruff **0.12.7** lint and format checks: **passed** for all four scoped files.
- `python -m compileall -q` for all four files: **passed**.
- Tracked scoped `git diff --check` plus direct trailing-whitespace/final-newline
  checks of all four files (including untracked additions): **passed**.
- No standalone root type checker is configured; no packaging/dependency/resource
  changes are introduced by these fixes.

## Findings not changed

- Native environment cleanup is registered after pipeline construction returns.
  If a pipeline constructor raises after creating its environment, the runner
  still closes its owned simulator/Xvfb, and the CLI process exits and releases
  native threads, but an in-process caller of `run()` cannot rely on an explicit
  environment `shutdown()` in that partial-construction case. A reliable generic
  fix belongs to pipeline/environment lifecycle ownership, rather than bypassing
  registered class constructors or metaclass calls in the launcher. Reported to
  the parent; no broad lifecycle refactor made.
- `events_consumed` proves delivery into pipeline input, not that an arbitrary
  command had a consumer or completed a transition. Runtime claims must use
  active-policy/frame/motion evidence as well.
- Per-frame `loop_work_s` is sampled before JSONL writing/flushing. It measures
  inference/state work, not disk recording cost; total wall and simulated
  durations remain recorded independently. Do not describe it as total I/O
  inclusive control-loop latency without changing the metric contract.
- The existing physical-robot `prepare()` workflow is intentionally replaced by
  the documented simulation reset start, so these trials do not certify lifted
  physical preparation or real hardware deployment.

H2H's first-update/FK constructor failure discovered by the parent's live suite
is outside these four files and is owned by a separate implementation assignment.

## Final full-scope review

The final review additionally covers `robojudo/environment/unitree_cpp_env.py`,
`robojudo/pipeline/rl_pipeline.py`, `tests/test_unitree_cpp_initial_state.py`, and
`tests/test_pipeline_motion_resume.py`, together with the four files above.
All other implementation assignments released code ownership before this pass.
The updated `unitree-deployment.md` contract was read before reviewing these paths.

### Newly verified behavior

- Native self-check precedes the first Python `update()`; the constructor now
  exposes measured joints/IMU/odometry and a real full FK cache before reference
  controller construction. Tests compare torso transforms to an independent
  bare MuJoCo oracle and let real `MotionH2HCtrl` consume first and changed
  feedback, with FK disabled also covered.
- A reduced G1 simulation config is adapted onto the native 29-joint FK model
  rather than feeding 29 feedback values into its reduced model. Matching full
  joint-order configs retain their own reference/FK settings.
- Active `[MOTION_FADE_IN]` keeps the balancing policy active and reaches the
  reference controller's real playback callback. `[MOTION_RESET]`, re-entry
  after blend-out, and tracker default-pose transitions retain their original
  blend/switch rules. Tests use real manager dispatch and BeyondMimic controller
  state transitions, rather than only asserting that a command was emitted.
- Command-update gap monitoring covers the first measured command delay, every
  emitted target, post-step processing and JSONL flush stalls. Continuous inner
  blends are accepted without catch-up bursts; real target starvation is rejected.
  The wall-time loop ends against a deadline and still requires sufficient DDS
  simulation-time advancement.
- Progress telemetry serializes only known finite scalar fields. It distinguishes
  reference hold from actual playback, retains pre-/post-switch policy identity,
  and records delivery time for events encountered inside a blocking blend.
  Non-scalar model/history payloads are not serialized into progress fields.

### Final checks

```bash
.venv/bin/python -m unittest \
  tests.test_unitree_policy_runner tests.test_unitree_cpp_initial_state \
  tests.test_unitree_policy_reset tests.test_pipeline_motion_resume \
  tests.test_unitree_mujoco_launcher tests.test_unitree_mujoco_runner \
  tests.test_phc_motionlib tests.test_phc_reference tests.test_phc_controllers
```

- **85 tests passed in 5.408 seconds**. Log:
  `logs/unitree_policy/final-review-tests.log`. These tests started no external
  DDS, simulator, viewer or input-device process.
- Ruff **0.12.7** lint and format checks passed for all eight task Python files.
- `compileall` passed for the same eight files.
- Scoped tracked `git diff --check` and direct whitespace/final-newline checks
  covering all eight tracked/untracked files passed.
- No new package-data, lock, dependency, submodule or numerical PHC-runtime
  changes appeared. Full PHC analytic, independent reference and controller
  regressions passed despite the expanded live-backend/FK integration scope.
- No additional code changes were needed during this final review pass.

### Evidence boundaries retained

The earlier partial-construction lifecycle limitation remains. The runner is a
CLI; it closes its owned external simulator/Xvfb on pipeline-load failure, and
CLI process exit releases native threads. It does not promise an in-process
partial-construction cleanup API.

`max_command_gap_s` starts when the measured command recorder is installed, after
the initial preload and live-reset startup, so it must not be interpreted as a
startup-inclusive interval. `max_loop_total_work_s` now includes JSONL recording
cost, while per-frame `loop_work_s` still describes the pre-recording outer work.

State/posture snapshots are collected at outer-step boundaries. During an
intentional inner blend, command gaps are monitored at every target emission,
but a transient state excursion that recovers before the outer step returns is
not independently sampled by `StateMonitor`. The principal fixed active-resume
path avoids that inner blend; documentation should not claim per-target posture
sampling for the legacy blend path.

The main-session spec/doc review should retain the explicit active-resume rule,
these metric boundaries, and the distinction between a paused reference, partial
playback and full motion completion. Final live result numbers and the current
documentation matrix remain owned by the main integration session.

## Final artifact audit

Independent artifact audit completed against the delivered report,
`docs/data/unitree_policy_results_2026-10-26.json`, current source/assets and
original ignored runtime files. No simulator, DDS or device process was started.
The read-only audit output is retained in
`logs/unitree_policy/final-artifact-audit.json` with an empty `errors` list.

- All **8 delivered Python source SHA256 values** match the current files. The
  stored quality-log checksum matches the actual **85-test passing log**, so the
  tested code and final delivered-code fingerprints agree.
- All **44 raw summary checksums** match. Compact exported fields, including
  all numeric runtime/progress/error information retained in the export, agree
  with the raw summaries. Absolute workspace paths normalized to relative paths
  in the export were accounted for explicitly.
- All **43 recorded JSONL checksums** match. The remaining record is the expected
  H1 configuration rejection, which occurs before the sample log is opened and
  has no measured control steps. Across the logs, **42,162 sample records** have
  the reported step counts and finite **29-dimensional target vectors**.
- Trial accounting agrees: **44 formal invocations**, **27 passing invocations**,
  and **854.714 cumulative measured simulation seconds**. Negative preflight and
  partial failed trials remain included as such. The 27 passing invocations are
  not a count of deployable configuration names.
- All **28 quantitative report rows** agree with their linked run's pass/fail
  status, control steps, simulated duration, minimum pelvis height and maximum
  tilt, allowing only the displayed decimal rounding.
- The current registry's **25 configurations** all occur in the deployment
  matrix; the actual formal record set covers attempts of all **20 G1 names**.
  Registry-derived default policy paths exactly match the exported **30 unique
  registered checkpoints**: **17 present** (all SHA256 values verified) and
  **13 absent**, with both groups explicitly listed in the report.
- **9 actual Python runner command examples** parse successfully against the
  delivered CLI. All **13 relative file links**, the one section anchor and
  fenced-code delimiters were checked and resolve correctly.
- The official checkout's commit and clean working-tree status match the
  export. Executable, scene and robot hashes match. Independent XML/config
  checks confirm **one floating joint, 29 motors, zero welds and disabled elastic
  support**.
- All **3 PNGs** decode correctly and are byte-identical to their source runtime
  screenshots. They were also visually inspected as actual official MuJoCo
  windows. The Dance image is the separate 6-second dynamic snapshot whose
  recorded reference frame is **247**, exactly as captioned; it is not presented
  as the off-camera final frame of the 145-second complete-motion run.

No artifact discrepancy requiring a code or documentation fix was found in this
core audit. The report correctly limits the count of 30 to **registered default
checkpoints**, not every model asset in the repository. The parent's additional
unregistered-asset breadth audit is a separate append-only scope; it does not
alter these verified 44-trial results or the checked Python source hashes.
