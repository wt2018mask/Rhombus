from pathlib import Path


def test_gamma_transport_regime_workflow_is_exact_and_transport_only():
    text = Path(
        ".github/workflows/r2-gamma-transport-regime.yml"
    ).read_text(encoding="utf-8")

    assert "df4431260652d2ea" in text
    assert "37545842461" in text
    assert (
        "b68c805b8f69bb2346ad3f5337cf5df64d9dd0c882af74bed397dcc00af34f02"
        in text
    )
    assert "4ab81ca72174667c" not in text
    assert "f47d66515f55ce3e" not in text
    assert "classify_transport_regime" in text
    assert '"conductivity" not in legacy' in text
