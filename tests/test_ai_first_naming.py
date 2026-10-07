from pathlib import Path


def test_canonical_rhombus_namespace_imports():
    import rhombus
    import rhombus.tools

    assert rhombus.__name__ == "rhombus"
    assert rhombus.tools.__name__ == "rhombus.tools"


def test_legacy_rudeus_namespace_remains_available():
    import rudeus

    assert rudeus.__name__ == "rudeus"


def test_ai_first_naming_contract_exists():
    root = Path(__file__).resolve().parents[1]
    text = (root / "docs/AI_FIRST_NAMING.md").read_text(encoding="utf-8")
    assert "Canonical Python package for all new v2 code: `rhombus`" in text
    assert "`rudeus` is legacy compatibility surface only" in text
    assert "`assess_finite_temperature_stability`" in text
    assert "`quantify_ionic_transport`" in text
