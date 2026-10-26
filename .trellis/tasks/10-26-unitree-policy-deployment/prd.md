# 实机部署框架与官方 MuJoCo 策略闭环联调

## Goal

通过现有实机部署后端在官方 unitree_mujoco 上运行项目策略，修复必要集成问题并在 docs 中交付可复现运行说明和策略部署矩阵。

## Requirements

- Use Anakin's deployment pipelines, policies and real Unitree backend against the official C++ simulator over loopback DDS.
- Achieve repeatable policy execution on a floating G1 without a weld or external support, with advancing feedback, finite commands, upright posture and sustained control. Inspect locomotion and motion policies, including switching where available.
- Inventory every registered G1/H1 configuration and each policy family; distinguish runtime pass, runtime failure and missing prerequisites. Report exact evidence and limits rather than treating file existence as deployability.
- Deliver reproducible launcher/validation commands and a Chinese report in docs/. Preserve physical-robot defaults, checkpoints, submodule revisions and unrelated dirty files.
- Work for at least one and at most four hours, as authorized by the user; use the time for integration, meaningful runtime trials and verification.

## Acceptance Criteria

- [x] A repeatable invocation runs actual framework policy inference and native DDS actuation on the official floating-base simulator.
- [x] Quantitative runtime records include duration, state freshness, posture/height, action validity, timing and task-specific behavior; no supported result relies on suspended tests alone.
- [x] The strategy matrix covers the complete current registry and all unique configured checkpoints with explicit prerequisites/failure reasons and evidence scope.
- [x] Relevant integration/regression tests, pinned Ruff and scoped whitespace checks pass.
- [x] docs/ explains startup, controls, shutdown, tested policies, unavailable policies and remaining limitations with evidence references.

## Notes

- Baseline HEAD: 379be5f. The earlier pipeline-run-guide task and all pre-existing changes are separate work.
- User explicitly authorized execution to completion; routine reversible integration work proceeds without another approval gate. Hardware deployment is outside this simulation task.

Completion evidence: `research/completion-audit.md`, `research/review.md`, the public report and its durable result JSON. Additional unregistered checkpoint coverage is in `research/additional-assets.md`.
