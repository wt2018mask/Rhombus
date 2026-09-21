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
qualification, artifact durability or remote replication. Inventory operations
do not launch code or integrate with receipts; controlled launch is explicit below.

## Controlled local launch

Invoke the installed launcher by absolute file path using the selected interpreter:

```powershell
C:/path/to/python.exe -I -S -B C:/path/to/Rhombus/rudeus/execution/launcher.py task.json bundle.json --bundle-hash SHA256 --git-root C:/path/to/Rhombus --store-root C:/path/to/archive --interpreter C:/path/to/python.exe --dependency-root C:/path/to/venv/Lib/site-packages
```

The equivalent API is `launch_local(task, bundle, bundle_hash, git_root=...,
store_root=..., interpreter=..., dependency_roots=[...])`. The installed launcher
and its control contracts are trusted local tooling. The CLI ignores ambient
Python import paths before loading these controls. The API assumes a trusted
calling process. Neither interface provides an independent execution witness.

The launcher verifies the supplied bundle against Git, restores exact committed
bytes to a fresh directory, and invokes the bundled bootstrap through an explicit
interpreter path with `-I -S -B`. The bootstrap checks the complete snapshot before
any repository/application import. Repository imports must match bundled bytes.
Other origins must lie in interpreter roots or explicit dependency directories;
an alternative `rudeus` package in those directories is rejected. User site, CWD,
PYTHONPATH, `.pth` execution, and automatic site customization are excluded.
Standard installed-package metadata discovery is preserved. Dependencies requiring
editable-install hooks or startup customization are not silently enabled.

After application imports and before computation, the bootstrap captures a
versioned RuntimeRecord: available interpreter/library hashes, Python version and
implementation, flags, dependency metadata, loaded-module origins/file hashes, and
explicit unavailable reasons. Origins are relative to named bundle/dependency/
stdlib roots; transient paths, timestamps and attempt IDs are absent from this
record's hash. Capture is partial: later imports, dynamic code, native execution
and the complete dependency closure are not attested.

ExecutionManifest binds the attempt ID, full H-1 TaskSpec content hash, bundle
hash, runtime-record hash, and launch policy `isolated-local-v1`. The attempt
references its manifest through existing environment metadata. This avoids hash
cycles and leaves scientific outputs and TaskSpec identity unchanged.

Canonical append-only records are retained under `code_bundles/`,
`runtime_records/`, and `execution_manifests/`, named by content hash. The launcher
rereads these records and checks their references after the child exits.
`verify_execution_records` verifies record hashes and bindings, not the truth of
observations. Successful record verification reports `execution_manifest` and
`runtime_record` as VERIFIED with `actual_execution_identity: NOT_ATTESTED`.

The existing direct local runner remains available; only the explicit controlled
path uses prepared bundle execution. Malicious tooling/interpreters, same-user
concurrent mutation, forged observations and runtime monkey-patching remain outside
this local trust boundary. There is no scheduler, remote replication change or
Git receipt integration; receipts do not yet prove retention of these new records.
