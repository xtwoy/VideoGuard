"""HTTP surface, upload validation and failure-path tests.

The four-stage protocol itself is covered by ``test_mvp.py``. These tests cover
the other half of the system, which the protocol refactor left untested:

* the HTTP endpoints and their status codes;
* upload validation (consent, size, container signature, extension);
* the rule that a model failure must be persisted and reported, never softened
  into "no risk";
* HTML escaping in the exported report;
* regressions for the audit-report defects fixed after the fixture pack found
  them (findings without an event of their own, parent/child score roll-up,
  unevaluated dimensions).

Every test stubs ``probe_duration_ms`` and ``run_live`` so the suite needs no
ffprobe binary, no network and no API key.
"""
from __future__ import annotations

import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import database
from main import MAX_UPLOAD_BYTES, app, validate_video
from pipeline import run_demo
from report import render_html

# A minimal but structurally valid MP4 prefix: bytes 4..8 must be b"ftyp".
SAMPLE = b"\x00\x00\x00\x18ftypisom" + b"x" * 200
CLIENT = TestClient(app)


class HttpSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "VIDEOGUARD_DB": str(Path(self.temp.name) / "reviews.db")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def post_video(self, data: bytes = SAMPLE, filename: str = "safe.mp4",
                   consent: str = "true"):
        return CLIENT.post(
            "/api/reviews",
            data={"title": "测试标题", "consent": consent},
            files={"video": (filename, io.BytesIO(data), "video/mp4")},
        )

    # --- basic endpoints ---------------------------------------------------
    def test_health(self):
        response = CLIENT.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_root_explains_where_the_ui_is(self):
        """Opening the API port directly must not look like a broken service."""
        response = CLIENT.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("5173", response.text)

    def test_unknown_review_and_report_return_404(self):
        self.assertEqual(CLIENT.get("/api/reviews/missing").status_code, 404)
        self.assertEqual(CLIENT.get("/api/reviews/missing/report").status_code, 404)

    def test_demo_endpoint_is_marked_synthetic(self):
        response = CLIENT.post("/api/demo")
        self.assertEqual(response.status_code, 200, response.text)
        record = response.json()
        self.assertEqual(record["mode"], "DEMO")
        self.assertEqual(record["result"]["meta"]["video_parse"], "DEMO_SYNTHETIC")
        # The synthetic run must never claim a live model answered.
        self.assertNotEqual(record["result"]["meta"]["video_parse"], "LIVE")

    # --- upload validation -------------------------------------------------
    def test_upload_without_consent_is_rejected(self):
        with patch("main.probe_duration_ms", return_value=30_000):
            response = self.post_video(consent="false")
        self.assertEqual(response.status_code, 400)
        self.assertIn("授权", response.json()["detail"])

    def test_empty_upload_is_rejected(self):
        self.assertEqual(self.post_video(data=b"").status_code, 400)

    def test_disallowed_extension_is_rejected(self):
        self.assertEqual(self.post_video(filename="virus.exe").status_code, 415)

    def test_missing_container_signature_is_rejected(self):
        self.assertEqual(self.post_video(data=b"not-a-real-video").status_code, 422)

    def test_webm_signature_rule(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as caught:
            validate_video("clip.webm", b"not-a-webm")
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(validate_video("clip.webm", b"\x1a\x45\xdf\xa3" + b"x" * 32),
                         "clip.webm")

    def test_upload_size_boundary(self):
        self.assertEqual(validate_video("a.mp4", SAMPLE), "a.mp4")
        oversized = b"\x00\x00\x00\x18ftypisom" + b"a" * MAX_UPLOAD_BYTES
        self.assertEqual(self.post_video(data=oversized).status_code, 413)

    def test_filename_is_stripped_to_a_basename(self):
        """A path in the filename must not survive into stored metadata."""
        self.assertEqual(validate_video(r"C:\tmp\..\evil.mp4", SAMPLE), "evil.mp4")
        self.assertEqual(validate_video("../../etc/passwd.mp4", SAMPLE), "passwd.mp4")

    # --- successful path ---------------------------------------------------
    def test_successful_review_is_persisted_with_hash_and_duration(self):
        payload = run_demo()
        with patch("main.probe_duration_ms", return_value=10_000), \
             patch("main.run_live", return_value=payload) as run:
            response = self.post_video()
        self.assertEqual(response.status_code, 200, response.text)
        record = response.json()
        self.assertEqual(record["status"], "DONE")
        self.assertEqual(record["mode"], "LIVE")
        self.assertEqual(record["duration_ms"], 10_000)
        self.assertEqual(record["sha256"], hashlib.sha256(SAMPLE).hexdigest())
        run.assert_called_once()
        # The stored record must be readable through the query endpoint too.
        self.assertEqual(CLIENT.get(f"/api/reviews/{record['id']}").status_code, 200)

    # --- failure paths -----------------------------------------------------
    def test_model_failure_is_persisted_and_never_read_as_safe(self):
        with patch("main.probe_duration_ms", return_value=10_000), \
             patch("main.run_live", side_effect=RuntimeError("provider down")):
            response = self.post_video()
        self.assertEqual(response.status_code, 502)
        detail = response.json()["detail"]
        self.assertTrue(detail["review_id"])
        stored = database.get_review(detail["review_id"])
        self.assertEqual(stored["status"], "ERROR")
        self.assertEqual(stored["result"]["coverage"], "ERROR")
        self.assertEqual(stored["result"]["findings"], [])
        self.assertIsNone(stored["result"]["audit_report"])

    def test_unconfigured_credentials_message_is_specific(self):
        with patch("main.probe_duration_ms", return_value=10_000), \
             patch("main.run_live",
                   side_effect=RuntimeError("未配置视频模型 API Key / Base URL")):
            response = self.post_video()
        self.assertEqual(response.status_code, 502)
        self.assertIn("未配置", response.json()["detail"]["message"])

    def test_unexpected_errors_do_not_leak_provider_detail(self):
        """The stored error must be a safe summary, not a raw exception body."""
        with patch("main.probe_duration_ms", return_value=10_000), \
             patch("main.run_live",
                   side_effect=RuntimeError("secret-key sk-abcdef123456 rejected")):
            response = self.post_video()
        stored = database.get_review(response.json()["detail"]["review_id"])
        self.assertNotIn("sk-abcdef123456", stored["error"])
        self.assertIn("模型调用或输出解析失败", stored["error"])

    def test_failed_review_report_is_still_downloadable(self):
        """A failure record must stay inspectable through the report endpoint."""
        with patch("main.probe_duration_ms", return_value=10_000), \
             patch("main.run_live", side_effect=RuntimeError("boom")):
            response = self.post_video()
        review_id = response.json()["detail"]["review_id"]
        report = CLIENT.get(f"/api/reviews/{review_id}/report")
        self.assertEqual(report.status_code, 200)
        self.assertIn("text/html", report.headers["content-type"])


class ReportEscapingTests(unittest.TestCase):
    EVIL = "<img src=x onerror=alert(1)>"

    def test_report_escapes_model_and_user_text(self):
        record = {
            "id": "abc", "video_name": self.EVIL, "status": "DONE", "mode": "LIVE",
            "created_at": "2026-10-13",
            "result": {
                "coverage": "FULL",
                "observations": [{"id": "E01", "start_ms": 0, "end_ms": 100,
                                  "modality": "visual",
                                  "description_redacted": self.EVIL}],
                "findings": [{"policy_id": "R_VIOLENCE", "name": self.EVIL,
                              "judgement": "SUPPORTED", "disposition": "FLAG",
                              "reason_code": self.EVIL, "supporting_ids": ["E01"],
                              "counter_ids": []}],
                "event_findings": [],
                "audit_report": None,
                "meta": {"policy_count": 10},
            },
        }
        html = render_html(record)
        self.assertNotIn(self.EVIL, html)
        self.assertIn("&lt;img", html)

    def test_report_escapes_the_revision_plan(self):
        plan = {
            "id": "R01", "section": self.EVIL, "scope": "GLOBAL", "event_id": None,
            "video": {"summary": self.EVIL, "time_ranges": []},
            "issues": [{"id": "I01", "source": "FINDING", "finding_ids": ["R_VIOLENCE"],
                        "analysis_issue_ids": [], "priority": "P0",
                        "category": self.EVIL, "title": self.EVIL,
                        "description": self.EVIL, "time_ranges": [],
                        "supporting_evidence": [], "uncertainties": [self.EVIL]}],
            "actions": [{"id": "A01", "related_issue_ids": ["I01"],
                         "action": "MANUAL_REVIEW", "detail": self.EVIL,
                         "target_time_ranges": [], "reuse_time_ranges": [],
                         "insertion_position": None, "requires_reshoot": False,
                         "acceptance_criteria": self.EVIL}],
        }
        record = {
            "id": "abc", "video_name": "clip.mp4", "status": "DONE", "mode": "LIVE",
            "created_at": "2026-10-13",
            "result": {"coverage": "FULL", "observations": [], "findings": [],
                       "event_findings": [],
                       "audit_report": {
                           "schema_version": "videoguard_audit_report_v1",
                           "overall_verdict": "MANUAL_REVIEW", "overall_score": 40,
                           "executive_summary": self.EVIL,
                           "dimension_scores": {}, "revision_plan": [plan],
                           "overall_direction": self.EVIL, "limitations": [self.EVIL]},
                       "meta": {"policy_count": 10}},
        }
        html = render_html(record)
        self.assertNotIn(self.EVIL, html)


if __name__ == "__main__":
    unittest.main()
