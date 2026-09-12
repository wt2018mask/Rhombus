"""P1 MLIP relaxation stage ([P1] athermal relaxation & stability).

CONTENTS:
- sharding.py: stateless batch protocol (batch_id, SHARD=i/OF=M split, atomic
  result files). CPU-tested with stub relaxations; MLIP-agnostic by design.
- relax.py: real mace_mp("medium-mpa-0") relaxation + manifest writer.

See DESIGN.md (finalized 2026-09) before touching anything here.
"""

from rudeus.mlip.sharding import (
    make_batch_id,
    assign_shard,
    shard_batches,
    write_json_atomic,
    make_batch_file,
    run_batches,
)
from rudeus.mlip.relax import (
    default_model_path,
    sha256_file,
    ensure_checkpoint,
    load_calculator,
    energies_match,
    relax_structure,
    ENERGY_MATCH_TOL_MEV_PER_ATOM_PROVISIONAL,
)

__all__ = [
    "make_batch_id",
    "assign_shard",
    "shard_batches",
    "write_json_atomic",
    "make_batch_file",
    "run_batches",
    "default_model_path",
    "sha256_file",
    "ensure_checkpoint",
    "load_calculator",
    "energies_match",
    "relax_structure",
    "ENERGY_MATCH_TOL_MEV_PER_ATOM_PROVISIONAL",
]