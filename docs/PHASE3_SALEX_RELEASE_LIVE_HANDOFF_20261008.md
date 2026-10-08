# Rhombus Phase 3 sAlex recovery — durable operator handoff (2026-10-08)

**Read first after any lost ChatGPT conversation.** This file records user-observed state, verified GitHub API state, exact safety constraints and actionable next steps. The authoritative compact development state is `data/development/CURRENT.json`, handoff index `docs/DEVELOPMENT_HANDOFF.md`, and immutable checkpoint events `data/development/checkpoints/`. Do not infer scientific completeness from outdated state code labels (some are historical append-only entries).

## User's most recent failure — exact text

```text
SALEX_RELEASE_LOCAL_SHA256_PASS parts=6 summary=1 manifest=1
SALEX_RELEASE_FAIL_CLOSED: ArchivalError: multiple releases have the frozen archival tag
```

The **local evidence validation succeeded**. The exception arises because authenticated GitHub Releases listing returns **two unpublished draft releases with the same tag**, a side effect of earlier retrieval and Windows subprocess decoding bugs. Do NOT delete or publish either; do NOT use `gh release upload TAG`, because the destination becomes ambiguous. The current user is running PowerShell on Windows, with a local checkout at `$HOME\Rhombus` and local original parts at `$HOME\Rhombus-sAlex-evidence`. Their earlier commands used a local path of `C:\Rhombus-sAlex-evidence` which did not exist; the corrected **user-home** directory succeeded.

## Live GitHub state verified through authenticated API, 2026-10-08

| Field | Value |
| --- | --- |
| Repository | `wt2018mask/Rhombus` (**public**) |
| Fixed production source commit | `643b8a260b6fcff78bb02f3a63f348c29fd91317` |
| Kaggle kernel ref | `wt2018mask/rhombus-salexcpu-643b8a260b6f` |
| Release tag shared by both drafts | `phase3-salex-643b8a260b6f-evidence-v1` |
| **Canonical original draft** | **Release ID `406879217`**; draft=true, correct exact source commit, **0 assets** on last inspection |
| **Duplicate empty draft** | **Release ID `406892209`**; draft=true, same tag/source commit, **0 assets** on last inspection |
| Latest uploader repair | **PR #227**, branch `worker/fix-release-windows-cp949-utf8-v1` |
| Earlier merged PRs | #224 (preserved science evidence), #225 (draft-only uploader), #226 (draft list+ID lookup) |
| Main branch at #227 creation | `f221c9023f05f75c69f6c27b6cd27725ee9238bc` |
| Upload outcome | **NOT COMPLETE / NOT VERIFIED** |

Re-query releases, their IDs, source commits and asset lists immediately before any subsequent action. Never treat a PR with pending checks as merged. Verify #227's latest head CI before merging.

## Detailed failure chain

1. The expensive Kaggle Phase 3 sAlex/WBM run finished. Earlier GitHub recovery Actions `37768069884` **downloaded 8 original files and independently verified hashes/row counts** before failing an outgoing-artifact-scanner path. Subsequent Kaggle CLI `kernels output` returned exit 0 with zero retrieved files; later advisory provider-status fixes did not restore those files.
2. A newly proposed Kaggle **output recovery** dataset `wt2018mask/rhombus-salex-production-evidence` returned 404/NOT_FOUND on run `37780385110`. This is distinct from the earlier **input request dataset**, which was successfully created. Do not ask the user to recreate that failed dataset or resubmit the long kernel.
3. Six original compressed parts were recovered from user-uploaded ChatGPT Library files, and their individual and combined compressed SHA256 were rechecked. Verified summary JSON is available, but original Kaggle `rhombus_phase3_salex_run_receipt.json` **raw bytes are NOT available**. See `data/development/phase3_salex_preserved_local_evidence_v1.json` for exact hashes and provenance.
4. PR #225 introduced `scripts/release/archive_salex_evidence.py`, a default-dry-run uploader. Its initial GitHub release-by-tag API could not see draft releases, returning 404 even after draft creation. First original empty draft `406879217` was created, then an erroneous second empty draft `406892209`.
5. PR #226 switched to authenticated Release listing and release-by-ID; merged to main as `f221c9023f05f75c69f6c27b6cd27725ee9238bc`. A subsequent Windows run validated local hashes but `subprocess.run(text=True)` decoded UTF-8 `gh api` output using cp949, raising `UnicodeDecodeError` and later `json.loads(None)` TypeError.
6. PR #227 fixes subprocess decoding with explicit UTF-8, and **also** adds safe duplicate handling: choose only original draft `406879217` when the competing drafts are empty/identical; fail closed otherwise. Upload is by the **official `https://uploads.github.com/repos/wt2018mask/Rhombus/releases/406879217/assets?name=...` URL**, not by ambiguous tag. Verify remote asset size, upload state, SHA256; no replace, delete, or publish. Latest branch code must pass CI before merge.
7. The user's latest `multiple releases have the frozen archival tag` error is from the **old main** version of the script before PR #227 is merged. Local preflight passed; user should NOT rerun until merged code is pulled.

## Safe continuation

1. Check `https://github.com/wt2018mask/Rhombus/pull/227` latest-head checks: **R2 Fast CI**, **Development Continuity**, **Wave 2 Canonical Synthetic E2E**. If all successful and branch mergeable, merge PR #227 using exact expected head SHA.
2. Recheck both draft release metadata by authenticated API, including `assets`. If either has unexpected assets or changed status/target, stop; do not overwrite/delete anything.
3. On Windows, **after** merged PR #227, run:
   ```powershell
   cd "$HOME\Rhombus"
   git pull origin main
   python .\scripts\release\archive_salex_evidence.py --data-dir "$HOME\Rhombus-sAlex-evidence"
   ```
   Require `SALEX_RELEASE_LOCAL_SHA256_PASS` + `DRY_RUN_ONLY`. Optionally set `$env:PYTHONUTF8 = "1"` as additional Windows defense.
4. Only after dry-run passes and latest code is present:
   ```powershell
   python .\scripts\release\archive_salex_evidence.py --data-dir "$HOME\Rhombus-sAlex-evidence" --upload-draft
   ```
   Expected 8 assets: membership parts `part0000` … `part0004`, one WBM overlap `part0000`, `rhombus_phase3_salex_summary.json`, and `phase3_salex_preserved_local_evidence_v1.json`. Require final `SALEX_RELEASE_DRAFT_VERIFIED`, and independently re-query original Release ID `406879217`, verify all eight uploaded asset digests/sizes, and confirm `draft=true`. If new errors occur, capture sanitized exception and inspect only; **do not repeatedly retry speculative fixes or run Kaggle**.
5. The duplicate empty draft `406892209` can remain untouched pending separate explicit manual review. **Never publish** a public Release without checking redistribution rights; `draft` is not a substitute for an independent backup.
6. Only after remote hash checks succeed, commit a **new** continuity checkpoint and update this handoff/README to truthfully mark the draft archive complete. Do not retroactively rewrite checkpoint history.

## Science and authorization

- Source sAlex SHA256: `48eb3664d95331e7fd84bfe1f04f5e741600bffcfb1253334c82dae92cebf1ef`; 10,447,765 source records.
- Source WBM SHA256: `98d545172c1ea9060f03f40cace6f8173a4ac06f1ee875ccd963765211519b58`; 256,963 structures.
- Previously validated sAlex membership SQLite rows: 10,447,765; WBM overlap JSONL rows: 256,963; earlier SQLite quick_check=ok. These full decompressed checks were **not re-run** in latest uploader dry-run.
- Exact matches 0; near duplicates 1,893; prototype overlaps 67, on that defined protocol. Full MPTrj training representation/lineage is **unattested**.
- **No `unseen_generalization` claims**, no sealed-cohort consumption, no protocol/claim authorization promotion.
- Never issue Kaggle `submit`/`resume` or attempt expensive recomputation.

## Entry points

- `data/development/CURRENT.json` — compact state and refs, read FIRST.
- `docs/DEVELOPMENT_HANDOFF.md` — succinct index, use refs to load only relevant context.
- `data/development/checkpoints/0060-salex-preserved-local-evidence-404-context.json` — original parts and dataset 404.
- `data/development/checkpoints/0061-salex-release-draft-archival-v1.json` — uploader implementation and limitations.
- `data/development/checkpoints/0062-release-draft-existing-id-lookup-v1.json` — first draft readback fix.
- `data/development/checkpoints/0063-windows-cp949-release-cli-utf8-v1.json` — encoding / duplicate draft recovery.
- `docs/PHASE3_SALEX_GITHUB_RELEASE_ARCHIVE_V1.md` — operator user guide.
- `scripts/release/archive_salex_evidence.py` and `tests/test_phase3_salex_release_archiver.py` — source and tests.
- `docs/CHAT_CONTEXT_RECOVERY_V1.md` — existing context recovery framework.

**Do not claim the archive is complete until GitHub actually holds the original uploaded assets and reports matching hashes.**
