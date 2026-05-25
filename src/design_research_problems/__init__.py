"""Curated public package interface with lazily resolved exports."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Final

from design_research_problems._lazy_exports import module_dir, resolve_lazy_export

_EXPORTS: Final[dict[str, str]] = {
    "Problem": "design_research_problems.problems:Problem",
    "ComputableProblem": "design_research_problems.problems:ComputableProblem",
    "ProblemKind": "design_research_problems.problems:ProblemKind",
    "ProblemMetadata": "design_research_problems.problems:ProblemMetadata",
    "ProblemCatalogSummary": "design_research_problems.problems:ProblemCatalogSummary",
    "ProblemTaxonomy": "design_research_problems.problems:ProblemTaxonomy",
    "Citation": "design_research_problems.problems:Citation",
    "ProblemAsset": "design_research_problems.problems:ProblemAsset",
    "TextProblem": "design_research_problems.problems:TextProblem",
    "DecisionEvaluation": "design_research_problems.problems:DecisionEvaluation",
    "DecisionProblem": "design_research_problems.problems:DecisionProblem",
    "OptimizationProblem": "design_research_problems.problems:OptimizationProblem",
    "OptimizationEvaluation": "design_research_problems.problems:OptimizationEvaluation",
    "GrammarProblem": "design_research_problems.problems:GrammarProblem",
    "GrammarTransition": "design_research_problems.problems:GrammarTransition",
    "MCPProblem": "design_research_problems.problems:MCPProblem",
    "ProblemRegistry": "design_research_problems._catalog:ProblemRegistry",
    "MissingOptionalDependencyError": "design_research_problems._exceptions:MissingOptionalDependencyError",
    "ProblemEvaluationError": "design_research_problems._exceptions:ProblemEvaluationError",
    "EvidenceTier": "design_research_problems.ideation:EvidenceTier",
    "IdeationPromptRecord": "design_research_problems.ideation:IdeationPromptRecord",
    "IdeationPromptVariant": "design_research_problems.ideation:IdeationPromptVariant",
    "IdeationPromptFamily": "design_research_problems.ideation:IdeationPromptFamily",
    "IdeationStudy": "design_research_problems.ideation:IdeationStudy",
    "IdeationCatalog": "design_research_problems.ideation:IdeationCatalog",
    "get_problem": "design_research_problems._catalog:get_problem",
    "get_problem_as": "design_research_problems._catalog:get_problem_as",
    "list_problems": "design_research_problems._catalog:list_problems",
    "search_problem_summaries": "design_research_problems._catalog:search_problem_summaries",
    "get_ideation_catalog": "design_research_problems.ideation:get_ideation_catalog",
}

__all__ = ["__version__", *_EXPORTS.keys()]
__all__.append("integration")

try:
    __version__ = version("design-research-problems")
except PackageNotFoundError:
    __version__ = "0+unknown"


def __getattr__(name: str) -> object:
    """Resolve and cache one deferred public export.

    Args:
        name: Public symbol name requested from the package module.

    Returns:
        Resolved export object.
    """
    if name == "integration":
        module = import_module("design_research_problems.integration")
        globals()[name] = module
        return module

    return resolve_lazy_export(
        module_name=__name__,
        exports=_EXPORTS,
        export_name=name,
        namespace=globals(),
    )


def __dir__() -> list[str]:
    """Return package attributes, including deferred exports.

    Returns:
        Sorted attribute list for interactive discovery.
    """
    return module_dir(globals(), __all__)


if TYPE_CHECKING:
    from ._catalog import ProblemRegistry as ProblemRegistry
    from ._catalog import get_problem as get_problem
    from ._catalog import get_problem_as as get_problem_as
    from ._catalog import list_problems as list_problems
    from ._catalog import search_problem_summaries as search_problem_summaries
    from ._exceptions import MissingOptionalDependencyError as MissingOptionalDependencyError
    from ._exceptions import ProblemEvaluationError as ProblemEvaluationError
    from .ideation import EvidenceTier as EvidenceTier
    from .ideation import IdeationCatalog as IdeationCatalog
    from .ideation import IdeationPromptFamily as IdeationPromptFamily
    from .ideation import IdeationPromptRecord as IdeationPromptRecord
    from .ideation import IdeationPromptVariant as IdeationPromptVariant
    from .ideation import IdeationStudy as IdeationStudy
    from .ideation import get_ideation_catalog as get_ideation_catalog
    from .integration import evaluate_problem_output as evaluate_problem_output
    from .integration import resolve_problem_binding as resolve_problem_binding
    from .problems import Citation as Citation
    from .problems import ComputableProblem as ComputableProblem
    from .problems import DecisionEvaluation as DecisionEvaluation
    from .problems import DecisionProblem as DecisionProblem
    from .problems import GrammarProblem as GrammarProblem
    from .problems import GrammarTransition as GrammarTransition
    from .problems import MCPProblem as MCPProblem
    from .problems import OptimizationEvaluation as OptimizationEvaluation
    from .problems import OptimizationProblem as OptimizationProblem
    from .problems import Problem as Problem
    from .problems import ProblemAsset as ProblemAsset
    from .problems import ProblemCatalogSummary as ProblemCatalogSummary
    from .problems import ProblemKind as ProblemKind
    from .problems import ProblemMetadata as ProblemMetadata
    from .problems import ProblemTaxonomy as ProblemTaxonomy
    from .problems import TextProblem as TextProblem
