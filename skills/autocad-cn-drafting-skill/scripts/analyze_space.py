#!/usr/bin/env python3
"""Analyze ergonomics, clearance conflicts, and room space utilization."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from cad_common import load_json, load_rules, project_issues, write_json, write_text


EPSILON = 1e-7


def polygon_area(points: list[list[float]]) -> float:
    return abs(
        sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        )
    ) / 2.0


def orientation(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a: list[float], b: list[float], p: list[float]) -> bool:
    return (
        min(a[0], b[0]) - EPSILON <= p[0] <= max(a[0], b[0]) + EPSILON
        and min(a[1], b[1]) - EPSILON <= p[1] <= max(a[1], b[1]) + EPSILON
        and abs(orientation(a, b, p)) <= EPSILON
    )


def segments_intersect(
    a: list[float], b: list[float], c: list[float], d: list[float]
) -> bool:
    o1, o2, o3, o4 = orientation(a, b, c), orientation(a, b, d), orientation(c, d, a), orientation(c, d, b)
    if ((o1 > EPSILON and o2 < -EPSILON) or (o1 < -EPSILON and o2 > EPSILON)) and (
        (o3 > EPSILON and o4 < -EPSILON) or (o3 < -EPSILON and o4 > EPSILON)
    ):
        return True
    return any(
        (
            abs(o1) <= EPSILON and on_segment(a, b, c),
            abs(o2) <= EPSILON and on_segment(a, b, d),
            abs(o3) <= EPSILON and on_segment(c, d, a),
            abs(o4) <= EPSILON and on_segment(c, d, b),
        )
    )


def point_in_polygon(point: list[float], polygon: list[list[float]]) -> bool:
    inside = False
    x, y = point
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        if on_segment(first, second, point):
            return True
        if (first[1] > y) != (second[1] > y):
            crossing_x = (second[0] - first[0]) * (y - first[1]) / (second[1] - first[1]) + first[0]
            if x < crossing_x:
                inside = not inside
    return inside


def polygons_intersect(first: list[list[float]], second: list[list[float]]) -> bool:
    for index, a in enumerate(first):
        b = first[(index + 1) % len(first)]
        for second_index, c in enumerate(second):
            d = second[(second_index + 1) % len(second)]
            if segments_intersect(a, b, c, d):
                return True
    return point_in_polygon(first[0], second) or point_in_polygon(second[0], first)


def polygon_inside(inner: list[list[float]], outer: list[list[float]]) -> bool:
    return all(point_in_polygon(point, outer) for point in inner)


def door_swing_polygon(door: dict[str, Any], segments: int = 12) -> list[list[float]]:
    hinge = door["hinge"]
    width = float(door["width"])
    base = math.radians(float(door.get("angle", 0)))
    direction = -1 if door.get("swing", "left") == "right" else 1
    sweep = math.radians(float(door.get("opening_angle", 90))) * direction
    points = [hinge]
    for index in range(segments + 1):
        angle = base + sweep * index / segments
        points.append([hinge[0] + width * math.cos(angle), hinge[1] + width * math.sin(angle)])
    return points


def path_target_width(path: dict[str, Any], room: dict[str, Any], rules: dict[str, Any]) -> tuple[float, str]:
    profiles = rules["ergonomics"]["profiles"]
    names = path.get("user_profiles") or room.get("user_profiles") or ["general_adult"]
    target = 0.0
    governing = "general_adult"
    for name in names:
        width = float(profiles[name]["minimum_passage_width_mm"])
        if width > target:
            target, governing = width, name
    return target, governing


def analyze(project: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    errors, validation_warnings = project_issues(project, rules)
    if errors:
        return {
            "status": "invalid_project",
            "validation_errors": errors,
            "validation_warnings": validation_warnings,
            "rooms": [],
            "findings": [],
        }

    utilization = rules["ergonomics"]["space_utilization"]
    rooms = {room["id"]: room for room in project.get("rooms", [])}
    furniture_by_room: dict[str, list[dict[str, Any]]] = {room_id: [] for room_id in rooms}
    findings: list[dict[str, Any]] = []
    for item in project.get("furniture", []):
        room_id = item["room_id"]
        if room_id not in rooms:
            findings.append(
                {
                    "severity": "error",
                    "classification": "baseline",
                    "code": "UNKNOWN_FURNITURE_ROOM",
                    "object_id": item.get("id"),
                    "message": f"Furniture references unknown room '{room_id}'.",
                }
            )
            continue
        furniture_by_room[room_id].append(item)

    room_results: list[dict[str, Any]] = []
    for room_id, room in rooms.items():
        boundary = room["boundary"]
        room_area_mm2 = polygon_area(boundary)
        room_area_m2 = room_area_mm2 / 1_000_000
        furniture = furniture_by_room[room_id]
        footprint_area = sum(polygon_area(item["footprint"]) for item in furniture)
        clearance_area = sum(
            polygon_area(zone["polygon"])
            for item in furniture
            for zone in item.get("clearance_zones", [])
        )
        coverage = footprint_area / room_area_mm2 if room_area_mm2 else 1.0
        nominal_free_ratio = max(0.0, 1.0 - (footprint_area + clearance_area) / room_area_mm2) if room_area_mm2 else 0.0

        if room_area_m2 < float(utilization["minimum_room_area_m2"]):
            findings.append(
                {
                    "severity": "warning",
                    "classification": "baseline",
                    "code": "SMALL_ROOM_AREA",
                    "room_id": room_id,
                    "value_m2": round(room_area_m2, 3),
                    "message": "Room area is below the configurable ergonomic baseline.",
                }
            )
        if coverage > float(utilization["maximum_furniture_coverage_ratio"]):
            findings.append(
                {
                    "severity": "warning",
                    "classification": "baseline",
                    "code": "HIGH_FURNITURE_COVERAGE",
                    "room_id": room_id,
                    "ratio": round(coverage, 4),
                    "message": "Furniture footprint occupies too much of the room.",
                }
            )
        if nominal_free_ratio < float(utilization["minimum_circulation_reserve_ratio"]):
            findings.append(
                {
                    "severity": "warning",
                    "classification": "baseline",
                    "code": "LOW_CIRCULATION_RESERVE",
                    "room_id": room_id,
                    "ratio": round(nominal_free_ratio, 4),
                    "message": "Nominal free space after furniture and activity zones is low.",
                }
            )

        for item in furniture:
            if not polygon_inside(item["footprint"], boundary):
                findings.append(
                    {
                        "severity": "error",
                        "classification": "baseline",
                        "code": "FURNITURE_OUTSIDE_ROOM",
                        "room_id": room_id,
                        "object_id": item.get("id"),
                        "message": "Furniture footprint extends outside the room boundary.",
                    }
                )
            for zone in item.get("clearance_zones", []):
                if not polygon_inside(zone["polygon"], boundary):
                    findings.append(
                        {
                            "severity": "warning",
                            "classification": zone.get("classification", "baseline"),
                            "code": "CLEARANCE_OUTSIDE_ROOM",
                            "room_id": room_id,
                            "object_id": item.get("id"),
                            "zone": zone.get("name", "clearance"),
                            "message": "Required activity clearance extends outside the room.",
                        }
                    )
                for other in furniture:
                    if other is not item and polygons_intersect(zone["polygon"], other["footprint"]):
                        findings.append(
                            {
                                "severity": "warning",
                                "classification": zone.get("classification", "baseline"),
                                "code": "CLEARANCE_CONFLICT",
                                "room_id": room_id,
                                "object_id": item.get("id"),
                                "conflicts_with": other.get("id"),
                                "zone": zone.get("name", "clearance"),
                                "message": "An activity clearance overlaps another furniture footprint.",
                            }
                        )

        for first_index, first in enumerate(furniture):
            for second in furniture[first_index + 1 :]:
                if polygons_intersect(first["footprint"], second["footprint"]):
                    findings.append(
                        {
                            "severity": "error",
                            "classification": "baseline",
                            "code": "FURNITURE_COLLISION",
                            "room_id": room_id,
                            "object_id": first.get("id"),
                            "conflicts_with": second.get("id"),
                            "message": "Furniture footprints overlap.",
                        }
                    )

        room_results.append(
            {
                "room_id": room_id,
                "name": room.get("name", room_id),
                "area_m2": round(room_area_m2, 3),
                "furniture_area_m2": round(footprint_area / 1_000_000, 3),
                "activity_clearance_area_m2": round(clearance_area / 1_000_000, 3),
                "furniture_coverage_ratio": round(coverage, 4),
                "nominal_circulation_reserve_ratio": round(nominal_free_ratio, 4),
                "user_profiles": room.get("user_profiles", ["general_adult"]),
            }
        )

    for path in project.get("circulation_paths", []):
        room = rooms.get(path.get("room_id"))
        if not room:
            findings.append(
                {
                    "severity": "error",
                    "classification": "baseline",
                    "code": "UNKNOWN_PATH_ROOM",
                    "object_id": path.get("id"),
                    "message": "Circulation path references an unknown room.",
                }
            )
            continue
        target, profile = path_target_width(path, room, rules)
        actual = float(path["clear_width"])
        if actual < target:
            findings.append(
                {
                    "severity": "error" if path.get("classification") == "code" else "warning",
                    "classification": path.get("classification", "baseline"),
                    "code": "INSUFFICIENT_PATH_WIDTH",
                    "object_id": path.get("id"),
                    "room_id": room["id"],
                    "actual_mm": actual,
                    "target_mm": target,
                    "governing_profile": profile,
                    "message": "Declared clear path width is below the governing profile.",
                }
            )

    all_furniture = project.get("furniture", [])
    for door in project.get("doors", []):
        sweep = door_swing_polygon(door)
        for item in all_furniture:
            if polygons_intersect(sweep, item["footprint"]):
                findings.append(
                    {
                        "severity": "error",
                        "classification": "baseline",
                        "code": "DOOR_SWING_CONFLICT",
                        "object_id": door.get("id"),
                        "conflicts_with": item.get("id"),
                        "message": "Door swing overlaps a furniture footprint.",
                    }
                )

    severities = {item["severity"] for item in findings}
    status = "fail" if "error" in severities else "pass_with_warnings" if findings else "pass"
    return {
        "status": status,
        "rules_version": rules.get("rules_version"),
        "rooms": room_results,
        "findings": findings,
        "disclaimer": "Code, ergonomic baseline, and advisory findings require project-specific professional review.",
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Ergonomics and Space Utilization",
        "",
        f"- Status: **{result['status']}**",
        f"- Rules version: `{result.get('rules_version', 'unknown')}`",
        "",
        "## Room Metrics",
        "",
        "| Room | Area m2 | Furniture % | Circulation reserve % | Profiles |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for room in result.get("rooms", []):
        lines.append(
            f"| {room['name']} | {room['area_m2']:.3f} | "
            f"{room['furniture_coverage_ratio'] * 100:.1f} | "
            f"{room['nominal_circulation_reserve_ratio'] * 100:.1f} | "
            f"{', '.join(room['user_profiles'])} |"
        )
    lines.extend(["", "## Findings", ""])
    for item in result.get("findings", []):
        lines.append(
            f"- **{item['severity'].upper()} / {item['classification']} / {item['code']}**: "
            f"{item['message']}"
        )
    if not result.get("findings"):
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `code`: traced to a cited regulation or explicit project requirement.",
            "- `baseline`: configurable ergonomic design value, not automatically statutory.",
            "- `advisory`: recommendation requiring human judgement.",
            "",
            f"> {result.get('disclaimer', '')}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--rules")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    project = load_json(args.project)
    rules = load_rules(args.rules)
    result = analyze(project, rules)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "space-analysis.json", result)
    write_text(output_dir / "space-analysis.md", markdown_report(result))
    print(f"Space analysis: {result['status']}")
    return 2 if result["status"] in {"invalid_project", "fail"} else 0


if __name__ == "__main__":
    sys.exit(main())
