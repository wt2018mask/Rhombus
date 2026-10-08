# Phase 3: bounded complete first-frame MPTrj source probe (v1)

## Scientific purpose and limit

A valid opening `structure` key is weaker evidence than a valid **complete pymatgen Structure** inside a real upstream MPTrj frame. This change extends the existing manual, bounded [MPTrj HTTPS Range probe](PHASE3_MPTRJ_RANGE_PREFIX_PROBE_V1.md) with `--require-complete-frame`. It consumes **the same capped byte prefix**, not a second HTTP request or a whole-dataset download.

It requires canonical nested first material/frame keys, a complete JSON frame, a valid and nonempty `pymatgen.core.Structure`, and preserves only **presence flags** for the three different source energy labels. It rejects truncation, duplicate fields, malformed structures, and nonnumeric energy labels. No raw frame bytes or raw energy values are persisted.

The first complete frame is only an **untrusted prefix observation**. Remaining JSON may be incomplete, 12GB original file hash remains unverified, no row-count/whole-corpus coverage is established, and MACE-MPA-0's exact model training frame/energy selection remains **UNATTESTED**. All exposure, calibration and unseen-generalization gates stay disabled.

## Optional execution (manual, explicit network opt-in)

```powershell
cd "$HOME\Rhombus"
python -m pip install -e ".[phase3-mptrj]"
python -m scripts.development.probe_mptrj_source_prefix --probe --require-complete-frame --prefix-bytes 262144 --report ".\mptrj-first-frame-observation.json"
```

- Maximum returned range payload is **1MiB**; default remains **256KiB**.
- The server must reply with **HTTP 206** and the exact `Content-Range` for frozen Figshare file ID 41619375, or the probe **fails before reading**. No HTTP 200 full-download fallback.
- A first frame larger than the chosen prefix budget is reported as insufficient; do not infer invalid source format from mere truncation.
- Even with a fully parsed first frame, the report is labeled diagnostic, **never** a verified full MPTrj source or a verified MACE training record.
- This step is **not enabled in GitHub Actions or Kaggle**. There has been no live Figshare Range GET in this PR. Tests simulate HTTP 206 with synthetic source data.

## Next development step

Use this tool only when an operator explicitly authorizes the limited upstream request and records its result. Follow with memory/throughput checks and research into MACE-MPA-0 checkpoint-bound frame and label selection. The frozen sAlex dataset and its GitHub Draft Release remain unchanged.
