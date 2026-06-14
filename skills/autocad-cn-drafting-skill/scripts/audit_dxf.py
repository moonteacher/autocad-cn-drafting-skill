#!/usr/bin/env python3
"""Audit an ASCII DXF against the CAD drafting skill's layer and geometry rules."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from cad_common import load_rules, write_json, write_text


def read_pairs(path: Path) -> list[tuple[int, str]]:
    raw = path.read_bytes()
    if b"\x00" in raw[:4096]:
        raise ValueError("Binary DXF is unsupported. Export an ASCII DXF.")
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
    lines = text.splitlines()
    if len(lines) % 2:
        raise ValueError("DXF group code/value line count is not even.")
    pairs: list[tuple[int, str]] = []
    for index in range(0, len(lines), 2):
        try:
            code = int(lines[index].strip())
        except ValueError as exc:
            raise ValueError(f"Invalid DXF group code on line {index + 1}.") from exc
        pairs.append((code, lines[index + 1].strip()))
    return pairs


def parse_entities(pairs: list[tuple[int, str]]) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    section = None
    current: dict[str, Any] | None = None
    for code, value in pairs:
        if code == 0 and value == "SECTION":
            section = "pending"
            continue
        if section == "pending" and code == 2:
            section = value
            continue
        if code == 0 and value == "ENDSEC":
            if current:
                entities.append(current)
                current = None
            section = None
            continue
        if section != "ENTITIES":
            continue
        if code == 0:
            if current:
                entities.append(current)
            current = {"type": value, "groups": {}}
        elif current is not None:
            current["groups"].setdefault(code, []).append(value)
    if current:
        entities.append(current)
    return entities


def value(entity: dict[str, Any], code: int, default: str | None = None) -> str | None:
    items = entity["groups"].get(code, [])
    return items[0] if items else default


def float_value(entity: dict[str, Any], code: int) -> float | None:
    raw = value(entity, code)
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


def normalized_line_key(entity: dict[str, Any], tolerance: float) -> tuple | None:
    coords = [
        float_value(entity, 10),
        float_value(entity, 20),
        float_value(entity, 11),
        float_value(entity, 21),
    ]
    if any(item is None for item in coords):
        return None
    x1, y1, x2, y2 = coords
    rounded = lambda item: round(item / tolerance)  # noqa: E731
    p1, p2 = (rounded(x1), rounded(y1)), (rounded(x2), rounded(y2))
    return tuple(sorted((p1, p2)))


def audit(path: Path, rules: dict[str, Any]) -> dict[str, Any]:
    pairs = read_pairs(path)
    entities = parse_entities(pairs)
    allowed = set(rules["layers"])
    required = set(rules.get("required_layers", []))
    tolerance = float(rules.get("audit", {}).get("coordinate_tolerance_mm", 0.01))
    duplicate_tolerance = float(rules.get("audit", {}).get("duplicate_tolerance_mm", 0.1))
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    layer_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    line_keys: Counter[tuple] = Counter()

    for index, entity in enumerate(entities):
        entity_type = entity["type"]
        layer = value(entity, 8, "0") or "0"
        layer_counts[layer] += 1
        type_counts[entity_type] += 1
        if layer not in allowed:
            errors.append(
                {"code": "UNKNOWN_LAYER", "entity_index": index, "entity_type": entity_type, "layer": layer}
            )
        if entity_type == "LINE":
            x1, y1 = float_value(entity, 10), float_value(entity, 20)
            x2, y2 = float_value(entity, 11), float_value(entity, 21)
            if None not in (x1, y1, x2, y2):
                if math.hypot(x2 - x1, y2 - y1) <= tolerance:
                    errors.append(
                        {"code": "ZERO_LENGTH_LINE", "entity_index": index, "layer": layer}
                    )
                key = normalized_line_key(entity, duplicate_tolerance)
                if key:
                    line_keys[(layer, key)] += 1
        if entity_type in {"TEXT", "MTEXT"} and not (value(entity, 1, "") or "").strip():
            warnings.append({"code": "EMPTY_TEXT", "entity_index": index, "layer": layer})

    for (layer, key), count in line_keys.items():
        if count > 1:
            warnings.append(
                {"code": "DUPLICATE_LINE", "layer": layer, "count": count, "normalized_points": key}
            )
    missing_required = sorted(required - set(layer_counts))
    for layer in missing_required:
        warnings.append({"code": "REQUIRED_LAYER_UNUSED", "layer": layer})

    status = "fail" if errors else "pass_with_warnings" if warnings else "pass"
    return {
        "status": status,
        "source": str(path),
        "entity_count": len(entities),
        "entity_types": dict(sorted(type_counts.items())),
        "layers": dict(sorted(layer_counts.items())),
        "errors": errors,
        "warnings": warnings,
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# ASCII DXF Audit",
        "",
        f"- Source: `{result['source']}`",
        f"- Status: **{result['status']}**",
        f"- Entities: {result['entity_count']}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- `{item['code']}`: `{json.dumps(item, ensure_ascii=False)}`" for item in result["errors"])
    if not result["errors"]:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    lines.extend(
        f"- `{item['code']}`: `{json.dumps(item, ensure_ascii=False)}`"
        for item in result["warnings"]
    )
    if not result["warnings"]:
        lines.append("- None")
    lines.extend(["", "## Layer Counts", ""])
    lines.extend(f"- `{layer}`: {count}" for layer, count in result["layers"].items())
    lines.extend(
        [
            "",
            "> Automated checks are limited to machine-readable DXF properties and do not",
            "> replace professional drawing review.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dxf")
    parser.add_argument("--rules")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = audit(Path(args.dxf), load_rules(args.rules))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    write_json(output_dir / "dxf-audit.json", result)
    write_text(output_dir / "dxf-audit.md", markdown_report(result))
    print(f"DXF audit: {result['status']} ({result['entity_count']} entities)")
    return 2 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
