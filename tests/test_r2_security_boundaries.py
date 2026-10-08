from pathlib import Path
from scripts.security.scan_secrets import scan_path


def test_security_scanner_blocks_private_keys_and_literal_keys(tmp_path):
    p=tmp_path/"example.txt"
    p.write_text('KAGGLE_API_TOKEN=abcdefghijklmnopqrstuvwxyz12345')
    assert any(code=="POSSIBLE_LITERAL_API_SECRET" for _,code in scan_path(p))
    p.write_text('-----BEGIN PRIVATE KEY-----')
    assert any(code=="PRIVATE_KEY_BLOCK" for _,code in scan_path(p))


def test_security_scanner_ignores_variable_references(tmp_path):
    p=tmp_path/"example.txt"
    p.write_text('KAGGLE_API_TOKEN: ${{ secrets.KAGGLE_API_TOKEN }}')
    assert scan_path(p)==[]


def test_production_approval_and_redaction_contract():
    workflow=Path(".github/workflows/r2-phase3-salex-kaggle-full-run.yml").read_text()
    assert "environment: kaggle-production" in workflow
    assert 'github.actor == \'wt2018mask\'' in workflow
    assert "PROVIDER_BODY_REDACTED" in workflow
    assert "RAW_KAGGLE_LOGS_SUPPRESSED_FOR_SECURITY" in workflow
    assert "python scripts/security/scan_secrets.py" in workflow
    assert "KAGGLE_API_TOKEN: ${{ secrets.KAGGLE_API_TOKEN }}" in workflow
    assert "KAGGLE_API_TOKEN: ${{ secrets.KAGGLE_API_TOKEN }}\n      GH_TOKEN" not in workflow


def test_ai_tool_default_denies_kaggle_dispatch():
    text=Path("rhombus/tools/evidence_query.py").read_text()
    assert 'if tool_name != "get_candidate_evidence":' in text
    assert "subprocess.run" not in text
