from pathlib import Path


def test_completed_gamma_extension_reclassification_is_bound_exactly():
    workflow = Path(
        ".github/workflows/r2-gamma-transport-extension-reclassify.yml"
    ).read_text(encoding="utf-8")

    assert "37565227536" in workflow
    assert "11459255242" in workflow
    assert "f691326014cdb510" in workflow
    assert (
        "7ab21ad71eac807e1377b7c2d138421c5d0f1c76ec33e7e05cd71e7dc33e9077"
        in workflow
    )
    assert "production_steps_completed" in workflow
    assert "classify_transport_regime" in workflow
    assert "verify_traj_artifact" in workflow
