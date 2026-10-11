# Phase 3 checkpoint 0139 — source-author extraction triage, NOT materials qualification

## Exact source premise

Checkpoint 0138's **actual** [pinned Shon run](https://github.com/wt2018mask/Rhombus/actions/runs/38112359163) observed **4,924** JSON root objects, chemistry field-name indicators in **4,924**, literature indicators in **4,907**, and 0 recognized broad conductivity/temperature fields. This proves that the 0138 *generic key dictionary* was not sufficient to interpret the source, **not** that the original source contains zero extracted conductivity data.

The authors' own original [database.py](https://github.com/shonyeajin/Ionical_conductivity_database/blob/bec7ffb07b3dde33191eba6aceda1fbfd3b03ea3/database.py) explicitly creates `BatteryConductivity` extraction records with nested `value`, `names`, `compound` and optional DOI metadata. Critically, it **expands combinations of compound names and parsed values into multiple output rows**; such rows cannot be assumed independent physical samples or experiment measurements. The authors' original [README](https://github.com/shonyeajin/Ionical_conductivity_database/blob/bec7ffb07b3dde33191eba6aceda1fbfd3b03ea3/README.md) describes text mining, not experimental specimen attestation.

## 0139 narrow engineering objective

After validating the exact original 7,063,926-byte Git blob and SHA256, classify actual author-defined nested extraction records using a *single in-memory*, resource-bounded, read-only audit. Report only fixed-key aggregate counters for: author container shape, finite positive scalar extraction values (not measured conductivity truth), author compound-name signal, optional DOI syntax metadata, value-shape rejected/missing, and intersection for further **manual source-paper review**. No formula, DOI, source key, measurement value, original row, per-record digest or raw source extraction leaves the CI worker. Never upload original source bytes.

The output's eligibility funnel must explicitly carry `verified_experimental_samples=0`, `independent_material_count=null`, `actual_measurement_temperature_attested=0`, `rights_to_republish=false`, `exact_MACE_training_frames_authenticated=false`, `new_blinded_cohort_qualified=false`, and `scientific_score_authorized=false`. Counters are not newly independent benchmark materials and must **not** be merged into the public scored benchmark. Original public OBELiX TEST 121 remain reserved.

## Exit conditions and follow-up

- [ ] Exact-final-HEAD Fast CI, Development Continuity, Wave 2 and real original-source workflow all pass.
- [ ] Actual original 0139 aggregate receipt confirms source SHA256, conservation of root-entry denominator and no science promotion.
- [ ] Independent P0-01 blind cohort/steward [#304](https://github.com/wt2018mask/Rhombus/issues/304), exact MACE selected training frames [#305](https://github.com/wt2018mask/Rhombus/issues/305), and sufficiently powered independently attested material evidence [#306](https://github.com/wt2018mask/Rhombus/issues/306) remain OPEN until external proofs exist.

Next: bind scientific original-paper citation, temperature, specimen/phase identity and rights to *independent* experiment-level candidates; acquire additional original publisher/licensed sources without inventing effective sample counts. No new Kaggle/GPU request.
