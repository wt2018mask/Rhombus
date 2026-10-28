"""Compatibility alias for the corrected version 2 manual importer.

Historical v1 remains in the immutable 0202 execution commit. Its partial
records require revalidation from the original archive.
"""
from rhombus.atomistics.manual_import_v2 import import_manual_result

__all__ = ('import_manual_result',)
