# Rhombus AI structure and domain preflight v1

These optional, read-only local MCP tools inspect agent-supplied inputs. Neither tool issues scientific PASS, makes unseen-generalization claims, creates a verified evidence artifact, or starts Kaggle.

## Opt-in from a trusted local host

Default MCP discovery still exposes only get_candidate_evidence. To enable additional tools, launch the MCP subprocess with the following host-only arguments:

    python -m rhombus.tools.mcp_server --evidence-jsonl /trusted/evidence.jsonl --enable-preflight-tools --model-domain-snapshot /trusted/medium-mpa-0-domain-v1.json --model-domain-snapshot-sha256 51bd681f03d5873b1add0b1765ea1865881776bcfc0fb188c730daf0e2f1b1e5

The digest shown is the frozen raw file SHA256 recorded in the repository model_domain_snapshot_index_v1.json. The host chooses the path and digest, never the model. If the snapshot bytes differ, assessment fails closed.

## get_domain_assessment

Requires candidate_id, atomic_numbers (1..256 valid atomic numbers), and claim_kind. Uses the existing Rhombus composition and element-coverage contracts. Unsupported elements can produce FAR_OOD; supported elements are UNQUALIFIED (never IN_DOMAIN from element coverage alone). Model ID, exact checkpoint SHA256 and exact snapshot file digest are reported. The overall scientific_verdict is UNKNOWN and claim_authorized is false.

## validate_candidate_structure

Requires candidate_id, atomic_numbers, cell_lengths_angstrom, cell_angles_degrees and matching fractional_coordinates. Bounded periodic-representation validation uses existing pymatgen/Phase 3 fingerprint contracts. It may return WELL_FORMED_PERIODIC_STRUCTURE with a coarse fingerprint, but this is NOT stability, physical plausibility, exact structure membership or verified provenance. Scientific verdict remains UNKNOWN, domain UNQUALIFIED and claim_authorized false.

## Security and limitations

- Explicit --enable-preflight-tools switch and host-pinned model snapshot are mandatory.
- No token access, network listener, Kaggle submission, privileged file paths, or science computation authorization.
- Input source binding is MODEL_SUPPLIED_NOT_SOURCE_VERIFIED; no scientific claims may be based on this alone.
- Invalid source or structure produces an error, not a scientific PASS.
- Phase 3 training exposure, calibrated domain assessment and persisted structure verification remain separate incomplete work.

Focused tests: python -m pytest -q tests/test_r2_ai_preflight.py tests/test_r2_ai_preflight_mcp.py

Stacked on checkpoint 0044 security PR #202; merge 0044 first, then retarget/revalidate the AI checkpoint 0045.
