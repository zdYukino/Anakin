# Implementation

1. Revalidate simulator/build, environment and registry; inspect real deployment initialization and policy contracts.
2. Run the native framework against loopback official G1. Resolve simulation startup coordination and any evidenced integration failures.
3. Add a repeatable runner with bounded duration, deterministic optional inputs, telemetry and meaningful exit status. Reuse launcher/state-monitor helpers.
4. Exercise available locomotion/mimic/tracker policies and multi-policy transitions in fresh simulator instances. Inspect blocked families offline and persist exact reasons. Extend runtime coverage while staying within the 1–4 hour envelope.
5. Run affected unittest suites and Ruff 0.12.7 lint/format; review complete diff, commands and result coverage.
6. Write docs/ deployment instructions and evidence-backed policy matrix. Capture durable integration contracts in specs and task research. Leave unrelated work and unrequested commits untouched.

Validation: actual floating-base closed-loop runs, state freshness/posture checks, nonzero-command response, motion playback completion/transitions, malformed or unavailable assets rejected, process cleanup, and focused regression tests for discovered bugs.
