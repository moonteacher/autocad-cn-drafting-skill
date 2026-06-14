# AutoCAD CN Drafting Skill

An alpha Codex/Agent Skill for producing and auditing two-dimensional AutoCAD
architectural and interior drawing packages with:

- configurable Chinese drafting conventions;
- text, dimensioned-image, SVG, and structured JSON workflows;
- cross-platform AutoLISP for full AutoCAD on Windows and macOS;
- ergonomics, activity-clearance, circulation, and space-utilization analysis;
- ASCII DXF layer, geometry, and duplicate-line auditing.

The project does **not** install itself into Codex. The distributable Skill is in
[`skills/autocad-cn-drafting-skill`](skills/autocad-cn-drafting-skill).

中文说明见 [`README.zh-CN.md`](README.zh-CN.md)。

## Alpha Workflow

```bash
SKILL=skills/autocad-cn-drafting-skill

python3 "$SKILL/scripts/validate_project.py" examples/apartment/project.json
python3 "$SKILL/scripts/analyze_space.py" examples/apartment/project.json \
  --output-dir build/space
python3 "$SKILL/scripts/build_package.py" examples/apartment/project.json \
  --output-dir build/apartment
```

In full AutoCAD, load `build/apartment/autocad-cn-drafting.lsp`, run `CADBUILD`,
review the drawing, then run `CADAUDIT`. Save DWG, export ASCII DXF, and audit it:

```bash
python3 "$SKILL/scripts/audit_dxf.py" exported.dxf --output-dir build/dxf-audit
```

## Status

`v0.2 alpha`. Automated tests run without AutoCAD, but real DWG rendering and
plot output still require human verification in AutoCAD. Do not use generated
drawings for construction without qualified professional review.

## Learning Dataset

The repository includes a provenance-first workflow for organizing authorized
floor-plan references. Public visibility on a social platform is not treated as
permission to copy or train. Use `register_plan_reference.py`,
`validate_learning_dataset.py`, and `summarize_design_patterns.py` to build a
traceable local dataset without committing source media to this repository.

## Test

```bash
python3 -m unittest discover -s tests -v
python3 /path/to/skill-creator/scripts/quick_validate.py \
  skills/autocad-cn-drafting-skill
```

## License

MIT. Referenced standards remain the property of their publishers; this
repository provides original summaries and configurable implementation rules,
not copies of standard texts.
