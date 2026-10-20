# Verification — PASS

## Publication and source preservation

- Viewer fork branch `anakin-improvements`:
  `a16a7997b4e9c340e4e25a504208fef9997a9fe2`, parent
  `31af945ef640d276a3bafe5e9b858d80c46c8509`.
- Unitree fork branch `anakin-improvements`:
  `6f995d601be08e72528117f5cc13bd666e7d145e`, parent
  `222028cdaa79cdd7c7cda6645ebd2b02d201be0c`.
- Both pushes completed without force. Independent `ls-remote` reads matched
  published SHAs, local submodule HEADs and intended parent gitlink targets.
- Both origin URLs exactly match the user-provided SSH destinations. Original
  repositories remain as upstream remotes; parent local clone URL config is synced.
- Submodule working trees are clean. Before commit, all three source files and
  complete diffs matched saved migration snapshots byte-for-byte.

## Independent full-scope review

The checker independently SSH-cloned both fork branches into
`/tmp/anakin-fork-review-3xsx19kr/` and verified the clean source SHA256 values
against `research/publication.md`. No historical patch was applied.

- Six native-binding viewer regressions passed, forcing import from the clean
  temporary viewer clone via PYTHONPATH.
- Unitree native extension import and `cmake.version = ">=3.15"` TOML assertion passed.
- `uv lock --check --offline` passed. Runtime, locked and installed root dependency
  metadata confirm MuJoCo 3.16.0; uv files are unchanged.
- YAML/TOML/Git configuration checks passed, including exact target URL changes,
  absent active viewer/Unitree patches, and unchanged other submodule configuration.
- `git diff --check` passed. No new source changes required a type checker or
  extra lint-tool installation.
- Historical patch files are unchanged and documented as historical; root clone
  and setup instructions use the current Anakin project and pinned fork commits.
- No unresolved findings and no review-side edits.

## Limits and completion state

- No desktop window was launched. Native callback behavior is covered headlessly.
- Full parent remote-clone verification was not performed; parent commit
  `6a77265` is local and no parent push is part of this task. Both dependencies
  were independently cloned from their published forks.
- Parent configuration/docs/gitlink changes were committed after explicit user
  confirmation. Exact staged paths, SSH URLs, published gitlink targets and clean
  submodules were rechecked before commit; `git diff --cached --check` passed.
- `.gitattributes` and `.archify/` remain unrelated, untracked and untouched.
