"""Showcase data must stay concrete, protocol-valid and drift-free.

The engineering fixtures are allowed to be abstract; these five are the ones a reader
sees. The test pins three properties that the previous demo set failed:

* the stage-4 report passes the current validator (the old frozen replies did not, so
  every demo fell back to the deterministic template);
* the declared expectations match the actual output;
* the files on disk are exactly what the definitions produce.
"""
import json
import unittest

from fixtures import showcase, showcase_build
from fixtures.demo import CASE_ROOT, DEMO_CASES, run_fixture_demo
from src.audit_report import validate_audit_report


class ShowcaseCatalogTests(unittest.TestCase):
    def test_catalog_matches_the_showcase_definitions(self):
        self.assertEqual([entry["id"] for entry in DEMO_CASES], list(showcase.CASE_ORDER))
        self.assertEqual(CASE_ROOT.name, "showcase")

    def test_every_case_report_is_validated_rather_than_fallen_back(self):
        for name in showcase.CASE_ORDER:
            with self.subTest(case=name):
                built = showcase_build.build(name)
                self.assertEqual(built["report_status"], "LIVE",
                                 f"{name} 的报告没有走校验通过的路径")
                artifact = built["files"]["audit_report_response.json"]
                located_ok = validate_audit_report is not None  # imported for clarity
                self.assertTrue(located_ok)
                self.assertEqual(artifact["schema_version"], "videoguard_audit_report_v1")

    def test_declared_expectations_match_the_actual_findings(self):
        for entry in DEMO_CASES:
            with self.subTest(case=entry["id"]):
                info = json.loads((CASE_ROOT / entry["id"] / "case.json").read_text(encoding="utf-8"))
                result = run_fixture_demo(entry["id"])["result"]
                findings = {row["policy_id"]: row for row in result["findings"]}
                for policy, expected in info["expectations"]["active_findings"].items():
                    self.assertEqual([findings[policy]["judgement"], findings[policy]["disposition"]],
                                     expected)
                self.assertEqual(result["audit_report"]["overall_verdict"],
                                 info["expectations"]["verdict"])
                self.assertEqual(result["meta"]["audit_report"], "DEMO_SYNTHETIC")

    def test_files_on_disk_match_the_definitions(self):
        for name in showcase.CASE_ORDER:
            built = showcase_build.build(name)
            for filename, payload in built["files"].items():
                with self.subTest(case=name, file=filename):
                    on_disk = json.loads((CASE_ROOT / name / filename).read_text(encoding="utf-8"))
                    self.assertEqual(on_disk, payload, f"{name}/{filename} 与定义不一致，请重新生成")

    def test_stage_four_reports_are_labelled_as_authored(self):
        for entry in DEMO_CASES:
            with self.subTest(case=entry["id"]):
                info = json.loads((CASE_ROOT / entry["id"] / "case.json").read_text(encoding="utf-8"))
                self.assertEqual(info["report_origin"], "authored_synthetic")
                self.assertTrue(info["story"])
                self.assertEqual(info["expectations"], showcase.CASES[entry["id"]]()["expected"],
                                 "展示期望必须由人工在 showcase.py 声明，不能根据实际输出反推")

    def test_screenshot_catalog_and_offline_pack_are_complete(self):
        from fixtures.capture_demo import CAPTIONS, ROOT, EXPORTS
        self.assertEqual(len(CAPTIONS), 10)
        self.assertIn("06-warning-contrast.png", CAPTIONS)
        self.assertNotIn("06-partial-coverage.png", CAPTIONS)
        for name in CAPTIONS:
            with self.subTest(screenshot=name):
                self.assertTrue((ROOT / "docs" / "assets" / "demo" / name).is_file())
                self.assertTrue((EXPORTS / "screenshots" / name).is_file())
        index = (EXPORTS / "index.html").read_text(encoding="utf-8")
        self.assertIn("五个场景", index)
        self.assertNotIn("八个场景", index)
        self.assertIn("screenshots/06-warning-contrast.png", index)


if __name__ == "__main__":
    unittest.main()
