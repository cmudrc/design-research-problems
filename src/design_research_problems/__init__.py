"""Curated public package interface with lazily resolved exports."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Final

from design_research_problems._lazy_exports import module_dir, resolve_lazy_export

_EXPORTS: Final[dict[str, str]] = {
    "Problem": "design_research_problems.problems:Problem",
    "ComputableProblem": "design_research_problems.problems:ComputableProblem",
    "ProblemKind": "design_research_problems.problems:ProblemKind",
    "ProblemMetadata": "design_research_problems.problems:ProblemMetadata",
    "ProblemTaxonomy": "design_research_problems.problems:ProblemTaxonomy",
    "Citation": "design_research_problems.problems:Citation",
    "ProblemAsset": "design_research_problems.problems:ProblemAsset",
    "TextProblem": "design_research_problems.problems:TextProblem",
    "DecisionProblem": "design_research_problems.problems:DecisionProblem",
    "DiscreteOptionDecisionProblem": "design_research_problems.problems:DiscreteOptionDecisionProblem",
    "EmpiricalChoiceDecisionProblem": "design_research_problems.problems:EmpiricalChoiceDecisionProblem",
    "OptimizationProblem": "design_research_problems.problems:OptimizationProblem",
    "OptimizationEvaluation": "design_research_problems.problems:OptimizationEvaluation",
    "GrammarProblem": "design_research_problems.problems:GrammarProblem",
    "GrammarTransition": "design_research_problems.problems:GrammarTransition",
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
    "list_problems": "design_research_problems._catalog:list_problems",
    "get_ideation_catalog": "design_research_problems.ideation:get_ideation_catalog",
}

__all__ = ["__version__", *_EXPORTS.keys()]

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
    from ._catalog import list_problems as list_problems
    from ._exceptions import MissingOptionalDependencyError as MissingOptionalDependencyError
    from ._exceptions import ProblemEvaluationError as ProblemEvaluationError
    from .ideation import EvidenceTier as EvidenceTier
    from .ideation import IdeationCatalog as IdeationCatalog
    from .ideation import IdeationPromptFamily as IdeationPromptFamily
    from .ideation import IdeationPromptRecord as IdeationPromptRecord
    from .ideation import IdeationPromptVariant as IdeationPromptVariant
    from .ideation import IdeationStudy as IdeationStudy
    from .ideation import get_ideation_catalog as get_ideation_catalog
    from .problems import Citation as Citation
    from .problems import ComputableProblem as ComputableProblem
    from .problems import DecisionProblem as DecisionProblem
    from .problems import DiscreteOptionDecisionProblem as DiscreteOptionDecisionProblem
    from .problems import EmpiricalChoiceDecisionProblem as EmpiricalChoiceDecisionProblem
    from .problems import GrammarProblem as GrammarProblem
    from .problems import GrammarTransition as GrammarTransition
    from .problems import OptimizationEvaluation as OptimizationEvaluation
    from .problems import OptimizationProblem as OptimizationProblem
    from .problems import Problem as Problem
    from .problems import ProblemAsset as ProblemAsset
    from .problems import ProblemKind as ProblemKind
    from .problems import ProblemMetadata as ProblemMetadata
    from .problems import ProblemTaxonomy as ProblemTaxonomy
    from .problems import TextProblem as TextProblem
