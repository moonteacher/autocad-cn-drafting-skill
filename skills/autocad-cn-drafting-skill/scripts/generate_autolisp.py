#!/usr/bin/env python3
"""Generate cross-platform AutoLISP from a validated CAD project JSON."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

from cad_common import load_json, load_rules, project_issues, write_text


GENERATOR_VERSION = "0.1.0-alpha"


def lisp_string(value: Any) -> str:
    text = str(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def number(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".") or "0"


def point(value: list[float]) -> str:
    return f"(list {number(value[0])} {number(value[1])} 0.0)"


def wall_polygon(wall: dict[str, Any]) -> list[list[float]]:
    x1, y1 = wall["start"]
    x2, y2 = wall["end"]
    length = math.hypot(x2 - x1, y2 - y1)
    offset = wall["thickness"] / 2.0
    nx = -(y2 - y1) / length * offset
    ny = (x2 - x1) / length * offset
    return [
        [x1 + nx, y1 + ny],
        [x2 + nx, y2 + ny],
        [x2 - nx, y2 - ny],
        [x1 - nx, y1 - ny],
    ]


def lisp_list(values: list[str]) -> str:
    return "(list " + " ".join(values) + ")"


def entity_lines(project: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    wall_layers = {
        "existing": "A-WALL-EXST",
        "new": "A-WALL-NEW",
        "demolish": "A-WALL-DEMO",
    }
    for wall in project.get("walls", []):
        polygon = lisp_list([point(item) for item in wall_polygon(wall)])
        layer = wall.get("layer", wall_layers[wall.get("kind", "existing")])
        lines.append(f"  (cad:poly {polygon} T {lisp_string(layer)})")

    for door in project.get("doors", []):
        hinge = door["hinge"]
        width = door["width"]
        angle = math.radians(door.get("angle", 0))
        direction = -1 if door.get("swing", "left") == "right" else 1
        closed = [
            hinge[0] + width * math.cos(angle),
            hinge[1] + width * math.sin(angle),
        ]
        open_angle = angle + direction * math.radians(door.get("opening_angle", 90))
        opened = [
            hinge[0] + width * math.cos(open_angle),
            hinge[1] + width * math.sin(open_angle),
        ]
        start_deg = math.degrees(min(angle, open_angle))
        end_deg = math.degrees(max(angle, open_angle))
        lines.extend(
            [
                f"  (cad:line {point(hinge)} {point(opened)} \"A-DOOR\")",
                f"  (cad:arc {point(hinge)} {number(width)} {number(start_deg)} {number(end_deg)} \"A-DOOR\")",
                f"  (cad:line {point(hinge)} {point(closed)} \"A-NPLT-REVIEW\")",
            ]
        )

    for window in project.get("windows", []):
        start, end = window["start"], window["end"]
        x1, y1 = start
        x2, y2 = end
        length = math.hypot(x2 - x1, y2 - y1)
        offset = window.get("frame_depth", 50) / 2.0
        nx, ny = -(y2 - y1) / length * offset, (x2 - x1) / length * offset
        for sign in (-1, 1):
            a = [x1 + sign * nx, y1 + sign * ny]
            b = [x2 + sign * nx, y2 + sign * ny]
            lines.append(f"  (cad:line {point(a)} {point(b)} \"A-WIND\")")
        lines.append(f"  (cad:line {point(start)} {point(end)} \"A-WIND\")")

    for item in project.get("furniture", []):
        footprint = lisp_list([point(vertex) for vertex in item["footprint"]])
        lines.append(f"  (cad:poly {footprint} T \"A-FURN\")")
        for zone in item.get("clearance_zones", []):
            zone_points = lisp_list([point(vertex) for vertex in zone["polygon"]])
            lines.append(f"  (cad:poly {zone_points} T \"A-NPLT-REVIEW\")")

    for path in project.get("circulation_paths", []):
        centerline = lisp_list([point(vertex) for vertex in path["centerline"]])
        lines.append(f"  (cad:poly {centerline} nil \"A-NPLT-REVIEW\")")

    for geometry in project.get("geometry", []):
        layer = geometry.get("layer", "A-REF")
        kind = geometry["type"]
        if kind == "line":
            lines.append(
                f"  (cad:line {point(geometry['start'])} {point(geometry['end'])} {lisp_string(layer)})"
            )
        elif kind in {"polyline", "polygon"}:
            points = lisp_list([point(item) for item in geometry["points"]])
            lines.append(
                f"  (cad:poly {points} {'T' if kind == 'polygon' else 'nil'} {lisp_string(layer)})"
            )
        elif kind == "rectangle":
            x, y = geometry["origin"]
            width, height = geometry["width"], geometry["height"]
            points = [[x, y], [x + width, y], [x + width, y + height], [x, y + height]]
            lines.append(
                f"  (cad:poly {lisp_list([point(item) for item in points])} T {lisp_string(layer)})"
            )
        elif kind == "circle":
            lines.append(
                f"  (cad:circle {point(geometry['center'])} {number(geometry['radius'])} {lisp_string(layer)})"
            )

    scale = float(project["metadata"]["scale"])
    text_height = 3.5 * scale
    for room in project.get("rooms", []):
        label = room.get("name", "ROOM")
        if room.get("area") is not None:
            label += f"\\P{room['area']} m2"
        lines.append(
            f"  (cad:mtext {point(room['label_point'])} {lisp_string(label)} {number(text_height)} \"A-ANNO-TEXT\")"
        )

    annotations = project.get("annotations", {})
    for note in annotations.get("notes", []):
        lines.append(
            f"  (cad:mtext {point(note['point'])} {lisp_string(note['text'])} {number(note.get('height', text_height))} {lisp_string(note.get('layer', 'A-ANNO-TEXT'))})"
        )
    for dim in annotations.get("dimensions", []):
        lines.append(
            f"  (cad:dim {point(dim['start'])} {point(dim['end'])} {point(dim['location'])})"
        )
    return lines


def generate(project: dict[str, Any], rules: dict[str, Any]) -> str:
    metadata = project["metadata"]
    drawing = project["drawing"]
    layers = rules["layers"]
    allowed_layers = sorted(layers)
    scale = float(metadata["scale"])
    dim_style = rules["dimension_style"]
    sheet_name = drawing.get("sheet", "A3")
    sheet_width, sheet_height = rules["sheets"][sheet_name]
    if drawing.get("orientation", "landscape") == "landscape":
        sheet_width, sheet_height = max(sheet_width, sheet_height), min(sheet_width, sheet_height)
    else:
        sheet_width, sheet_height = min(sheet_width, sheet_height), max(sheet_width, sheet_height)
    layout_name = drawing.get("layout_name", sheet_name)

    layer_specs = []
    for name, spec in layers.items():
        layer_specs.append(
            f"    ({lisp_string(name)} {spec['color']} {lisp_string(spec['linetype'])} {spec['lineweight']} {'T' if spec.get('plot', True) else 'nil'})"
        )
    layer_data = "'(\n" + "\n".join(layer_specs) + "\n  )"
    allowed_data = "'(" + " ".join(lisp_string(item) for item in allowed_layers) + ")"
    font_data = "'(" + " ".join(
        lisp_string(item) for item in rules["text_style"]["preferred_fonts"]
    ) + ")"
    objects = entity_lines(project)
    object_code = (
        "\n".join(objects)
        if objects
        else '  (princ "\\nNo model geometry was defined.")'
    )

    return f"""; Auto-generated by autocad-cn-drafting-skill {GENERATOR_VERSION}
; Project: {metadata.get('project_name', '')}
; Load this file in full AutoCAD, then run CADBUILD.
; Review all geometry before construction use.

(setq cad:*project-name* {lisp_string(metadata.get('project_name', ''))})
(setq cad:*drawing-title* {lisp_string(metadata.get('drawing_title', ''))})
(setq cad:*drawing-number* {lisp_string(metadata.get('drawing_number', ''))})
(setq cad:*designer* {lisp_string(metadata.get('designer', ''))})
(setq cad:*drawing-date* {lisp_string(metadata.get('date', ''))})
(setq cad:*scale* {number(scale)})
(setq cad:*layout-name* {lisp_string(layout_name)})
(setq cad:*sheet-width* {number(sheet_width)})
(setq cad:*sheet-height* {number(sheet_height)})
(setq cad:*allowed-layers* {allowed_data})
(setq cad:*layer-specs* {layer_data})
(setq cad:*font-candidates* {font_data})

(defun cad:ensure-linetype (name /)
  (if (and (/= name "CONTINUOUS") (not (tblsearch "LTYPE" name)))
    (command "_.-LINETYPE" "_Load" name
             (if (findfile "acadiso.lin") "acadiso.lin" "acad.lin") "")
  )
)

(defun cad:set-dxf (code value data / old)
  (setq old (assoc code data))
  (if old (subst (cons code value) old data) (append data (list (cons code value))))
)

(defun cad:ensure-layer (spec / name color ltype lw plotFlag entity data)
  (setq name (nth 0 spec)
        color (nth 1 spec)
        ltype (nth 2 spec)
        lw (nth 3 spec)
        plotFlag (nth 4 spec))
  (cad:ensure-linetype ltype)
  (if (tblsearch "LAYER" name)
    (progn
      (setq entity (tblobjname "LAYER" name) data (entget entity))
      (setq data (cad:set-dxf 62 color data))
      (setq data (cad:set-dxf 6 ltype data))
      (setq data (cad:set-dxf 290 (if plotFlag 1 0) data))
      (setq data (cad:set-dxf 370 lw data))
      (entmod data)
    )
    (entmake
      (list
        '(0 . "LAYER") '(100 . "AcDbSymbolTableRecord") '(100 . "AcDbLayerTableRecord")
        (cons 2 name) (cons 70 0) (cons 62 color) (cons 6 ltype)
        (cons 290 (if plotFlag 1 0)) (cons 370 lw)
      )
    )
  )
)

(defun cad:line (p1 p2 layer /)
  (entmake (list '(0 . "LINE") '(100 . "AcDbEntity") (cons 8 layer)
                 '(100 . "AcDbLine") (cons 10 p1) (cons 11 p2)))
)

(defun cad:poly (pts closed layer / data)
  (setq data
    (list '(0 . "LWPOLYLINE") '(100 . "AcDbEntity") (cons 8 layer)
          '(100 . "AcDbPolyline") (cons 90 (length pts)) (cons 70 (if closed 1 0))))
  (foreach p pts (setq data (append data (list (cons 10 (list (car p) (cadr p)))))))
  (entmake data)
)

(defun cad:circle (center radius layer /)
  (entmake (list '(0 . "CIRCLE") '(100 . "AcDbEntity") (cons 8 layer)
                 '(100 . "AcDbCircle") (cons 10 center) (cons 40 radius)))
)

(defun cad:arc (center radius startAngle endAngle layer /)
  (entmake (list '(0 . "ARC") '(100 . "AcDbEntity") (cons 8 layer)
                 '(100 . "AcDbCircle") (cons 10 center) (cons 40 radius)
                 '(100 . "AcDbArc") (cons 50 (* pi (/ startAngle 180.0)))
                 (cons 51 (* pi (/ endAngle 180.0)))))
)

(defun cad:mtext (insert value height layer /)
  (entmake (list '(0 . "MTEXT") '(100 . "AcDbEntity") (cons 8 layer)
                 '(100 . "AcDbMText") (cons 10 insert) (cons 40 height)
                 (cons 41 (* height 20.0)) (cons 71 5) (cons 1 value)))
)

(defun cad:dim (p1 p2 location /)
  (setvar "CLAYER" "A-ANNO-DIMS")
  (command "_.DIMALIGNED" p1 p2 location "")
)

(defun cad:first-font (items / found)
  (while (and items (not found))
    (if (findfile (car items)) (setq found (car items)))
    (setq items (cdr items))
  )
  found
)

(defun cad:ensure-text-style (/ font entity data styleName)
  (setq font (cad:first-font cad:*font-candidates*))
  (if (not font)
    (progn
      (setq font "{rules['text_style']['fallback_font']}")
      (princ "\\nWARNING: Preferred Chinese font not found; using fallback txt.shx.")
    )
  )
  (setq styleName "{rules['text_style']['name']}")
  (if (tblsearch "STYLE" styleName)
    (progn
      (setq entity (tblobjname "STYLE" styleName) data (entget entity))
      (setq data (cad:set-dxf 3 font data))
      (setq data (cad:set-dxf 40 0.0 data))
      (setq data (cad:set-dxf 41 1.0 data))
      (entmod data)
    )
    (entmake
      (list '(0 . "STYLE") '(100 . "AcDbSymbolTableRecord")
            '(100 . "AcDbTextStyleTableRecord") (cons 2 styleName)
            '(70 . 0) '(40 . 0.0) '(41 . 1.0) '(50 . 0.0)
            '(71 . 0) '(42 . 3.5) (cons 3 font) '(4 . ""))
    )
  )
  (setvar "TEXTSTYLE" styleName)
)

(defun cad:ensure-dim-style (/ styleName)
  (setq styleName "{dim_style['name']}")
  (setvar "DIMTXT" {number(dim_style['paper_text_height_mm'] * scale)})
  (setvar "DIMASZ" {number(dim_style['arrow_size_mm'] * scale)})
  (setvar "DIMEXO" {number(dim_style['extension_offset_mm'] * scale)})
  (setvar "DIMDEC" {int(dim_style['decimal_places'])})
  (setvar "DIMLUNIT" 2)
  (setvar "DIMASSOC" 2)
  (if (tblsearch "DIMSTYLE" styleName)
    (command "_.-DIMSTYLE" "_Save" styleName "_Yes")
    (command "_.-DIMSTYLE" "_Save" styleName)
  )
  (command "_.-DIMSTYLE" "_Restore" styleName)
)

(defun cad:sheet-line (p1 p2 /)
  (entmake (list '(0 . "LINE") '(100 . "AcDbEntity") '(67 . 1)
                 (cons 410 cad:*layout-name*) '(8 . "A-BORDER")
                 '(100 . "AcDbLine") (cons 10 p1) (cons 11 p2)))
)

(defun cad:sheet-text (p value height layer /)
  (entmake (list '(0 . "TEXT") '(100 . "AcDbEntity") '(67 . 1)
                 (cons 410 cad:*layout-name*) (cons 8 layer)
                 '(100 . "AcDbText") (cons 10 p) (cons 40 height)
                 (cons 1 value) (cons 7 "{rules['text_style']['name']}")))
)

(defun cad:setup-layout (/ oldTab margin x0 y0 x1 y1 titleX)
  (setq oldTab (getvar "CTAB"))
  (if (not (member cad:*layout-name* (layoutlist)))
    (command "_.-LAYOUT" "_New" cad:*layout-name*)
  )
  (setvar "CTAB" cad:*layout-name*)
  (setq margin 10.0 x0 margin y0 margin
        x1 (- cad:*sheet-width* margin) y1 (- cad:*sheet-height* margin)
        titleX (- x1 180.0))
  (cad:sheet-line (list x0 y0 0.0) (list x1 y0 0.0))
  (cad:sheet-line (list x1 y0 0.0) (list x1 y1 0.0))
  (cad:sheet-line (list x1 y1 0.0) (list x0 y1 0.0))
  (cad:sheet-line (list x0 y1 0.0) (list x0 y0 0.0))
  (cad:sheet-line (list titleX y0 0.0) (list titleX (+ y0 40.0) 0.0))
  (cad:sheet-line (list titleX (+ y0 40.0) 0.0) (list x1 (+ y0 40.0) 0.0))
  (cad:sheet-line (list titleX (+ y0 20.0) 0.0) (list x1 (+ y0 20.0) 0.0))
  (cad:sheet-text (list (+ titleX 3.0) (+ y0 29.0) 0.0) cad:*project-name* 3.5 "A-TTLB")
  (cad:sheet-text (list (+ titleX 3.0) (+ y0 9.0) 0.0) cad:*drawing-title* 5.0 "A-TTLB")
  (cad:sheet-text (list (- x1 55.0) (+ y0 29.0) 0.0) cad:*drawing-number* 3.5 "A-TTLB")
  (cad:sheet-text (list (- x1 55.0) (+ y0 9.0) 0.0) (strcat "1:" (rtos cad:*scale* 2 0)) 3.5 "A-TTLB")
  (setvar "CTAB" oldTab)
)

(defun cad:entity-distance (entity / data p1 p2)
  (setq data (entget entity) p1 (cdr (assoc 10 data)) p2 (cdr (assoc 11 data)))
  (if (and p1 p2) (distance p1 p2) nil)
)

(defun c:CADAUDIT (/ ss index entity data layer type errors warnings lengthValue)
  (setq errors 0 warnings 0 ss (ssget "_X"))
  (if ss
    (progn
      (setq index 0)
      (repeat (sslength ss)
        (setq entity (ssname ss index) data (entget entity)
              layer (cdr (assoc 8 data)) type (cdr (assoc 0 data)))
        (if (not (member layer cad:*allowed-layers*))
          (progn (setq errors (1+ errors))
                 (princ (strcat "\\nERROR unknown layer: " layer))))
        (if (= type "LINE")
          (progn
            (setq lengthValue (cad:entity-distance entity))
            (if (and lengthValue (< lengthValue 0.01))
              (progn (setq errors (1+ errors)) (princ "\\nERROR zero-length LINE")))))
        (setq index (1+ index))
      )
    )
  )
  (if (= errors 0)
    (princ "\\nCADAUDIT PASS: no machine-detectable errors.")
    (princ (strcat "\\nCADAUDIT FAIL: " (itoa errors) " error(s).")))
  (princ "\\nRun the Python ASCII DXF audit for the delivery report.")
  (princ)
)

(defun c:CADBUILD (/ oldEcho oldSnap oldLayer)
  (setq oldEcho (getvar "CMDECHO") oldSnap (getvar "OSMODE") oldLayer (getvar "CLAYER"))
  (setvar "CMDECHO" 0)
  (setvar "OSMODE" 0)
  (setvar "INSUNITS" 4)
  (setvar "MEASUREMENT" 1)
  (foreach spec cad:*layer-specs* (cad:ensure-layer spec))
  (cad:ensure-text-style)
  (cad:ensure-dim-style)
  (setvar "CLAYER" "A-WALL-EXST")
{object_code}
  (cad:setup-layout)
  (setvar "CLAYER" oldLayer)
  (setvar "OSMODE" oldSnap)
  (setvar "CMDECHO" oldEcho)
  (command "_.ZOOM" "_Extents")
  (princ "\\nCADBUILD complete. Review geometry, layout viewport, fonts, and plot settings.")
  (princ "\\nRun CADAUDIT, save DWG, export ASCII DXF, then run the Python audit.")
  (princ)
)

(princ "\\nAutoCAD CN Drafting loaded. Commands: CADBUILD, CADAUDIT.")
(princ)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--rules")
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-warnings", action="store_true")
    args = parser.parse_args()

    project = load_json(args.project)
    rules = load_rules(args.rules)
    errors, warnings = project_issues(project, rules)
    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 2
    if warnings and not args.allow_warnings:
        for item in warnings:
            print(f"WARNING: {item}", file=sys.stderr)
        print("Use --allow-warnings after reviewing warnings.", file=sys.stderr)
        return 3

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_text(output, generate(project, rules))
    print(f"Generated {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
