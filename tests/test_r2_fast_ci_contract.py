from pathlib import Path


def test_r2_fast_ci_is_bounded_and_keeps_canonical_wave2_separate():
    text = Path(".github/workflows/r2-fast-ci.yml").read_text(encoding="utf-8")

    assert "name: R2 Fast CI" in text
    assert "timeout-minutes: 8" in text
    assert "compileall -q rhombus scripts/development" in text
    assert "continuity.py check-pr" in text
    assert "tests/test_p2.py" in text
    assert "tests/test_known_material_b5_gamma_transport_regime_evidence.py" in text

    # Fast CI must not silently become another full canonical suite.
    assert "tests/test_known_material_*.py" not in text
    assert "render_cubic_llzo" not in text
    assert "run_failure_controls.py" not in text

    wave2 = Path(
        ".github/workflows/wave2-synthetic-e2e.yml"
    ).read_text(encoding="utf-8")
    assert "name: Wave 2 Canonical Synthetic E2E" in wave2
