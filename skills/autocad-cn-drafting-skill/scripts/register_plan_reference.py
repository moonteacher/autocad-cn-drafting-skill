#!/usr/bin/env python3
"""Register an authorized floor-plan sample or a reference-only platform link."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from learning_common import (
    PLATFORMS,
    RIGHTS_BASES,
    SPLITS,
    TRAINING_RIGHTS,
    annotation_issues,
    append_manifest,
    load_annotation,
    read_manifest,
    sha256_file,
)


SAMPLE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--platform", choices=sorted(PLATFORMS), required=True)
    parser.add_argument("--source-url")
    parser.add_argument("--creator", required=True)
    parser.add_argument("--rights-basis", choices=sorted(RIGHTS_BASES), required=True)
    parser.add_argument("--permission-note", default="")
    parser.add_argument("--media")
    parser.add_argument("--annotation")
    parser.add_argument("--split", choices=sorted(SPLITS), default="unassigned")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir).resolve()
    sample_id = args.sample_id
    if not SAMPLE_ID_RE.fullmatch(sample_id):
        print("ERROR: sample-id must use 2-64 lowercase letters, digits, or hyphens.", file=sys.stderr)
        return 2
    if args.platform in {"xiaohongshu", "douyin"} and not args.source_url:
        print("ERROR: platform references require --source-url.", file=sys.stderr)
        return 2
    if args.rights_basis == "reference_only":
        if args.media:
            print("ERROR: reference_only records cannot copy or store platform media.", file=sys.stderr)
            return 2
        if args.split not in {"reference", "unassigned"}:
            print("ERROR: reference_only records must use split reference or unassigned.", file=sys.stderr)
            return 2
    elif args.rights_basis in {"explicit_permission", "licensed", "public_domain"}:
        if not args.permission_note.strip():
            print("ERROR: this rights basis requires --permission-note.", file=sys.stderr)
            return 2

    try:
        records = read_manifest(dataset_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if any(record.get("sample_id") == sample_id for record in records):
        print(f"ERROR: duplicate sample-id '{sample_id}'.", file=sys.stderr)
        return 2

    annotation_relative = None
    if args.annotation:
        annotation_source = Path(args.annotation).resolve()
        try:
            annotation = load_annotation(annotation_source)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        issues = annotation_issues(annotation, sample_id)
        if issues:
            for issue in issues:
                print(f"ERROR: {issue}", file=sys.stderr)
            return 2
        annotation_target = dataset_dir / "annotations" / f"{sample_id}.json"
        annotation_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(annotation_source, annotation_target)
        annotation_relative = annotation_target.relative_to(dataset_dir).as_posix()

    media_relative = None
    media_sha256 = None
    if args.media:
        if args.rights_basis not in TRAINING_RIGHTS:
            print("ERROR: media requires a training-eligible rights basis.", file=sys.stderr)
            return 2
        media_source = Path(args.media).resolve()
        if not media_source.is_file():
            print(f"ERROR: media file not found: {media_source}", file=sys.stderr)
            return 2
        media_sha256 = sha256_file(media_source)
        duplicate = next(
            (record for record in records if record.get("media_sha256") == media_sha256),
            None,
        )
        if duplicate:
            print(
                f"ERROR: media duplicates sample '{duplicate.get('sample_id')}'.",
                file=sys.stderr,
            )
            return 2
        suffix = media_source.suffix.lower() or ".bin"
        media_target = dataset_dir / "media" / f"{sample_id}{suffix}"
        media_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(media_source, media_target)
        media_relative = media_target.relative_to(dataset_dir).as_posix()

    record = {
        "sample_id": sample_id,
        "platform": args.platform,
        "source_url": args.source_url or "",
        "creator": args.creator,
        "rights_basis": args.rights_basis,
        "permission_note": args.permission_note,
        "split": args.split,
        "media_path": media_relative,
        "media_sha256": media_sha256,
        "annotation_path": annotation_relative,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    append_manifest(dataset_dir, record)
    print(f"Registered {sample_id} ({args.rights_basis}, {args.split}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
