"""Read-only checks for the historical, candidate-free Wave 2 closure."""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import unittest
from unittest.mock import patch

from rudeus.execution.contracts import ExecutionError
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.downstream import FinalDiscoveryManifest
from rudeus.science.pipeline_release import ReleaseRecord
from rudeus.science.wave2_cohort_closure import (
    AUTH_PATH, EXPECTED_IDS, NONDIFFUSIVE, OUT_DIR, P2_FAIL, P2_INDETERMINATE,
    assemble_closure_release, build_closure,
)


ROOT = Path(__file__).resolve().parents[1]


class Wave2CohortClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = build_closure(ROOT)

    def test_all_nine_retained_dispositions_and_no_p3_task(self):
        rows = self.closure["dispositions"]
        self.assertEqual({row["batch_id"] for row in rows}, EXPECTED_IDS)
        self.assertEqual(len(rows), 9)
        self.assertEqual({row["batch_id"] for row in rows if row["p25_state"] == "NONDIFFUSIVE"}, NONDIFFUSIVE)
        self.assertEqual({row["batch_id"] for row in rows if row["p2_state"] == "FAIL"}, P2_FAIL)
        self.assertEqual({row["batch_id"] for row in rows if row["p2_state"] == "INDETERMINATE"}, P2_INDETERMINATE)
        self.assertFalse(any(row["p3_admissible"] for row in rows))
        self.assertEqual(self.closure["p3_admissible_count"], 0)
        self.assertEqual(self.closure["scientific_status"], "NO_P3_QUALIFYING_CANDIDATE")
        self.assertEqual(self.closure["new_canonical_provider_execution"], False)

    def test_missing_ingestion_receipts_are_explicit(self):
        for row in self.closure["dispositions"]:
            for group in (row["source_artifacts"], row["transition_artifacts"]):
                for ref in group.values():
                    self.assertEqual(ref["canonical_ingestion"], "VERIFIED_BUT_NOT_CANONICALLY_INGESTED")
                    self.assertEqual(ref["retention"], "GIT_COMMITTED_AT_CHECKPOINT")
        out, release = assemble_closure_release(self.closure)
        self.assertFalse(release.qualification["durable_artifacts_complete"])
        self.assertFalse(release.qualification["provenance_complete"])
        self.assertEqual(release.evidence_index, {})
        self.assertEqual(out.execution_references, ())

    def test_candidate_free_out_and_software_only_ci(self):
        out, release = assemble_closure_release(self.closure)
        self.assertIsNone(out.candidate_id)
        self.assertEqual(out.final_assessment, "UNKNOWN")
        self.assertEqual(set(out.claim_vector.values()), {"UNKNOWN"})
        self.assertEqual({name: item.verdict for name, item in out.stage_assessments.items()},
                         {name: "UNKNOWN" for name in ("X", "N", "S", "APPLICATION")})
        self.assertEqual(release.stage_receipts, {})
        self.assertIsNone(release.p3_series_hash)
        self.assertEqual(release.release_evidence["production_science"], ())
        self.assertEqual(release.release_evidence["historical_science"], (digest(self.closure),))
        self.assertFalse(release.qualification["real_remote_e2e_pass"])
        self.assertEqual(self.closure["software_qualification"]["classification"], "SOFTWARE_ONLY")

    def test_replay_is_deterministic(self):
        again = build_closure(ROOT)
        self.assertEqual(again, self.closure)
        first_out, first_release = assemble_closure_release(self.closure)
        next_out, next_release = assemble_closure_release(again)
        self.assertEqual((first_out.content_hash, first_release.content_hash),
                         (next_out.content_hash, next_release.content_hash))

    def test_persisted_artifacts_bind_closure_out_and_release(self):
        out, release = assemble_closure_release(self.closure)
        for kind, value in (("closure", self.closure), ("out", out.to_dict()),
                            ("release", release.to_dict())):
            identity = digest(value)
            path = ROOT / OUT_DIR / kind / f"{identity}.json"
            self.assertEqual(path.read_bytes().replace(b"\r\n", b"\n"), canonical_bytes(value))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), value)
        self.assertEqual(FinalDiscoveryManifest.from_dict(out.to_dict()), out)
        self.assertEqual(ReleaseRecord.from_dict(release.to_dict()), release)
        self.assertEqual(release.out_hash, out.content_hash)

    def test_changed_checkpoint_bytes_block_closure(self):
        original_run = subprocess.run

        def changed_authorization(*args, **kwargs):
            result = original_run(*args, **kwargs)
            command = args[0]
            if command[-2:] == ["show", f"HEAD:{AUTH_PATH}"]:
                return subprocess.CompletedProcess(command, 0, result.stdout + b"corrupt", result.stderr)
            return result

        with patch("rudeus.science.wave2_cohort_closure.subprocess.run", side_effect=changed_authorization):
            with self.assertRaises(ExecutionError):
                build_closure(ROOT)


if __name__ == "__main__":
    unittest.main()
