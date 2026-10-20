# Source-verification recovery before the 0195 experiment

Observed 2026-10-20. Canonical main is
`1aaaa555a9a1ce2c9123845402fec4e664626708` (checkpoint 0192).
[PR 363](https://github.com/wt2018mask/Rhombus/pull/363) is draft, targets main,
and has head `3c2f42f6f5c3c88acfb55fcd6cdf7acab8b76802` (0193).
[PR 364](https://github.com/wt2018mask/Rhombus/pull/364) is draft, targets
`worker/p3-0193-nonmonotonic-choice-gate`, and has head
`81be2d09491cd5c89de26c4d2289630fd1cc36c9` (0194). Git ancestry confirms
363 is an ancestor of 364. Neither is canonically merged.

## Observed blockers and limits of diagnosis

The public Checks pages show 50 successes / 6 failures for 363 and
51 successes / 6 failures for 364. Fast CI, Development Continuity and Wave 2
succeeded for both recorded heads. All twelve failed jobs identify the same
step: `Download genuine pinned SI ZIP then analyze publisher 8 CIF against 2 original TRAIN`.
The shared downloader is `download_pinned_publisher_zip()` in
`scripts/science/obelix_original_si_cif_0155.py`, reused by the physical-source
workflows. A representative failure is
[0155 run 39193413806](https://github.com/wt2018mask/Rhombus/actions/runs/39193413806/job/117871437134).

The public annotations expose exit 1, not a Python traceback. Detailed logs
require authentication, and the current cloud proxy denies GitHub API access.
Consequently, the previously reported historical HTTP 500 cannot be independently
localized to metadata search, metadata detail or file retrieval in this run.
It must not be described as a proven scientific-code defect or a proven remote
server outage. Current local reproduction stops earlier: Figshare requests fail
with `Tunnel connection failed: 403 Forbidden`. Both Wiley destinations likewise
fail at the proxy tunnel, before receiving publisher HTML. These current proxy
denials are distinct from a publisher-origin 403 or the reported historical 500.

Network draft additions: `api.github.com`, `api.figshare.com`, `acs.figshare.com`,
`ndownloader.figshare.com`, `s3-eu-west-1.amazonaws.com`,
`chemistry-europe.onlinelibrary.wiley.com`, `onlinelibrary.wiley.com`.
Existing package-manager presets are preserved. Draft saving does not apply the
policy to this machine or publish the environment. No credential values were
requested or copied. No authenticated replacement source or retained original
source bytes were available to validate here; the original ZIP SHA256 and
redirect restrictions remain unchanged.

## Confirmed code defect and correction

At 364's recorded head, `fetch_publisher()` caught every exception, including
source-validation errors; `run()` then caught the resulting `ValueError` and
used frozen constants when the diagnostic option was enabled. Reproduction:
inject `ValueError("original Table2 value or S/cm unit mutated")` from the fetch
operation. Before correction this produced a JSON artifact labeled
`BLOCKED_PUBLISHER_ACCESS`. After correction the error propagates and no output
is written. The old result did not authorize scientific GO, but incorrectly
classified received, invalid evidence as unavailable evidence.

`PublisherUnavailable` now identifies only bounded HTTP availability failures,
network failures or timeouts. DOI, table, units and numeric validation errors,
TLS trust errors and programming exceptions cannot invoke the diagnostic.
Tests exercise actual mocked HTTP fetches, including first-route denial followed
by a mutated second-route table. HTTP/network denial still fails by default;
the explicit numerical fallback remains marked unverified, with no source hash.

The 0194 workflow exposes **Strict live publisher source verification** as a
separate job without a fallback flag. Its failure remains visible when access
is blocked. A green frozen-table diagnostic cannot satisfy that job. Source
hashes, expected values, TLS checks and scientific assertions are not weakened.

## Verification and scientific meaning

- 0193/0194 focused contracts: 18 passed.
- 0154/0155 source/archive/structure contracts: 25 passed.
- Repository Fast CI compile and scientific-contract run: 1751 passed, 8 warnings.
- Real strict 0194 CLI: exit 1, `PublisherUnavailable`, no output artifact.
- Explicit unverified 0194 CLI: reproduced diagnostic, source admission blocked,
  hash null, model abstentions 6, scientific GO false. This is not live source
  authentication or a new measurement.

Commands use the activated Python 3.11 `.venv` from `/workspace/Rhombus`.
Run `python -m pytest -q tests/test_phase3_obelix_solo_oxide_author_te_hotpress_0194.py tests/test_phase3_obelix_solo_oxide_nonmonotonic_choice_0193.py`
and the three `test_phase3_*0154.py`/`test_phase3_original_si_cif_join_0155.py`
source contracts. Execute Fast CI's compile and test blocks from its workflow.
The complete Wave 2 workflow has not been rerun on this recovery change; prior
head successes are not evidence of CI success on a new commit.

No new independent paper was admitted, no new conductivity labels were
collected, and no model was trained or compared. The proposed same-process
new-author experiment remains **INCONCLUSIVE / NOT EXECUTED**. Do not pool
conventional sintering with 56 MPa hot pressing or count 18 conditions as 18
independent materials. No official OBELiX TEST labels were opened. Production
remains disabled and P0-01, P0-02 and P0-03 remain BLOCKED.

## Integration and continuation

This correction starts at 364's exact head and is prepared as an update to its
existing `worker/p3-0194-original-te-garnet-hotpress-choice` branch. It preserves
the immutable 0193/0194 events and does not add another checkpoint to PR 364.
Checkpoint 0195 remains reserved for the next scientific task. This is not a
main-target STACK_REPAIR and must not be presented as canonical integration.

After network settings take effect, retrieve the exact failed logs, identify
the historical failure, and retry the DOI-bound metadata / original ZIP fetch.
Only verified original bytes may unblock source checks. Then run the required
exact-head CI, integrate 363 into main only with explicit authorization, and
retarget/recheck 364 against that canonical result. The corrected 364 must pass
continuity against its actual 363 base and all required exact-head checks.

The next scientific experiment still needs a genuinely separate, compatible
process paper. Freeze its eligibility and equal-compute selection baselines
before reading any unexposed evaluation labels. Include always-hotter and other
no-training rules, source/material denominators, abstention, error and selection
regret separately. Current work establishes a stricter evidence boundary, not
improved material-selection performance.
