# Implementation

1. Review callbacks and installed signatures; reproduce camera callback failure headlessly.
2. Adapt confirmed mouse API incompatibilities and extend the existing viewer patch with only those changes.
3. Pin the authoritative requirement, regenerate `uv.lock`, and sync existing optional dependencies.
4. Add regression coverage for drag/scroll, legacy signature dispatch and selection/perturbation where feasible.
5. Run regression tests, scoped lint, uv lock validation, installed-version and patch reproduction checks; inspect final diffs.
6. Document compatibility and patch maintenance in specs and patch documentation; record task progress and deliver the result.

Do not reset or commit unrelated pre-existing work. Do not launch an interactive GUI without required environment permission.

## Status

- Implementation, regression verification and independent full-scope review passed.
- Specs and patch documentation updated; details are recorded in `verification.md`.
- Phase 3.4 completed after user confirmation: `dde491d` and `ec39201`.
- `.trellis/` records remain local and ignored; archival and journal use
  `--no-commit`. No push was made.
