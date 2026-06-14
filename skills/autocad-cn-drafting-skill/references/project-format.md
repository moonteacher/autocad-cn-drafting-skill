# Project Format

Use UTF-8 JSON. Keep all model-space geometry in millimetres at 1:1.

## Required Top-Level Objects

- `metadata`: project identity, unit, plotted scale, assumptions, and open issues.
- `source`: source type and scale verification.
- `drawing`: sheet, orientation, and layout name.
- `walls`, `doors`, `windows`, `rooms`: architectural objects.
- `furniture`: furniture or fixed-equipment footprints and activity zones.
- `circulation_paths`: declared clear routes evaluated against user profiles.
- `geometry`: supplemental traced geometry.
- `annotations`: dimensions and notes.

Use `examples/apartment/project.json` as the canonical example.

## Metadata

```json
{
  "metadata": {
    "project_name": "Apartment Study",
    "drawing_title": "Furniture Plan",
    "drawing_number": "A-101",
    "designer": "Designer",
    "date": "2026-06-14",
    "units": "mm",
    "scale": 50,
    "assumptions": [],
    "open_issues": []
  }
}
```

Keep `open_issues` empty before generating a formal package. Record a decision
as an assumption only after the user accepts it.

## Source

Set `type` to `text`, `image`, `svg`, or `structured`.

- For images, set `scale_verified` only after a real dimension or known scale is
  confirmed.
- For SVG, prefer physical `mm`, `cm`, or `in` dimensions with a `viewBox`.
  Otherwise provide a known SVG length and its real millimetre length.
- Do not infer construction dimensions from pixels alone.

## Architectural Objects

A wall uses a centreline plus thickness:

```json
{"id":"W1","start":[0,0],"end":[6000,0],"thickness":200,"kind":"existing"}
```

A door uses a hinge, width, closed-leaf angle in degrees, handing, and opening
angle:

```json
{"id":"D1","hinge":[1000,0],"width":900,"angle":90,"swing":"left","opening_angle":90}
```

A room must include a closed conceptual boundary without repeating the first
point. Assign the user profiles that govern its design:

```json
{
  "id":"R1",
  "name":"Living Room",
  "boundary":[[0,0],[6000,0],[6000,4000],[0,4000]],
  "label_point":[3000,2000],
  "user_profiles":["general_adult","older_adult"]
}
```

## Furniture and Activity Zones

Represent furniture as a simple polygon. Add every clearance that must remain
usable as a named polygon:

```json
{
  "id":"F-SOFA",
  "room_id":"R1",
  "category":"sofa",
  "footprint":[[500,500],[2500,500],[2500,1400],[500,1400]],
  "clearance_zones":[
    {
      "name":"front_access",
      "classification":"baseline",
      "polygon":[[500,1400],[2500,1400],[2500,2200],[500,2200]]
    }
  ]
}
```

Use:

- `code` only for a value traced to a cited regulation or explicit project rule;
- `baseline` for configurable ergonomic values;
- `advisory` for qualitative design recommendations.

Keep clearance polygons separate even when they overlap each other. The analyzer
treats their summed area as a conservative nominal reservation, not as an exact
union-area calculation.

## Circulation Paths

Declare a centreline for review visibility and the measured minimum clear width:

```json
{
  "id":"P1",
  "room_id":"R1",
  "centerline":[[3000,500],[3000,3500]],
  "clear_width":1000,
  "user_profiles":["general_adult"],
  "classification":"baseline"
}
```

The analyzer compares `clear_width` against the most demanding selected profile.
It does not derive width from arbitrary polygon geometry in v0.1.

## Supplemental Geometry

Supported types:

- `line`: `start`, `end`
- `polyline` or `polygon`: `points`
- `rectangle`: `origin`, `width`, `height`
- `circle`: `center`, `radius`

Assign traced source objects to `A-REF`. Assign uncertain objects to
`A-NPLT-REVIEW`.

## Annotations

```json
{
  "annotations": {
    "dimensions": [
      {"start":[0,0],"end":[6000,0],"location":[3000,-600]}
    ],
    "notes": [
      {"point":[500,3500],"text":"VERIFY ON SITE","layer":"A-NPLT-REVIEW"}
    ]
  }
}
```
