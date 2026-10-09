# Phase 3 — bounded multi-frame MPTrj sample admission (v1)

Checkpoint 0082 prepares the next *scientific source-adapter* step after the
first successfully observed real MPTrj frame. This feature does not fetch new
data. The GitHub Actions manual workflow remains frozen at its original
256KiB, metadata-only diagnostic. No MACE-MPA-0 training frame membership,
full-data integrity or model generalization claim is authorized.

## Offline analysis of an explicitly captured sample

The original first 256KiB source SHA256 from manual run
[37852263493](https://github.com/wt2018mask/Rhombus/actions/runs/37852263493)
is pinned to the preserved archival receipt in
\`data/development/observations/mptrj-run-37852263493/\`.

A local operator may inspect an independently available **exact 256KiB or
1MiB** raw prefix without network access:

\`\`\`powershell
python -m scripts.development.inspect_mptrj_prefix_frames --sample .\mptrj-prefix.bin --max-frames 16
\`\`\`

The command first requires an exact SHA256 match for the **first 256KiB**
against the stored real observation. Then it streams the nested
\`material-id → frame-id → frame\` JSON events and retains only
**fully parsed and validated pymatgen Structures**, bounded to
16 frames, 16 material keys and a 1MiB scalar budget. Outputs have
bounded material/frame identifiers, atom count, reduced formula, energy
field-presence booleans and JSON Pointer-compatible source locator.

The terminal result is a machine-readable JSON object. It marks the
uninspected tail as unverified, even if the input happens to include a
closed JSON root. An incomplete or malformed next frame is **never**
reported as a complete scientific frame. Duplicate IDs, duplicate
frame fields, invalid Structures and exceeded budgets fail closed.
Neither a frame preview nor a size-matching sample proves full source
coverage or the exact training subset for the MACE-MPA-0 checkpoint.

## Optional separate original-source capture, never automatic

If the operator *separately* authorizes one bounded remote Range
operation, the existing local-only probe permits explicitly retaining
either **262144 or 1048576 bytes**:

\`\`\`powershell
python -m scripts.development.probe_mptrj_source_prefix --probe --require-complete-frame --prefix-bytes 1048576 --report .\new-receipt.json --sample-output .\mptrj-prefix.bin
python -m scripts.development.inspect_mptrj_prefix_frames --sample .\mptrj-prefix.bin --max-frames 16
\`\`\`

The strict HTTP-206 and 1MiB maximum remain unchanged. This separate
network operation has **not** been run by checkpoint 0082. The
1MiB diagnostic receipt should be validated with
\`python -m scripts.development.verify_mptrj_probe_receipt
--receipt .\new-receipt.json --expected-prefix-bytes 1048576\`.
The original production manual Actions workflow still requests 256KiB
and uploads only JSON metadata, never raw structure bytes.

## Science and data ethics

Matching the preserved first 256KiB anchor strengthens identity
consistency **only for that small prefix**. It does not prove
the complete 12,188,168,685-byte source, its canonical checksum,
the exact MACE-MPA-0 training membership, preprocessing or
reference-label selection. No exposure audit, empirical calibration,
unseen generalization or production claim is enabled.


## Separate optional 1MiB metadata-only GitHub Actions workflow

Checkpoint 0083 adds an explicitly operator-dispatched workflow for 1MiB bounded source validation and metadata-only artifacts. This is **not triggered by code commits or pull requests**, does not store original source data, and has not been run by this PR. See [manual observation guide](PHASE3_MPTRJ_MANUAL_1MIB_MULTIFRAME_V1.md).
