from pathlib import Path


WORKFLOW = Path(".github/workflows/b5-dev-remaining-libh4-p2.yml")


def test_remaining_p2_workflow_targets_exact_two_libh4_units():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "4ab81ca72174667c" in text
    assert "f47d66515f55ce3e" in text
    assert "aee6596b93fa37b8cecf59c0724731723b2320ed0e6366e078bf591e286458e4" in text
    assert "0692867e4f86ca738cbc0be3f65a987c712880884a61850dae62a01007f71090" in text

    # Gamma-LiAlO2 already has corrected P2 evidence and must not rerun here.
    assert "df4431260652d2ea" not in text

    # Cubic Al-LLZO remains P0 INDETERMINATE and is not downstream-authorized.
    assert "llzo-cubic-al-stabilized" not in text

    assert text.count("material_key: libh4-phase-transition-pair") == 2
    assert "component_label: hexagonal" in text
    assert "component_label: orthorhombic" in text


def test_remaining_p2_workflow_preserves_p2_transport_neutrality():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'assert "transport_state" not in result' in text
    assert "b5_p2_authorization_v1.json" in text
