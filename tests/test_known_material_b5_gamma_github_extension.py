from pathlib import Path


def test_gamma_github_extension_is_exact_and_kaggle_is_manual_only():
    github = Path(
        ".github/workflows/r2-gamma-transport-extension-github.yml"
    ).read_text(encoding="utf-8")
    kaggle = Path(
        ".github/workflows/r2-gamma-transport-extension-kaggle.yml"
    ).read_text(encoding="utf-8")

    assert "name: R2 Gamma Transport Extension GitHub CPU" in github
    assert "runs-on: ubuntu-24.04" in github
    assert "timeout-minutes: 120" in github
    assert "--device cpu" in github
    assert "rudeus.mlip.run_p25_extension" in github
    assert "rudeus.mlip.freeze_p25_extension_authorization" in github
    assert "rudeus.mlip.freeze_p25_transition_environment" in github
    assert "classify_transport_regime" in github

    assert "37523686854" in github
    assert "37545842461" in github
    assert "37558945417" in github
    assert "df4431260652d2ea" in github
    assert "f691326014cdb510" in github
    assert (
        "b68c805b8f69bb2346ad3f5337cf5df64d9dd0c882af74bed397dcc00af34f02"
        in github
    )
    assert (
        "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"
        not in github
    )

    # Kaggle remains available only as an explicit fallback, never automatic.
    assert "workflow_dispatch:" in kaggle
    assert "pull_request:" not in kaggle
