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

This security change deliberately does not alter repository collaborators,
remove existing credentials, or change scientific evidence.
