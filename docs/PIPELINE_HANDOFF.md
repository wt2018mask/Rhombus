# P1 through P3 entry: canonical handoff adapter

`rudeus.science.pipeline_handoff` is a read-only adapter for prospective
Candidate/P0 → P1 → P2 → P2.5 → P3 task planning. It does not migrate or
reinterpret frozen batch files. The legacy scientific runners and their
thresholds remain authoritative for the verdicts they produce.

| Boundary | Required verified input | Gate | Next task inputs |
| --- | --- | --- | --- |
| Candidate → P1 | Candidate JSON bytes and `ArtifactManifest`; legacy structure SHA | P0 `PLAUSIBLE` or `SUPPORTED` | Candidate logical hash |
| P1 → P2 | `p1.json` and extracted `relaxed.json`, each tied to one successful `ExecutionAttempt` | `KEEP_FOR_P2`; matching candidate, parent, batch, input and relaxed structure hashes | P1 result and relaxed structure logical hashes |
| P2 → P2.5 | `p2.json` and canonical `p2-traj-v1` bytes, tied to one successful attempt | P2 dynamic `PASS`; matching trajectory, temperature, seed and protocol/config | P2 result and trajectory logical hashes |
| P2.5 → P3 | Verified `p25.json`, verified P2 result and trajectory | P2.5 `DIFFUSIVE` only; matching candidate, batch, parent, species, temperature, seed and provenance | P2.5 result, P2 result and trajectory logical hashes |

The canonical JSON logical hash differs from the historical
`structure_dict_sha256` convention. The P2 task therefore binds the canonical
relaxed artifact as an input and retains the historical relaxed SHA in its
full-TaskSpec provenance. Its execution attempt must bind the full TaskSpec.
Backend retries retain the task ID and require a new attempt ID. At most one
successful attempt may be selected for an assessed output. Scientific failures
terminate task generation; `UNKNOWN` or `INDETERMINATE` are not promoted.

`verify_output` checks raw and logical artifact integrity using the existing
evidence verifier. The P2 trajectory uses the existing canonical trajectory
hash, not the NPZ container hash. The adapter does not execute MLIP or MD.
The synthetic test in `tests/test_pipeline_handoff.py` creates a tiny trajectory,
runs the existing P2.5 analyzer, and proves an `INDETERMINATE` transport result
cannot create a P3 task. Its P1/P2 verdicts are fixtures for contract testing,
not new scientific results.

## Real-compute boundary

The historical P1/P2/P2.5 batch runners write legacy result files, not canonical
attempt/manifest sidecars. A remote producer must emit those sidecars with exact
task/output bindings and durable bytes before this adapter can hand off real
records. Candidate Supply must provide a candidate artifact manifest plus its
identity and P0 result; this lane does not change Candidate Supply policy.
The adapter does not infer a remote backend, launch Kaggle, or confer Git
durability. A separate ingestion path may publish verified sidecars through the
existing evidence archive and its Git receipt flow.

The existing P3 analyzer/ClaimAssessment and explicit follow-up machinery remain
available. P3's quantitative uncertainty, reconstruction, and calibration
qualification remain unresolved as documented in `P3_SCIENTIFIC_SLICE.md`.
P3 evidence is an entry to later X → N → S → Application compatibility → Final
Claim Vector → OUT stages, not a final Rhombus verdict.
