#!/usr/bin/env python3
"""Validate a CAD project JSON against the skill's baseline rules."""

from __future__ import annotations

import argparse
import sys

from cad_common import load_json, load_rules, preflight_report, project_issues, write_json, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Path to project JSON")
    parser.add_argument("--rules", help="Optional custom rules JSON")
    parser.add_argument("--report", help="Optional Markdown report path")
    parser.add_argument("--json-report", help="Optional JSON report path")
    args = parser.parse_args()

    project = load_json(args.project)
    rules = load_rules(args.rules)
    errors, warnings = project_issues(project, rules)
    status = "fail" if errors else "pass_with_warnings" if warnings else "pass"
    result = {"status": status, "errors": errors, "warnings": warnings}

    if args.report:
        write_text(args.report, preflight_report(project, errors, warnings))
    if args.json_report:
        write_json(args.json_report, result)

    print(f"Validation: {status}")
    for item in errors:
        print(f"ERROR: {item}")
    for item in warnings:
        print(f"WARNING: {item}")
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
