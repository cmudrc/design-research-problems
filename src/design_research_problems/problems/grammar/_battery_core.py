"""Compatibility alias for shared battery helper utilities."""

from __future__ import annotations

import sys

from design_research_problems.problems._domains import battery_core as _backend

sys.modules[__name__] = _backend
