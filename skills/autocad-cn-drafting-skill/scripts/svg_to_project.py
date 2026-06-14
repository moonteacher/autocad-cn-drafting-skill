#!/usr/bin/env python3
"""Convert basic SVG geometry into a scale-verified CAD project JSON."""

from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from cad_common import write_json


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
LENGTH_RE = re.compile(rf"^\s*({NUMBER})\s*(mm|cm|in|px)?\s*$")
PATH_TOKEN_RE = re.compile(rf"[A-Za-z]|{NUMBER}")


def parse_length(value: str | None) -> tuple[float | None, str | None]:
    if not value:
        return None, None
    match = LENGTH_RE.match(value)
    if not match:
        return None, None
    return float(match.group(1)), match.group(2) or "px"


def mat_mul(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    a1, b1, c1, d1, e1, f1 = a
    a2, b2, c2, d2, e2, f2 = b
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def transform_matrix(value: str | None) -> tuple[float, ...]:
    result = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    if not value:
        return result
    for name, raw in re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", value):
        nums = [float(item) for item in re.findall(NUMBER, raw)]
        if name == "translate" and nums:
            matrix = (1.0, 0.0, 0.0, 1.0, nums[0], nums[1] if len(nums) > 1 else 0.0)
        elif name == "scale" and nums:
            matrix = (nums[0], 0.0, 0.0, nums[1] if len(nums) > 1 else nums[0], 0.0, 0.0)
        elif name == "matrix" and len(nums) == 6:
            matrix = tuple(nums)
        elif name == "rotate" and nums:
            angle = math.radians(nums[0])
            rotate = (math.cos(angle), math.sin(angle), -math.sin(angle), math.cos(angle), 0.0, 0.0)
            if len(nums) >= 3:
                cx, cy = nums[1], nums[2]
                matrix = mat_mul(
                    mat_mul((1.0, 0.0, 0.0, 1.0, cx, cy), rotate),
                    (1.0, 0.0, 0.0, 1.0, -cx, -cy),
                )
            else:
                matrix = rotate
        else:
            raise ValueError(f"Unsupported SVG transform: {name}")
        result = mat_mul(result, matrix)
    return result


def apply_matrix(point: Iterable[float], matrix: tuple[float, ...]) -> list[float]:
    x, y = point
    a, b, c, d, e, f = matrix
    return [a * x + c * y + e, b * x + d * y + f]


def parse_points(value: str) -> list[list[float]]:
    nums = [float(item) for item in re.findall(NUMBER, value)]
    if len(nums) % 2:
        raise ValueError("SVG points must contain x/y pairs.")
    return [[nums[i], nums[i + 1]] for i in range(0, len(nums), 2)]


def parse_simple_path(value: str) -> tuple[list[list[float]], bool]:
    tokens = PATH_TOKEN_RE.findall(value)
    points: list[list[float]] = []
    index = 0
    command = ""
    current = [0.0, 0.0]
    start = [0.0, 0.0]
    closed = False
    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
        if command in {"Z", "z"}:
            closed = True
            current = start[:]
            command = ""
            continue
        if command in {"M", "L", "m", "l"}:
            if index + 1 >= len(tokens):
                raise ValueError("Incomplete SVG path point.")
            x, y = float(tokens[index]), float(tokens[index + 1])
            index += 2
            if command.islower():
                x += current[0]
                y += current[1]
            current = [x, y]
            if not points:
                start = current[:]
            points.append(current[:])
            if command in {"M", "m"}:
                command = "l" if command == "m" else "L"
        elif command in {"H", "h"}:
            x = float(tokens[index])
            index += 1
            current[0] = current[0] + x if command == "h" else x
            points.append(current[:])
        elif command in {"V", "v"}:
            y = float(tokens[index])
            index += 1
            current[1] = current[1] + y if command == "v" else y
            points.append(current[:])
        else:
            raise ValueError(
                "Only M, L, H, V, and Z SVG path commands are supported in v0.1."
            )
    return points, closed


def determine_scale(
    root: ET.Element, known_svg_length: float | None, known_mm_length: float | None
) -> tuple[float, bool, str]:
    if known_svg_length and known_mm_length:
        if known_svg_length <= 0 or known_mm_length <= 0:
            raise ValueError("Known lengths must be positive.")
        return known_mm_length / known_svg_length, True, "known_dimension"

    width, unit = parse_length(root.get("width"))
    unit_to_mm = {"mm": 1.0, "cm": 10.0, "in": 25.4}
    view_box = [float(item) for item in re.findall(NUMBER, root.get("viewBox", ""))]
    if width and unit in unit_to_mm and len(view_box) == 4 and view_box[2] > 0:
        return width * unit_to_mm[unit] / view_box[2], True, "physical_svg_units"
    raise ValueError(
        "SVG scale is unknown. Provide --known-svg-length and --known-mm-length."
    )


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def convert_svg(path: Path, scale: float) -> list[dict]:
    root = ET.parse(path).getroot()
    geometry: list[dict] = []

    def visit(node: ET.Element, parent_matrix: tuple[float, ...]) -> None:
        matrix = mat_mul(parent_matrix, transform_matrix(node.get("transform")))
        name = local_name(node.tag)
        item: dict | None = None
        if name == "line":
            item = {
                "type": "line",
                "start": [float(node.get("x1", 0)), float(node.get("y1", 0))],
                "end": [float(node.get("x2", 0)), float(node.get("y2", 0))],
            }
        elif name == "rect":
            item = {
                "type": "rectangle",
                "origin": [float(node.get("x", 0)), float(node.get("y", 0))],
                "width": float(node.get("width", 0)),
                "height": float(node.get("height", 0)),
            }
        elif name in {"polyline", "polygon"}:
            item = {"type": name, "points": parse_points(node.get("points", ""))}
        elif name == "circle":
            item = {
                "type": "circle",
                "center": [float(node.get("cx", 0)), float(node.get("cy", 0))],
                "radius": float(node.get("r", 0)),
            }
        elif name == "path":
            points, closed = parse_simple_path(node.get("d", ""))
            item = {"type": "polygon" if closed else "polyline", "points": points}

        if item:
            if item["type"] == "line":
                item["start"] = apply_matrix(item["start"], matrix)
                item["end"] = apply_matrix(item["end"], matrix)
            elif item["type"] == "rectangle":
                x, y = item.pop("origin")
                width, height = item.pop("width"), item.pop("height")
                item["type"] = "polygon"
                item["points"] = [
                    apply_matrix(point, matrix)
                    for point in ([x, y], [x + width, y], [x + width, y + height], [x, y + height])
                ]
            elif item["type"] in {"polyline", "polygon"}:
                item["points"] = [apply_matrix(point, matrix) for point in item["points"]]
            elif item["type"] == "circle":
                item["center"] = apply_matrix(item["center"], matrix)
                sx = math.hypot(matrix[0], matrix[1])
                sy = math.hypot(matrix[2], matrix[3])
                if not math.isclose(sx, sy, rel_tol=1e-6):
                    raise ValueError("Non-uniformly scaled SVG circles are unsupported.")
                item["radius"] *= sx
            item["layer"] = "A-REF"
            for key in ("start", "end", "center"):
                if key in item:
                    item[key] = [round(item[key][0] * scale, 6), round(-item[key][1] * scale, 6)]
            if "points" in item:
                item["points"] = [
                    [round(point[0] * scale, 6), round(-point[1] * scale, 6)]
                    for point in item["points"]
                ]
            if "radius" in item:
                item["radius"] = round(item["radius"] * scale, 6)
            geometry.append(item)

        for child in node:
            visit(child, matrix)

    visit(root, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    return geometry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg")
    parser.add_argument("--known-svg-length", type=float)
    parser.add_argument("--known-mm-length", type=float)
    parser.add_argument("--project-name", default="SVG Reconstruction")
    parser.add_argument("--drawing-title", default="Architectural Plan")
    parser.add_argument("--scale", type=float, default=100)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        root = ET.parse(args.svg).getroot()
        scale_factor, verified, method = determine_scale(
            root, args.known_svg_length, args.known_mm_length
        )
        geometry = convert_svg(Path(args.svg), scale_factor)
    except (ET.ParseError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    project = {
        "metadata": {
            "project_name": args.project_name,
            "drawing_title": args.drawing_title,
            "drawing_number": "A-101",
            "designer": "",
            "date": "",
            "units": "mm",
            "scale": args.scale,
            "assumptions": [],
            "open_issues": [
                "Classify traced SVG geometry into walls, doors, windows, fixtures, and annotations."
            ],
        },
        "source": {
            "type": "svg",
            "path": str(Path(args.svg)),
            "scale_verified": verified,
            "scale_method": method,
            "mm_per_svg_unit": scale_factor,
        },
        "drawing": {"sheet": "A3", "orientation": "landscape", "layout_name": "A3"},
        "walls": [],
        "doors": [],
        "windows": [],
        "rooms": [],
        "geometry": geometry,
        "annotations": {"dimensions": [], "notes": []},
    }
    write_json(args.output, project)
    print(f"Wrote {len(geometry)} SVG objects to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
