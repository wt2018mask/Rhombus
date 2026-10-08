# Phase 3 — explicit local 256KiB source-byte replay (v1)

Checkpoint 0079 closes the *local reproducibility* gap between a first-frame diagnostic JSON receipt and the actual 256KiB sample that produced it. This does not change the manually dispatched GitHub Actions workflow: it continues to upload **metadata only**, and no upstream request is made by this PR.

## Capture only if independently authorized

An operator who **separately chooses** a local network request can invoke the existing bounded probe with one new *optional* argument:

```powershell
python -m scripts.development.probe_mptrj_source_prefix --probe --require-complete-frame --prefix-bytes 262144 --report .\observed-receipt.json --sample-output .\mptrj-prefix-256k.bin
```

Only exact 256KiB complete-first-frame probes may use `--sample-output`; output paths must not already exist or be symlinks. The network request remains opt-in and keeps strict HTTP 206 `Content-Range`, HTTPS, identity encoding and at-most-256KiB body reads. Only after the complete frame and source metadata report pass does the CLI save the sampled bytes. The existing GitHub Actions workflow omits the flag, writes only JSON metadata and still does not save source bytes.

## Offline replay without network

After a successful explicit capture, run:

```powershell
python -m scripts.development.replay_mptrj_prefix_sample --sample .\mptrj-prefix-256k.bin --receipt .\observed-receipt.json
```

The replay command makes **zero network requests and zero writes**. It rejects symlinks, byte-count deviations, oversized/duplicate-key receipts, SHA256 mismatches, unparseable pymatgen Structures, and first-frame ID/site-count/formula/energy-presence disagreements between independently reparsed bytes and the original report.

A pass means **only that two local files are mutually consistent**: the 256KiB sample, receipt SHA256, and independently parsed first-frame observations. It does not prove those bytes were downloaded from Figshare or from the correct complete original source, nor establish source-level SHA256 for ~12.2GB, exact MACE-MPA-0 frame selection, training label provenance, WBM unseen status or scientific authorization.

No live run, Kaggle job, or training-set audit is triggered. Fixture-only tests use a simulated HTTP 206 source response.
