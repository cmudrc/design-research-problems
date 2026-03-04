"""Compatibility alias for shared battery layout helpers."""

from __future__ import annotations

import sys

from design_research_problems.problems._domains import battery_layout as _backend

sys.modules[__name__] = _backend
