# 0141 — P0-02 public training-lineage availability audit and provider evidence request

## Reproducible observations versus unsupported inference

- **Real checkpoint bytes:** checkpoint 0140 [GitHub Actions](https://github.com/wt2018mask/Rhombus/actions/runs/38114320683) SHA-256-verified the complete 79,462,305-byte public MACE-MPA-0 medium model. This is **not** evidence of its selected frames.
- **Public foundation-model repository snapshot:** [ACEsuit/mace-foundations @ `16a9f178706ce053f3ca8531efbab00a305d0854`](https://github.com/ACEsuit/mace-foundations/tree/16a9f178706ce053f3ca8531efbab00a305d0854), 32 Git-tree entries.
- **Public implementation repository snapshot:** [ACEsuit/mace @ `0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b`](https://github.com/ACEsuit/mace/tree/0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b), 469 Git-tree entries, including `mace/calculators/foundations_models/mace-mpa-0-medium.model`, `tests/golden/fixtures/manifest.json` and `mace/cli/fine_tuning_select.py`. The latter two are **test fixtures / a general selection tool** and must not be mistaken for the *actual* checkpoint-selected training frame manifest.
- The official published model declares **MPTrj + sAlex** training families; family membership does not identify actual selected frames. The two Git trees are *limited snapshots*, not an exhaustive search of external training storage, private workspaces, Zenodo, Hugging Face, or GitHub releases. **Absence of required evidence in these two trees is not proof that it does not exist elsewhere.**

## 0141 deliverable

Implement a deterministic, standard-library-only read-only intake of both *fully enumerated* pinned Git trees and the exact official release metadata. Reject changed SHA/asset ID, truncation, duplicate entries, unsafe paths, unexpected tree shapes and missing model/golden fixture paths. Emit **fixed aggregate boolean observations only** (never raw paths, source file bytes or training frame IDs). The output remains `P0_02_BLOCKED` regardless of path matches, because Git repository tree listing alone cannot independently attest selected training membership.

## Publisher/independent auditor evidence request (unsent)

> For the exact `mace-mpa-0-medium.model` release binary SHA-256 `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`, please provide the **complete immutable actual training selection**, separately for MPTrj and sAlex: (1) full source releases and content SHA-256; (2) selected frame IDs or fully committed inclusion manifests linked to their source records and source hashes, including excluded validation/test frames; (3) exact training preprocessing and atom/reference-energy corrections; (4) selected raw-versus-corrected DFT energies, forces and stress labels and units; (5) original training command/config/seeds, versioned scripts and material identity/deduplication rules; (6) signed publisher provenance and independent source observer/auditor attestations if possible. It is acceptable to provide protected identifiers via a mutually agreed independent auditor so embargoed/proprietary or private samples do not appear on public GitHub. Merely naming MPTrj/sAlex or supplying complete source datasets is **not** evidence of the exact selected training members.

**Not sent to the upstream maintainers automatically.** The repository owner may contact them or designate an authorized scientific steward. Do not create public upstream issues disclosing confidential identities.

## P0 science stop lines

Keep [#304](https://github.com/wt2018mask/Rhombus/issues/304) independent newly sealed blind evaluation, [#305](https://github.com/wt2018mask/Rhombus/issues/305) exact selected training lineage, and [#306](https://github.com/wt2018mask/Rhombus/issues/306) independent-sample statistical precision all **OPEN**. No source-list inventory, GitHub CI, checkpoint hash, raw dataset download or additional MLIP/MD computation may automatically close them.
