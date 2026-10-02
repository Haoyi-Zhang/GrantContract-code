#!/usr/bin/env python3
"""Reproduce the complete finite study in one bounded standard-library process.

Run from the standalone repository: python reproduce.py --output reproduced
No network or external solver is used. Existing unrelated directories are rejected.
"""
from __future__ import annotations
import argparse, csv, itertools, json, pathlib, resource, sys, time
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from model import build_events, programs, verdict, oracle, background
from observe import contract, minimal_masks, separation_edges, maximal_rectangles, project
from bridge_study import run_bridge
from parametric_bridge import run_parametric
from metaoracle import run_metaoracle

def save(path,data): path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')

def run(out: pathlib.Path) -> dict:
    if out.exists() and any(out.iterdir()): raise ValueError('output directory must be absent or empty')
    out.mkdir(parents=True,exist_ok=True)
    resource.setrlimit(resource.RLIMIT_AS,(2_500_000_000,2_500_000_000))
    resource.setrlimit(resource.RLIMIT_CPU,(120,120))
    start=time.process_time(); wall=time.monotonic()
    inputs=json.loads((ROOT/'inputs'/'programs.json').read_text())
    if inputs != list(programs()): raise ValueError('retained universe differs from declared generator')
    rows=[]; masks=[]; summaries={}; witnesses=[]; metricchecks=0; pairs=0
    totals={'programs':len(inputs),'graphs':0,'background_graphs':0,'allowed_graphs':0,
            'oracle_mismatches':0,'original_rc11_differences':0,'observation_masks':0,
            'mixed_masks':0,'full_observation_failures':0,'max_vertices':0,'max_base_edges':0}
    for case in inputs:
        nr=sum(e.kind=='R' for e in build_events(case)); universe=[]; bs=[]
        stats=summaries.setdefault(case['schema'],{'programs':0,'graphs':0,'background':0,
            'allowed':0,'nonconstant_profiles':0,'all_safe_profiles':0,'max_min_observed':0})
        stats['programs']+=1
        for rf in itertools.product((0,1),repeat=nr):
            v=verdict(case,rf); ref=oracle(case,rf); rc11=oracle(case,rf,original_rc11=True)
            metricchecks+=3
            if v['allowed']!=ref: raise AssertionError(('oracle mismatch',case,rf))
            if v['allowed'] and not rc11: raise AssertionError('strengthened target did not refine original specialization')
            b=background(case,rf)
            if v['allowed'] and not b: raise AssertionError('safe graph outside declared background')
            rows.append({'program':case['id'],'reads':''.join(map(str,rf)), 'background':int(b),
                         'allowed':int(v['allowed']),'original_rc11_allowed':int(rc11),
                         'coherence_violation':int(bool(v['coherence'])),
                         'sc_violation':int(bool(v['sc'])), 'nta_violation':int(bool(v['no_thin_air']))})
            universe.append((rf,v['allowed']))
            if b: bs.append((rf,v['allowed']))
            totals['graphs']+=1; stats['graphs']+=1
            totals['background_graphs']+=b;stats['background']+=b
            totals['allowed_graphs']+=v['allowed'];stats['allowed']+=v['allowed']
            totals['original_rc11_differences']+=int(ref!=rc11)
            totals['max_vertices']=max(totals['max_vertices'],v['vertices'])
            totals['max_base_edges']=max(totals['max_base_edges'],v['base_edges'])
        best=minimal_masks(bs)
        edges=separation_edges(bs)
        ng=sum(g for _,g in bs); nb=len(bs)-ng
        pairs+=ng*nb
        stats['nonconstant_profiles']+=int(bool(ng and nb))
        stats['all_safe_profiles']+=int(not nb)
        stats['max_min_observed']=max(stats['max_min_observed'], min(m.bit_count() for m in best))
        for mask in range(1<<nr):
            c=contract(bs,mask)
            exact=all(mask&e for e in edges)
            if c['exact'] != exact: raise AssertionError('separation theorem mismatch')
            accepted=set(c['accepted'])
            if any(project(o,mask) in accepted and not good for o,good in bs):
                raise AssertionError('unsound contract')
            # Each omitted feasible observation has a bad completion; maximality certificate.
            for obs in {project(o,mask) for o,_ in bs}-accepted:
                if not any(project(o,mask)==obs and not good for o,good in bs):
                    raise AssertionError('not maximally permissive')
            totals['observation_masks']+=1; totals['mixed_masks']+=int(not c['exact'])
            metricchecks+=1
            masks.append({'program':case['id'],'mask':mask,'observed_count':mask.bit_count(),
                'fibers':c['fibers'],'exact':int(c['exact']), 'mixed_fibers':len(c['mixed']),
                'false_rejected_safe_graphs':c['false_rejections'],
                'existential_unsafe_acceptances':c['existential_false_acceptances'],
                'inclusion_minimal_exact':int(mask in best)})
            if mask==(1<<nr)-1 and not c['exact']: totals['full_observation_failures']+=1
            if c['mixed']:
                candidates=[(sum(a!=b for a,b in zip(g,bad)),g,bad)
                  for g,yes in bs if yes for bad,no in bs if not no and project(g,mask)==project(bad,mask)]
                distance,g,bad=min(candidates)
                witnesses.append({'program':case['id'],'mask':mask,'good':g,'bad':bad,
                    'observation':project(g,mask),'minimum_read_source_hamming_distance':distance,
                    'metric_scope':'within this retained program and background universe only'})
    # One-message dependency-set comparison. This is not a cache protocol lower bound.
    dependency=[]
    for k in range(1,5):
        sets=range(1<<k)
        errors=0; prefixloss=0
        for need,have in itertools.product(sets,repeat=2):
            exact=(need&have)==need
            tag=need.bit_length() # 0 for empty, otherwise the largest identifier
            max_member=(tag==0 or bool(have&(1<<(tag-1))))
            full_prefix=(have&((1<<tag)-1))==((1<<tag)-1)
            errors+=int(max_member and not exact); prefixloss+=int(exact and not full_prefix)
            metricchecks+=1
        dependency.append({'independent_writes':k,'required_sets':1<<k,'exact_fixed_bits':k,
            'decisions':1<<(2*k),'max_member_unsafe_acceptances':errors,
            'full_prefix_safe_rejections':prefixloss})
    rectangles=maximal_rectangles({(0,0),(0,1),(1,1)})
    if len(rectangles)!=2: raise AssertionError('factored-contract control failed')
    controls={
      'omit_sw_accepts_forbidden_MP':verdict({'schema':'MP','modes':['RLX','REL','ACQ','RLX']},(1,0),mutant='omit_sw')['allowed'],
      'omit_sc_accepts_forbidden_SB':verdict({'schema':'SB','modes':['SC']*4},(0,0),mutant='omit_sc')['allowed'],
      'acyclic_union_rejects_allowed_RA_IRIW':not verdict({'schema':'IRIW','modes':['REL','REL','ACQ','ACQ','ACQ','ACQ']},(1,0,1,0),mutant='acyclic_hb_eco')['allowed'],
      'actual_RA_IRIW_allowed':verdict({'schema':'IRIW','modes':['REL','REL','ACQ','ACQ','ACQ','ACQ']},(1,0,1,0))['allowed'],
      'mixed_SC_distinguishes_targets': all(oracle(c,(1,0,1,0),original_rc11=True) and not verdict(c,(1,0,1,0))['allowed'] for c in inputs if c['family']=='MIXED_CONTROL'),
      'existential_projection_accepts_forbidden_MP':contract([((0,0),True),((0,1),True),((1,0),False),((1,1),True)],1)['existential_false_acceptances']==1,
    }
    metricchecks+=len(controls)
    if not all(controls.values()): raise AssertionError('negative control not detected')
    totals['safe_bad_pair_obligations']=pairs
    totals['classification_and_mask_obligations']=metricchecks
    totals['counted_obligations']=pairs+metricchecks
    totals['witness_certificates']=len(witnesses)
    if totals['counted_obligations']>100_000: raise AssertionError('obligation budget exceeded')
    for filename, table in [('graphs.csv',rows),('observations.csv',masks)]:
        with (out/filename).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    save(out/'summary.json',{'totals':totals,'schemas':summaries,'dependency_sets':dependency,
         'negative_controls':controls,'factored_contract_maxima':rectangles,
         'counting_note':'Three semantic classifications per graph, one mask obligation per program/mask, one set decision per need/have pair, six named controls, and each distinct safe/bad pair per profile. Internal loop iterations and unit-test assertions are not called separate scientific obligations.'})
    save(out/'witnesses.json',witnesses)
    bridge_result=run_bridge(ROOT,out)
    parametric_result=run_parametric(4)
    save(out/'parametric-summary.json',parametric_result)
    metaoracle_result=run_metaoracle(4)
    save(out/'metaoracle-summary.json',metaoracle_result)
    combined=(totals['counted_obligations']+bridge_result['counted_obligations']
              +parametric_result['counted_obligations']
              +metaoracle_result['counted_obligations'])
    if combined>100_000:
        raise AssertionError('combined per-run obligation budget exceeded')
    usage=resource.getrusage(resource.RUSAGE_SELF)
    save(out/'resources.json',{'cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,
        'peak_rss_kib':usage.ru_maxrss,'workers':1,'process_cpu_limit_seconds':120,
        'address_space_limit_bytes':2_500_000_000,'inputs_bytes':(ROOT/'inputs'/'programs.json').stat().st_size,
        'network_requests':0,'randomness':'none; exhaustive lexicographic enumeration',
        'timing_scope':'complete event-graph, operational-bridge, parameterized, and tiny-plant meta-oracle experiments after imports; excludes compilation; RSS includes interpreter startup',
        'bridge_input_bytes':(ROOT/'inputs/bridge_cases.json').stat().st_size,
        'combined_counted_obligations':combined,
        'parametric_counted_obligations':parametric_result['counted_obligations'],
        'parametric_bounds_checked':parametric_result['bounds_checked'],
        'metaoracle_counted_obligations':metaoracle_result['counted_obligations'],
        'metaoracle_plants_checked':metaoracle_result['plants_checked'],
        'metaoracle_contract_candidates_checked':metaoracle_result['contract_candidates_checked']})
    return totals

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    try: print(json.dumps(run(args.output),indent=2))
    except (OSError,ValueError,AssertionError) as exc:
        print(f'reproduction failed: {exc}',file=sys.stderr);sys.exit(2)
