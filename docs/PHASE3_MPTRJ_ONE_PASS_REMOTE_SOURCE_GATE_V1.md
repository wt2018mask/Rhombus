# Phase 3 — zero-disk-stage full MPTrj source identity path (v1)

Checkpoint 0086 adds a potential **Kaggle CPU full-source validation executor** without downloading 12.2GB to Kaggle's limited working disk. It is deliberately *not* a Kaggle job launcher and has never been run on the real full MPTrj original.

## Offline preflight (no network)

~~~bash
python -m scripts.development.verify_mptrj_remote_stream --preflight
~~~

This checks both pinned source identity records and prints required whole-stream bytes (12,188,168,685), frames (1,580,395), official Figshare MD5 and the fact that it is **not** an authorized run. Preflight never requests the source, reads a model, writes a report, or launches Kaggle.

## Explicit whole-original execution on a separately approved backend

Only after a successful actual bounded 1MiB pilot, an independent resource/time/network review, and explicit operator authorization, an executor may run:

~~~bash
python -m scripts.development.verify_mptrj_remote_stream --execute-full-download --report /kaggle/working/mptrj-original-source-identity.json --progress-every-frames 5000
~~~

This is a SINGLE logical HTTPS GET of **the canonical Figshare file ID 41619375**, with HTTPS-only trusted redirects, HTTP status 200, identity encoding and Content-Length equal to the published file size. It does **not** attempt a permissive 206 Range fallback, resume, retry or fetch a converted extxyz derivative. The stream is passed directly to the existing bounded frame-at-a-time ijson/pymatgen reader and in-process MD5+SHA256 hashers. No original source bytes, 12GB temporary file, checkpoint model or SQLite production index is written.

Frame progress and parser-prefetched bytes are stderr diagnostics, **not authoritative PASS**. A report is written with exclusive new-file creation only after the entire original JSON stream is consumed, 1,580,395 frames are parsed and the exact source size + published MD5 match. A locally computed source SHA256 is recorded separately from an independently published SHA256, which is not available in the pinned metadata.

The absence of 12GB source-file disk staging does **not** guarantee acceptable peak pymatgen/parser RAM use, bounded network time, or Kaggle session viability. The raw input still transfers 12.2GB over HTTPS. A failed/disconnected run has no authoritative result; this initial v1 executor performs no resume. The preceding real 1MiB pilot is required before planning the expensive computation.

**Model-training lineage remains blocked.** A validated canonical MPTrj dataset cannot by itself establish which MPTrj frames, preprocessors or reference labels were selected to train the MACE-MPA-0 checkpoint. The WBM exposure-audit and empirical calibration gates remain false until their separate evidence contracts are satisfied.


## Checkpoint 0087 — intermediate redirect safety

The full-source HTTPS opener is now deliberately restricted to HTTPS publisher/CDN destinations **on every redirect hop**, not merely the ultimate `response.geturl()` hostname. Requests attempting HTTP downgrade, unrelated hosts (including loopback/link-local), userinfo, and nonstandard destination ports fail before the redirected request. A new opener is created per invocation and the global Python urllib opener is not changed. Offline positive and negative redirect fixtures test this policy; no full-source network call was executed by this change.


## Checkpoint 0088 — post-identity WBM **source-only** overlap

[Single-pass MPTrj↔WBM source-only overlap](PHASE3_MPTRJ_WBM_SOURCE_ONLY_ONE_PASS_V1.md) now accepts complete original-source frames via an observer during the existing full validation pass, and reports strict/near/prototype source overlap only after complete original file verification. Source match is not an MACE-MPA-0 training membership result, and no 12.2GB request has run here.
