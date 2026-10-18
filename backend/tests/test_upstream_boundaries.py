"""Upstream boundaries: which evidence is asked about, attributed, and exported.

These cover the fifth audit round: candidate-pair truncation, cross-event evidence
references, self-contradictory relation answers, and where cleaning happens on the
capture path.
"""
import copy
import json
import unittest
from pathlib import Path

from fixtures.compare_pead import load_input
from pipeline import clean_issue_locator, clean_video_parse
from src.issue_locator_client import build_jev_request
from src.relation_client import (build_request, select_pairs,
                                 select_pairs_with_coverage, validate_response)
from src.redaction import redact

ROOT_CASE = "danger_promotion"


def observation(oid, tag, event, start, end):
    return {"id": oid, "tag": tag, "event_id": event, "modality": "speech",
            "start_ms": start, "end_ms": end, "source_refs": ["src:" + oid],
            "time_confidence": "HIGH"}


class CandidateCoverageTests(unittest.TestCase):
    def test_same_event_pair_is_not_crowded_out_by_closer_ones(self):
        """Distance alone must not decide which relation gets asked about."""
        action = observation("A1", "danger_action", "EVT_A", 10_000, 11_000)
        # Three nearer phrases that belong to other events.
        noise = [observation(f"N{i}", "encouragement", f"EVT_OTHER_{i}", 10_000 + i, 10_500 + i)
                 for i in (1, 2, 3)]
        target = observation("P1", "encouragement", "EVT_A", 11_500, 12_000)

        pairs, coverage = select_pairs_with_coverage([action, *noise, target], 30_000, limit=3)
        chosen = {pair["stance_id"] for pair in pairs}
        self.assertIn("P1", chosen, "同一事件的真实关系被更近的跨事件话语挤出候选")
        self.assertEqual(coverage["eligible"], 4)
        self.assertEqual(coverage["selected"], 3)
        self.assertEqual(coverage["omitted"], 1)

    def test_coverage_counts_match_selection(self):
        action = observation("A1", "danger_action", "EVT_A", 1000, 2000)
        stances = [observation(f"P{i}", "encouragement", "EVT_A", 1000, 2000) for i in range(5)]
        pairs, coverage = select_pairs_with_coverage([action, *stances], 30_000, limit=3)
        self.assertEqual(len(pairs), 3)
        self.assertEqual(coverage["eligible"], 5)
        self.assertEqual(coverage["omitted"], 2)
        # The list-only helper stays consistent with the counting one.
        self.assertEqual([p["pair_id"] for p in select_pairs([action, *stances], 30_000, limit=3)],
                         [p["pair_id"] for p in pairs])

    def test_truncated_candidates_are_not_reported_as_complete(self):
        """Answered pairs are not the same as all qualifying pairs."""
        from src.relation_fusion import assess_joint

        action = observation("A1", "danger_action", "EVT_A", 1000, 2000)
        stances = [observation(f"P{i}", "encouragement", "EVT_A", 1000, 2000) for i in range(5)]
        observations = [action, *stances]
        pairs, coverage = select_pairs_with_coverage(observations, 30_000, limit=3)
        self.assertGreater(coverage["omitted"], 0)
        request = build_request(pairs)
        answers = {}
        for pair in pairs:
            answers[f"{pair['pair_id']}_relation"] = {
                "type": "choice", "choice": "encourages_same", "confidence": 0.95,
                "probabilities": {"encourages_same": 0.92, "warns_same": 0.03,
                                  "unrelated": 0.03, "insufficient": 0.02}}
            answers[f"{pair['pair_id']}_review"] = {"type": "noul", "noul": 0.01}
        result = assess_joint({"observations": observations, "coverage": "FULL"},
                              30_000, {"answers": answers})
        self.assertEqual(result["semantic_check"], "PARTIAL_CANDIDATES")
        self.assertEqual(result["pair_coverage"]["omitted"], coverage["omitted"])


class CrossEventReferenceTests(unittest.TestCase):
    def _raw_parse(self):
        raw = copy.deepcopy(load_input(ROOT_CASE)["video_parse"])
        return raw

    def test_event_cannot_cite_a_fact_from_another_scene(self):
        raw = self._raw_parse()
        events = raw["timeline"]["events"]
        facts = {fact["fact_id"]: fact for shot in raw["timeline"]["shots"]
                 for field in ("visual_facts", "speech_transcript", "subtitle_text",
                               "screen_text", "audio_observations")
                 for fact in shot.get(field, [])}
        foreign = next(shot["shot_id"] + ":" + fact["fact_id"]
                       for shot in raw["timeline"]["shots"]
                       if shot["shot_id"] != events[0]["evidence_refs"][0].split(":")[0]
                       for field in ("visual_facts", "speech_transcript")
                       for fact in shot.get(field, []))
        events[0]["evidence_refs"] = list(events[0]["evidence_refs"]) + [foreign]
        with self.assertRaises(ValueError):
            clean_video_parse(raw, 25_000)

    def test_counter_context_refs_follow_the_same_attribution_rule(self):
        raw = self._raw_parse()
        events = raw["timeline"]["events"]
        events[0].setdefault("context", {})["counter_context_refs"] = ["S999:F999"]
        with self.assertRaises(ValueError):
            clean_video_parse(raw, 25_000)

    def test_cue_cannot_borrow_another_events_evidence(self):
        raw = load_input(ROOT_CASE)
        parsed = clean_video_parse(copy.deepcopy(raw["video_parse"]), raw["duration_ms"])
        locator = copy.deepcopy(raw["issue_locator"])
        cue = locator["risk_cues"][0]
        detail = parsed["observation_detail"]
        owner = next(event for event in detail["timeline"]["events"]
                     if event["event_id"] == cue["event_id"])
        outside = [f"{shot['shot_id']}:{fact['fact_id']}"
                   for shot in detail["timeline"]["shots"]
                   for field in ("visual_facts", "speech_transcript", "subtitle_text",
                                 "screen_text", "audio_observations")
                   for fact in shot.get(field, [])
                   if not (fact["start_ms"] < owner["end_ms"] and owner["start_ms"] < fact["end_ms"])]
        self.assertTrue(outside, "该用例没有事件范围之外的事实，无法构造越界引用")
        cue["evidence_refs"] = [outside[0]]
        with self.assertRaises(ValueError):
            clean_issue_locator(locator, parsed)


class RelationAnswerConsistencyTests(unittest.TestCase):
    def _payload(self):
        return {"model": "m", "state": {"pairs": ["pair_0"]},
                "questions": {"pair_0_relation": {}, "pair_0_review": {}}}

    def _response(self, choice, probabilities, confidence=0.99):
        return {"answers": {
            "pair_0_relation": {"type": "choice", "choice": choice,
                                "confidence": confidence, "probabilities": probabilities},
            "pair_0_review": {"type": "noul", "noul": 0.01},
        }}

    def test_every_choice_contradicting_its_distribution_is_rejected(self):
        for choice in ("encourages_same", "warns_same", "unrelated"):
            with self.subTest(choice=choice):
                probabilities = {name: 0.01 for name in
                                 ("encourages_same", "warns_same", "unrelated", "insufficient")}
                probabilities["insufficient"] = 0.97
                result = validate_response(
                    self._payload(), self._response(choice, probabilities))
                self.assertEqual(result[0]["status"], "INVALID_RESPONSE")
                self.assertEqual(result[0]["reason"], "PROBABILITY_CONFLICT")

    def test_consistent_answer_is_still_accepted(self):
        probabilities = {"encourages_same": 0.9, "warns_same": 0.03,
                         "unrelated": 0.05, "insufficient": 0.02}
        result = validate_response(self._payload(),
                                   self._response("encourages_same", probabilities))
        self.assertEqual(result[0]["status"], "VALID")
        self.assertEqual(result[0]["choice"], "encourages_same")


class CapturePayloadTests(unittest.TestCase):
    def test_unknown_context_fields_never_reach_the_locator_request(self):
        raw = copy.deepcopy(load_input(ROOT_CASE)["video_parse"])
        event = raw["timeline"]["events"][0]
        event.setdefault("context", {})
        event["context"]["reviewer_note"] = "张三 138-1234-5678 住 XX路88号"
        parsed = clean_video_parse(raw, 25_000)
        payload = json.dumps(build_jev_request(parsed["observation_detail"]), ensure_ascii=False)
        self.assertNotIn("reviewer_note", payload)
        self.assertNotIn("张三", payload)
        self.assertNotIn("XX路", payload)


class RedactionTests(unittest.TestCase):
    def test_separated_mobile_numbers_are_covered(self):
        for value in ("138-1234-5678", "138 1234 5678", "+86 138 1234 5678"):
            with self.subTest(value=value):
                self.assertNotIn("12345678", redact(f"联系 {value} 谢谢"))

    def test_known_gaps_stay_documented(self):
        # Bank card numbers and free-text addresses are out of scope; if this ever
        # becomes covered, update the module docstring and the report wording too.
        self.assertIn("6222021234567890123", redact("卡号 6222021234567890123"))
        self.assertIn("XX路88号", redact("地址 XX路88号"))


class CapturePayloadShapeTests(unittest.TestCase):
    """The capture tool must hand the locator the detail, not the wrapper."""

    def _parsed(self):
        raw = load_input(ROOT_CASE)
        return clean_video_parse(copy.deepcopy(raw["video_parse"]), raw["duration_ms"])

    def test_wrapper_and_detail_are_not_interchangeable(self):
        from fixtures.upstream_capture import locator_payload

        parsed = self._parsed()
        wrong = build_jev_request(parsed)
        right = build_jev_request(locator_payload(parsed))
        self.assertEqual(wrong["state"]["events"], [])
        self.assertEqual(wrong["questions"], {})
        self.assertTrue(right["state"]["events"])
        self.assertTrue(right["questions"])

    def test_capture_hands_the_locator_the_detail_not_the_wrapper(self):
        """Call-level guard: fixing the helper is useless if capture bypasses it."""
        import contextlib
        import io
        import os
        import tempfile
        from unittest.mock import patch

        from fixtures import upstream_capture

        raw = load_input(ROOT_CASE)["video_parse"]
        seen = {}

        def fake_locate(payload):
            seen["payload"] = payload
            return {"schema_version": "videoguard_issue_locator_v1",
                    "risk_cues": [], "limitations": []}

        def fake_parse(_data_url, _duration, _title):
            return copy.deepcopy(raw)

        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "sample.mp4"
            video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
            env = {"VIDEO_MODEL_API_KEY": "k", "VIDEO_MODEL_BASE_URL": "http://x",
                   "VIDEO_PARSE_MODEL": "m", "ISSUE_LOCATOR_API_KEY": "k",
                   "ISSUE_LOCATOR_ENDPOINT": "http://y"}
            with patch.dict(os.environ, env), \
                    patch("dotenv.load_dotenv"), \
                    patch("main.validate_video", return_value="sample.mp4"), \
                    patch("main.probe_duration_ms", return_value=25_000), \
                    patch("src.model_gateway.parse_video", side_effect=fake_parse), \
                    patch("src.issue_locator_client.locate_issues", side_effect=fake_locate):
                with contextlib.redirect_stdout(io.StringIO()):
                    snapshot = upstream_capture.capture(video, "样例")

        payload = seen.get("payload")
        self.assertIsInstance(payload, dict, "locate_issues 没有被调用")
        self.assertIn("timeline", payload)
        self.assertTrue(payload["timeline"]["events"], "事件为空：说明传的是外层包装")
        self.assertNotIn("observation_detail", payload)
        # The raw provider reply is still preserved for forensics.
        self.assertEqual(snapshot["video_parse"]["coverage"]["status"], raw["coverage"]["status"])

    def test_missing_detail_is_rejected_instead_of_silently_emptied(self):
        from fixtures.upstream_capture import locator_payload

        with self.assertRaises(ValueError):
            locator_payload({"coverage": "FULL"})


class StructuredIdentifierTests(unittest.TestCase):
    """IDs are forwarded to external services, so the schema charset is enforced."""

    def _raw(self):
        return copy.deepcopy(load_input(ROOT_CASE)["video_parse"])

    def test_email_in_event_id_is_rejected(self):
        raw = self._raw()
        raw["timeline"]["events"][0]["event_id"] = "alice@example.com"
        with self.assertRaises(ValueError):
            clean_video_parse(raw, 25_000)

    def test_sensitive_text_in_fact_id_is_rejected(self):
        raw = self._raw()
        raw["timeline"]["shots"][0]["speech_transcript"][0]["fact_id"] = "张三 138-1234-5678"
        with self.assertRaises(ValueError):
            clean_video_parse(raw, 25_000)

    def test_normal_identifiers_still_pass(self):
        parsed = clean_video_parse(self._raw(), 25_000)
        self.assertTrue(parsed["observation_detail"]["timeline"]["events"])



if __name__ == "__main__":
    unittest.main()
