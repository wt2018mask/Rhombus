"""Placeholder test suite for rudeus.empirical."""

import rudeus.empirical


def test_empirical_module_namespace():
    """Verify empirical package is importable and has docstring."""
    assert rudeus.empirical.__doc__ is not None
    assert "OBELiX" in rudeus.empirical.__doc__
    assert "LiIon" in rudeus.empirical.__doc__
