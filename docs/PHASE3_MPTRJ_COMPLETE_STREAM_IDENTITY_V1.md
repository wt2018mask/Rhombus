# Phase 3 MPTrj: full-stream source identity and frame coverage, fixture v1

**Status:** IMPLEMENTED / SYNTHETIC TESTS ONLY. The 12,188,168,685-byte original dataset has **NOT** been fetched, hashed, parsed or audited by this change. No Kaggle compute.

## Why this is a separate gate

The 2023 Figshare MPtrj v2 original contains 1,580,395 structure frames (see [Figshare API](https://api.figshare.com/v2/articles/23713842)). A parser yielding a few valid frames is **not** evidence of complete source coverage. The new `rhombus/domain/mptrj_integrity.py` exhausts the existing `ijson` MPTrj reader and in a **single pass** checks:

- One well-formed nested JSON root with valid `pymatgen.Structure` objects.
- No duplicate material/frame keys (inherited from nested frame parser).
- All frames read and **exact** declared frame-count match.
- **Full source byte size** match against frozen file size, and official Figshare **MD5** match.
- Locally computed SHA256 (never an *independent publisher SHA256* absent a separately pinned hash).
- No verified report on early interruption, malformed data, byte/MD5 drift or count mismatch.
- Bounded-size reads and one-frame-at-a-time parsing (subject to nested scalar allocation limitations described in earlier adapter guide).

This establishes at most **source file byte identity plus coverage**, *not* exact MACE-MPA-0 training frame selection. The original Figshare file was associated with CHGNet training; official [Materials Project MPtrj documentation](https://docs.materialsproject.org/services/ml-and-ai-applications/mptrj) explicitly notes that **subsets** of MPTrj were used in models including MACE-MP-0. Exact MPA-0 checkpoint-bound frame membership remains **UNATTESTED**.

## Optional offline full-file check (not triggered automatically)

Only if an **existing, already obtained** exact original source file is available:

```powershell
cd "$HOME\Rhombus"
python -m pip install -e ".[phase3-mptrj]"
python -m scripts.development.verify_mptrj_frames --source "D:\existing-data\MPtrj_2022.9_full.json" --report ".\mptrj-whole-file-identity.json"
```

The example path is a placeholder, not an instruction to download 12GB. The source must exist, match the exact canonical filename, have official byte size, parse completely into 1,580,395 frames, and match its upstream MD5. **Never run this merely to see whether the file exists.** It performs a full ~12GB read and structure construction; preview the resource budget before authorizing a real run.

The report is created with exclusive file creation and never overwrites existing evidence. Reports do **not** grant WBM training exposure audit authority, calibrated uncertainty or unseen-generalization claims. The separate MPTrj actual MACE-MPA-0 training selection remains unattested.

## Important append-only licence record repair

The original source [Figshare article 23713842 v2](https://api.figshare.com/v2/articles/23713842) currently reports `license.name: "MIT"`. An earlier checkpoint 0066 erratum incorrectly stated CC BY 4.0; that is associated with a **different derivative dataset** ([Figshare article 25353307](https://figshare.com/articles/dataset/MPtrj_2022_9_full/25353307)) and must **not** replace the original MPtrj dataset licence.

For traceability, do not delete or rewrite prior frozen JSON records. The authoritative new override is `data/development/phase3_mptrj_figshare_license_final_correction_v1.json` and explicitly supersedes the mistaken `phase3_mptrj_figshare_license_correction_v1.json`. Publication/redistribution of **sAlex** or mixed archives still needs a separate licence review.

## Next phase

1. Obtain an independently verifiable limited *source-derived* real MPTrj shape sample or use an already-held original, without bulk access if avoidable, to validate fixture assumptions. Official schema alone is not empirical file parsing.
2. Benchmark bounded sample throughput, memory and canonical JSON handling; then determine whether any full source read is justified or available.
3. Investigate MACE-MPA-0 checkpoint-bound preprocessing and frame selection. If unattested, preserve scientific UNKNOWN.
4. Design fail-closed staging of any full MPTrj membership index as a **separate** change. Existing sAlex Draft Release ID 406879217 is not touched.

Scientific gates remain closed. Sealed qualification cohort is not consumed.
