"""Counterexamples found by reviewing the first PyArg delivery."""
from __future__ import annotations
import copy
import itertools
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from src.evidence_graph import decide
from src.pead_rules import load_rules, RuleSet


def evidence(oid,tag,event='A',start=0,end=1000):
    return dict(id=oid,tag=tag,referent_key=event,modality='visual' if tag=='danger_action' else 'speech',start_ms=start,end_ms=end,source_refs=['src:'+oid],time_confidence='HIGH')


def relation(a,s,stance='encourages_same',**extra):
    return dict(action_id=a,stance_id=s,stance=stance,**extra)


def evaluate(atoms,relations=None,limit=0,**kwargs):
    return decide(atoms,30000,'FULL',15000,relations,counterfactual_limit=limit,**kwargs)


def base():return [evidence('A','danger_action'),evidence('P','encouragement')]


class EvidenceConsistencyTests(unittest.TestCase):
    def test_enumerated_scope_location_relation_and_coverage_invariants(self):
        rules=load_rules()
        choices=(None,'encourages_same','warns_same','unrelated','insufficient','REVIEW')
        combinations=itertools.product(('A','B',None),('A','B',None),(True,False),(True,False),choices,choices,('FULL','PARTIAL'),(True,False))
        checked=0
        for pe,we,pl,wl,pr,wr,coverage,required in combinations:
            atoms=[evidence('A','danger_action'),evidence('P','encouragement',pe,0 if pl else None,1000 if pl else None),
                   evidence('W','warning',we,0 if wl else None,1000 if wl else None)]
            relations=[relation('A',oid,choice) for oid,choice in [('P',pr),('W',wr)] if choice is not None]
            finding,graph=decide(atoms,30000,coverage,15000,relations,require_relation=required,counterfactual_limit=0,ruleset=rules)
            if we=='A':self.assertNotEqual(finding['disposition'],'FLAG')
            if pe=='A' and pl and pr=='encourages_same' and we=='B' and wr=='warns_same':
                self.assertEqual(finding['disposition'],'FLAG')
            ids={a['id'] for a in graph['arguments']}
            self.assertEqual(len(ids),len(graph['arguments']))
            self.assertTrue(all(e['source'] in ids and e['target'] in ids for e in graph['attacks']))
            block=finding['counter_evidence']
            self.assertEqual(block['found'],bool(finding['counter_ids']))
            if block['relation_checked']:
                self.assertEqual(block['relation_status'],'COMPLETE')
                self.assertGreater(block['relation_candidate_pairs'],0)
                self.assertEqual(block['relation_candidate_pairs'],block['relation_checked_pairs'])
            for row in graph['event_decisions']:
                labels=row['argument_labels']['labels']
                for node in graph['arguments']:
                    attackers=[edge['source'] for edge in graph['attacks'] if edge['target']==node['id']]
                    if node['label']=='IN':self.assertTrue(all(labels[a]=='OUT' for a in attackers))
                    elif node['label']=='OUT':self.assertTrue(any(labels[a]=='IN' for a in attackers))
                    else:
                        self.assertFalse(any(labels[a]=='IN' for a in attackers))
                        self.assertTrue(any(labels[a]=='UNDECIDED' for a in attackers))
                if row['disposition']=='FLAG':
                    self.assertTrue(any(node['label']=='IN' and node['polarity']=='SUPPORT' for node in graph['arguments']))
            checked+=1
        expected=3*3*2*2*len(choices)*len(choices)*2*2
        self.assertEqual(checked,expected)

    def test_unlocated_warning_is_retained_and_blocks_automatic_flag(self):
        finding,graph=evaluate(base()+[evidence('W','warning',start=None,end=None)],[relation('A','P')])
        self.assertEqual(finding['disposition'],'REVIEW')
        self.assertIn('W',finding['counter_ids'])
        self.assertTrue(finding['counter_evidence']['found'])
        self.assertTrue(any(a['kind']=='UNLOCATED_COUNTER' for a in graph['arguments']))

    def test_unlocated_counter_tags_are_all_conservative(self):
        for tag in ('warning','education_context','news_context','fiction_context'):
            with self.subTest(tag=tag):
                finding,_=evaluate(base()+[evidence('W',tag,start=None,end=None)],[relation('A','P')])
                self.assertEqual(finding['disposition'],'REVIEW')

    def test_model_warning_for_another_event_cannot_cancel_valid_support(self):
        finding,graph=evaluate(base()+[evidence('W','warning','B')],[relation('A','P'),relation('A','W','warns_same')])
        self.assertEqual(finding['disposition'],'FLAG')
        self.assertNotIn('W',finding['counter_ids'])
        invalid=[a for a in graph['arguments'] if a['kind']=='MODEL_COUNTER']
        self.assertTrue(invalid)
        self.assertTrue(all(a['label']=='OUT' for a in invalid))

    def test_unresolved_model_warning_is_reviewed_when_no_support_exists(self):
        finding,_=evaluate([evidence('A','danger_action'),evidence('W','warning',None)],[relation('A','W','warns_same')])
        self.assertEqual(finding['disposition'],'REVIEW')

    def test_structural_argument_ids_cannot_collide(self):
        atoms=[evidence('a:b','danger_action'),evidence('a','danger_action'),evidence('c','encouragement'),evidence('b:c','encouragement')]
        _,graph=evaluate(atoms,require_relation=False)
        nodes=[a for a in graph['arguments'] if a['kind']=='LOCAL_PROMOTION']
        expected={tuple(sorted(pair)) for pair in itertools.product(['a:b','a'],['c','b:c'])}
        self.assertEqual({tuple(a['premise_ids']) for a in nodes},expected)
        self.assertEqual(len(nodes),len(expected))
        self.assertEqual(len({a['id'] for a in nodes}),len(nodes))

    def test_reserved_event_prefixes_do_not_merge_known_and_unknown_events(self):
        atoms=[evidence('x','danger_action',None),evidence('y','danger_action','unresolved:x'),evidence('P','encouragement','unresolved:x')]
        _,graph=evaluate(atoms,require_relation=False)
        self.assertEqual(len(graph['event_decisions']),2)
        dispositions={r['disposition'] for r in graph['event_decisions']}
        self.assertEqual(dispositions,{'REVIEW','FLAG'})

    def test_static_assessment_never_claims_a_model_relation_was_checked(self):
        finding,_=evaluate(base(),require_relation=False)
        block=finding['counter_evidence']
        self.assertFalse(block['relation_checked'])
        self.assertEqual(block['relation_status'],'NOT_REQUIRED')
        self.assertEqual(block['relation_checked_pairs'],0)

    def test_explicit_event_ids_override_a_shared_actor_or_referent(self):
        atoms=base()+[evidence('W','warning')]
        for atom in atoms:
            atom['event_id']='EVENT_B' if atom['id']=='W' else 'EVENT_A'
            atom['referent_key']='same-actor'
        finding,graph=evaluate(atoms,[relation('A','P'),relation('A','W','warns_same')])
        self.assertEqual(finding['disposition'],'FLAG')
        self.assertEqual(graph['event_decisions'][0]['event_key'],'EVENT_A')
        self.assertNotIn('W',finding['counter_ids'])

    def test_mixed_scope_schemas_are_rejected_instead_of_silently_merged(self):
        atoms=base();atoms[0]['event_id']='A'
        with self.assertRaises(ValueError):evaluate(atoms)

    def test_partial_and_invalid_relation_results_are_not_reported_complete(self):
        atoms=base()+[evidence('P2','encouragement')]
        finding,_=evaluate(atoms,[relation('A','P')])
        block=finding['counter_evidence']
        self.assertEqual(block['relation_status'],'PARTIAL')
        self.assertLess(block['relation_checked_pairs'],block['relation_candidate_pairs'])
        self.assertFalse(block['relation_checked'])
        finding,_=evaluate(base(),[relation('A','P','REVIEW',valid=False)])
        self.assertEqual(finding['counter_evidence']['relation_status'],'NOT_CHECKED')

    def test_invalid_provider_reply_has_no_successful_relation_provenance(self):
        from src.relation_fusion import assess_joint
        result=assess_joint({'coverage':'FULL','observations':base()},30000,{})
        self.assertEqual(result['semantic_check'],'API_FAILED')
        finding=next(f for f in result['merged']['findings'] if f['policy_id']=='R_DANGER_PROMOTION')
        self.assertFalse(finding['counter_evidence']['relation_checked'])

    def test_invalid_flag_overrides_a_positive_stance_and_aliases_require_all_valid(self):
        finding,_=evaluate(base(),[relation('A','P',valid=False)])
        self.assertEqual(finding['disposition'],'REVIEW')
        atoms=base();alias=copy.deepcopy(atoms[1]);alias['id']='P_ALIAS';atoms.append(alias)
        finding,_=evaluate(atoms,[relation('A','P'),relation('A','P_ALIAS','REVIEW',valid=False)])
        self.assertEqual(finding['disposition'],'REVIEW')
        self.assertFalse(finding['counter_evidence']['relation_checked'])

    def test_graph_construction_stops_at_argument_and_attack_limits(self):
        for key in ('max_arguments','max_attacks'):
            raw=load_rules().model_dump(mode='json');raw['limits'][key]=1
            atoms=base()+[evidence('P2','encouragement'),evidence('W','warning')]
            with patch('src.argumentation.get_grounded_extension',side_effect=AssertionError('overflow must not solve')):
                finding,graph=evaluate(atoms,[relation('A','P')],ruleset=RuleSet.model_validate(raw))
            self.assertEqual(finding['disposition'],'REVIEW')
            self.assertLessEqual(len(graph['arguments']),raw['limits']['max_arguments'])
            self.assertLessEqual(len(graph['attacks']),raw['limits']['max_attacks'])
            self.assertFalse(finding['counter_evidence']['checked'])
            self.assertFalse(graph['certificates'])
            self.assertEqual(finding['counter_evidence']['relation_status'],'INCOMPLETE')

    def test_removal_distinguishes_global_result_from_event_changes(self):
        atoms=base()+[evidence('B','danger_action','B'),evidence('Q','encouragement','B')]
        _,graph=evaluate(atoms,[relation('A','P'),relation('B','Q')],limit=8)
        removed=next(row for row in graph['counterfactuals'] if row['removed_ids']==['P'])
        self.assertFalse(removed['changed'])
        self.assertEqual(removed['scope'],'GLOBAL_POLICY')
        event=next(row for row in removed['event_changes'] if row['event_key']=='A')
        self.assertEqual(event['before']['disposition'],'FLAG')
        self.assertNotEqual(event['after']['disposition'],'FLAG')

    def test_zero_removal_budget_is_explicit_and_not_called_overflow(self):
        from report import evidence_graph_content
        _,graph=evaluate(base(),[relation('A','P')],limit=0)
        self.assertEqual(graph['counterfactuals_skipped_reason'],'DISABLED')
        self.assertIn('预算为零',evidence_graph_content(graph))
        self.assertNotIn('本次超出求解规模预算',evidence_graph_content(graph))

    def test_malformed_fields_fail_closed_without_unhashable_type_errors(self):
        from src.pead_engine import assess
        for field,value in [('id',[]),('tag',[]),('modality',{}),('time_confidence',[]),('referent_key',{})]:
            atoms=base();atoms[1][field]=value
            result=assess({'coverage':'FULL','observations':atoms},30000)
            self.assertTrue(result['invalid_evidence_ids'])
        for invalid in ([],{},False):
            with self.assertRaises(ValueError):evaluate(base(),[relation('A','P',invalid)])


class RuleSafetyReviewTests(unittest.TestCase):
    def test_every_protected_generation_rule_rejects_disabling_conditions(self):
        original=load_rules().model_dump(mode='json')
        protected=[r['id'] for r in original['argument_rules'] if r['kind'] not in {'LOCAL_PROMOTION','MODEL_PROMOTION'}]
        for rid in protected:
            raw=copy.deepcopy(original)
            next(r for r in raw['argument_rules'] if r['id']==rid)['when']={'all_of':['coverage_failure']}
            with self.subTest(rule=rid):
                with self.assertRaises(ValidationError):RuleSet.model_validate(raw)

    def test_extra_support_rules_cannot_invent_evidence(self):
        raw=load_rules().model_dump(mode='json')
        extra=copy.deepcopy(next(r for r in raw['argument_rules'] if r['kind']=='MODEL_PROMOTION'))
        extra.update(id='A_FORGED_SUPPORT',when={})
        raw['argument_rules'].append(extra)
        with self.assertRaises(ValidationError):RuleSet.model_validate(raw)

    def test_failure_priorities_and_reason_codes_are_consistent(self):
        original=load_rules().model_dump(mode='json')
        raw=copy.deepcopy(original)
        for rule in raw['decision_rules']:
            if rule['id']=='D_UNAVAILABLE':rule['priority']=980
            elif rule['id']=='D_INVALID':rule['priority']=1000
        with self.assertRaises(ValidationError):RuleSet.model_validate(raw)
        raw=copy.deepcopy(original)
        next(r for r in raw['decision_rules'] if r['id']=='D_UNAVAILABLE')['reason_code']='NO_SUPPORTING_RELATION'
        with self.assertRaises(ValidationError):RuleSet.model_validate(raw)
        raw=copy.deepcopy(original)
        next(r for r in raw['decision_rules'] if r['id']=='D_LOCAL_SUPPORTED')['judgement']='NOT_SUPPORTED'
        with self.assertRaises(ValidationError):RuleSet.model_validate(raw)


class ReportAuthorityTests(unittest.TestCase):
    def state(self,name='relation_wrong_encouragement'):
        from fixtures.compare_pead import load_input
        from fixtures.simulate import simulate
        data=load_input(name)
        return simulate(data['video_parse'],data['issue_locator'],data['duration_ms'],data['relation'])

    def test_report_model_cannot_forge_counter_evidence_status(self):
        from src.audit_report import validate_audit_report
        state=self.state();raw=copy.deepcopy(state['audit_report'])
        for plan in raw['revision_plan']:
            plan['counter_evidence']={'checked':False,'source':'NOT_CHECKED','found':False,'relation_checked':True}
        cleaned=validate_audit_report(raw,state['located'],state['findings'],24000)
        self.assertIsNotNone(cleaned)
        blocks=[p['counter_evidence'] for p in cleaned['revision_plan'] if any('R_DANGER_PROMOTION' in i['finding_ids'] for i in p['issues'])]
        self.assertTrue(blocks)
        self.assertTrue(all(b['checked'] and b['found'] for b in blocks))

    def test_structured_safety_status_cannot_contradict_findings(self):
        from src.audit_report import validate_audit_report
        for name in ('danger_promotion','relation_wrong_encouragement'):
            state=self.state(name);raw=copy.deepcopy(state['audit_report'])
            dimension=raw['dimension_scores']['safety_risk_control']
            dimension.update(status='PASS',score=100)
            for item in dimension['items']:item.update(status='PASS',score=100)
            self.assertIsNone(validate_audit_report(raw,state['located'],state['findings'],24000))

    def test_locator_ids_cannot_overwrite_event_or_fact_catalog(self):
        from fixtures.compare_pead import load_input
        from pipeline import clean_video_parse,clean_issue_locator
        data=load_input('danger_promotion');parsed=clean_video_parse(data['video_parse'],24000)
        reserved=[parsed['observation_detail']['timeline']['events'][0]['event_id'],'S002:F001']
        for identifier in reserved:
            raw=copy.deepcopy(data['issue_locator']);raw['risk_cues'][0]['cue_id']=identifier
            with self.assertRaises(ValueError):clean_issue_locator(raw,parsed)

    def test_review_only_findings_recommend_manual_review(self):
        state=self.state()
        plans=[p for p in state['audit_report']['revision_plan'] if any('R_DANGER_PROMOTION' in i['finding_ids'] for i in p['issues'])]
        self.assertTrue(plans)
        self.assertTrue(all(a['action']=='MANUAL_REVIEW' for p in plans for a in p['actions']))

    def test_counter_aggregation_is_independent_of_finding_order(self):
        from src.audit_report import _counter_for_findings
        applicable={'counter_evidence':{'checked':True,'source':'COUNTER_CONTEXT_TAGS','found':True,'relation_checked':False}}
        ignored={'counter_evidence':{'checked':False,'source':'NOT_APPLICABLE','found':False,'relation_checked':False}}
        self.assertEqual(_counter_for_findings([applicable,ignored]),_counter_for_findings([ignored,applicable]))
        self.assertTrue(_counter_for_findings([ignored,applicable])['found'])

    def multi_event_report(self):
        from src.audit_report import build_fallback_audit_report
        state=self.state('danger_promotion');located=copy.deepcopy(state['located'])
        detail=located['observation_detail']
        evt=copy.deepcopy(detail['timeline']['events'][0]);evt['event_id']='EVT_REVIEW';detail['timeline']['events'].append(evt)
        originals=list(located['observations']);cues=list(detail['risk_cues'])
        for i,atom in enumerate(originals):
            clone=copy.deepcopy(atom);clone['id']='X'+atom['id'];clone['referent_key']='EVT_REVIEW';clone['event_id']='EVT_REVIEW';located['observations'].append(clone)
            cue=copy.deepcopy(cues[i]);cue['cue_id']=clone['id'];cue['event_id']='EVT_REVIEW';detail['risk_cues'].append(cue)
        rel=[relation('E01','E02'),relation('E01','E03'),relation('XE01','XE02','REVIEW')]
        finding,_=decide(located['observations'],24000,'FULL',15000,rel,counterfactual_limit=0)
        finding['id']=finding['policy_id']
        report=build_fallback_audit_report(located,[finding],24000)
        return located,finding,report

    def test_flagged_event_does_not_hide_reviewed_event_or_relabel_its_action(self):
        located,finding,report=self.multi_event_report()
        plans={p['event_id']:p for p in report['revision_plan'] if any('R_DANGER_PROMOTION' in i['finding_ids'] for i in p['issues'])}
        self.assertEqual(set(plans),{'EVT_DANGER','EVT_REVIEW'})
        self.assertTrue(all(a['action']=='REMOVE' for a in plans['EVT_DANGER']['actions']))
        self.assertTrue(all(a['action']=='MANUAL_REVIEW' for a in plans['EVT_REVIEW']['actions']))
        self.assertIn('XE01',finding['supporting_ids'])

    def test_model_report_must_cover_each_active_event(self):
        from src.audit_report import validate_audit_report
        located,finding,report=self.multi_event_report()
        self.assertIsNotNone(validate_audit_report(report,located,[finding],24000))
        report['revision_plan']=[p for p in report['revision_plan'] if p['event_id']!='EVT_REVIEW']
        self.assertIsNone(validate_audit_report(report,located,[finding],24000))

    def test_model_edit_on_review_only_issue_is_normalized_to_manual(self):
        from src.audit_report import validate_audit_report
        state=self.state();raw=copy.deepcopy(state['audit_report'])
        for plan in raw['revision_plan']:
            for action in plan['actions']:
                if any('R_DANGER_PROMOTION' in issue['finding_ids'] for issue in plan['issues']):
                    action.update(action='REMOVE',target_time_ranges=plan['issues'][0]['time_ranges'])
        cleaned=validate_audit_report(raw,state['located'],state['findings'],24000)
        self.assertIsNotNone(cleaned)
        actions=[a for p in cleaned['revision_plan'] if any('R_DANGER_PROMOTION' in i['finding_ids'] for i in p['issues']) for a in p['actions']]
        self.assertTrue(all(a['action']=='MANUAL_REVIEW' for a in actions))


class FrozenInputTests(unittest.TestCase):
    def test_fixture_inspection_is_read_only(self):
        from fixtures import generate
        root=Path('fixtures/cases')
        before={str(p):p.read_bytes() for p in root.rglob('*.json')}
        generate.build_manifest([generate.build_case(name) for name in __import__('fixtures.cases',fromlist=['CASE_ORDER']).CASE_ORDER])
        self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*.json')})

    def test_all_frozen_model_reports_have_their_declared_digest(self):
        import hashlib
        digests=json.loads(Path('fixtures/frozen_report_inputs.json').read_text(encoding='utf-8'))
        for name,digest in digests.items():
            self.assertEqual(hashlib.sha256((Path('fixtures/cases')/name/'audit_report_response.json').read_bytes()).hexdigest(),digest)


if __name__=='__main__':unittest.main()
