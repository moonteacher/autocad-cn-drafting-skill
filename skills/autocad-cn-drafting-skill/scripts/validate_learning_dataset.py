#!/usr/bin/env python3
"""Validate provenance, annotations, duplicates, and dataset split isolation."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from learning_common import (
    PLATFORMS,
    RIGHTS_BASES,
    SPLITS,
    TRAINING_RIGHTS,
    annotation_issues,
    load_annotation,
    read_manifest,
    resolve_dataset_path,
    sha256_file,
)


def validate(dataset_dir: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        records = read_manifest(dataset_dir)
    except ValueError as exc:
        return {"status": "fail", "records": 0, "errors": [str(exc)], "warnings": []}

    ids: set[str] = set()
    hashes: dict[str, list[dict]] = defaultdict(list)
    for index, record in enumerate(records):
        prefix = f"record[{index}]"
        sample_id = str(record.get("sample_id", ""))
        if not sample_id:
            errors.append(f"{prefix}: sample_id is required.")
        elif sample_id in ids:
            errors.append(f"{prefix}: duplicate sample_id '{sample_id}'.")
        ids.add(sample_id)

        platform = record.get("platform")
        rights = record.get("rights_basis")
        split = record.get("split")
        if platform not in PLATFORMS:
            errors.append(f"{prefix}: invalid platform '{platform}'.")
        if rights not in RIGHTS_BASES:
            errors.append(f"{prefix}: invalid rights_basis '{rights}'.")
        if split not in SPLITS:
            errors.append(f"{prefix}: invalid split '{split}'.")
        if platform in {"xiaohongshu", "douyin"} and not record.get("source_url"):
            errors.append(f"{prefix}: platform record requires source_url.")
        if rights == "reference_only" and record.get("media_path"):
            errors.append(f"{prefix}: reference_only record cannot contain media.")
        if rights == "reference_only" and split in {"train", "val", "test"}:
            errors.append(f"{prefix}: reference_only record cannot enter a training split.")

        media_path = record.get("media_path")
        media_hash = record.get("media_sha256")
        if media_path:
            try:
                media = resolve_dataset_path(dataset_dir, media_path)
            except ValueError as exc:
                errors.append(f"{prefix}: {exc}")
            else:
                if not media.is_file():
                    errors.append(f"{prefix}: missing media '{media_path}'.")
                else:
                    actual_hash = sha256_file(media)
                    if actual_hash != media_hash:
                        errors.append(f"{prefix}: media hash mismatch.")
                    hashes[actual_hash].append(record)
        elif split in {"train", "val", "test"}:
            errors.append(f"{prefix}: training split requires stored authorized media.")

        annotation_path = record.get("annotation_path")
        if annotation_path:
            try:
                annotation_file = resolve_dataset_path(dataset_dir, annotation_path)
                annotation = load_annotation(annotation_file)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{prefix}: invalid annotation: {exc}")
            else:
                errors.extend(
                    f"{prefix}: {issue}"
                    for issue in annotation_issues(annotation, sample_id)
                )
        elif split in {"train", "val", "test"}:
            errors.append(f"{prefix}: training split requires an annotation.")

        if rights in TRAINING_RIGHTS and not record.get("permission_note") and rights != "owned":
            errors.append(f"{prefix}: rights basis requires a permission note.")
        if split == "unassigned":
            warnings.append(f"{prefix}: sample '{sample_id}' has no final split.")

    for media_hash, duplicate_records in hashes.items():
        if len(duplicate_records) < 2:
            continue
        sample_ids = sorted(record["sample_id"] for record in duplicate_records)
        split_names = {record.get("split") for record in duplicate_records}
        errors.append(f"duplicate media hash {media_hash}: {', '.join(sample_ids)}.")
        if len(split_names & {"train", "val", "test"}) > 1:
            errors.append(
                f"split leakage for duplicate media: {', '.join(sample_ids)}."
            )

    status = "fail" if errors else "pass_with_warnings" if warnings else "pass"
    return {
        "status": status,
        "records": len(records),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_dir")
    parser.add_argument("--json-report")
    args = parser.parse_args()
    result = validate(Path(args.dataset_dir).resolve())
    if args.json_report:
        Path(args.json_report).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Learning dataset: {result['status']} ({result['records']} records)")
    for item in result["errors"]:
        print(f"ERROR: {item}")
    for item in result["warnings"]:
        print(f"WARNING: {item}")
    return 2 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
