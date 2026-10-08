# Phase 3 sAlex — safe GitHub Releases archival (v1)

## Status and scope

This workflow archives **previously computed evidence only**. It never starts Kaggle, performs new calculations, or converts a failed retriever run into a scientific success.

The six exact original zstd split pieces and the byte-identical `rhombus_phase3_salex_summary.json` remain available in the user's ChatGPT Library uploads. **Their raw bytes are not present in GitHub Actions and have NOT been uploaded to a GitHub Release yet.** The historical original `rhombus_phase3_salex_run_receipt.json` is missing. The byte-checked preservation record committed to GitHub is `data/development/phase3_salex_preserved_local_evidence_v1.json`.

The Rhombus repository is **public**. Creating a GitHub Release as a **DRAFT** does not authorize publication. Before publishing a public Release, separately verify the permissions for redistributing source-derived scientific data, and check that the provenance limitations are documented.

## Requirements (Windows PowerShell)

- GitHub CLI installed: [GitHub CLI download](https://cli.github.com/)
- Python 3.11+ installed
- Authenticated maintainer GitHub CLI: `gh auth login`
- A local checkout of this repository's `main` branch
- A local folder, e.g. `C:\Rhombus-sAlex-evidence`, containing the **original exact seven files**:
  - `rhombus_phase3_salex_membership.sqlite.zst.part0000`
  - `rhombus_phase3_salex_membership.sqlite.zst.part0001`
  - `rhombus_phase3_salex_membership.sqlite.zst.part0002`
  - `rhombus_phase3_salex_membership.sqlite.zst.part0003`
  - `rhombus_phase3_salex_membership.sqlite.zst.part0004`
  - `rhombus_phase3_wbm_salex_overlap.jsonl.zst.part0000`
  - `rhombus_phase3_salex_summary.json`

Download the existing 6 parts and the verified summary from the original ChatGPT file Library as needed; **do not** attempt another Kaggle computation or guess a new Kaggle Dataset slug.

The preserved summary in ChatGPT Library is named `rhombus_phase3_salex_summary_verified.json`; its exact SHA256 matches the original summary. **Copy** it to `rhombus_phase3_salex_summary.json` inside the evidence directory without editing its contents. On Windows PowerShell, from that evidence directory: `Copy-Item .\rhombus_phase3_salex_summary_verified.json .\rhombus_phase3_salex_summary.json`. The script checks its full SHA256 before any upload. Do **not** add the large binary parts to a Git commit.

## Run locally

From the repository checkout in PowerShell:

```powershell
git pull origin main
python scripts/release/archive_salex_evidence.py --data-dir "C:\Rhombus-sAlex-evidence"
```

Expected ending: `SALEX_RELEASE_LOCAL_SHA256_PASS` followed by `DRY_RUN_ONLY`. Any missing/modified input, manifest mismatch or incorrect SHA256 returns a nonzero exit and **does not call GitHub**.

Only when dry-run succeeds and the local directory contains the seven exact original files:

```powershell
gh auth login
python scripts/release/archive_salex_evidence.py --data-dir "C:\Rhombus-sAlex-evidence" --upload-draft
```

The script creates or resumes a **DRAFT** GitHub Release under the tag
`phase3-salex-643b8a260b6f-evidence-v1` pointing to the immutable scientific source commit
`643b8a260b6fcff78bb02f3a63f348c29fd91317`.
It uploads 8 attachments: the six original compressed parts, the byte-checked summary, and the exact Git-tracked preserved-evidence manifest. It verifies the server-side GitHub SHA256 digest, reported size, and uploaded state on each asset before reporting success.

This operation is idempotent for an existing draft with matching bytes; it never uses `--clobber`, deletes an asset, changes an existing tag, nor publishes a release. On a partial failure, **re-run the same command**; checked assets are skipped.

## Before publication

GitHub Release draft uploads are not a substitute for independent backups. A published Release from a public repository is accessible to the public. Do not publish without:

1. Confirming the original dataset terms permit public redistribution of the processed archive.
2. Explicitly labeling that the original Kaggle run receipt **raw bytes are missing**; do not synthesize it from a summary.
3. Checking full training-lineage (`MPTRJ_TRAINING_REPRESENTATION_UNATTESTED`) remains unresolved and no unseen-generalization claim is made.
4. Optionally enabling GitHub's **immutable releases** repository setting **before publishing**; only published releases become immutable.
5. Keeping an independent second copy of the seven original files.

Do not treat `gh release verify` as a substitute for the SHA256 checks done by this script. It verifies GitHub attestation, not the original Kaggle scientific provenance.

## Failure policy

- Missing files, wrong content hash, wrong size, wrong release source commit, unknown extra remote asset, absent remote SHA256, published release, changed tag, credential/API failure: **stop**.
- The script does not automatically publish, and it never generates a new Kaggle computation.
- If inputs are not available on the Windows machine, this is a **preparation/CI implementation only**, not a completed GitHub archive.
