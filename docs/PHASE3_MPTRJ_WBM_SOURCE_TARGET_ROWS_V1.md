# Phase 3 — positive original MPTrj source-to-WBM material match rows (checkpoint 0089)

These are original-source diagnostic rows, not MACE-MPA-0 checkpoint training membership. The public MPTrj source is not attested to be identical to the selected model training frames.

The CLI now optionally writes a JSONL output of **positive** matches in WBM material-ID order. Each row separately reports strict source structure match, near source duplicate, and source prototype overlap. It includes the original source SHA256 and frozen WBM file SHA256. All training-membership, unseen-generalization, and calibration authorizations remain false. Unmatched materials are omitted, NOT classified as unseen.

A normal offline preflight does not make any source request:

    python -m scripts.development.run_mptrj_wbm_source_overlap --preflight --wbm-target-db /path/to/frozen-wbm-target.sqlite

Only following an actual approved bounded real 1MiB pilot, sufficient resource review, and explicit further operator authorization, the optional full-original one-pass command may be used:

    python -m scripts.development.run_mptrj_wbm_source_overlap --execute-full-download --wbm-target-db /path/to/frozen-wbm-target.sqlite --report /path/to/summary.json --matched-targets-jsonl /path/to/matched-original-source.jsonl

This never stages original source structures or force labels to disk. Matched target rows are constructed only **after** the complete source JSON, frame count, publisher MD5, total bytes and computed SHA256 are verified. They are staged as metadata-only rows to a unique temporary file, then published through exclusive no-overwrite link creation. On errors partial stage files are cleaned up. No real source request was made by this development PR.
