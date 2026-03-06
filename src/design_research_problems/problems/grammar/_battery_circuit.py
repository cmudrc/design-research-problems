"""Compatibility alias for the shared explicit battery-circuit backend."""

from __future__ import annotations

import sys

from design_research_problems.problems._domains import battery_circuit as _backend

sys.modules[__name__] = _backend
