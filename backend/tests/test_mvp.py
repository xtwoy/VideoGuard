import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from pipeline import clean_video_parse, clean_issue_locator, run_demo, run_live
from main import report as report_endpoint
from src.audit_report import build_fallback_audit_report, validate_audit_report
from src.issue_locator_client import adapt_jev_response, build_jev_request

ROOT = Path(__file__).resolve().parents[1]
PARSE = json.loads((ROOT / "fixtures/demo_video_parse_response.json").read_text(encoding="utf-8"))
LOCATOR = json.loads((ROOT / "fixtures/demo_issue_locator_response.json").read_text(encoding="utf-8"))


class ProtocolTests(unittest.TestCase):
    def test_demo_uses_traceable_parse_and_structured_audit_report(self):
        result = run_demo()
        self.assertEqual(result["meta"]["video_parse"], "DEMO_SYNTHETIC")
        self.assertEqual(result["meta"]["issue_locator"], "DEMO_SYNTHETIC")
        self.assertEqual(len(result["findings"]), 10)
        self.assertEqual(len(result["observations"]), 8)
        self.assertEqual(result["audit_report"]["schema_version"], "videoguard_audit_report_v1")
        self.assertTrue(result["audit_report"]["revision_plan"])

    def test_video_parse_is_facts_only(self):
        parsed = clean_video_parse(PARSE, 25_000)
        self.assertEqual(parsed["observation_detail"]["schema_version"], "videoguard_video_parse_v2")
        self.assertNotIn("risk_cues", parsed["observation_detail"])
        fact = parsed["observation_detail"]["timeline"]["shots"][0]["visual_facts"][0]
        self.assertEqual((fact["start_ms"], fact["end_ms"]), (1200, 4800))
        summary = parsed["observation_detail"]["video_summary"]
        self.assertTrue(summary["evidence_refs"])
        self.assertTrue(summary["time_ranges"])

    def test_content_analysis_requires_a_limitation_when_it_has_no_evidence(self):
        broken = deepcopy(PARSE)
        section = broken["content_analysis"]["audio_visual_quality"]
        section["evidence_refs"] = []
        section["time_ranges"] = []
        section["limitations"] = []
        with self.assertRaises(ValueError):
            clean_video_parse(broken, 25_000)

    def test_content_analysis_only_carries_audio_visual_readability(self):
        """Commercial content-quality blocks are not part of this protocol."""
        parsed = clean_video_parse(PARSE, 25_000)
        self.assertEqual(set(parsed["observation_detail"]["content_analysis"]),
                         {"audio_visual_quality"})

    def test_legacy_content_quality_blocks_are_dropped_not_rejected(self):
        """A provider still sending the old blocks must not break the pipeline."""
        legacy = deepcopy(PARSE)
        legacy["content_analysis"]["material_completeness"] = {
            "summary": "旧协议残留", "observed_materials": [], "evidence_refs": [],
            "time_ranges": [], "issues": [], "limitations": ["历史字段"],
        }
        parsed = clean_video_parse(legacy, 25_000)
        self.assertNotIn("material_completeness", parsed["observation_detail"]["content_analysis"])

    def test_shot_quality_cannot_cite_another_shot(self):
        broken = deepcopy(PARSE)
        broken["timeline"]["shots"][0]["quality"]["visual"]["evidence_refs"] = ["S002:F004"]
        with self.assertRaises(ValueError):
            clean_video_parse(broken, 25_000)

    def test_old_video_protocol_is_rejected(self):
        with self.assertRaises(ValueError):
            clean_video_parse({"schema_version": "videoguard_observation_v2"})

    def test_full_coverage_rejects_a_shot_gap(self):
        broken = deepcopy(PARSE)
        broken["timeline"]["shots"][1]["start_ms"] = 5001
        with self.assertRaises(ValueError):
            clean_video_parse(broken, 25_000)

    def test_video_parse_requires_a_contiguous_shot_id_sequence(self):
        broken = deepcopy(PARSE)
        broken["timeline"]["shots"][1]["shot_id"] = "S003"
        with self.assertRaises(ValueError):
            clean_video_parse(broken, 25_000)

    def test_locator_requires_existing_event_and_fact_refs(self):
        parsed = clean_video_parse(PARSE, 25_000)
        bad = {"schema_version": "videoguard_issue_locator_v1", "risk_cues": [{
            "cue_id": "C1", "tag": "violence", "event_id": "missing", "modality": "visual",
            "evidence_refs": ["S01:F01"], "observation": "x"
        }]}
        with self.assertRaises(ValueError):
            clean_issue_locator(bad, parsed)

    def test_jev_request_uses_documented_typed_shape(self):
        request = build_jev_request(clean_video_parse(PARSE, 25_000)["observation_detail"])
        self.assertIn("state", request)
        self.assertIn("questions", request)
        self.assertTrue(all(item["type"] == "noul" for item in request["questions"].values()))
        question = request["questions"]["EVT_PRIVACY__pii_candidate"]
        self.assertIn("EVT_PRIVACY", question["instructions"])
        self.assertIn("pii_candidate", question["criteria"]["true"])

    def test_jev_response_is_adapted_without_provider_fields(self):
        detail = clean_video_parse(PARSE, 25_000)["observation_detail"]
        request = build_jev_request(detail)
        answers = {name: {"type": "noul", "noul": 0.0} for name in request["questions"]}
        answers["EVT_PRIVACY__pii_candidate"]["noul"] = 0.96
        output = adapt_jev_response(request, {"model": "provider-internal", "answers": answers})
        self.assertEqual(output["schema_version"], "videoguard_issue_locator_v1")
        self.assertEqual(output["risk_cues"][0]["event_id"], "EVT_PRIVACY")
        self.assertNotIn("model", output)

    def test_locator_projection_redacts_sensitive_values(self):
        parsed = clean_video_parse(PARSE, 25_000)
        output = clean_issue_locator(LOCATOR, parsed)
        self.assertNotIn("13812345678", str(output))
        privacy = next(item for item in output["observations"] if item["id"] == "E05")
        self.assertEqual((privacy["start_ms"], privacy["end_ms"]), (12500, 14500))

    def test_audit_report_rejects_an_uncovered_evidence_time_range(self):
        result = run_demo()
        candidate = deepcopy(result["audit_report"])
        candidate["revision_plan"][0]["issues"][0]["time_ranges"][0]["start_ms"] = 6000
        candidate["revision_plan"][0]["issues"][0]["time_ranges"][0]["end_ms"] = 6500
        self.assertIsNone(validate_audit_report(candidate, result, result["findings"], 25_000))

    def test_audit_report_requires_dimension_items_and_evidence_ranges(self):
        result = run_demo()
        candidate = deepcopy(result["audit_report"])
        candidate["dimension_scores"]["audit_coverage"]["items"] = []
        self.assertIsNone(validate_audit_report(candidate, result, result["findings"], 25_000))

        candidate = deepcopy(result["audit_report"])
        candidate["revision_plan"][0]["issues"][0]["supporting_evidence"][0]["time_ranges"] = []
        self.assertIsNone(validate_audit_report(candidate, result, result["findings"], 25_000))

    def test_analysis_issues_must_enter_the_revision_plan(self):
        raw = deepcopy(PARSE)
        raw["content_analysis"]["audio_visual_quality"]["issues"] = [{
            "id": "A_AV_01", "category": "AUDIOVISUAL", "severity": "LOW",
            "summary": "后段口播与背景音乐重叠，部分字句难以辨认。",
            "start_ms": 1200, "end_ms": 2300,
            "evidence_refs": ["S001:F001", "S001:F002"], "limitations": [],
        }]
        parsed = clean_video_parse(raw, 25_000)
        observations = clean_issue_locator(LOCATOR, parsed)
        findings = run_demo()["findings"]
        report = build_fallback_audit_report(observations, findings, 25_000)
        analysis_issues = [
            issue for plan in report["revision_plan"] for issue in plan["issues"]
            if issue["source"] == "ANALYSIS"
        ]
        self.assertEqual(analysis_issues[0]["analysis_issue_ids"], ["A_AV_01"])
        report["revision_plan"] = [
            plan for plan in report["revision_plan"]
            if not any(issue["source"] == "ANALYSIS" for issue in plan["issues"])
        ]
        self.assertIsNone(validate_audit_report(report, observations, findings, 25_000))

    def _readability_only_report(self):
        """A full-coverage video whose only problem is that it is hard to read."""
        raw = deepcopy(PARSE)
        raw["content_analysis"]["audio_visual_quality"]["issues"] = [{
            "id": "A_AV_02", "category": "AUDIOVISUAL", "severity": "MEDIUM",
            "summary": "背景音乐盖住口播，关键表述无法辨认。",
            "start_ms": 1200, "end_ms": 2300,
            "evidence_refs": ["S001:F001", "S001:F002"], "limitations": [],
        }]
        parsed = clean_video_parse(raw, 25_000)
        observations = clean_issue_locator(LOCATOR, parsed)
        benign = [{**finding, "judgement": "NOT_SUPPORTED", "disposition": "NONE"}
                  for finding in run_demo()["findings"]]
        report = build_fallback_audit_report(observations, benign, 25_000)
        return report, observations, benign

    def test_readability_problem_alone_does_not_ask_for_content_revision(self):
        """Unreadable audio is "we could not judge", not "rewrite the video"."""
        report, _, _ = self._readability_only_report()
        self.assertEqual(report["overall_verdict"], "MANUAL_REVIEW")
        self.assertNotEqual(report["overall_verdict"], "NEEDS_REVISION")
        self.assertIn("音画可读性", report["overall_direction"])

    def test_validator_rejects_needs_revision_driven_by_readability_alone(self):
        report, observations, findings = self._readability_only_report()
        candidate = deepcopy(report)
        candidate["overall_verdict"] = "NEEDS_REVISION"
        self.assertIsNone(validate_audit_report(candidate, observations, findings, 25_000))

    def test_dimension_lists_stay_in_sync_across_the_three_definitions(self):
        """The rubric lives in three files; a change to one must not drift."""
        from src.audit_report import DIMENSIONS
        from report import DIMENSION_LABELS

        self.assertEqual(list(DIMENSIONS), list(DIMENSION_LABELS))

        frontend = (ROOT.parent / "frontend" / "app" / "lib" / "labels.ts").read_text(encoding="utf-8")
        for name in DIMENSIONS:
            self.assertIn(f"{name}:", frontend, f"前端文案表缺少维度 {name}")
        for retired in ("material_completeness", "narrative_structure",
                        "hook_clarity", "subject_presentation"):
            self.assertNotIn(f"{retired}:", frontend, f"前端文案表仍保留已退役维度 {retired}")

    def test_report_keeps_disconnected_evidence_ranges_separate(self):
        result = run_demo()
        claim = next(plan for plan in result["audit_report"]["revision_plan"] if plan["event_id"] == "EVT_CLAIM")
        ranges = claim["issues"][0]["time_ranges"]
        self.assertEqual([(item["start_ms"], item["end_ms"]) for item in ranges], [(17000, 19000), (19500, 21500)])

    def test_html_report_is_inline_for_the_embedded_report_mode(self):
        record = {"id": "demo-report", "video_name": "demo", "mode": "DEMO", "status": "DONE", "result": run_demo()}
        with patch("main.get_review", return_value=record):
            response = report_endpoint("demo-report")
        self.assertTrue(response.headers["content-disposition"].startswith("inline;"))
        body = response.body.decode("utf-8")
        for label in ("审核覆盖", "证据可追溯性", "风险控制状态", "语境完整性", "音视频可读性"):
            self.assertIn(label, body)

    def test_exported_html_report_does_not_show_retired_content_quality_dimensions(self):
        """The printable report must not resurrect commercial quality dimensions."""
        record = {"id": "demo-report", "video_name": "demo", "mode": "DEMO", "status": "DONE", "result": run_demo()}
        with patch("main.get_review", return_value=record):
            body = report_endpoint("demo-report").body.decode("utf-8")
        for retired in ("素材完整性", "内容结构", "开头信息建立", "主体展示"):
            self.assertNotIn(retired, body, f"导出的报告仍渲染已退役维度：{retired}")

    def test_model_chain_accepts_separate_parse_and_locator(self):
        def fake_parse(url, duration, title):
            self.assertTrue(url.startswith("data:;base64,"))
            return PARSE

        def fake_locator(detail):
            self.assertEqual(detail["schema_version"], "videoguard_video_parse_v2")
            return LOCATOR

        with patch.dict(os.environ, {
            "VIDEO_MODEL_API_KEY": "key", "VIDEO_MODEL_BASE_URL": "https://example.invalid",
            "RELATION_MODEL_API_KEY": ""
        }, clear=False):
            result = run_live(b"video", 25_000, "demo", parse_fn=fake_parse,
                              locator_fn=fake_locator, relation_fn=lambda _: None,
                              report_fn=lambda _: None)
        self.assertEqual(result["meta"]["issue_locator"], "LIVE")
        self.assertEqual(len(result["observations"]), 8)
        self.assertEqual(result["audit_report"]["schema_version"], "videoguard_audit_report_v1")


if __name__ == "__main__":
    unittest.main()
