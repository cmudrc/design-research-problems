"""Export problem provenance and references for a paper-draft workflow.

## Introduction
Select a packaged ideation problem and carry its exact prompt lineage and curated
sources into the shared paper-contribution contract.

## Technical Implementation
1. Load writing support by stable problem ID.
2. Verify that every contribution citation resolves to an exported reference.
3. Print contribution and reporting-gap identifiers for downstream inspection.

## Expected Results
Prints contract version 0.1.0, three peanut-shelling references, Background and
Methods contributions, and a visible gap for the provisional source record.

## References
- docs/paper_contributions.rst
"""

from __future__ import annotations

import design_research_problems as drp


def main() -> None:
    """Collect and inspect one Experiments-compatible component packet."""
    packet = drp.collect_problem_paper_contributions("ideation_peanut_shelling")
    assert packet["schema_version"] == drp.PAPER_CONTRIBUTION_VERSION
    reference_keys = {reference["key"] for reference in packet["references"]}
    assert all(set(contribution["citation_keys"]) <= reference_keys for contribution in packet["contributions"])

    print("Paper contribution contract:", drp.PAPER_CONTRIBUTION_VERSION)
    print("Problem:", packet["source"]["component_id"])
    print("References:", len(packet["references"]))
    print(
        "Contributions:",
        ", ".join(item["contribution_id"] for item in packet["contributions"]),
    )
    print(
        "Reporting gaps:",
        ", ".join(item["gap_id"] for item in packet["reporting_gaps"]),
    )


if __name__ == "__main__":
    main()
