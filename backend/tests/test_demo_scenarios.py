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
                    self.assertEqual(record["duration_ms"], 24000)
                    result = record["result"]
                    for stage in ("video_parse", "issue_locator", "relation_check", "audit_report"):
                        self.assertNotEqual(result["meta"][stage], "LIVE")
                    expected = json.loads((CASE_ROOT / entry["id"] / "expectations.json").read_text(encoding="utf-8"))
                    findings = {row["policy_id"]: row for row in result["findings"]}
                    for policy, verdict in expected["findings"].items():
                        self.assertEqual([findings[policy]["judgement"], findings[policy]["disposition"]], verdict)
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
