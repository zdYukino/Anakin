# Design

Use existing ConfigManager, pipeline classes, PolicyWrapper and UnitreeCppEnv. A dedicated official-simulator runner overrides the network to lo, DDS state topic to rt/sportmodestate, and replaces device input with deterministic test inputs only when requested. Robot configuration defaults stay unchanged.

The simulator remains the external official C++ executable. Use its own reset/pause mechanisms to coordinate slow SDK/model startup with initial posture. Never claim successful balance from a welded scene. Any generated scene must preserve official inertias, joints, actuators, sensors and contact dynamics and document initialization changes.

Start with the existing Unitree locomotion policy, then load/execute available policy families and switching pipelines. Integrate minimum fixes at their actual owners (policy shape/metadata, deployment preparation, controller/backend boundary) only when runtime evidence requires them. Save raw logs under ignored logs/ and compact durable evidence under docs/.

Scope: new simulation deployment runner/tests and docs; narrowly justified framework fixes. No checkpoint retraining/replacement, external motion producer fabrication, H1-to-G1 remapping, broad controller refactor, physical deployment, package lock churn or unrelated WIP cleanup.
