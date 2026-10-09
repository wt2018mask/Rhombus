# Phase 3 — 1MiB manually dispatched MPTrj multi-frame observation

Checkpoint 0083 introduces a separate **manual-only** GitHub Actions workflow, distinct from the existing frozen 256KiB diagnostic. To run it, an operator must explicitly select the workflow **Phase 3 MPTrj 1MiB Multi-Frame Manual** and click **Run workflow** on a trusted main commit. **This development PR does not dispatch the workflow.**

The job first validates the Git-retained ZIP/receipt from the real MPTrj 256KiB observation (run 37852263493). It uses a strict HTTPS Range request for at most 1MiB of original Figshare source (file ID 41619375), requires HTTP 206 and exact declared source size, and keeps the response in memory. A redirect can involve additional HTTP requests. The first 256KiB SHA256 must equal the frozen real source digest, or the job fails without uploading anything.

At most 16 complete frames are parsed using pymatgen. The report includes material/frame IDs, atom count, formula, energy field presence, first 256KiB SHA256, 1MiB sample SHA256, declared source size, and a warning that the remaining stream is unverified. It uploads *only* a JSON metadata receipt no larger than 16KiB with 7-day retention. It never uploads raw source bytes, triggers Kaggle, or downloads the whole MPTrj source.

The workflow independently validates the JSON metadata before uploading it, requires read-only GitHub permissions, and has no schedule/push/pull request trigger.

A successful observation does **not** verify all 12,188,168,685 bytes, prove the exact MACE-MPA-0 training frame selection, authorize a WBM exposure audit, support empirical calibration, or establish generalization to unseen structures. Those gates remain closed.


## Checkpoint 0085 — timed pilot metadata

The manual-only observation report has been versioned to **v2**, adding two non-authoritative timed diagnostics: logical 1MiB Range operation duration and bounded frame inspection duration. Neither is a validated extrapolation to the full 12.2GB dataset. See [timed pilot and resource preflight guide](PHASE3_MPTRJ_TIMED_PILOT_RESOURCE_GATE_V1.md). This code change itself does not run the source request.
