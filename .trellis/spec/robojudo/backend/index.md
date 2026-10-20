# RoboJuDo Backend Guidelines

Scope: the Python framework under `robojudo/`, including internal motion playback and its controller/config/resource boundaries.

## Guidelines

| Guide | Purpose |
| --- | --- |
| [PHC Motion Runtime](./phc-motion-runtime.md) | Supported playback API, robot resources, numerical compatibility, errors, and independent reference testing |

## Pre-Development Checklist

1. Consult CodeGraph before locating or understanding indexed code, following root AGENTS.md.
2. Read the relevant contract below and inspect its callers before changing a motion field, rotation convention, robot YAML/MJCF, or package resource path.
3. Keep optional training/vendor packages outside framework runtime imports. Existing deployment dependencies are declared in root `requirements.txt` and locked by uv.
4. Preserve other agents' and users' working-tree changes, especially documentation edits that overlap this task's paths.

## Quality Check

- Run the affected `unittest` tests, including independent PHC reference tests for numerical or resource changes.
- Run pinned Ruff 0.12.7 lint and formatting checks on changed Python files. The new motion runtime is included in lint scope.
- Validate installed resource resolution when moving/adding YAML, XML, or source notices; package data belongs to `robojudo.motion`.
- Run `git diff --check`; review the installed environment and lock only when dependencies or packaging change. No root standalone type-checker is configured.
- Preserve all existing submodule pins unless the task explicitly changes them. PHC is now internal playback code, not a submodule.
