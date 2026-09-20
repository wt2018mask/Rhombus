# Repository CodeBundle v1

`rudeus.execution.code_bundle.reconstruct_bundle(task, git_root=...)` inventories
the exact commit named by `TaskSpec.code_revision`. `verify_bundle(bundle,
bundle_hash, task, git_root=...)` independently reconstructs and compares the full
inventory. Pass a CodeBundle or its JSON dictionary; retain `canonical_bytes(bundle)`
and `bundle.bundle_hash`. Verification needs those records and the Git objects,
not the original checkout. No files are written by either operation.

Scope is all committed files under `rudeus/`, including `execution/local.py`, plus
`pyproject.toml`, `requirements.txt`, and `config.yaml`. The fixed entrypoint is
`rudeus/execution/local.py`. Every entry contains its repository-relative path,
Git mode/blob OID, and SHA256 of exact committed blob bytes. Inventories are sorted
and complete. Commit/tree identities and Git object format are recorded alongside
the versioned scope policy and inherited Record schema version.

`bundle_hash = digest(bundle)` uses the existing canonical JSON SHA256 utility;
equivalently it is SHA256 of `canonical_bytes(bundle)`. The existing `digest`
already canonicalizes, so passing serialized bytes to it is not supported.

Only regular Git blobs are supported. Scoped symlinks, submodules, LFS pointers,
external/noncanonical inventory paths and alternate entrypoints are rejected.
This inventories repository bytes, not an import/dependency closure: declarations
of Python dependencies are retained as bytes, not fetched or executed. It does
not analyze arbitrary source code to discover dynamic external imports.

Git replacement objects and inherited Git environment overrides are disabled.
Checkout edits, line-ending conversions, HEAD changes and untracked files do not
alter the inventory of an immutable requested commit. Missing/corrupt objects or
retained-inventory/hash mismatches fail with INTEGRITY; unsupported external Git
entries fail with UNSUPPORTED_INPUT. No missing identity is inferred.

Success means `repository_bundle: VERIFIED`, `execution_identity: NOT_ATTESTED`.
It does not establish executed code, interpreter/dependency identity, scientific
qualification, artifact durability or remote replication. This slice adds no
launcher, execution observations, attempt changes, or receipt integration.
