"""Finite regression tests. These are not machine-checked general proofs."""
import csv
import itertools
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from model import SCHEMAS, build_events, programs, verdict, oracle, background, closure
from observe import project, contract, minimal_masks, separation_edges, maximal_rectangles

class SemanticTests(unittest.TestCase):
    def test_exact_input_universe(self):
        cases=list(programs())
        self.assertEqual(len(cases),270)
        self.assertEqual(len({c['id'] for c in cases}),270)
        self.assertEqual(json.loads((ROOT/'inputs/programs.json').read_text()),cases)
        self.assertEqual(sum(c['family']=='MIXED_CONTROL' for c in cases),3)

    def test_message_passing(self):
        c={'schema':'MP','modes':['RLX','REL','ACQ','RLX']}
        for outcome in itertools.product((0,1),repeat=2):
            self.assertEqual(verdict(c,outcome)['allowed'], outcome!=(1,0))
            self.assertEqual(oracle(c,outcome),outcome!=(1,0))
        self.assertTrue(verdict(c,(1,0),mutant='omit_sw')['allowed'])

    def test_store_buffering(self):
        c={'schema':'SB','modes':['SC']*4}
        self.assertFalse(verdict(c,(0,0))['allowed'])
        self.assertTrue(verdict(c,(0,0),mutant='omit_sc')['allowed'])
        self.assertTrue(verdict({'schema':'SB','modes':['RLX']*4},(0,0))['allowed'])

    def test_ir_iw_ra_not_sc(self):
        c={'schema':'IRIW','modes':['REL','REL','ACQ','ACQ','ACQ','ACQ']}
        self.assertTrue(verdict(c,(1,0,1,0))['allowed'])
        self.assertFalse(verdict(c,(1,0,1,0),mutant='acyclic_hb_eco')['allowed'])
        self.assertFalse(verdict({'schema':'IRIW','modes':['SC']*6},(1,0,1,0))['allowed'])

    def test_target_separation(self):
        for c in programs():
            if c['family']=='MIXED_CONTROL':
                self.assertTrue(oracle(c,(1,0,1,0),original_rc11=True))
                v=verdict(c,(1,0,1,0))
                self.assertFalse(v['allowed'])
                self.assertTrue(v['sc'])
                self.assertFalse(v['coherence'])
                self.assertFalse(v['no_thin_air'])

    def test_background_is_not_bridge_evidence(self):
        c={'schema':'CoRR','modes':['RLX']*3}
        self.assertFalse(background(c,(1,0)))
        self.assertFalse(verdict(c,(1,0))['allowed'])
        for b in [(0,0),(0,1),(1,1)]:
            self.assertTrue(background(c,b))
            self.assertTrue(verdict(c,b)['allowed'])

    def test_nta_on_separate_owned_fixture(self):
        # This synthetic load-buffering fixture exercises an axiom not falsified
        # by the five retained topologies. It is a unit test, not corpus coverage.
        key='test_load_buffering'
        self.assertNotIn(key,SCHEMAS)
        SCHEMAS[key]=((('R','x'),('W','y')),(('R','y'),('W','x')))
        try:
            c={'schema':key,'modes':['RLX']*4}
            self.assertTrue(verdict(c,(1,1))['no_thin_air'])
            self.assertFalse(verdict(c,(1,1))['allowed'])
            self.assertFalse(oracle(c,(1,1)))
        finally:
            del SCHEMAS[key]

    def test_invalid_inputs(self):
        for c in [{'schema':'bad','modes':[]}, {'schema':'MP','modes':['RLX']},
                  {'schema':'MP','modes':['ACQ','REL','ACQ','RLX']}]:
            with self.assertRaises(ValueError): build_events(c)
        c={'schema':'MP','modes':['RLX']*4}
        for b in [(1,), (2,0), (True,0), ('1',0)]:
            with self.assertRaises(ValueError): verdict(c,b)
            with self.assertRaises(ValueError): oracle(c,b)
        for mask in [-1,4]:
            with self.assertRaises(ValueError): project((0,1),mask)

    def test_closure_cycle(self):
        self.assertEqual(closure(('a','b'),{('a','b')}),{('a','b')})
        self.assertEqual(closure(('a','b'),{('a','b'),('b','a')}),
                         set(itertools.product(('a','b'),repeat=2)))

class ContractTests(unittest.TestCase):
    def test_all_two_bit_truth_tables(self):
        outcomes=list(itertools.product((0,1),repeat=2))
        for labels in itertools.product((False,True),repeat=4):
            rows=list(zip(outcomes,labels))
            edges=separation_edges(rows)
            for mask in range(4):
                c=contract(rows,mask)
                self.assertEqual(c['exact'],all(mask&e for e in edges))
                accepted=set(c['accepted'])
                self.assertTrue(all(g for o,g in rows if project(o,mask) in accepted))
                for obs in {project(o,mask) for o in outcomes}-accepted:
                    self.assertTrue(any(not g and project(o,mask)==obs for o,g in rows))
            for m in minimal_masks(rows):
                self.assertTrue(contract(rows,m)['exact'])
                for k in range(4):
                    if k!=m and k&m==k: self.assertFalse(contract(rows,k)['exact'])

    def test_message_passing_fiber(self):
        rows=[((0,0),True),((0,1),True),((1,0),False),((1,1),True)]
        c=contract(rows,1)
        self.assertEqual(c['accepted'],[(0,)])
        self.assertEqual(c['false_rejections'],1)
        self.assertEqual(c['existential_false_acceptances'],1)
        self.assertEqual(minimal_masks(rows),[3])
        self.assertEqual(contract(rows,0)['accepted'],[])

    def test_maximal_rectangles(self):
        ans=maximal_rectangles({(0,0),(0,1),(1,1)})
        self.assertEqual(set(ans),{((0,),(0,1)),((0,1),(1,))})
        self.assertEqual(maximal_rectangles(set()),[])
        self.assertEqual(maximal_rectangles(set(itertools.product((0,1),repeat=2))),
                         [((0,1),(0,1))])

    def test_injective_dependency_messages(self):
        for k in range(1,5):
            for a,b in itertools.combinations(range(1<<k),2):
                # For any distinct needs, a receiver state separates them.
                self.assertTrue(any(((a&t)==a)!=((b&t)==b) for t in (a,b)))

    def test_retained_single_forbidden_shape(self):
        groups={}
        with (ROOT/'results/graphs.csv').open(newline='') as handle:
            for row in csv.DictReader(handle):
                if row['background']=='1': groups.setdefault(row['program'],[]).append(row)
        mixed=0
        for rows in groups.values():
            bad=[row for row in rows if row['allowed']=='0']
            if bad and len(bad)<len(rows):
                mixed+=1
                self.assertEqual(len(bad),1)
                self.assertEqual(len(rows),1<<len(rows[0]['reads']))
        self.assertEqual(mixed,29)

    def test_retained_witnesses(self):
        cases={c['id']:c for c in programs()}
        witnesses=json.loads((ROOT/'results/witnesses.json').read_text())
        for w in witnesses:
            c=cases[w['program']];g=tuple(w['good']);b=tuple(w['bad']);m=w['mask']
            self.assertTrue(background(c,g));self.assertTrue(background(c,b))
            self.assertTrue(oracle(c,g));self.assertFalse(oracle(c,b))
            self.assertEqual(project(g,m),project(b,m))
            self.assertEqual(list(project(g,m)),w['observation'])
            distance=sum(x!=y for x,y in zip(g,b))
            self.assertEqual(distance,w['minimum_read_source_hamming_distance'])
            # All retained minima are one: distinct binary words cannot have
            # Hamming distance less than one. No global trace-minimality claim.
            self.assertEqual(distance,1)

if __name__=='__main__': unittest.main()
