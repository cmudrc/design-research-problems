# IDETC 2025-2024 Ideation Audit

Working notes for auditing IDETC proceedings against
`src/design_research_problems/_assets/ideation/catalog.toml`.

## Scope

- Goal: identify ideation- or prompt-relevant IDETC papers that are missing
  from the packaged ideation catalog.
- Source proceedings:
  - `conferences/2025 IDETC/`
  - `conferences/2024 IDETC/`
- Current focus:
  - papers that expose reusable design prompts, task briefs, study materials,
    or structured ideation experiments
  - not every paper that merely mentions creativity or AI

## 2025 IDETC

### Already represented in catalog

| Paper | DETC ID | Catalog status | Notes |
| --- | --- | --- | --- |
| Musical Playlists to Improve the Ideation Environment: An Exploratory Study | `DETC2025-164691` | Present | Four verbatim prompt variants already captured. |
| Impact of Problem Brief Characteristics and Influencing Factors on Design Outcomes in a Project-Based Engineering Course | `DETC2025-168538` | Present | Four project briefs already captured. |

### Candidate papers under review

| Paper | DETC ID | Status | Notes |
| --- | --- | --- | --- |
| Analogical Saturation and Affordance in Ideation | `DETC2025-167284` | Skip | Ideation study confirmed, but the accessible text points to varying class project statements rather than a stable reusable prompt. |
| Influence of AI Use on Creativity in a Speculative Design Process | `DETC2025-168557` | Skip | The main reusable artifact is a Futures Wheel process around the future of aeronautics, not a clearly recoverable prompt-family addition. |
| Designing Trust: How System-Level Design Attributes Shape AI-Assisted Design Ideation | `DETC2025-168783` | Partial capture | The proceedings name four sustainable household prompt topics and print the AIDA intro text. Follow-up on the cited upstream paper recovered the full sustainable washing-machine prompt, but the accessible text still does not fully print the lighting, HVAC, or toilet prompt wording. |
| Enhancing Usability and Functionality: A Study of Prototyping and Testing for a Creativity Assessment Platform | `DETC2025-169554` | Skip | Appears to be platform evaluation rather than a source of reusable design briefs. |
| Chain-of-Thought for Design Creativity Evaluation | `DETC2025-167500` | Skip | Creativity-evaluation method paper, not a prompt source. |
| Prompt Engineering for Requirements Elicitation: A Comparative Evaluation of Eight Techniques Using O1 | `DETC2025-169451` | Skip | Prompt-engineering methodology sits outside the current ideation prompt catalog scope. |

### Early observations

- `DETC2025-167284` is clearly an ideation experiment, but the extracted text
  so far suggests participants worked on varying project statements prepared in
  class. That may make it non-catalogable if no stable prompt text is given.
- `DETC2025-168557` uses a Futures Wheel activity centered on the future of
  aeronautics. The current extraction suggests the study may report process
  prompts rather than reusable design briefs.
- `DETC2025-168783` was worth following up because it explicitly states
  participants designed sustainable washing machines, lighting systems, HVAC
  systems, and toilets for households.
- Follow-up on the cited upstream source (`Liao & MacDonald, 2021`,
  `10.3390/su13095227`) recovered a full washing-machine prompt and that prompt
  has now been added to the catalog.
- Remaining unresolved 2025 household prompts:
  - sustainable lighting systems
  - sustainable HVAC systems
  - sustainable toilets
  The accessible 2025 proceedings text names these themes but does not print
  their full wording, so they remain uncaptured for now.

## 2024 IDETC

### Candidate pool

Initial scan complete; confirmed candidate papers now include:
- `DETC2024-146351`
- `DETC2024-142619`
- `DETC2024-143871`
- `DETC2024-143225`
- `DETC2024-142785`
- `DETC2024-146409`

### Catalog additions made

- `DETC2024-143871`
  - upgraded the existing spill-proof coffee-cup family with verbatim wording
    from the 2024 paper's adapted Jansson-and-Smith prompt
- `DETC2024-142619`
  - added `prompt_sub_saharan_wash_access_eli`
- `DETC2024-146351`
  - added example prompts for hearing-impairment group conversations, delivery
    truck route efficiency, and reducing construction impact on local
    ecosystems
- `DETC2024-142785`
  - added a verbatim peanut-shelling prompt variant and a new milk-frothing
    prompt entry from the appendices
- `DETC2024-143225`
  - added the wall-offset parallel-tube mounting challenge
- `DETC2024-146409`
  - added the outdoor-toy ideation task for children ages 5-8

### Remaining 2024 notes

- `DETC2024-143166` (`AutoTRIZ`) looked more like a method/tool paper using
  case problems than a source of reusable prompt briefs for this catalog.
- `DETC2024-143598` (`Elicitron`) focused on requirements-elicitation
  simulation rather than recoverable ideation prompt packets.
