# Rhombus AI Tool expansion — read-only analysis v1

Exactly three local MCP tools are exposed:

- `get_candidate_evidence` — content-addressed evidence lookup.
- `get_domain_assessment` — frozen-model element-coverage preflight.
- `validate_candidate_structure` — bounded periodic input representation preflight.

Neither new tool accesses Kaggle, shell commands, paid compute, other local
files, or model credentials. A successfully parsed structure is **not** known
stable; supported model elements do **not** imply calibrated `IN_DOMAIN`.

## Trusted local host configuration

The original MCP command needs a trusted EvidenceRecord JSONL export. Add the
fixed medium-mpa-0 model snapshot path (chosen by the local host, not the AI):

```powershell
py -3.11 -m rhombus.tools.mcp_server --evidence-jsonl "C:\Rhombus\trusted\evidence.jsonl" --model-domain-snapshot "C:\Rhombus\data\benchmarks\known_material\model_domains\medium-mpa-0-domain-v1.json"
```

The exact snapshot bytes must have SHA256
`51bd681f03d5873b1add0b1765ea1865881776bcfc0fb188c730daf0e2f1b1e5`;
the pinned model checkpoint is
`75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`.
A missing, altered or unconfigured snapshot fails closed. An AI cannot
choose an alternate filesystem path.

A domain tool input example:

```json
{"candidate_id":"nacl","model_id":"medium-mpa-0","claim_kind":"finite_temperature_stability","atomic_numbers":[11,17]}
```

Supported elements remain `domain_status=UNQUALIFIED`. Unsupported
elements produce `FAR_OOD`; in both cases aggregate
`scientific_verdict=UNKNOWN` and `claim_authorized=false`. Element
coverage is not Phase 3 distance calibration, training-set overlap,
or full unseen-material generalization qualification.

## Structure preflight input

```json
{"candidate_id":"nacl","structure":{"lattice_vectors_angstrom":[[4,0,0],[0,4,0],[0,0,4]],"atomic_numbers":[11,17],"fractional_coords":[[0,0,0],[0.5,0.5,0.5]]}}
```

Checks: 3x3 finite nondegenerate lattice, integer atomic numbers 1..118,
matching finite fractional coordinates, no more than 128 atoms, and exact
periodic coincident-site locations. The deterministic
`input_structure_sha256` binds the submitted JSON representation only;
it is not a certified artifact or a physical structure-equivalence hash.

Outputs `VALID_REPRESENTATION` or `INVALID_COINCIDENT_PERIODIC_SITES`.
Either way `scientific_verdict=UNKNOWN` and `claim_authorized=false`.
No chemical bond threshold, site occupancy, charge balance, model relaxation,
dynamic stability, synthesis or ionic-transport verdict is computed.

Inputs are limited to 128 KiB; all tools are explicitly read-only,
side-effect-free and contain no shell/path execution arguments. This is
only a local MCP entry point; multi-user authentication and independent
compute authorization must be designed before any remote service is exposed.

## Remaining blockers

- No independently verified full sAlex/WBM production overlap yet.
- MPTrj model training-exposure lineage remains unresolved.
- Qualified domain calibration and full scientific structure validation
  are not implemented here.
- Remote/public hosted MCP, simulations, job scheduling and Kaggle access
  are not exposed.

This code stacks after security checkpoint 0044; do not merge until the
security parent branch is integrated into canonical main.
