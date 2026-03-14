# IDETC 2023 Ideation Audit

Working notes for auditing `conferences/2023 IDETC/` against
`src/design_research_problems/_assets/ideation/catalog.toml`.

## Scope

- Goal: identify IDETC 2023 papers that expose reusable ideation prompts,
  task briefs, or participant-facing study materials that are not yet captured
  in the ideation catalog.
- Focus:
  - participant-facing engineering design prompts
  - study appendices or figures that print reusable task materials
  - prompt lineage that materially changes catalog coverage
- Out of scope:
  - survey-only creativity papers
  - chatbot or question-set papers that do not present engineering ideation
    briefs
  - software-specific tasks without a stable recoverable prompt packet

## Confirmed 2023 additions

- `DETC2023-117127`
  - added `prompt_personal_entertainment_system`
  - accessible methods section reports the participant-facing task as:
    "design a future personal entertainment system"

## Already represented or not a new catalog gap

- `DETC2023-114673`
  - household-moving prompt is already represented in the catalog from the
    later 2025 playlists paper
  - 2023 provides an earlier printed version and adds the instruction to
    consider the physical setting, but it does not open a wholly new prompt
    family
- `DETC2023-114983`
  - appendix prints full milk-frother and peanut-shelling study packets
  - both problem families are already represented in the catalog from earlier
    and later sources, so this paper is lineage-enriching rather than a new
    family miss
- `DETC2023-116838`
  - uses the established 12 one-line Goucher-Lambert and Cagan style prompts
    for LLM generation
  - no new prompt families identified in the accessible text

## Skips

- `DETC2023-115318`
  - empathetic-chatbot trust study centered on student-advising conversations,
    not an engineering ideation brief
- `DETC2023-116725`
  - useful prompt-question set for social-impact reflection, but outside the
    current problem-brief catalog scope
- `DETC2023-116688`
  - creativity-climate survey and concept-screening analysis, not a prompt
    source
- `DETC2023-116874`
  - interactive robot-design task depends on the Build-a-Bot software
    environment rather than a stable text brief
