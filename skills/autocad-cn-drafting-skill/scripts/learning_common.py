#!/usr/bin/env python3
"""Shared helpers for provenance-first floor-plan learning datasets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PLATFORMS = {"xiaohongshu", "douyin", "owned", "other"}
RIGHTS_BASES = {
    "reference_only",
    "owned",
    "explicit_permission",
    "licensed",
    "public_domain",
}
TRAINING_RIGHTS = RIGHTS_BASES - {"reference_only"}
SPLITS = {"unassigned", "reference", "train", "val", "test"}
ANNOTATION_LIST_FIELDS = {
    "quality_tags",
    "room_types",
    "layout_features",
    "ergonomics_observations",
}
RECOGNITION_CLASSES = {
    "walls",
    "doors",
    "windows",
    "rooms",
    "furniture",
    "dimensions",
    "text_regions",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(dataset_dir: Path) -> list[dict[str, Any]]:
    manifest = dataset_dir / "manifest.jsonl"
    if not manifest.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifest.jsonl line {line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"manifest.jsonl line {line_number} must be an object.")
        records.append(record)
    return records


def append_manifest(dataset_dir: Path, record: dict[str, Any]) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    with (dataset_dir / "manifest.jsonl").open(
        "a", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_annotation(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Annotation root must be an object.")
    return data


def annotation_issues(annotation: dict[str, Any], sample_id: str) -> list[str]:
    issues: list[str] = []
    if annotation.get("sample_id") != sample_id:
        issues.append("annotation.sample_id must match the manifest sample_id.")
    if not str(annotation.get("plan_type", "")).strip():
        issues.append("annotation.plan_type is required.")
    for field in sorted(ANNOTATION_LIST_FIELDS):
        value = annotation.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            issues.append(f"annotation.{field} must be an array of strings.")
    labels = annotation.get("recognition_labels")
    if not isinstance(labels, dict):
        issues.append("annotation.recognition_labels must be an object.")
    else:
        for label_class in sorted(RECOGNITION_CLASSES):
            if not isinstance(labels.get(label_class), list):
                issues.append(
                    f"annotation.recognition_labels.{label_class} must be an array."
                )
    return issues


def resolve_dataset_path(dataset_dir: Path, relative_path: str) -> Path:
    root = dataset_dir.resolve()
    target = (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"Dataset path escapes root: {relative_path}")
    return target
