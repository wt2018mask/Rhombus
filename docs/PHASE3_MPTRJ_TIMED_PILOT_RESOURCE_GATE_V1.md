# MPTrj 1MiB timed real-source pilot — resource gate (checkpoint 0085)

The 1MiB **manual-only** Actions workflow introduced in checkpoint 0083 now
separately records `range_operation_elapsed_ms` and
`frame_inspection_elapsed_ms`. These are measured using a monotonic clock
on the actual GitHub runner at the time of **explicit manual dispatch**.
The new JSON contract is v2. The workflow remains workflow_dispatch-only,
metadata-only, <=16KiB, source bytes held only in RAM, 7-day receipt retention,
without automatically invoking Kaggle or retrieving the entire MPTrj original.

## How to obtain meaningful real evidence

After PR #249 is fully merged, deliberately dispatch:

[Manual Phase 3 MPTrj 1MiB workflow](https://github.com/wt2018mask/Rhombus/actions/workflows/phase3-mptrj-multiframe-1mib-manual.yml)

Use the trusted `main` branch. The output JSON now includes both stage durations,
observed number of complete frames, first 256KiB real-source SHA256 match, the
full 1MiB prefix SHA256, and first-frame structure/energy-label presence.
Review the GitHub run and archive digest before freezing the receipt to a
subsequent append-only checkpoint.

## What the timings mean — and do NOT mean

- Range elapsed time covers an actual logical HTTPS Range operation, redirects,
  response byte transfer, and the first-frame parsing already performed in
  the range probe. It is **not a pure network benchmark**.
- Frame inspection elapsed time covers re-parsing the in-memory 1MiB sample
  (up to 16 full frames) with `ijson`/pymatgen. It is NOT a representative
  12.2GB CPU workload benchmark.
- They are not guaranteed accurate enough to extrapolate to a whole-source
  runtime. The single prefix can be atypical and network and cache performance
  may change. The report sets `full_corpus_runtime_estimate_authorized=false`.
- The eventual full-source execution needs independent staged throughput,
  memory and disk-resource preflight, and an authorized target (such as Kaggle
  CPU). It also needs per-frame count, complete source size, official source
  MD5, and computed source SHA256 checks; until finished these remain false.
- No 1MiB sample or scientific model-training membership can resolve the exact
  subset of MPTrj used in the MACE-MPA-0 checkpoint without upstream training
  selection/preprocessing lineage evidence.

No extra network request, actual 1MiB run or Kaggle job was made to create
this development change.
