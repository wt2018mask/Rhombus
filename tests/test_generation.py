"""Placeholder test suite for rudeus.generation."""

import rudeus.generation


def test_generation_module_namespace():
    """Verify generation package is importable and has docstring."""
    assert rudeus.generation.__doc__ is not None
    assert "G1 Generation" in rudeus.generation.__doc__
    assert "G2 Generation" in rudeus.generation.__doc__
