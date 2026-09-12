"""P1 MLIP relaxation stage ([P1] athermal relaxation & stability).

CONTENTS:
- sharding.py: stateless batch protocol (v2 batch_id, SHARD=i/OF=M split,
  atomic result files, legacy guard, resume-by-structure-hash).
  CPU-tested with stub relaxations; MLIP-agnostic by design.
- relax.py: real mace_mp("medium-mpa-0") relaxation + manifest writer.
- analysis.py: post-relax structural metrics + parent-collapse annotation.
- gitpush.py: worker-side commit/push safety (done files only, never main).

See DESIGN.md (finalized 2026-09) before touching anything here.
"""

from rudeus.mlip.analysis import (
    annotate_post_relax_novelty,
    compare_structures,
)
from rudeus.mlip.gitpush import (
    GitSafetyError,
    commit_done_files,
    push_branch,
    select_commit_files,
)

from rudeus.mlip.sharding import (
    BATCH_ID_SCHEME_V2,
    ERROR_VERDICTS,
    SKIPPED_VERDICTS,
    make_batch_id,
    make_batch_id_v1,
    structure_dict_sha256,
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
    "BATCH_ID_SCHEME_V2",
    "ERROR_VERDICTS",
    "SKIPPED_VERDICTS",
    "make_batch_id",
    "make_batch_id_v1",
    "structure_dict_sha256",
    "assign_shard",
    "shard_batches",
    "write_json_atomic",
    "make_batch_file",
    "run_batches",
    "annotate_post_relax_novelty",
    "compare_structures",
    "GitSafetyError",
    "commit_done_files",
    "push_branch",
    "select_commit_files",
    "default_model_path",
    "sha256_file",
    "ensure_checkpoint",
    "load_calculator",
    "energies_match",
    "relax_structure",
    "ENERGY_MATCH_TOL_MEV_PER_ATOM_PROVISIONAL",
]