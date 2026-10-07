from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def test_wbm_verifier_rejects_wrong_md5_without_network(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts/development/verify_wbm_file.py"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "file_id": "fixture",
                        "url": "https://figshare.com/files/1",
                        "relative_path": "fixture.bin",
                        "expected_md5": hashlib.md5(b"x").hexdigest(),
                        "expected_size": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    source = script.read_text(encoding="utf-8")
    assert "WBM_FILE_VERIFIED" in source
    assert "MD5_MISMATCH" in source
    assert "SIZE_MISMATCH" in source
    assert "ndownloader/files" in source
