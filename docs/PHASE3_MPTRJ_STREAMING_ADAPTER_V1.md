# Phase 3 MPTrj frame streaming — fixture-only adapter v1

## What was implemented

`rhombus/domain/mptrj.py` parses the published nested structure `mp-id → frame-id → frame dict → structure`, without loading any entire material trajectory or full MPTrj dataset into memory. Each frame is interpreted with `pymatgen.core.Structure.from_dict`. A separate diagnostic iterator maps one frame at a time to the existing `MembershipIndexRecord` format with RFC 6901 JSON-pointer source locators (escaping `~` and `/`); it does not produce an authoritative exposure audit.

Use `pip install -e ".[phase3-mptrj]"` to add the optional pinned `ijson==3.5.1`. Nothing is downloaded by importing or calling this adapter except whatever caller-supplied local data are explicitly read.

### Memory and validation properties

- Incremental binary stream parsed with `ijson.basic_parse`; each frame is built independently with `ObjectBuilder`.
- Event and scalar budgets per frame, plus hard caps on material-ID and per-material frame-ID sets (limits are caller configurable, strictly positive). No full-file JSON load. This is a **resource-bounded diagnostic**, not a measured production-memory benchmark.
- Fail-closed on unsupported root/material/frame shapes, invalid/missing `pymatgen Structure`, duplicate material IDs/frame IDs/any nested frame keys, empty dataset, malformed or truncated JSON, and unexpected second top-level JSON value.
- The generator must be **fully consumed to EOF** to validate its JSON stream. Partially consumed output is non-authoritative; upstream byte identity, source SHA256 and completeness are *not verified* by this reader.
- Source locators encode `/material-id/frame-id` using RFC 6901 escaping to prevent collisions when IDs contain `/` or `~`.
- Any full production index must later verify original input hash, expected row count, complete source coverage, and correct training dataset identity and **MACE-MPA-0 training selection** before scientific authorization.

### Provenance review (2026-10-09)

[Original Figshare MPTrj v2 record](https://figshare.com/articles/dataset/Materials_Project_Trjectory_MPtrj_Dataset/23713842) declares **CC BY 4.0**. The immutable `data/development/phase3_mptrj_figshare_metadata_v1.json` incorrectly recorded `MIT` (possibly confusing a model/code license with source-data license). **Do not modify that frozen file**; instead read `data/development/phase3_mptrj_figshare_license_correction_v1.json`, which explicitly supersedes only its license field.

[Official MACE foundation docs](https://mace-docs.readthedocs.io/en/latest/guide/foundation_models.html) and [the official MACE foundations repository](https://github.com/ACEsuit/mace-foundations) describe MACE-MPA-0 as using MPTrj + sAlex. These public declarations do not, by themselves, identify the **exact preprocessing, training frame selection, train/validation split, and checkpoint-bound source hashes**. See `data/development/phase3_mace_mpa0_training_evidence_review_v1.json`.

### Synthetic fixture example

```python
import io, json
from pymatgen.core import Structure, Lattice
from rhombus.domain.mptrj import iter_mptrj_frames

structure = Structure(Lattice.cubic(4), ["Li"], [[0, 0, 0]]).as_dict()
synthetic = {"mp-fixture": {"relax-000": {"structure": structure}}}
for frame in iter_mptrj_frames(io.BytesIO(json.dumps(synthetic).encode())):
    print(frame.source_locator, len(frame.structure))
```

Expected: `/mp-fixture/relax-000 1`. This example is synthetic only and makes no claims about actual MPTrj structures.

## What remains blocked

- Full original 12.2 GB MPTrj source hash **not computed or verified**.
- Source adapter tested against **synthetic fixtures only**; not validated on upstream bytes; no production SQLite index built.
- MACE-MPA-0 exact training-byte manifest or frame selection **not attested**.
- sAlex output remains safely archived in Draft Release 406879217, **no Kaggle rerun**.
- No WBM unseen/exposure promotion, no sealed cohort consumption, no dataset publication or license assumptions.

## Next bounded tasks

1. Verify canonical MPTrj file and exact nested frame shape against an **authorized** limited upstream sample if available, without bulk retrieval.
2. Integrate vetted iterator into source-hash-bound staging / full-coverage index only after hash and resource budget gates exist; measure performance with fixtures first.
3. Seek training-specific frame selection and checkpoint-bound metadata; retain `UNATTESTED` where missing.
