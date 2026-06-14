#!/usr/bin/env python3
"""Aggregate authorized floor-plan annotations into reusable design patterns."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from learning_common import (
    TRAINING_RIGHTS,
    load_annotation,
    read_manifest,
    resolve_dataset_path,
)
from validate_learning_dataset import validate


FIELDS = {
    "plan_types": "plan_type",
    "quality_tags": "quality_tags",
    "room_types": "room_types",
    "layout_features": "layout_features",
    "ergonomics_observations": "ergonomics_observations",
}


def summarize(dataset_dir: Path, include_reference_only: bool = False) -> dict:
    records = read_manifest(dataset_dir)
    counters = {name: Counter() for name in FIELDS}
    platforms: Counter[str] = Counter()
    included_samples: list[str] = []
    for record in records:
        rights = record.get("rights_basis")
        if rights not in TRAINING_RIGHTS and not include_reference_only:
            continue
        annotation_path = record.get("annotation_path")
        if not annotation_path:
            continue
        annotation = load_annotation(resolve_dataset_path(dataset_dir, annotation_path))
        included_samples.append(record["sample_id"])
        platforms[record["platform"]] += 1
        for output_name, annotation_field in FIELDS.items():
            value = annotation.get(annotation_field, [])
            values = [value] if isinstance(value, str) else value
            counters[output_name].update(item for item in values if item)
    return {
        "included_samples": sorted(included_samples),
        "sample_count": len(included_samples),
        "platforms": dict(platforms.most_common()),
        **{
            name: dict(counter.most_common())
            for name, counter in counters.items()
        },
        "reference_only_included": include_reference_only,
    }


def markdown_report(result: dict) -> str:
    lines = [
        "# Floor-Plan Design Pattern Summary",
        "",
        f"- Samples: {result['sample_count']}",
        f"- Reference-only observations included: {result['reference_only_included']}",
        "",
    ]
    for section in (
        "platforms",
        "plan_types",
        "room_types",
        "layout_features",
        "ergonomics_observations",
        "quality_tags",
    ):
        lines.extend([f"## {section.replace('_', ' ').title()}", ""])
        values = result[section]
        lines.extend(f"- `{name}`: {count}" for name, count in values.items())
        if not values:
            lines.append("- None")
        lines.append("")
    lines.extend(
        [
            "> This report contains aggregate annotations, not copied platform media.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_dir")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--include-reference-only", action="store_true")
    args = parser.parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    validation = validate(dataset_dir)
    if validation["errors"]:
        print("ERROR: validate the learning dataset before summarizing.", file=sys.stderr)
        return 2
    result = summarize(dataset_dir, args.include_reference_only)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "design-patterns.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "design-patterns.md").write_text(
        markdown_report(result), encoding="utf-8"
    )
    print(f"Summarized {result['sample_count']} annotated samples.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
