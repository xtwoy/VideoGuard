"""Public demo scenarios must preserve fixture expectations and synthetic provenance."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from fixtures.demo import CASE_ROOT, DEMO_CASES
from main import app


class DemoScenarioTests(unittest.TestCase):
    def test_catalog_cases_run_real_pead_and_export_without_network(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"VIDEOGUARD_DB": str(Path(directory) / "demo.db")}
        ), patch("socket.create_connection", side_effect=AssertionError("demo must stay offline")):
            client = TestClient(app)
            catalog = client.get("/api/demo/cases").json()["cases"]
            self.assertEqual([row["id"] for row in catalog], [row["id"] for row in DEMO_CASES])
            for entry in catalog:
                with self.subTest(case=entry["id"]):
                    response = client.post("/api/demo", params={"case": entry["id"]})
                    self.assertEqual(response.status_code, 200, response.text)
                    record = response.json()
                    self.assertEqual(record["mode"], "DEMO")
                    case_info = json.loads((CASE_ROOT / entry["id"] / "case.json").read_text(encoding="utf-8"))
                    self.assertEqual(record["duration_ms"], case_info["duration_ms"])
                    result = record["result"]
                    for stage in ("video_parse", "issue_locator", "relation_check", "audit_report"):
                        self.assertNotEqual(result["meta"][stage], "LIVE")
                    # The showcase cases carry an authored stage-4 report, so the demo
                    # must run the validated report path, not the fallback template.
                    self.assertEqual(result["meta"]["audit_report"], "DEMO_SYNTHETIC")
                    expected = case_info["expectations"]
                    findings = {row["policy_id"]: row for row in result["findings"]}
                    actual_active = {policy: [finding["judgement"], finding["disposition"]]
                                     for policy, finding in findings.items() if finding["disposition"] != "NONE"}
                    self.assertEqual(actual_active, expected["active_findings"])
                    self.assertEqual(result["audit_report"]["overall_verdict"], expected["verdict"])
                    self.assertEqual(result["audit_report"]["overall_score"], expected["score"])
                    self.assertTrue(result["meta"]["fixture_sha256"])
                    self.assertIsNotNone(result["audit_report"])
                    self.assertEqual(client.get(f"/api/reviews/{record['id']}").json(), record)
                    exported = client.get(f"/api/reviews/{record['id']}/report")
                    self.assertEqual(exported.status_code, 200)
                    self.assertIn("合成", exported.text)

    def test_unknown_or_path_like_case_is_rejected(self):
        client = TestClient(app)
        for name in ("missing", "../demo_video_parse_response", "", "C:/Windows"):
            with self.subTest(case=name):
                self.assertEqual(client.post("/api/demo", params={"case": name}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
