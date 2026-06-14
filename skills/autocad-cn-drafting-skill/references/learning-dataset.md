# Authorized Floor-Plan Learning Dataset

## Objective

Build a traceable dataset for floor-plan recognition and design-pattern
analysis. Separate visual inspiration from media that may legally and
contractually be copied, annotated, and used for model training.

## Collection Policy

Use one of these rights bases:

- `owned`: the user or organization owns the media.
- `explicit_permission`: the creator or rights holder granted permission.
- `licensed`: a license permits the intended storage and training use.
- `public_domain`: the work is confirmed to be in the public domain.
- `reference_only`: retain the public URL and original observations only. Do not
  download or store the platform media in the dataset.

Public visibility is not a training license. Do not scrape, bypass login or
rate limits, remove watermarks, imitate private APIs, or collect personal
information that is not necessary for provenance.

Platform rules change. Recheck the current official terms before each collection
project:

- Xiaohongshu user agreement:
  <https://agree.xiaohongshu.com/h5/terms/ZXXY20220331001/-1>
- Xiaohongshu community rules:
  <https://agree.xiaohongshu.com/h5/terms/ZXXY20221213003/-1>
- Douyin user agreement:
  <https://www.douyin.com/agreements/?id=6773906068725565448>
- Douyin Open Platform:
  <https://open.douyin.com/>

Use an official API only for capabilities and data scopes actually granted to
the authorized application and user.

## Dataset Layout

```text
dataset/
  manifest.jsonl
  media/
  annotations/
  summaries/
```

`manifest.jsonl` is the source of truth. Each record stores the platform, URL,
creator, rights basis, permission note, split, file hash, and annotation path.
Raw media is ignored by this repository and must not be committed.

## Annotation Scope

Start from `assets/plan-annotation-template.json`. Record:

- source quality: scan, screenshot, clean export, skew, watermark, low contrast;
- plan type and room types;
- walls, doors, windows, room regions, furniture, dimensions, and text regions;
- layout features such as open living/dining, wet-area clusters, corridor type,
  daylight orientation, storage walls, and flexible partitions;
- ergonomic observations such as route continuity, door conflicts, turning
  space, furniture clearances, and inaccessible controls.

Use pixel coordinates for recognition labels. Keep scale and physical dimensions
separate until a reliable dimension is confirmed.

## Split Rules

- Assign one dwelling or drawing family to only one of `train`, `val`, or `test`.
- Keep revisions, crops, screenshots, and recolored copies in the same split.
- Run exact-hash validation before training.
- Add perceptual duplicate detection before a production training run.
- Reserve difficult scans and unfamiliar drawing styles for the test set.

## Learning Outputs

Aggregate patterns, not copied posts. Suitable outputs include:

- room-combination frequencies;
- common circulation structures;
- recurring furniture and wet-area arrangements;
- recognition failure categories;
- ergonomic risks and successful clearance strategies;
- annotation coverage and dataset balance.

Do not publish source media, creator-private data, or a reconstruction that is
substantially identical to a protected drawing without permission.
