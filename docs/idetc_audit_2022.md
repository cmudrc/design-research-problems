# IDETC 2022 Ideation Audit

Working notes for auditing `conferences/2022 IDETC/` against
`src/design_research_problems/_assets/ideation/catalog.toml`.

## Scope

- Goal: identify IDETC 2022 papers that expose reusable ideation prompts,
  task briefs, or participant-facing study materials not yet captured in the
  ideation catalog.
- Focus:
  - participant-facing engineering design prompts
  - appendix or figure materials that print reusable briefs
  - studies that materially deepen prompt coverage rather than only discussing
    creativity in general

## Confirmed 2022 additions

- `DETC2022-91313`
  - added `prompt_mass_production_corn_shucker`
  - added `prompt_peanut_shelling_50kg_per_hour`
  - appendix prints both full task packets verbatim
- `DETC2022-90024`
  - added `prompt_long_range_dtss_inspection`
  - added `prompt_dexterous_aerial_manipulation`
  - the two aerial-robot workshop briefs were recoverable from the figure
    panels after visual inspection of the proceedings PDF

## Already represented or not a new catalog gap

- `DETC2022-90029`
  - sustainable-design evaluation study using the Sub-Saharan clean-water and
    sanitation brief
  - the paper points to an earlier prompt source and does not fully print the
    complete brief in the accessible text; the family is already represented in
    the catalog from later verbatim coverage
- `DETC2022-91313`
  - the appendix peanut-sheller brief adds a richer study-specific variant, but
    the underlying peanut-shelling family was already present before this pass

## Skips

- `DETC2022-91059`
  - empathetic-chatbot interaction study for advising conversations, not an
    engineering ideation brief
- `DETC2022-89723`
  - computational visual-analogy method paper, not a source of participant
    prompts
- `DETC2022-88924`
  - empathy-measurement interview study, not a design-brief source
- `DETC2022-87505`
  - machine-versus-human exploratory-creativity comparison, but the task set is
    graphic/product text prompts rather than engineering problem briefs
