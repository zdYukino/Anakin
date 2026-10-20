# Design

## Ownership and boundaries

This is one integrated migration: publishing both dependency commits enables the
parent configuration/gitlinks update. Existing source fixes are preserved, not
reimplemented. Main session owns Git commits, remote configuration and pushes;
implementation/check agents own or review parent config/docs and validation.

## Submodule publication

- Keep the existing current commit in each worktree as its base.
- Preserve the original origin as `upstream` and set `origin` to the provided
  SSH fork URL. Preflight existing remote names/branch refs before changing them.
- Create `anakin-improvements` from the current pinned base, commit only the
  known modified files, then push with an explicit branch refspec and upstream
  tracking. If a branch already exists remotely, require a fast-forward-compatible
  update; never overwrite it. Resolve unexpected remote divergence before publishing.
- Viewer commit owns both source files (visualization and mouse fixes). Unitree
  commit owns only `pyproject.toml` (scikit-build CMake option).

## Parent configuration

- Change only the two requested URL entries in `.gitmodules`, synchronize local
  configuration, and preserve all other submodules.
- Stage the new gitlinks only after their commits exist remotely.
- Remove active patch entries for these submodules from `submodule_cfg.yaml`.
  Preserve patch files as historical artifacts and explain their original bases
  in `third_party/patches/README.md`.
- Update root README clone/install instructions to use the pinned fork commits
  without patch application. Preserve uv dependency versions and existing tests.

## Verification and rollback

- Compare all changed submodule source bytes before/after commit; run viewer
  regression tests and inspect Unitree build metadata.
- Verify exact remote branch SHAs using `ls-remote`; check parent gitlinks match.
- Verify clean source checkouts from the published refs and uv lock consistency.
- Rollback local URL/config/doc/gitlink changes independently if publication is
  blocked; keep local source improvements and created commits. No destructive
  reset, cleanup, remote-branch deletion or history rewrite is planned.
- Main-project commit has a separate workflow confirmation gate. Fork pushes are
  explicitly within the user's requested scope after this plan is approved.
