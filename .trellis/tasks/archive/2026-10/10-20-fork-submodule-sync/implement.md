# Implementation Plan

1. Recheck source diffs and branch/remote refs; capture known current commit SHAs
   and confirm remote publication can proceed without forced updates.
2. Read applicable viewer and Unitree specs. Dispatch the implementation agent for
   parent `.gitmodules`, `submodule_cfg.yaml`, root README and patch README edits;
   it must not commit, push or change submodule source independently.
3. Main session configures submodule upstream/origin remotes, creates the approved
   branches and prepares scoped commits containing the current source improvements.
4. Run relevant checks before publishing: viewer regressions, source whitespace,
   Unitree build metadata and unchanged uv dependency contracts. Finish any fixes
   before remote publication.
5. Commit/push the two submodule branches with explicit refspecs; confirm remote
   SHAs. Update the parent gitlink targets and synchronize clone URLs.
6. Dispatch a final full-scope check: verify remote refs, temporary clean source
   checkouts, clean submodule worktrees, patch-free installation configuration,
   docs, viewer tests and uv lock/metadata consistency.
7. Update relevant specs/task verification notes. Present a concrete parent commit
   plan for one-shot confirmation; do not push the parent repository.
8. After approved parent commit, archive and record the session locally (Trellis
   is ignored). Leave `.gitattributes` untracked.

No automatic legacy installer execution: it resets/cleans initialized submodules.
No new broad test framework or unrelated runtime refactor is needed.

## Status

- Steps 1-6 completed. Both fork commits were pushed and independently cloned;
  review PASS with all planned checks.
- Step 7 completed: specs/verification updated; parent commit `6a77265` created
  after explicit user confirmation. No parent push.
- Step 8: archive and record locally with `--no-commit`, honoring ignored Trellis
  records and leaving `.gitattributes` and `.archify/` untouched.
