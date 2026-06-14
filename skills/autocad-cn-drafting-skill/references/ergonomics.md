# Ergonomics and Space Utilization

## Purpose

Evaluate whether a room is usable by its intended occupants, not merely whether
its gross area is large enough. Treat furniture, body movement, door operation,
reach, turning, and circulation as geometry.

## Analysis Model

For each room:

1. Define a verified room boundary.
2. Select one or more user profiles.
3. Place every major furniture and fixed-equipment footprint.
4. Draw activity-clearance polygons for opening, sitting, standing, reaching,
   transferring, cleaning, and maintenance.
5. Declare circulation paths and measured clear widths.
6. Run `analyze_space.py`.
7. Resolve collisions and insufficient widths before drafting completion.

The report calculates:

- net room area from its boundary;
- furniture footprint coverage;
- nominal circulation reserve after footprint and activity reservations;
- furniture-to-furniture collisions;
- activity-zone conflicts;
- furniture outside a room;
- door-swing conflicts;
- declared path width against the governing user profile.

The nominal circulation reserve is conservative because v0.1 sums activity-zone
areas instead of calculating their geometric union. Use it as a warning metric,
not a property valuation or legal area calculation.

## User Profiles

`assets/default_rules.json` provides editable profiles:

- `general_adult`
- `accessible_wheelchair`
- `older_adult`
- `child`

Select profiles based on the actual brief. Do not apply a wheelchair profile
only to obtain a compliance label; confirm the project scope and the applicable
regulation.

## Rule Classification

- `code`: a requirement with a recorded source, edition, clause, and project
  applicability decision.
- `baseline`: a configurable ergonomic design value used for early design.
- `advisory`: a recommendation that cannot be reduced to one reliable threshold.

Never silently convert a baseline into a code requirement. When adding a code
rule, record its source in project notes or a project-specific rules file.

## Design Review Questions

- Can the intended person enter, turn, approach, use, and leave?
- Can doors, drawers, appliances, wardrobes, and chairs operate simultaneously?
- Is the clear route continuous, or does one pinch point invalidate it?
- Are frequently used controls within the intended reach range?
- Does furniture arrangement preserve daylight, ventilation, privacy, and a
  legible movement path?
- Can older adults or children use the room without creating avoidable hazards?
- Does accessible space remain available after movable furniture is installed?

These questions require human judgement even when the automated report passes.
