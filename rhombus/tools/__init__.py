"""Small, explicitly registered AI-facing Rhombus tool surface.

Tool calls are read-only until evidence and scientific execution contracts
individually authorize additional capabilities. No implicit legacy exports.
"""

from .evidence_query import ReadOnlyEvidenceTools, list_tool_specs

__all__ = ["ReadOnlyEvidenceTools", "list_tool_specs"]
