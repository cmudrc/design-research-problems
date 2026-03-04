"""Compatibility alias for shared battery cell-model helpers."""

from __future__ import annotations

import sys

from design_research_problems.problems._domains import battery_cell_model as _backend

sys.modules[__name__] = _backend
