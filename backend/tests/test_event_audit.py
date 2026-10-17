
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

    def test_event_grouping_prefers_the_event_instance_over_the_referent(self):
        """Two distinct events pointing at the same entity must stay separate.

        `_same_referent` treats a differing event_id as a different event, so the
        grouping key must do the same; using referent_key first would merge them.
        """
        observations=[
            {"id":"E1","referent_key":"SAME_ENTITY","event_id":"EVT_A",
             "modality":"visual","tag":"danger_action","start_ms":1000,"end_ms":2000},
            {"id":"E2","referent_key":"SAME_ENTITY","event_id":"EVT_B",
             "modality":"speech","tag":"encouragement","start_ms":1100,"end_ms":1900},
        ]
        findings=[
            {"policy_id":"R_DANGER_PROMOTION","judgement":"CONFLICTED",
             "disposition":"REVIEW","reason_code":"CONFLICTING_STANCE",
             "supporting_ids":["E1","E2"],"counter_ids":[]}
        ]
        result=build_event_findings(observations, findings, 10000)
        self.assertEqual(len(result),2,"同一 referent_key 的两个事件被合并成了一条记录")
        self.assertEqual({item["event_id"] for item in result},
                         {"R_DANGER_PROMOTION:EVT_A","R_DANGER_PROMOTION:EVT_B"})
        self.assertEqual([item["evidence_ids"] for item in result], [["E1"],["E2"]])

if __name__=="__main__":
    unittest.main()
