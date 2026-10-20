# Unitree Build and Fork Compatibility

## 1. Scope / Trigger

Use this contract when publishing local Unitree build fixes or changing the
parent project's submodule reference. The validated source baseline is upstream
`222028cdaa79cdd7c7cda6645ebd2b02d201be0c`; newer fork defaults include separate
torso-IMU and dummy-SDK features, so do not upgrade to them incidentally.

## 2. Signatures

The supported scikit-build-core setting in the submodule `pyproject.toml` is:

```toml
[tool.scikit-build]
cmake.version = ">=3.15"
cmake.build-type = "Release"
```

Root setup uses:

```bash
git submodule update --init packages/unitree_cpp
uv sync --locked --extra unitree --inexact
```

## 3. Contracts

- Persistent fork URL: `git@github.com:zdYukino/unitree_cpp.git`.
- Publish current baseline fixes on `anakin-improvements`; preserve the original
  upstream repository in a local `upstream` remote.
- Keep package versions and runtime source unchanged for a build-metadata fix.
- Commit source changes in the fork, push without force, then update the parent
  gitlink to a remotely available commit.
- `third_party/patches/unitree_cpp.patch` is historical against the original
  upstream baseline. The current fork commit already contains its change;
  installation configuration and docs must not apply it again.
- A regular build still uses the real installed Unitree SDK2. Do not substitute
  a dummy SDK or upgrade to newer fork defaults while migrating remote ownership.

## 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Current scikit-build-core | `cmake.version` constraint is parsed and accepted |
| Old `cmake.minimum-version` | Deprecated setting; keep the committed replacement |
| Fresh pinned fork checkout | Includes build fix without patch application |
| Local dirty source | Preserve it before any checkout; never run installer cleanup for verification |
| Remote branch exists with incompatible history | Do not force-update it |
| Parent gitlink points to local-only commit | Publish and verify before recording the gitlink |

## 5. Good / Base / Bad Cases

- Good: publish the one-line metadata fix from the existing validated base and
  make the parent consume its exact commit.
- Base: initialize a pinned fork commit and use the already documented real SDK.
- Bad: switch to `master` to publish the fix, implicitly adopting newer upstream
  behavior, or reapply the historical patch during installation.

## 6. Tests Required

- Parse the TOML and assert `tool.scikit-build.cmake.version == ">=3.15"`.
- Compare source bytes and package metadata before and after publication.
- Verify native `import unitree_cpp` in the existing validated environment.
- Verify remote SHA, clean checkout contents, parent gitlink and absent active
  patch entry. Rebuild only when source, environment or unresolved concerns
  require it; a Git-only migration does not itself alter source bytes.

## 7. Wrong vs Correct

Wrong for current scikit-build-core:

```toml
cmake.minimum-version = "3.15"
```

Correct:

```toml
cmake.version = ">=3.15"
```
