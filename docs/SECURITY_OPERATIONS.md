# Rhombus Kaggle and AI Tool security

## Production Kaggle execution (default deny)

Set repository Actions **variable** `KAGGLE_PRODUCTION_ENABLED=true` only when
explicitly permitting new production runs. Without it, the Kaggle launch and
controller jobs are skipped. This **does not revoke any existing Kaggle keys**.
Disable the variable to block *new submissions* (already-running jobs are not cancelled).

**In-flight job recovery:** A narrowly scoped, temporary exception permits ONLY
`resume` and `retrieve` operations when `expected_commit` is exactly
`643b8a260b6fcff78bb02f3a63f348c29fd91317`, the source commit of the job already submitted before this security
migration. `submit` remains disabled without explicit production opt-in.
Do not remove this exception until final retrieval is independently verified;
then remove it in a follow-up security checkpoint. The approval environment
still applies to continuation jobs. Environment reviewer rules, if enabled,
may require explicit approval for each resume/retrieve dispatch.

The Kaggle controller is bound to GitHub Actions environment
`kaggle-production`. **Repository administrator must configure this
environment's Required reviewers and restrict deployments to protected
branches** in GitHub Settings → Environments. Merely referencing an
environment in workflow YAML does **not** enforce approval until its
protection rules exist. Requiring review on the controller may also require
review for automated resume/retrieve jobs; plan around that before enabling
large computations.

GitHub workflow permissions are read-only by default. Only Kaggle controller
and authorized launch jobs receive scoped `actions: write` for workflow
dispatch and continuation. Secrets remain stored in Actions, never in code.
A user who can edit trusted main-branch workflows or repository secrets can
still misuse them; branch protection and collaborator access are separate
controls (not modified here).

## Log boundaries

Provider HTTP error body is no longer written to Actions artifacts or logs.
Kaggle kernel failure logs are captured into memory by a bounded process and
sanitized before uploading; raw logs do not become an artifact. The scanner
detects common token signatures and any known runtime secret values, but
no regular-expression scrubber can guarantee identifying every credential
shape. Review error reports before exposing artifacts to external readers.

## AI Tool boundary

Only `get_candidate_evidence` is exposed by the current MCP integration.
It has no remote HTTP listener and does not expose Kaggle credentials,
Kaggle launch, arbitrary shell commands or writable file paths. The local
trusted host controls the evidence source. An unauthenticated **remote**
MCP or execution endpoint must not be deployed without separate
per-user authentication, explicit authorization, resource limits and
secret isolation. Merely naming a tool read-only does not provide authentication.

## Credential audit scope

`.github/workflows/secret-history-audit.yml` runs a read-only audit
automatically when this security workflow or its source is first merged to
`main`, and also supports manual dispatch. It scans:

- all **locally reachable** Git blob objects after full-depth checkout,
  including branches and tags fetched by checkout;
- all GitHub Actions artifacts **accessible to the workflow token** through
  the paginated API, including non-expired ZIP entries within size limits.

Audit JSON contains rule names and object identifiers, **never credential
values**. Expired archives, inaccessible data, oversized binary files,
unfetched Git refs, and some unrecognized secret formats are explicitly not
proven safe. An incomplete audit emits `INCOMPLETE`, not PASS. Any detected
matches emit `FINDINGS` and require human review, false-positive assessment,
and if warranted secret rotation. This scan cannot prove that a historical
credential never existed or was never previously accessed.

Check Actions → **Secret History and Artifact Audit** → artifact
`rhombus-secret-audit-<run-id>` for findings and exact coverage counts.

## Historical audit follow-up — checkpoint 0121

The metadata-only receipt from [run 38018699703](https://github.com/wt2018mask/Rhombus/actions/runs/38018699703)
reports **FINDINGS (20)** from reachable Git blobs: 9 bearer-pattern
matches, 10 assignment-pattern matches and 1 private-key-pattern match.
All 20 object/path entries point to historical security-test Python paths;
that is a triage lead, **not** independent proof that every match is synthetic.
No credential value is reproduced here. The receipt also shows 3 Git blobs
excluded by size and 767 Actions archives skipped, with 0 archive entries
scanned. It is **not** a complete clean history/artifact audit.

The checkpoint 0121 scanner now strips the GitHub token on cross-origin
artifact redirects (and rejects plaintext-HTTP redirects), bounds ZIP entry
count and cumulative declared uncompressed bytes before extraction, keeps
per-entry size enforcement, and records safe skip-reason counts. Any skipped
archive/entry or Git object still yields INCOMPLETE; any pattern still yields
FINDINGS. Neither the presence of tests nor a benign review disposition
may silently downgrade the result. A human must review the source object
and exposure path of every finding, rotate actually exposed credentials,
and separately resolve skipped/expired artifacts where feasible.

The associated evidence is recorded without secret values in
`data/development/phase3_security_audit_0121_evidence_v1.json`.
The scanner update has only offline synthetic regression coverage until
a later read-only full audit actually completes. It does not certify
exhaustive historical confidentiality.

**Repository-admin gate:** the main branch summary was marked protected
but showed zero required status checks with enforcement level `off`,
while the detailed protection endpoint returned 403 and the accessible
rulesets list was empty. These observations do not prove that all
server-side controls are disabled; an administrator must independently
capture effective settings and verify that a deliberately failing dummy
PR is *unmergeable*, without merging or bypassing it. This cannot be
resolved by passing CI or editing workflow YAML alone.

This security change deliberately does not alter repository collaborators,
remove existing credentials, or change scientific evidence.

## Opaque audit coverage — checkpoint 0122

The historical auditor previously returned an empty pattern set whenever the
first 1,024 bytes contained a NUL byte. That was a false-clearance pathway:
a visible credential signature placed after a NUL would not be reported.
The scanner now performs raw-byte signature matching regardless of NULs,
and *separately* marks unreadable/opaque content as incomplete.

Both reachable Git blobs and first-level Actions ZIP entries explicitly
mark opaque content based on binary NUL, nested archive/database signatures
(ZIP, gzip, zstd, SQLite) and common opaque file extensions. Recorded
counts and reason categories contain **no payload bytes**. Nested content
is not recursively unpacked: an apparently clean outer ZIP entry containing
a compressed inner archive remains `INCOMPLETE`, not a clean audit.
Recognizable signatures in opaque bytes are still reported as `FINDINGS`.
A normal bounded plaintext object can still be marked `COMPLETE`.

This is a **bounded offline engineering correction**, not an exhaustive
historical audit. No historical finding was downgraded or waived.
The previous 20 pattern detections, previously skipped archives/blobs,
admin-enforced required checks, external scientific evidence and Kaggle
new-submission prohibitions remain unresolved. Full inspection would require
a separately reviewed bounded recursive scanner or independent authorized
archive inspection, and cannot be assumed from this change.

Evidence: `data/development/phase3_security_audit_0122_evidence_v1.json`.
Regression tests: `tests/test_credential_audit_opaque_inputs.py`.

