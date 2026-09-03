"""Placeholder test suite for rudeus.bench."""

import rudeus.bench


def test_bench_module_namespace():
    """Verify bench package is importable and has docstring."""
    assert rudeus.bench.__doc__ is not None
    assert "OBELiX" in rudeus.bench.__doc__
    assert "Filter enrichment" in rudeus.bench.__doc__
