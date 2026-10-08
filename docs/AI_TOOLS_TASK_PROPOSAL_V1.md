# Rhombus AI scientific task proposal v1 (deny by default)

This milestone adds the pure function-calling/MCP tool `plan_scientific_task`.
**It creates a proposal only.** It does not authenticate anyone, approve
execution, reserve CPU/GPU resources, create Kaggle runs, call a paid API,
operate a scheduler, access credentials, or make scientific claims.

## Inputs

Agent supplies an explicit candidate ID, one of the known Rhombus scientific
operations (`relax_structure`, `assess_finite_temperature_stability`,
`quantify_ionic_transport`), a `manifest:sha256:<64-hex>` ID, a requested
backend (`LOCAL_CPU` or `KAGGLE_CPU`), and hard bounded budgets:

- `max_walltime_seconds`: 1..21600
- `max_cpu_cores`: 1..8
- `max_memory_mib`: 256..16384

All seven inputs are required; unexpected arguments are rejected, especially
filesystem paths, bearer tokens, owner-approval fields, arbitrary shell
commands, or unexpected paid providers. The agent-supplied manifest ID is
**not source-authenticated merely because it has a valid SHA256 form**.

## Output

The deterministic `proposal_id` binds the exact normalized request and
requested budget by SHA256. The output always contains:

- `task_state=PROPOSED_ONLY`
- `execution_authorized=false`
- `approval_status=REQUIRES_TRUSTED_HOST_APPROVAL`
- `dispatch_status=NOT_SUBMITTED`
- `evidence_manifest_id_verified=false`
- `paid_service_authorized=false`
- `scientific_verdict=UNKNOWN`, `domain_status=UNQUALIFIED`,
  `claim_authorized=false`

No API endpoint for approval, cancellation or execution is offered to AI
agents. **A trusted, authenticated host approval flow and source-bound inputs
must be implemented and independently security-tested before an executor can
honor any proposal.** A hash ID is identity, NOT authorization. The requested
budget is not reserved; resource admission is still unimplemented.

This design is intentionally useful as a constrained interface for a later
host-side approval gate but cannot execute scientific jobs in its current form.

Focused tests:

    python -m pytest -q tests/test_r2_ai_task_proposal.py tests/test_r2_ai_task_proposal_mcp.py

Integration order: security #202, domain preflight #206, evidence manifest #208,
then this task-proposal PR (checkpoint 0047).
