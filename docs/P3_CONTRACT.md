# P3 Quantitative Transport Contract v1 (Provisional)

Status: contract only — no P3 implementation is authorized by this document.

Base revision: f7718d5bd25da630988a21e9471c7bc9bed4cd44

## 1. Scope

P3 consumes verified, persisted P2/P2.5 transport evidence and adds quantitative,
multi-temperature transport analysis.

P2.5 answers whether the target mobile sublattice exhibits a diffusive regime.
P3 quantifies transport within that evidence and tests temperature dependence.

P3 MUST NOT reinterpret or overwrite P2/P2.5 state-machine verdicts.

## 2. Protected existing contract

The following fields are inherited from P2/P2.5 and are immutable inputs to P3:

- candidate_material_id
- batch_id
- p2_dynamic_state
- p2_verdict
- temperature_K
- temperature_source
- target_species
- transport_state
- p25_verdict
- transport_claim_status
- provenance.p2_result_path
- provenance.trajectory_artifact_path
- provenance.trajectory_artifact_sha256
- provenance.artifact_format_version
- provenance.p2_config_hash
- provenance.p2_protocol_version
- provenance.p2_seed
- provenance.p25_config_hash
- provenance.p25_version
- transport.*
- sufficiency.*
- diagnostics.*
- evidence_events.*

The existing `TransportState` enum remains:

- NOT_RUN
- NONDIFFUSIVE
- INDETERMINATE
- DIFFUSIVE

`p25_verdict` is an alias of the P2.5 final transport state and is not a
second scientific verdict.

## 3. New P3 namespace

P3 MUST place new quantitative outputs under:

```json
{
  "quantitative_transport": {
    "self_diffusion": {},
    "conductivity_estimate": {},
    "collective_transport": {},
    "temperature_dependence": {},
    "extrapolation": {}
  }
}
```

No new P3 quantity may be written into the existing P2.5 `transport` object.

## 4. Self diffusion

`self_diffusion` represents tracer/self diffusion only.

Required semantic fields:

```json
{
  "species": "Li",
  "D_A2_per_ps": null,
  "D_m2_per_s": null,
  "fit_method": "",
  "fit_window": [],
  "n_mobile_ions": 0,
  "n_frames": 0,
  "n_valid_lags": 0,
  "uncertainty": {
    "method": "",
    "ci_level": 0.68,
    "D_A2_per_ps_ci": null
  }
}
```

Null/absent uncertainty MUST remain explicit when the evidence is insufficient.
P3 MUST NOT replace an unavailable uncertainty with zero.

## 5. Conductivity estimate

Nernst–Einstein output MUST be represented as an estimate, never as measured
or experimental conductivity.

```json
{
  "method": "nernst_einstein",
  "value_S_per_m": null,
  "temperature_K": null,
  "carrier_density_per_m3": null,
  "D_m2_per_s": null,
  "uncertainty": {
    "method": "",
    "ci_level": 0.68,
    "value_S_per_m_ci": null
  },
  "claim_status": "estimate"
}
```

The contract deliberately uses `conductivity_estimate`, not `conductivity`.

## 6. Collective transport

Collective charge transport is evidence-dependent and MUST NOT be fabricated
when trajectory length or statistical support is insufficient.

```json
{
  "available": false,
  "status": "INSUFFICIENT",
  "method": "",
  "sigma_S_per_m": null,
  "uncertainty": {
    "method": "",
    "ci_level": 0.68,
    "sigma_S_per_m_ci": null
  },
  "charge_displacement_definition": "",
  "n_frames": 0,
  "n_mobile_ions": 0
}
```

When sufficient, `available` MAY be true and `status` MUST identify the
actual evidence state. The implementation MUST define the charge-displacement
observable before producing a numerical value.

## 7. Self/collective correlation

If both self and collective transport are statistically supported, P3 MAY
record a correlation factor:

```json
{
  "correlation": {
    "available": true,
    "factor": null,
    "factor_definition": ""
  }
}
```

The generic name `factor` is intentional until the implementation fixes a
specific physical definition. The term "Haven factor" MUST NOT be used without
an explicit definition matching the literature quantity.

## 8. Temperature dependence

P3 MUST treat each temperature as an independently evidenced data point.

```json
{
  "temperature_dependence": {
    "temperatures_K": [],
    "diffusion_points": [],
    "conductivity_points": [],
    "fit": {
      "model": "arrhenius",
      "available": false,
      "activation_energy_eV": null,
      "activation_energy_ci_eV": null,
      "prefactor": null,
      "fit_diagnostics": {}
    }
  }
}
```

An Arrhenius fit is a model analysis, not a transport verdict. A successful
fit MUST NOT imply PASS, DIFFUSIVE, experimental agreement, or room-temperature
validity by itself.

No fixed goodness-of-fit threshold is part of this v1 contract.

## 9. Extrapolation

Any value outside the simulated temperature support MUST be explicitly marked
as extrapolated.

```json
{
  "extrapolation": {
    "target_temperature_K": null,
    "available": false,
    "quantity": "",
    "value": null,
    "uncertainty": {
      "ci_level": 0.68,
      "value_ci": null
    },
    "source_temperature_range_K": [],
    "extrapolation_distance_K": null,
    "model": "",
    "status": "NOT_REQUESTED"
  }
}
```

Allowed status semantics are implementation-defined but MUST distinguish at
least requested-but-unavailable from an actual extrapolated result.

An extrapolated value MUST NOT be serialized as if it were a directly simulated
point.

## 10. P3 provenance

P3 depends on multiple temperature-specific artifacts, so provenance MUST be
per-temperature and content-addressed.

```json
{
  "provenance": {
    "p25_result_paths": [],
    "trajectory_artifacts": [
      {
        "temperature_K": null,
        "path": "",
        "sha256": ""
      }
    ],
    "p2_config_hashes": [],
    "p25_config_hashes": [],
    "p3_config_hash": "",
    "p3_version": ""
  }
}
```

Existing P2/P2.5 provenance MUST NOT be replaced by P3 provenance.

## 11. EvidenceEvent compatibility

P3 MUST continue using the existing `EvidenceEvent` contract from
`rudeus/schema.py` without changing its field types.

For structured uncertainty, the existing scalar `uncertainty` field MAY
remain null while interval/multivariate uncertainty is stored in
`conditions`.

A P3 evidence event SHOULD use:

- `level = "P3"`
- a method-specific `method`
- conditions containing the quantitative result and conditions
- the relevant artifact hash(es) or a deterministic aggregate artifact
- the model/data version actually used
- an immutable timestamp

P3 evidence is appended; it does not rewrite prior P2/P2.5 events.

## 12. Forbidden semantic overreach

P3 MUST NOT:

1. call Nernst–Einstein output experimental conductivity;
2. equate D_self with conductivity;
3. treat an Arrhenius fit as a scientific PASS criterion;
4. represent extrapolated values as measured/simulated values;
5. overwrite P2/P2.5 `TransportState`;
6. silently recompute or mutate persisted P2/P2.5 artifacts;
7. invent uncertainty when statistical support is insufficient;
8. introduce arbitrary numerical verdict thresholds solely for presentation.

## 13. Schema evolution rule

This document freezes the P3 result namespace before implementation.

Changing `TransportState` or the existing `EvidenceEvent` field contract is
out of scope for P3 v1 and requires a separate schema migration.

P3 implementation MUST add tests for:

- protected P2/P2.5 fields;
- exact `quantitative_transport` namespace;
- explicit estimate/extrapolation semantics;
- insufficient-evidence behavior;
- multi-temperature provenance;
- append-only EvidenceEvent behavior.
