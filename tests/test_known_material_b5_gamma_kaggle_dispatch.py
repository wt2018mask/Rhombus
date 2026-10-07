from pathlib import Path


def test_gamma_kaggle_dispatch_is_exact_private_and_fail_closed():
    workflow = Path(
        ".github/workflows/r2-gamma-transport-extension-kaggle.yml"
    ).read_text(encoding="utf-8")
    driver = Path(
        "scripts/kaggle/gamma_transport_extension.py"
    ).read_text(encoding="utf-8")

    assert "wt2018mask/rhombus-gamma-transport-extension-input" in workflow
    assert "wt2018mask/rhombus-gamma-transport-extension-run" in workflow
    assert '"isPrivate": true' in workflow
    assert '"is_private": true' in workflow
    assert '"enable_gpu": true' in workflow
    assert '"enable_internet": true' in workflow

    assert "KAGGLE_API_TOKEN" in workflow
    assert "REMOTE_NOT_CONFIGURED" in workflow
    assert "scientific_verdict" in workflow
    assert "null" in workflow

    assert "37523686854" in workflow
    assert "37545842461" in workflow
    assert "37558945417" in workflow
    assert "df4431260652d2ea" in workflow
    assert "f691326014cdb510" in workflow
    assert (
        "b68c805b8f69bb2346ad3f5337cf5df64d9dd0c882af74bed397dcc00af34f02"
        in workflow
    )

    assert "rudeus.mlip.run_p25_extension" in driver
    assert "rudeus.mlip.freeze_p25_extension_authorization" in driver
    assert "classify_transport_regime" in driver
    assert "run_p25_extension" in driver
    assert "f691326014cdb510" not in driver
    assert "No scientific threshold is changed here." in driver
