from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "autocad-cn-drafting-skill"
SCRIPTS = SKILL / "scripts"
PROJECT_PATH = ROOT / "examples" / "apartment" / "project.json"

sys.path.insert(0, str(SCRIPTS))

from analyze_space import analyze  # noqa: E402
from audit_dxf import audit  # noqa: E402
from cad_common import load_json, load_rules, project_issues  # noqa: E402
from generate_autolisp import generate  # noqa: E402
from svg_to_project import convert_svg, determine_scale  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = load_json(PROJECT_PATH)
        self.rules = load_rules()

    def test_example_project_validates(self) -> None:
        errors, warnings = project_issues(self.project, self.rules)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_open_issue_blocks_generation(self) -> None:
        self.project["metadata"]["open_issues"] = ["Confirm wall thickness"]
        errors, _ = project_issues(self.project, self.rules)
        self.assertTrue(any("open_issues" in item for item in errors))

    def test_unknown_ergonomic_profile_fails(self) -> None:
        self.project["rooms"][0]["user_profiles"] = ["unknown"]
        errors, _ = project_issues(self.project, self.rules)
        self.assertTrue(any("unknown user profiles" in item for item in errors))


class SpaceAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = load_json(PROJECT_PATH)
        self.rules = load_rules()

    def test_example_space_analysis_passes(self) -> None:
        result = analyze(self.project, self.rules)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["rooms"]), 1)
        self.assertGreater(result["rooms"][0]["nominal_circulation_reserve_ratio"], 0.3)

    def test_furniture_collision_is_error(self) -> None:
        collision = copy.deepcopy(self.project["furniture"][0])
        collision["id"] = "F-COLLISION"
        collision["clearance_zones"] = []
        self.project["furniture"].append(collision)
        result = analyze(self.project, self.rules)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any(item["code"] == "FURNITURE_COLLISION" for item in result["findings"])
        )

    def test_path_width_uses_governing_profile(self) -> None:
        self.project["circulation_paths"][0]["user_profiles"] = ["accessible_wheelchair"]
        self.project["circulation_paths"][0]["clear_width"] = 1000
        result = analyze(self.project, self.rules)
        finding = next(
            item for item in result["findings"] if item["code"] == "INSUFFICIENT_PATH_WIDTH"
        )
        self.assertEqual(finding["target_mm"], 1200)
        self.assertEqual(finding["governing_profile"], "accessible_wheelchair")


class GeneratorTests(unittest.TestCase):
    @staticmethod
    def assert_lisp_balanced(test_case: unittest.TestCase, text: str) -> None:
        depth = 0
        in_string = False
        escaped = False
        for line in text.splitlines():
            for char in line:
                if escaped:
                    escaped = False
                    continue
                if in_string and char == "\\":
                    escaped = True
                    continue
                if char == '"':
                    in_string = not in_string
                elif not in_string and char == ";":
                    break
                elif not in_string and char == "(":
                    depth += 1
                elif not in_string and char == ")":
                    depth -= 1
                    test_case.assertGreaterEqual(depth, 0)
        test_case.assertFalse(in_string)
        test_case.assertEqual(depth, 0)

    def test_lisp_contains_commands_and_ergonomic_layers(self) -> None:
        project = load_json(PROJECT_PATH)
        text = generate(project, load_rules())
        self.assertIn("(defun c:CADBUILD", text)
        self.assertIn("(defun c:CADAUDIT", text)
        self.assertIn('"A-FURN"', text)
        self.assertIn('"A-NPLT-REVIEW"', text)
        self.assertIn("cad:*font-candidates*", text)
        self.assertIn('"CN-CAD-DIM"', text)
        self.assertIn("(entmod data)", text)
        self.assertNotIn("vl-load-com", text)
        self.assert_lisp_balanced(self, text)

    def test_build_package_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build_package.py"),
                    str(PROJECT_PATH),
                    "--output-dir",
                    temp,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = {
                "project.json",
                "rules.json",
                "autocad-cn-drafting.lsp",
                "preflight.md",
                "space-analysis.json",
                "space-analysis.md",
                "manifest.json",
            }
            self.assertTrue(expected.issubset({path.name for path in Path(temp).iterdir()}))
            manifest = json.loads((Path(temp) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "alpha_human_review_required")


class SvgTests(unittest.TestCase):
    def test_physical_svg_scale_and_geometry(self) -> None:
        path = ROOT / "examples" / "svg" / "simple-plan.svg"
        root = ET.parse(path).getroot()
        scale, verified, method = determine_scale(root, None, None)
        self.assertEqual(scale, 10.0)
        self.assertTrue(verified)
        self.assertEqual(method, "physical_svg_units")
        geometry = convert_svg(path, scale)
        self.assertEqual(len(geometry), 5)
        self.assertTrue(all(item["layer"] == "A-REF" for item in geometry))


class DxfTests(unittest.TestCase):
    def test_clean_ascii_dxf_has_no_errors(self) -> None:
        result = audit(ROOT / "examples" / "dxf" / "sample-clean.dxf", load_rules())
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["entity_count"], 3)

    def test_unknown_layer_and_zero_length_fail(self) -> None:
        content = """0
SECTION
2
ENTITIES
0
LINE
8
BAD-LAYER
10
1
20
1
11
1
21
1
0
ENDSEC
0
EOF
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.dxf"
            path.write_text(content, encoding="ascii")
            result = audit(path, load_rules())
        codes = {item["code"] for item in result["errors"]}
        self.assertEqual({"UNKNOWN_LAYER", "ZERO_LENGTH_LINE"}, codes)


if __name__ == "__main__":
    unittest.main()
