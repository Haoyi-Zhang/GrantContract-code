"""Regression checks for the bounded operational protocol and its boundaries."""
import json
from pathlib import Path
import sys
import unittest
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from bridge import (State,MECHANISMS,plant_graph,oracle_edges,transitions,replay,
    grant_formula,all_continuations_safe,explore_case,pregrant_fibers,grant_allowed,symbol,knowledge_fibers)
from model import verdict,oracle,background
from bridge_study import EXPECTED_CASES,MP

class BridgeTests(unittest.TestCase):
    def test_all_state_codes(self):
        self.assertEqual({State.decode(n).code() for n in range(64)},set(range(64)))

    def test_reject_bad_state(self):
        for kw in ({'flag':True},{'old_pending':2},{'phase':-1},{'phase':4}):
            with self.assertRaises(ValueError):State(**kw)
        for code in (-1,64,True):
            with self.assertRaises(ValueError):State.decode(code)

    def test_unknown_mechanisms_and_policies(self):
        with self.assertRaises(ValueError):transitions(State(),'unknown')
        with self.assertRaises(ValueError):explore_case('raw','unknown')

    def test_transition_oracles(self):
        for mech in MECHANISMS:
            self.assertEqual(plant_graph(mech)[1],oracle_edges(mech))

    def test_state_transition_caps(self):
        for mech in MECHANISMS:
            states,edges=plant_graph(mech)
            self.assertLessEqual(len(states),64);self.assertLessEqual(len(edges),256)

    def test_all_reachable_grant_guards(self):
        for mech in MECHANISMS:
            for state in plant_graph(mech)[0]:
                if state.flag and state.phase==0:
                    self.assertEqual(grant_formula(state,mech),all_continuations_safe(state,mech))

    def test_raw_receipt_late_fill(self):
        s=replay('raw',1,['flag','ack','grant','fill','read0'])
        self.assertEqual(s.phase,2)

    def test_useful_action_envelope_distinguishes_generation(self):
        raw = explore_case("raw", "pending_receipt")["traces"]
        drain = explore_case("drain", "receipt")["traces"]
        generation = explore_case("generation", "receipt")["traces"]

        for row in raw:
            if row["outcome"] == "one":
                self.assertEqual(row["actions"].count("fill"), row["initial_old_pending"])
        for row in drain:
            if row["outcome"] == "one":
                self.assertEqual(row["actions"].count("fill"), row["initial_old_pending"])

        delivered = {
            row["actions"].count("fill")
            for row in generation
            if row["outcome"] == "one" and row["initial_old_pending"] == 1
        }
        self.assertEqual(delivered, {0, 1})

    def test_generation_discards_late_fill(self):
        s=replay('generation',1,['flag','ack','grant','fill','read1'])
        self.assertEqual(s.phase,3)
        with self.assertRaises(ValueError):replay('generation',1,['flag','ack','grant','fill','read0'])

    def test_drain_blocks_early_ack(self):
        with self.assertRaises(ValueError):replay('drain',1,['ack'])
        self.assertEqual(replay('drain',1,['fill','ack']).old_pending,0)

    def test_repeat_invalidation_repairs(self):
        s=replay('raw',1,['ack','fill','ack'])
        self.assertEqual((s.old_cache,s.old_pending),(0,0))
        with self.assertRaises(ValueError):replay('no_repair',1,['ack','fill','ack'])

    def test_late_generation_is_not_retroactive(self):
        self.assertEqual(replay('late_generation',1,['ack','fill','flag','grant','read0']).phase,2)

    def test_irreversible_demand_read(self):
        q=replay('raw',1,['flag','ack','grant','fill'])
        self.assertIn('read0',[a for a,_ in transitions(q,'raw')])
        s=replay('raw',1,['flag','ack','grant','fill','read0'])
        self.assertEqual(transitions(s,'raw'),())

    def test_initial_pending_not_visible(self):
        g=replay('raw',0,['flag','ack']);b=replay('raw',1,['flag','ack'])
        self.assertNotEqual(g.old_pending,b.old_pending)
        self.assertEqual(symbol('ack',g,'receipt'),symbol('ack',b,'receipt'))
        self.assertNotEqual(symbol('ack',g,'pending_receipt'),symbol('ack',b,'pending_receipt'))

    def test_quiescent_good_branch(self):
        g=replay('raw',0,['flag','ack'])
        self.assertEqual([a for a,_ in transitions(g,'raw')],['grant'])
        self.assertTrue(all_continuations_safe(g,'raw'))
        self.assertFalse(grant_allowed(g,('flag','ack'),'raw','safe_history'))

    def test_bare_history_theorem(self):
        for row in pregrant_fibers('raw','receipt'):
            self.assertEqual(row['universally_safe_grant'],
                'flag' in row['observation'] and row['observation'].count('ack')>=2)

    def test_pending_receipt_theorem(self):
        for row in pregrant_fibers('raw','pending_receipt'):
            self.assertEqual(row['universally_safe_grant'],
                'flag' in row['observation'] and 'ack:0' in row['observation'])

    def test_prediction_controls(self):
        for name,m,p,safe,complete in EXPECTED_CASES:
            result=explore_case(m,p)
            self.assertEqual((result['safe'],result['complete']),(safe,complete),name)

    def test_minimum_bad_trace_lengths(self):
        expected={'eager':3,'receipt':5,'cache_only':5}
        for policy,minimum in expected.items():
            trace=explore_case('raw',policy)['shortest_bad']
            self.assertEqual(len(trace['actions']),minimum)

    def test_all_trace_source_maps(self):
        for _,mech,policy,_,_ in EXPECTED_CASES:
            for trace in explore_case(mech,policy)['traces']:
                if trace['outcome']=='blocked':continue
                word=(1,int(trace['outcome']=='one'))
                self.assertTrue(background(MP,word))
                self.assertEqual(verdict(MP,word)['allowed'],word==(1,1))
                self.assertEqual(oracle(MP,word),word==(1,1))

    def test_no_post_read_transport(self):
        for mech in MECHANISMS:
            for state in plant_graph(mech)[0]:
                if state.phase>=2:self.assertEqual(transitions(state,mech),())

    def test_stable_state_and_pending_receipt_same_language(self):
        def words(policy):
            return {(r['initial_old_pending'],tuple(r['actions'])) for r in explore_case('raw',policy)['traces']}
        self.assertEqual(words('stable_state'),words('pending_receipt'))

    def test_hidden_closure_observation_oracle(self):
        for mech,policy in [('raw','receipt'),('raw','pending_receipt'),('drain','receipt'),('generation','receipt')]:
            explicit={tuple(row['observation']):tuple(row['states']) for row in pregrant_fibers(mech,policy)}
            self.assertEqual(knowledge_fibers(mech,policy),explicit)
        # The raw flag/ack history also permits a fill after the last receipt.
        self.assertIn(56,knowledge_fibers('raw','receipt')[('flag','ack')])

    def test_exact_initial_choices(self):
        spec=json.loads((ROOT/'inputs/bridge_cases.json').read_text())
        self.assertEqual(spec['initial_old_fill'],[0,1])
        self.assertEqual(spec['source_prefix'],['write_data_1','write_release_flag_1'])

if __name__=='__main__':unittest.main()
