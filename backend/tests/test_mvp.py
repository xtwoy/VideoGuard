import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app, MAX_UPLOAD_BYTES, validate_video, probe_duration_ms
from database import get_review
from pipeline import clean_observations, run_demo, run_live, _run_models
from report import render_html

SAMPLE = b"\x00\x00\x00\x18ftypisom" + b"x"*200
CLIENT = TestClient(app)

class MVPSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{"VIDEOGUARD_DB":str(Path(self.temp.name)/"reviews.db")})
        self.env.start()
    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def post_video(self, data=SAMPLE, filename="safe.mp4", consent="true"):
        return CLIENT.post(
            "/api/reviews",
            data={"title":"测试标题","consent":consent},
            files={"video":(filename,io.BytesIO(data),"video/mp4")}
        )
    def test_health(self):
        self.assertEqual(CLIENT.get("/api/health").status_code,200)
    def test_missing_record(self):
        self.assertEqual(CLIENT.get("/api/reviews/missing").status_code,404)
        self.assertEqual(CLIENT.get("/api/reviews/missing/report").status_code,404)
    def test_demo_workflow_and_report(self):
        response=CLIENT.post("/api/demo")
        self.assertEqual(response.status_code,200,response.text)
        payload=response.json()
        self.assertEqual(payload["mode"],"DEMO")
        self.assertIn("DEMO_SYNTHETIC",payload["result"]["meta"]["omni"])
        self.assertEqual(len(payload["result"]["findings"]),10)
        self.assertEqual(sum(f["disposition"]!="NONE" for f in payload["result"]["findings"]),5)
        self.assertEqual(len(payload["result"]["observations"]),8)
        self.assertEqual(len(payload["result"]["event_findings"]),5)
        self.assertEqual(payload["result"]["meta"]["policy_count"],10)
        self.assertEqual(CLIENT.get("/api/reviews/"+payload["id"]).status_code,200)
        report=CLIENT.get(f"/api/reviews/{payload['id']}/report")
        self.assertEqual(report.status_code,200)
        self.assertIn("text/html",report.headers["content-type"])
        self.assertIn("attachment;",report.headers["content-disposition"])
        self.assertIn("合成演示",report.text)
        self.assertIn("修改建议",report.text)
        self.assertIn("事件级审计记录",report.text)
        self.assertIn("危险行为诱导",report.text)
        self.assertIn("已评估审核点",report.text)
        self.assertIn("10 类",report.text)
        self.assertNotIn("Jev",report.text)
        self.assertNotIn("Omni",report.text)
        self.assertNotIn("Qwen Max",report.text)
        self.assertNotIn("R_DANGER_PROMOTION",report.text)
        self.assertNotIn("JEV_UNAVAILABLE_SEMANTIC_REVIEW",report.text)
    def test_no_consent(self):
        with patch("main.probe_duration_ms",return_value=30000):
            response=self.post_video(consent="false")
        self.assertEqual(response.status_code,400)
    def test_empty_upload(self):
        r=self.post_video(data=b"")
        self.assertEqual(r.status_code,400)
    def test_disallow_extension(self):
        r=self.post_video(filename="virus.exe")
        self.assertEqual(r.status_code,415)
    def test_oversized_upload_boundary(self):
        self.assertEqual(validate_video("a.mp4",SAMPLE),"a.mp4")
        oversized=b"\x00\x00\x00\x18ftypisom"+b"a"*MAX_UPLOAD_BYTES
        r=self.post_video(data=oversized)
        self.assertEqual(r.status_code,413)
    def test_bad_video_signature(self):
        r=self.post_video(data=b"not-a-real-video")
        self.assertEqual(r.status_code,422)
    def test_upload_success_with_fake_model(self):
        data=run_demo()
        data["meta"]["omni"]="LIVE_FAKE_TEST"
        with patch("main.probe_duration_ms",return_value=10000),\
             patch("main.run_live",return_value=data) as remote:
            response=self.post_video()
        self.assertEqual(response.status_code,200,response.text)
        info=response.json()
        self.assertEqual(info["status"],"DONE")
        self.assertEqual(info["duration_ms"],10000)
        self.assertEqual(len(info["sha256"]),64)
        remote.assert_called_once()
        html=CLIENT.get(f"/api/reviews/{info['id']}/report").text
        self.assertIn("危险行为诱导",html)
        self.assertIn("VIDEOGUARD-E",html)
    def test_model_failure_is_logged_and_never_auto_cleared(self):
        with patch("main.probe_duration_ms",return_value=10000),\
             patch("main.run_live",side_effect=RuntimeError("no API")):
            response=self.post_video()
        self.assertEqual(response.status_code,502)
        detail=response.json()["detail"]
        record=get_review(detail["review_id"])
        self.assertEqual(record["status"],"ERROR")
        self.assertEqual(record["result"]["coverage"],"ERROR")
        self.assertEqual(record["result"]["findings"],[])
    def test_clean_provider_output_redacts_sensitive_values(self):
        parsed=clean_observations({
            "coverage":"FULL",
            "observations":[{
                "id":"E01","modality":"screen_text","tag":"pii_candidate",
                "start_ms":1000,"end_ms":2000,
                "text_redacted":"手机13812345678 / contact a@example.com"
            }],
            "candidate_risks":[]
        })
        dumped=str(parsed)
        self.assertNotIn("13812345678",dumped)
        self.assertNotIn("a@example.com",dumped)
    def test_invalid_observation_timestamp_is_not_exposed(self):
        parsed=clean_observations({
            "coverage":"FULL","observations":[{
                "id":"E01","modality":"visual","tag":"violence",
                "start_ms":9000,"end_ms":1000
            }]
        },duration_ms=5000)
        self.assertIsNone(parsed["observations"][0]["start_ms"])
        self.assertIsNone(parsed["observations"][0]["end_ms"])
    def test_provider_duplicate_evidence_rejected(self):
        with self.assertRaises(ValueError):
            clean_observations({
                "coverage":"FULL",
                "observations":[{"id":"A"},{"id":"A"}]
            })
    def test_unknown_coverage_wont_mean_safe(self):
        parsed=clean_observations({"coverage":"INVENTED","observations":[]})
        result=_run_models(parsed,1000,
                           jev_fn=lambda _:None,max_fn=lambda _:None,
                           allow_jev=False,allow_max=False)
        self.assertEqual(result["coverage"],"UNKNOWN")
        self.assertTrue(any(x["judgement"]=="UNKNOWN" for x in result["findings"]))
    def test_missing_omni_credentials(self):
        with patch.dict(os.environ,{"DASHSCOPE_API_KEY":"","DASHSCOPE_BASE_URL":""}):
            with self.assertRaises(RuntimeError):
                run_live(SAMPLE,1000,"test")
    def test_report_html_escapes_model_injection(self):
        evil='<img src=x onerror=alert(1)>'
        info={
            "id":"123","video_name":evil,"status":"DONE","mode":"LIVE",
            "result":{"coverage":"FULL","observations":[{
                "id":"A","start_ms":0,"end_ms":100,
                "modality":"visual","description_redacted":evil
            }],"findings":[{
                "policy_id":"R_VIOLENCE","name":evil,"judgement":"SUPPORTED",
                "disposition":"FLAG","reason_code":evil,"supporting_ids":["A"],
                "counter_ids":[]
            }],"recommendations":[{"finding_id":"R_VIOLENCE",
                "reason":evil,"edit_suggestions":[{"detail":evil}]}],
                "meta":{"omni":"LIVE"}},
            "created_at":"2026-10-12"
        }
        html=render_html(info)
        self.assertNotIn(evil,html)
        self.assertIn("&lt;img",html)
    def test_external_jev_absence_is_marked(self):
        result=run_demo()
        self.assertEqual(result["meta"]["jev"],"SKIPPED_NO_KEY")
        self.assertEqual(result["meta"]["jev_semantic_check"],"SKIPPED_NO_KEY")
        self.assertEqual(len(result["event_findings"]),5)
        by_policy={item["policy_id"]:item for item in result["event_findings"]}
        self.assertEqual(by_policy["R_DANGER_PROMOTION"]["disposition"],"REVIEW")
        self.assertEqual(by_policy["R_PRIVACY_EXPOSURE"]["disposition"],"FLAG")
        self.assertEqual(by_policy["R_FRAUD_SCAM"]["disposition"],"REVIEW")
    def test_partial_max_response_keeps_rule_templates_for_missing_findings(self):
        observations=clean_observations({
            "coverage":"FULL","observations":[
                {"id":"E1","modality":"visual","tag":"danger_action",
                 "start_ms":1000,"end_ms":4000,"referent_key":"A"},
                {"id":"E2","modality":"speech","tag":"encouragement",
                 "start_ms":2000,"end_ms":4500,"referent_key":"A"},
                {"id":"E3","modality":"screen_text","tag":"pii_candidate",
                 "start_ms":5000,"end_ms":6000}
            ]
        },duration_ms=10000)
        def partial_max(context):
            return {"items":[{
                "finding_id":"R_PRIVACY_EXPOSURE","reason":"疑似联系方式露出",
                "evidence_ids":["E3"],"edit_suggestions":[{
                    "time_start_ms":5200,"time_end_ms":5800,"action":"遮挡",
                    "detail":"遮挡疑似联系方式","evidence_ids":["E3"]
                }]
            }]}
        outcome=_run_models(observations,10000,jev_fn=lambda _:None,
                            max_fn=partial_max,allow_jev=False,allow_max=True)
        by_id={note["finding_id"]:note for note in outcome["recommendations"]}
        self.assertEqual(by_id["R_PRIVACY_EXPOSURE"]["source"],"QWEN_MAX")
        self.assertEqual(by_id["R_DANGER_PROMOTION"]["source"],"RULE_TEMPLATE")
    def test_configured_direct_cue_policy_is_audited(self):
        observations=clean_observations({
            "coverage":"FULL","observations":[{
                "id":"E1","modality":"speech","tag":"fraud_or_scam",
                "start_ms":1000,"end_ms":2000,"description_redacted":"疑似高风险获利诱导"
            }]
        },duration_ms=5000)
        outcome=_run_models(observations,5000,jev_fn=lambda _:None,
                            max_fn=lambda _:None,allow_jev=False,allow_max=False)
        finding=next(item for item in outcome["findings"]
                     if item["policy_id"]=="R_FRAUD_SCAM")
        self.assertEqual((finding["judgement"],finding["disposition"]),
                         ("SUPPORTED","REVIEW"))
        self.assertTrue(any(item["policy_id"]=="R_FRAUD_SCAM"
                            for item in outcome["event_findings"]))
    def test_full_model_chain_with_mocked_provider_responses(self):
        """Omni -> Jev -> PEAD -> Max, using fakes but real pipeline code."""
        def fake_omni(url, duration, title):
            self.assertTrue(url.startswith("data:;base64,"))
            return {
                "coverage":"FULL",
                "observations":[
                    {"id":"E1","modality":"visual","tag":"danger_action",
                     "start_ms":1000,"end_ms":4000,"referent_key":"A",
                     "description_redacted":"危险动作"},
                    {"id":"E2","modality":"speech","tag":"encouragement",
                     "start_ms":2000,"end_ms":4800,"referent_key":"A",
                     "description_redacted":"鼓励尝试"}
                ],
                "candidate_risks":[]
            }
        def fake_jev(request):
            answers={}
            for key in request["state"]["pairs"]:
                probs={s:(0.94 if s=="encourages_same" else 0.02)
                       for s in ("encourages_same","warns_same","unrelated","insufficient")}
                answers[f"{key}_relation"]={
                    "type":"choice","choice":"encourages_same",
                    "confidence":0.94,"probabilities":probs
                }
                answers[f"{key}_review"]={"type":"noul","noul":0.1}
            return {"model":"jev-1.13.0","answers":answers}
        def fake_max(context):
            self.assertTrue(any(f["policy_id"]=="R_DANGER_PROMOTION"
                                for f in context["findings"]))
            return {"items":[{
                "finding_id":"R_DANGER_PROMOTION",
                "reason":"语音与危险动作指向同一事件",
                "evidence_ids":["E1","E2"],
                "edit_suggestions":[{
                    "time_start_ms":2100,"time_end_ms":2600,
                    "action":"修改",
                    "detail":"删除引导模仿的语音",
                    "evidence_ids":["E2"]
                }]
            }]}
        with patch.dict(os.environ,{"DASHSCOPE_API_KEY":"fake-key",
                                     "DASHSCOPE_BASE_URL":"https://fake.example/v1",
                                     "TYPESAFE_API_KEY":"fake-key"}):
            outcome=run_live(
                SAMPLE,10000,"video",omni_fn=fake_omni,
                jev_fn=fake_jev,max_fn=fake_max
            )
        finding=next(x for x in outcome["findings"]
                     if x["policy_id"]=="R_DANGER_PROMOTION")
        self.assertEqual((finding["judgement"],finding["disposition"]),
                         ("SUPPORTED","FLAG"))
        self.assertEqual(outcome["meta"]["jev"],"LIVE")
        self.assertEqual(outcome["meta"]["max"],"LIVE")
        self.assertTrue(any(n["source"]=="QWEN_MAX"
                            for n in outcome["recommendations"]))
    def test_ffprobe_rejects_invalid_file(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            probe_duration_ms(SAMPLE,".mp4")

if __name__=="__main__":
    unittest.main()
