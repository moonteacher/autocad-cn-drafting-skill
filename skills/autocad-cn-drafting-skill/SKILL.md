---
name: autocad-cn-drafting-skill
description: Create and audit two-dimensional AutoCAD architectural and interior drawings that follow a configurable Chinese drafting baseline. Organize authorized floor-plan learning references with provenance, annotation, deduplication, split-leakage checks, and aggregate design-pattern summaries. Use when Codex must turn a written brief, dimensioned image, SVG, or structured project JSON into AutoLISP for AutoCAD; standardize layers, text, dimensions, sheets, and title blocks; inspect an ASCII DXF; prepare a licensed floor-plan recognition dataset; or produce CAD and space-quality reports. Trigger for floor plans, interior plans, drawing reconstruction, CAD cleanup, CAD standards checks, DWG/DXF delivery preparation, authorized Xiaohongshu/Douyin design-reference analysis, and requests mentioning GB/T 50001 or GB/T 50104.
---

# AutoCAD CN Drafting

Create traceable drawing packages for full AutoCAD on Windows or macOS. Treat this
skill as drafting automation, not as statutory design approval.

## Workflow

1. Inspect the source and determine whether it is text, an image, SVG, or an
   existing ASCII DXF.
2. Read `references/project-format.md` before authoring project JSON.
3. For an image, require at least one trustworthy real-world dimension or a
   declared scale. Stop and ask for missing dimensions instead of guessing.
4. For SVG, run `scripts/svg_to_project.py`; pass a known SVG length and its
   real millimetre length when physical units are unavailable.
5. Complete the generated project JSON. Record assumptions in
   `metadata.assumptions` and unresolved items in `metadata.open_issues`.
6. Define room boundaries, furniture footprints, activity clearances, target
   user profiles, and circulation paths. Read `references/ergonomics.md`.
7. Run `scripts/analyze_space.py`, then `scripts/validate_project.py`. Do not generate a formal drawing package
   while validation errors or open issues remain.
8. Run `scripts/build_package.py` to generate the `.lsp`, manifest, project copy,
   and preflight report.
9. In full AutoCAD, load the generated `.lsp`, run `CADBUILD`, visually inspect
   the result, save DWG/DXF, and plot PDF. Read `references/autocad-runbook.md`
   for the exact operator sequence.
10. Export ASCII DXF and run `scripts/audit_dxf.py`. Resolve errors before
   delivery; document accepted warnings.

## Learning References

1. Read `references/learning-dataset.md` before collecting platform references.
2. Do not scrape, bypass access controls, remove watermarks, or download media
   merely because it is publicly viewable.
3. Register public links as `reference_only`. Store media for training only when
   the user owns it, has explicit permission, has a suitable license, or it is
   public domain.
4. Read `references/plan-semantics.md`, then create an annotation from
   `assets/plan-annotation-template.json`.
5. Run `scripts/register_plan_reference.py`, then
   `scripts/validate_learning_dataset.py`.
6. Run `scripts/summarize_design_patterns.py` to aggregate room combinations,
   layout features, quality conditions, and ergonomic observations.
7. Keep raw datasets outside the repository. Commit schemas, scripts, synthetic
   examples, and aggregate findings only.

## Commands

```bash
python3 scripts/validate_project.py project.json
python3 scripts/svg_to_project.py plan.svg --known-svg-length 240 \
  --known-mm-length 12000 --output project.json
python3 scripts/analyze_space.py project.json --output-dir space-analysis
python3 scripts/build_package.py project.json --output-dir build
python3 scripts/audit_dxf.py drawing.dxf --output-dir audit
python3 scripts/register_plan_reference.py --help
python3 scripts/validate_learning_dataset.py dataset
python3 scripts/summarize_design_patterns.py dataset --output-dir patterns
```

Use only Python's standard library. Keep project geometry in millimetres and
model space at 1:1. Use drawing scale only for annotation and sheet planning.

## Drawing Rules

- Load `assets/default_rules.json` unless the project supplies a reviewed custom
  rules file.
- Use BYLAYER color, linetype, and lineweight for generated entities.
- Preserve source geometry in a separate non-plot reference layer when tracing.
- Put uncertain or inferred content on `A-NPLT-REVIEW` and keep it out of formal
  output.
- Treat room function, occupant profile, activity zones, furniture footprints,
  reach ranges, door swings, and circulation as explicit design data.
- Separate cited code requirements from configurable ergonomic baselines and
  advisory recommendations in every report.
- Prefer usable clear space over nominal room area. Do not approve a layout only
  because its total area is sufficient.
- Never claim that automated checks cover fire safety, accessibility, structure,
  MEP coordination, code compliance, or professional sign-off.
- Read `references/standards.md` before changing the baseline rules.

## Failure Rules

- Stop when an image or unitless SVG lacks a trustworthy scale.
- Stop when wall endpoints, door handing, room use, or sheet requirements are
  materially ambiguous.
- Reject non-millimetre project files until they are converted.
- Reject binary DXF input; request an ASCII DXF export.
- Report missing fonts and plot devices. Do not silently substitute a commercial
  font or machine-specific PC3 file.

## Outputs

Produce:

- a validated project JSON;
- generated cross-platform AutoLISP exposing `CADBUILD` and `CADAUDIT`;
- a manifest with checksums and version information;
- a Markdown/JSON preflight report;
- a room-by-room ergonomic and space-utilization report;
- after AutoCAD execution, DWG, ASCII DXF, PDF, and a final DXF audit report.

This repository is `v0.2 alpha`. Require a human AutoCAD review before using any
output for construction.
