# Security hardening checkpoint — 2026-10-08

## Implemented in proposed PR #205

- The Kaggle production controller is actor restricted (repository owner or the GitHub Actions bot) and requests the `kaggle-production` environment. **This is not a configured approval until an administrator enables required reviewers for that environment.** Environment protection and repository access permissions cannot be altered by this PR.
- Kaggle credentials are no longer injected into the entire controller job. Only steps that need provider access receive those environment variables. GitHub's automatic secret masking still applies.
- Provider HTTP response bodies and raw Kaggle failure logs are not saved to public Actions artifacts. Status logs are reduced to enum codes. A conservative no-values-printed scanner checks outgoing artifacts.
- Ordinary Rhombus AI tool calls stay explicitly read-only. The current MCP PR #200 must preserve the one-tool allowlist; no Kaggle API keys or dispatch rights are exposed to user tools. External authentication is required **before** introducing any privileged tool in a separate PR.
- Artifact retention for this production controller is reduced to one day. This changes the availability of scientific outputs; longer-term storage needs an authenticated private evidence archive instead of public CI artifacts.

## Required account-side action

In GitHub Settings → Environments, create/configure `kaggle-production`; add required reviewers and prevent self-review if available. Move Kaggle secrets from general repository secrets to **environment secrets** and verify the workflow runs only after approval. This is a manually administered account setting. Actor restrictions do not replace approval.

## Historical scan coverage (not full clearance)

The currently connected GitHub connector allows repository file inspection and targeted workflow artifact retrieval, but does not provide a complete repository-wide inventory of prior Actions artifacts or arbitrary Git history blobs in one operation. **No full historical scan has been completed or certified.**

Run a trusted offline clone scan over **all Git history**, including branches and tags, using Gitleaks or equivalent, and inventory all Actions artifact ZIPs through an administrator-authorized GitHub API download. The included scanner is an extra high-confidence local guard, not a substitute for full-history secret detection. Do not put any discovered secret value into issues, logs, or reports. Revoke and rotate any key found exposed, then evaluate its usage history.

The code changes are pending CI and merge; the environment reviewer setting remains pending administrator action.
