# Phase 3 — manual MPTrj probe diagnostic receipt admission (v1)

## Why this check exists

The [manual first-frame MPTrj workflow](PHASE3_MPTRJ_MANUAL_ACTIONS_PROBE_V1.md) is capable of generating a small JSON report after a capped **256KiB HTTPS 206** request. A generated, copied or edited JSON file might accidentally contain inconsistent material/frame IDs, a wrong Figshare source ID, misleading whole-file hash claims, or fields that imply the model training set was actually verified. The result must be **rejected before artifact upload**, rather than mistaken for evidence suitable for a WBM exposure or calibration decision.

## Added behavior

- `rhombus/domain/mptrj_probe_receipt.py`: strict source/observation/schema/policy validation and a canonical digest of the **diagnostic report metadata only**.
- `scripts/development/verify_mptrj_probe_receipt.py`: local CLI, no network, checks that the report is a normal **non-symlink file at most 16KiB**, parses JSON rejecting duplicate keys, and reports an explicitly non-authoritative status. It writes **no new files**.
- `.github/workflows/phase3-mptrj-first-frame-manual.yml`: mandatory report validation **after** bounded probe and **before** artifact upload. A mismatch fails the job and prevents successful artifact upload.
- `tests/test_phase3_mptrj_probe_receipt.py`: synthetic tampering, wrong source, duplicate fields, malformed energy presence, claim-promotion and workflow-order regressions; Fast CI only.

## Local validation example

```powershell
python -m scripts.development.verify_mptrj_probe_receipt --receipt .\mptrj-first-frame-observation.json --expected-prefix-bytes 262144
```

A successful report emits `MPTRJ_DIAGNOSTIC_REPORT_SCHEMA_PASS` and `FULL_SOURCE_NOT_ATTESTED`. **It does not certify where the JSON came from**: the digest is just a stable checksum for report content, not a Figshare prefix hash, a trusted GitHub Actions run signature or a full MPTrj source hash. The submitted report's `prefix_sha256` is checked for syntax but cannot be recomputed without the source bytes, and is therefore **not independently authenticated** here.

A schema-valid report never grants MACE-MPA-0 exact training frame membership, WBM unseen status, source-wide MD5/SHA256, domain calibration or any scientific release authorization. The 12.2GB upstream source has not been downloaded or scanned; previous sAlex evidence and original Kaggle work remain unchanged.

## Next steps

After this PR passes all CI and merges, an operator can *separately dispatch* the manual-only 256KiB GitHub Action. If it succeeds, inspect the run ID, workflow SHA, report JSON and execution provenance using the actual GitHub Actions run metadata before interpreting its limited source-shape observation. No workflow is automatically launched by this PR.
