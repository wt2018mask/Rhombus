# 0154-B: Real publisher original supplementary-material access experiment

## Original source and scope

The canonical [2018 Weiss et al. ACS journal paper](https://pubs.acs.org/doi/10.1021/acsami.8b00842) lists **free** supplementary Rietveld diffraction/difference-Fourier/pellet density PDF and a ZIP containing original Rietveld-refined `.cif` files across the Li1+xAlxGe2-x(PO4)3 substitution series. The 0153 [OSTI accepted author-manuscript](https://www.osti.gov/servlets/purl/1434719) was downloaded in **real GitHub Actions**: SHA256 `e5fc22ec69db52f403f8776cbcf10e11ed771d6abf69b3c3ac610bb30edfe368`, 1,697,087 bytes, 26 pages, 65,862 extracted text characters. It is not guaranteed to be the final publisher version. This source paper is linked to **two** actual 0151 original OBELiX TRAIN review CIFs; they are not independent validated samples or confirmed experimental phases.

## New real-source probe

Run [the dedicated GitHub CPU original source job](../.github/workflows/phase3-lagp-original-supplementary-0154.yml) on the actual PR SHA and record the exact source access outcome in the Actions log and aggregate-only artifact. It tries **candidate** ACS supplementary DOI suffixes `.s001` and `.s002`; the paper listing establishes that original SI exists, **not that these guessed suffix paths resolve or contain the expected PDF/ZIP**. Both HTTPS redirects and byte read budgets are capped and URL hosts checked. Verify actual PDF magic/page census or ZIP magic, CRC, traversal/encryption/nesting, decompression limits and .cif syntax. Upload **no original SI bytes, CIF coordinate geometry, conductivity source rows, or measured labels**. If either candidate route is unavailable or returns HTML, report this honestly as a negative experimental access result.

## Interpretation limits and next work

Source byte-level integrity proves *access to one candidate supplementary asset* only; verified CIF member counts are distinct from **independent experimental specimens** and cannot automatically match source OBELiX geometry. Existing 0152 ten queue rows / eight publisher abstracts, 0153 accepted manuscript, and 0154 SI routes are different evidence scopes. All original 121 public TEST rows remain unparsed. Actual sample composition x, refined phase, Li/Al/Ge site occupancy, preparation, measured temperature, and bulk vs total ionic conductivity require **direct numerical and crystallographic paper/SI review and source-row identity mapping** before MACE-MD or public scientific material scoring. No Red Team P0 is closed. Next 0155-B: approved Figshare/ACS first-party SI metadata and real bytes if DOI suffix routes are insufficient; attempt source-bound exact CIF and paper sample matching, with all uncertain outcomes preserved.

## Live Figshare CDN safety exception (2026-10-11)

The read-only, original resource-DOI-filtered [Figshare public API](https://docs.figshare.com/v2/) returned **two exact** `resource_doi=10.1021/acsami.8b00842` entries; the metadata's two source files redirect from Figshare downloader to **exact hostname** `s3-eu-west-1.amazonaws.com` (observed in GitHub real source run). The controlled downloader now allows only this one additionally observed CDN hostname, enforces the publisher's exact metadata file size before acceptance and fully checks the contents. This is a narrowly scoped transport allowance, not permission to accept any arbitrary AWS/S3 URL or scientific phase/samples. Source file identity remains unconfirmed until final GitHub execution.

## Verified original Figshare retrieval — live result 0154

[Real original Actions #38135604841](https://github.com/wt2018mask/Rhombus/actions/runs/38135604841) **SUCCESS**: the direct `.s001` and `.s002` ACS DOI suffixes each returned HTTP 403 (not actual source bytes). An independent query to the [official public Figshare API](https://docs.figshare.com/v2/) matching the paper's **exact resource DOI** returned two source-specific article metadata entries, leading to genuine publisher-hosted public files via the explicitly observed Figshare download CDN. Both source files were *actually downloaded* and content parsed under size, ZIP safety and PDF checks:

| First-party SI bytes | Byte length | SHA256 | Meaning |
|---|---:|---|---|
| Rietveld refined experimental PDF | 553,276 | `db747a82235860cdcd21a798ad51d2fd0d22b906d3a213cd31e9ea9af72d94d3` | Valid real PDF, NOT manuscript specimen-level manual adjudication |
| Original neutron-refined CIF ZIP | 6,261 | `dc88a0a83857b172ebe7a8194eb1b50148f117d6cddb39f1adbb628ac7d1c382` | Real ZIP, **8** original CIF members; NOT 8 independent specimens |

Original contents are not re-uploaded. The reader derives a SHA256 for each individual CIF member but publishes only digests and binary flags. This allows checkpoint 0155 to compare against original OBELiX *official TRAIN* source structures after its own explicit protocol, without pretending publisher structure alone guarantees measured crystal phase or a matching specimen. The two source file hashes are now **frozen in verifier code**; any drift is a hard failure of that original provenance gate. P0 remains **0/3 closed**, science NO-GO. Next **0155-B** should materialize the actual SI CIF bytes temporarily within one GitHub CPU job, recompute original 0151 pinned TRAIN review queue, and compare 8 SI crystal compositions/partial occupancies against the two source-linked original CIFs, with no TEST access and no automatic temperature/phase/conductivity promotion.
