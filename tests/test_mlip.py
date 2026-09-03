"""Placeholder test suite for rudeus.mlip."""

import rudeus.mlip


def test_mlip_module_namespace():
    """Verify mlip package is importable and has docstring."""
    assert rudeus.mlip.__doc__ is not None
    assert "medium-mpa-0" in rudeus.mlip.__doc__
    assert "P1" in rudeus.mlip.__doc__
    assert "P2" in rudeus.mlip.__doc__
    assert "P3" in rudeus.mlip.__doc__
