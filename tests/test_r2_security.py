"""Security gates and secret-scanner contracts."""
from pathlib import Path

from scripts.security.redact_stream import redact
from scripts.security.audit_credential_history import classify

ROOT = Path(__file__).resolve().parents[1]

def test_provider_error_text_scrubbed(monkeypatch):
    monkeypatch.setenv("KAGGLE_API_TOKEN", "example-not-a-real-token-12345")
    source = (
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456\n"
        "api_key=abcdefg123456789\n"
        "KAGGLE_API_TOKEN=example-not-a-real-token-12345\n"
        "RuntimeError: frozen WBM source unavailable"
    )
    clean = redact(source)
    assert "example-not-a-real-token" not in clean
    assert "abcdefghijklmnopqrstuvwxyz123456" not in clean
    assert "abcdefg123456789" not in clean
    assert "RuntimeError: frozen WBM source unavailable" in clean

def test_history_scanner_recognizes_auth_tokens():
    assert classify(b"Authorization: Bearer " + b"x" * 28) == [
        "authorization_bearer"
    ]

def test_kaggle_default_deny_and_protected_environment():
    controller = (ROOT / ".github/workflows/r2-phase3-salex-kaggle-full-run.yml").read_text()
    launcher = (ROOT / ".github/workflows/r2-phase3-salex-kaggle-launch.yml").read_text()
    assert "vars.KAGGLE_PRODUCTION_ENABLED == 'true'" in controller
    assert "vars.KAGGLE_PRODUCTION_ENABLED == 'true'" in launcher
    assert "environment: kaggle-production" in controller
    assert '"provider_body_redacted": True' in controller
    assert '"kaggle_error_body": body' not in controller
    assert 'body[:2000]' not in controller
    assert "scripts/security/redact_stream.py" in controller
    assert "permissions:\n  contents: read\n\nconcurrency:" in controller

def test_ai_gateway_does_not_expose_kaggle_dispatch():
    from rhombus.tools.evidence_query import list_tool_specs
    assert [x["function"]["name"] for x in list_tool_specs()] == [
        "get_candidate_evidence", "get_domain_assessment", "validate_candidate_structure", "build_evidence_manifest", "plan_scientific_task", "get_task_status"
    ]
    mcp = (ROOT / "rhombus/tools/mcp_server.py").read_text()
    assert "KAGGLE_API_TOKEN" not in mcp
    assert "kaggle kernels push" not in mcp
    assert 'run(transport="stdio")' in mcp


def test_running_kaggle_kernel_continuation_preserved_without_new_submit():
    """A security release must not orphan the running exact-bound CPU job."""
    import re
    controller = (ROOT / ".github/workflows/r2-phase3-salex-kaggle-full-run.yml").read_text()
    gating = controller.split("  controller:\n", 1)[1].split("    runs-on:", 1)[0]
    assert "vars.KAGGLE_PRODUCTION_ENABLED == 'true'" in gating
    assert "inputs.operation != 'submit'" in gating
    assert "inputs.expected_commit == '643b8a260b6fcff78bb02f3a63f348c29fd91317'" in gating
    assert "||" in gating
    assert gating.count("643b8a260b6fcff78bb02f3a63f348c29fd91317") == 1
    # Both guard terms must occur together in a single branch.
    assert re.search(r"inputs.operation != 'submit'\s*&&\s*inputs.expected_commit", gating)
