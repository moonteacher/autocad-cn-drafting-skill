#!/usr/bin/env python3
"""Shared validation and file helpers for the CAD drafting skill."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = SKILL_ROOT / "assets" / "default_rules.json"


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def load_rules(path: str | Path | None = None) -> dict[str, Any]:
    return load_json(path or DEFAULT_RULES)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def is_point(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(is_number(item) for item in value)
    )


def distance(a: Iterable[float], b: Iterable[float]) -> float:
    ax, ay = a
    bx, by = b
    return math.hypot(bx - ax, by - ay)


def project_issues(
    project: dict[str, Any], rules: dict[str, Any] | None = None
) -> tuple[list[str], list[str]]:
    """Return validation errors and warnings without mutating the project."""
    rules = rules or load_rules()
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(project, dict):
        return ["Project root must be a JSON object."], warnings

    metadata = project.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object.")
        metadata = {}
    for key in ("project_name", "drawing_title"):
        if not str(metadata.get(key, "")).strip():
            errors.append(f"metadata.{key} is required.")
    if metadata.get("units") != "mm":
        errors.append("metadata.units must be 'mm'.")
    scale = metadata.get("scale")
    if not is_number(scale) or scale <= 0:
        errors.append("metadata.scale must be a positive number such as 50 or 100.")
    if metadata.get("open_issues"):
        errors.append("metadata.open_issues must be empty before formal generation.")

    source = project.get("source", {})
    if not isinstance(source, dict):
        errors.append("source must be an object.")
    else:
        source_type = source.get("type", "text")
        if source_type not in {"text", "image", "svg", "structured"}:
            errors.append("source.type must be text, image, svg, or structured.")
        if source_type in {"image", "svg"} and not source.get("scale_verified"):
            errors.append(
                "Image/SVG sources require source.scale_verified=true after a trustworthy dimension is confirmed."
            )

    drawing = project.get("drawing")
    if not isinstance(drawing, dict):
        errors.append("drawing must be an object.")
        drawing = {}
    sheet = drawing.get("sheet", "A3")
    if sheet not in rules.get("sheets", {}):
        errors.append(f"drawing.sheet '{sheet}' is not defined in the rules.")
    if drawing.get("orientation", "landscape") not in {"landscape", "portrait"}:
        errors.append("drawing.orientation must be landscape or portrait.")

    audit = rules.get("audit", {})
    walls = project.get("walls", [])
    if not isinstance(walls, list):
        errors.append("walls must be an array.")
        walls = []
    if not walls:
        warnings.append("No walls are defined.")
    seen_ids: set[str] = set()
    for index, wall in enumerate(walls):
        prefix = f"walls[{index}]"
        if not isinstance(wall, dict):
            errors.append(f"{prefix} must be an object.")
            continue
        object_id = str(wall.get("id", "")).strip()
        if not object_id:
            errors.append(f"{prefix}.id is required.")
        elif object_id in seen_ids:
            errors.append(f"Duplicate object id '{object_id}'.")
        else:
            seen_ids.add(object_id)
        if not is_point(wall.get("start")) or not is_point(wall.get("end")):
            errors.append(f"{prefix}.start and .end must be [x, y] points.")
        elif distance(wall["start"], wall["end"]) <= audit.get("coordinate_tolerance_mm", 0.01):
            errors.append(f"{prefix} has zero length.")
        thickness = wall.get("thickness")
        if not is_number(thickness):
            errors.append(f"{prefix}.thickness must be numeric.")
        elif not audit.get("minimum_wall_thickness_mm", 80) <= thickness <= audit.get(
            "maximum_wall_thickness_mm", 600
        ):
            warnings.append(f"{prefix}.thickness={thickness} mm is outside the configured range.")
        if wall.get("kind", "existing") not in {"existing", "new", "demolish"}:
            errors.append(f"{prefix}.kind must be existing, new, or demolish.")

    for collection, required_points in (
        ("doors", ("hinge",)),
        ("windows", ("start", "end")),
        ("rooms", ("label_point",)),
    ):
        items = project.get(collection, [])
        if not isinstance(items, list):
            errors.append(f"{collection} must be an array.")
            continue
        for index, item in enumerate(items):
            prefix = f"{collection}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object.")
                continue
            object_id = str(item.get("id", "")).strip()
            if object_id:
                if object_id in seen_ids:
                    errors.append(f"Duplicate object id '{object_id}'.")
                seen_ids.add(object_id)
            for key in required_points:
                if not is_point(item.get(key)):
                    errors.append(f"{prefix}.{key} must be an [x, y] point.")
            if collection == "rooms":
                boundary = item.get("boundary")
                if not isinstance(boundary, list) or len(boundary) < 3 or not all(
                    is_point(point) for point in boundary
                ):
                    errors.append(f"{prefix}.boundary must contain at least three [x, y] points.")
                profiles = item.get("user_profiles", ["general_adult"])
                valid_profiles = set(rules.get("ergonomics", {}).get("profiles", {}))
                if not isinstance(profiles, list) or not profiles:
                    errors.append(f"{prefix}.user_profiles must be a non-empty array.")
                else:
                    unknown = sorted(set(profiles) - valid_profiles)
                    if unknown:
                        errors.append(f"{prefix} has unknown user profiles: {', '.join(unknown)}.")

    for index, door in enumerate(project.get("doors", [])):
        width = door.get("width") if isinstance(door, dict) else None
        if not is_number(width):
            errors.append(f"doors[{index}].width must be numeric.")
        elif not audit.get("minimum_door_width_mm", 600) <= width <= audit.get(
            "maximum_door_width_mm", 2400
        ):
            warnings.append(f"doors[{index}].width={width} mm is outside the configured range.")
        if isinstance(door, dict) and door.get("swing", "left") not in {"left", "right"}:
            errors.append(f"doors[{index}].swing must be left or right.")

    geometry = project.get("geometry", [])
    if not isinstance(geometry, list):
        errors.append("geometry must be an array.")
    else:
        valid_types = {"line", "polyline", "polygon", "rectangle", "circle"}
        for index, item in enumerate(geometry):
            if not isinstance(item, dict) or item.get("type") not in valid_types:
                errors.append(f"geometry[{index}] has an unsupported type.")

    annotations = project.get("annotations", {})
    if not isinstance(annotations, dict):
        errors.append("annotations must be an object.")
    elif not annotations.get("dimensions"):
        warnings.append("No dimensions are defined.")

    furniture = project.get("furniture", [])
    if not isinstance(furniture, list):
        errors.append("furniture must be an array.")
    else:
        for index, item in enumerate(furniture):
            prefix = f"furniture[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object.")
                continue
            if not str(item.get("room_id", "")).strip():
                errors.append(f"{prefix}.room_id is required.")
            footprint = item.get("footprint")
            if not isinstance(footprint, list) or len(footprint) < 3 or not all(
                is_point(point) for point in footprint
            ):
                errors.append(f"{prefix}.footprint must contain at least three points.")
            for zone_index, zone in enumerate(item.get("clearance_zones", [])):
                polygon = zone.get("polygon") if isinstance(zone, dict) else None
                if not isinstance(polygon, list) or len(polygon) < 3 or not all(
                    is_point(point) for point in polygon
                ):
                    errors.append(
                        f"{prefix}.clearance_zones[{zone_index}].polygon must contain at least three points."
                    )

    circulation = project.get("circulation_paths", [])
    if not isinstance(circulation, list):
        errors.append("circulation_paths must be an array.")
    else:
        for index, path in enumerate(circulation):
            prefix = f"circulation_paths[{index}]"
            if not isinstance(path, dict):
                errors.append(f"{prefix} must be an object.")
                continue
            centerline = path.get("centerline")
            if not isinstance(centerline, list) or len(centerline) < 2 or not all(
                is_point(point) for point in centerline
            ):
                errors.append(f"{prefix}.centerline must contain at least two points.")
            if not is_number(path.get("clear_width")) or path["clear_width"] <= 0:
                errors.append(f"{prefix}.clear_width must be a positive number.")

    return errors, warnings


def preflight_report(
    project: dict[str, Any], errors: list[str], warnings: list[str]
) -> str:
    metadata = project.get("metadata", {})
    lines = [
        "# CAD Preflight Report",
        "",
        f"- Project: {metadata.get('project_name', 'Unnamed')}",
        f"- Drawing: {metadata.get('drawing_title', 'Untitled')}",
        f"- Status: {'FAIL' if errors else 'PASS WITH WARNINGS' if warnings else 'PASS'}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors)
    if not errors:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in warnings)
    if not warnings:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Review Boundary",
            "",
            "This automated check does not replace fire, accessibility, structural, MEP,",
            "code-compliance, or licensed professional review.",
            "",
        ]
    )
    return "\n".join(lines)
