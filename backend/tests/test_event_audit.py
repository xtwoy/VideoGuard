
import unittest
from src.pead_engine import build_event_findings

class EventAuditTest(unittest.TestCase):
    def test_events_keep_separate_contexts(self):
        observations=[
            {"id":"E1","referent_key":"A","modality":"visual","tag":"danger_action"},
            {"id":"E2","referent_key":"A","modality":"speech","tag":"encouragement"},
            {"id":"E3","referent_key":"B","modality":"visual","tag":"danger_action"},
            {"id":"E4","referent_key":"B","modality":"speech","tag":"warning"},
        ]
        findings=[
            {"policy_id":"R_DANGER_PROMOTION","judgement":"SUPPORTED",
             "disposition":"FLAG","reason_code":"RELATED_ACTION_AND_PROMOTION",
             "supporting_ids":["E1","E2"],"counter_ids":[]},
            {"policy_id":"R_DANGER_PROMOTION","judgement":"CONFLICTED",
             "disposition":"REVIEW","reason_code":"CONFLICTING_STANCE",
             "supporting_ids":["E3"],"counter_ids":["E4"]}
        ]
        result=build_event_findings(observations, findings, 10000)
        self.assertEqual(len(result),2)
        self.assertNotEqual(result[0]["event_id"],result[1]["event_id"])

if __name__=="__main__":
    unittest.main()
