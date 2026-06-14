#!/usr/bin/env python3
"""Build a reviewable AutoCAD drawing package from a project JSON."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from cad_common import (
    load_json,
    load_rules,
    preflight_report,
    project_issues,
    sha256_file,
    write_json,
    write_text,
)
from generate_autolisp import GENERATOR_VERSION, generate
from analyze_space import analyze, markdown_report as space_markdown_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--rules")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-warnings", action="store_true")
    args = parser.parse_args()

    project_path = Path(args.project).resolve()
    project = load_json(project_path)
    rules = load_rules(args.rules)
    errors, warnings = project_issues(project, rules)
    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 2
    if warnings and not args.allow_warnings:
        for item in warnings:
            print(f"WARNING: {item}", file=sys.stderr)
        print("Review warnings, then rerun with --allow-warnings.", file=sys.stderr)
        return 3

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    project_copy = output_dir / "project.json"
    rules_copy = output_dir / "rules.json"
    lisp_path = output_dir / "autocad-cn-drafting.lsp"
    report_path = output_dir / "preflight.md"
    space_json_path = output_dir / "space-analysis.json"
    space_report_path = output_dir / "space-analysis.md"
    shutil.copyfile(project_path, project_copy)
    write_json(rules_copy, rules)
    write_text(lisp_path, generate(project, rules))
    write_text(report_path, preflight_report(project, errors, warnings))
    space_result = analyze(project, rules)
    write_json(space_json_path, space_result)
    write_text(space_report_path, space_markdown_report(space_result))
    if space_result["status"] in {"invalid_project", "fail"}:
        print("ERROR: Ergonomic space analysis failed.", file=sys.stderr)
        return 4

    manifest = {
        "package_version": GENERATOR_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "alpha_human_review_required",
        "project": project.get("metadata", {}),
        "files": {},
        "required_operator_commands": ["APPLOAD", "CADBUILD", "CADAUDIT"],
        "expected_manual_outputs": ["DWG", "ASCII DXF", "PDF"],
    }
    for path in (
        project_copy,
        rules_copy,
        lisp_path,
        report_path,
        space_json_path,
        space_report_path,
    ):
        manifest["files"][path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    write_json(output_dir / "manifest.json", manifest)
    print(f"Built package in {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
