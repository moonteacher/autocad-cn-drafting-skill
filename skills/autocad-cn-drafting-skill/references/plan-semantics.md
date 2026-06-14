# Interior Floor-Plan Semantics

Use this taxonomy when comparing drawings from different creators or platforms.
Separate what is visibly present from design conclusions that require judgement.

## Recognition Layers

Label these visual classes independently:

- `walls`: wall face or centreline geometry; record likely structural status only
  when the drawing provides evidence.
- `doors`: opening, hinge, leaf width, swing direction, and opening angle.
- `windows`: opening span and likely sill or glazing type when shown.
- `rooms`: closed region, visible room name, inferred room type, and confidence.
- `furniture`: footprint, category, orientation, and whether fixed or movable.
- `dimensions`: number, unit, dimension line, witness lines, and referenced
  geometry.
- `text_regions`: room names, notes, door/window tags, axis labels, and title
  block text.

Store pixel coordinates for recognition labels. Convert to millimetres only
after scale verification.

## Spatial Meaning

Annotate room and layout meaning with consistent tags.

### Zoning

- `public_private_separated`
- `public_private_mixed`
- `service_core_compact`
- `wet_area_cluster`
- `quiet_zone_buffered`
- `bedroom_direct_to_living`

### Entrance

- `independent_foyer`
- `entrance_screen`
- `entrance_storage_wall`
- `direct_view_to_living`
- `direct_view_to_bathroom`
- `mudroom_or_shoe_change`

### Living And Dining

- `open_living_dining`
- `living_dining_balcony_axis`
- `central_living_room`
- `side_living_room`
- `flexible_study_in_public_zone`

### Kitchen

- `closed_kitchen`
- `open_kitchen`
- `semi_open_kitchen`
- `single_wall_kitchen`
- `galley_kitchen`
- `l_shaped_kitchen`
- `u_shaped_kitchen`
- `island_kitchen`
- `kitchen_dining_short_route`

### Bathroom

- `single_bathroom`
- `multiple_bathrooms`
- `dry_wet_separated`
- `three_part_bathroom`
- `bathroom_without_window`
- `shared_wet_core`

### Circulation

- `central_corridor`
- `loop_circulation`
- `through_living_circulation`
- `short_private_corridor`
- `long_internal_corridor`
- `continuous_accessible_route`
- `circulation_pinched`

### Light, Storage, And Flexibility

- `dual_aspect_daylight`
- `single_aspect_daylight`
- `dark_internal_room`
- `continuous_storage_wall`
- `distributed_storage`
- `walk_in_closet`
- `flexible_partition`
- `convertible_room`

## Design Interpretation

For each inferred feature, record:

- `evidence`: visible text, symbol, furniture, geometry, or adjacency;
- `confidence`: 0 to 1;
- `source`: manual, OCR, geometry, object detector, or multimodal inference;
- `requires_review`: true when confidence is below the project threshold.

Do not infer structural removability, code compliance, load-bearing status,
ownership, exact scale, or construction dimensions from appearance alone.

## Platform Comparison

Platform popularity is not design quality. Compare samples by:

- source resolution and drawing completeness;
- dwelling area and household brief;
- room adjacency and route length;
- usable clearance after furniture placement;
- daylight and ventilation evidence;
- storage quantity and location;
- unresolved assumptions;
- recognition confidence.

Aggregate these attributes across authorized samples. Do not rank a plan only by
likes, saves, comments, visual styling, or creator follower count.
