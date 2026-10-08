from pathlib import Path
import pytest
from scripts.security.redact import scrub,audit
ROOT=Path(__file__).resolve().parents[1]

def test_secret_patterns_are_removed():
    secret="ghp_"+"A"*32
    safe,n=scrub(secret+" Bearer "+"b"*30)
    assert n==2 and secret not in safe and "b"*30 not in safe

def test_artifact_guard_fails_closed(tmp_path):
    (tmp_path/"result.json").write_text("api_key="+"c"*32)
    with pytest.raises(ValueError,match="upload blocked"):
        audit(tmp_path)

def test_diagnostic_scrub(tmp_path):
    p=tmp_path/"kaggle-error.log"
    p.write_text("KGAT_"+"Z"*25)
    assert audit(tmp_path)==1
    assert "KGAT_" not in p.read_text()

def test_kaggle_approval_and_no_raw_provider_body():
    w=(ROOT/".github/workflows/r2-phase3-salex-kaggle-full-run.yml").read_text()
    assert "environment: rhombus-kaggle-production" in w
    assert "response.text[:3000]" not in w
    assert "steps.safety_gate.outcome == 'success'" in w

def test_agent_does_not_access_kaggle_credentials():
    src=(ROOT/"rhombus/tools/mcp_server.py").read_text()
    assert "get_candidate_evidence" in src
    assert "KAGGLE_API_TOKEN" not in src and "kernels_push" not in src
