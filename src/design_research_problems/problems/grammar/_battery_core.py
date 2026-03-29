"""Legacy battery-core import path compatibility shim."""

import sys

from design_research_problems.problems._domains import battery_core as _battery_core

sys.modules[__name__] = _battery_core
