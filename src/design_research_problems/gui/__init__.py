"""Core GUI integrations for design-research-problems."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from design_research_problems._lazy_exports import module_dir, resolve_lazy_export

_EXPORTS: Final[dict[str, str]] = {
    "GUIAppId": "design_research_problems.gui._launcher:GUIAppId",
    "list_gui_apps": "design_research_problems.gui._launcher:list_gui_apps",
    "launch_gui": "design_research_problems.gui._launcher:launch_gui",
    "main": "design_research_problems.gui._launcher:main",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> object:
    """Resolve and cache one deferred GUI export."""
    return resolve_lazy_export(
        module_name=__name__,
        exports=_EXPORTS,
        export_name=name,
        namespace=globals(),
    )


def __dir__() -> list[str]:
    """Return module attributes, including deferred exports."""
    return module_dir(globals(), __all__)


if TYPE_CHECKING:
    from ._launcher import GUIAppId as GUIAppId
    from ._launcher import launch_gui as launch_gui
    from ._launcher import list_gui_apps as list_gui_apps
    from ._launcher import main as main
