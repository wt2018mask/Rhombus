# Security hardening: 2026-10-08

The Kaggle controller is now assigned to environment rhombus-kaggle-production. Its name alone does NOT require approval. A repository admin must set Settings > Environments > rhombus-kaggle-production > Required reviewers, prevent self-review, and restrict deployment branches to protected main. Move KAGGLE_API_TOKEN from repository secrets to environment secrets after validating operation, and remove the broader copy. Do not place secrets in issues, logs, or PRs.

IMPORTANT: Approvals also apply to resume and retrieve operations. Review impact on currently running Kaggle jobs before merging this PR.

Raw Kaggle HTTP error response bodies are no longer logged. Provider kernel logs are scrubbed before artifact upload; a final safety gate rejects detected credentials in non-diagnostic artifacts. These are pattern-based controls and do not prove that all private data is absent.

The AI-facing MCP tool remains local, read-only, and restricted to get_candidate_evidence. There is no multi-user hosted server or Kaggle dispatch capability to authenticate yet. Any future server must authenticate each user and use independent authorization and user-scoped credentials before enabling actions.

Historical Git and Actions artifacts are not automatically removed by this PR. Audit coverage must be stated; expired and inaccessible artifacts are not verified. Rotate keys if exposure is suspected.
