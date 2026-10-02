"""Bounded exhaustive bridge evidence; shared by reproduction and pilot."""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import resource,time
from bridge import (MECHANISMS,POLICIES,State,plant_graph,oracle_edges,grant_formula,
    all_continuations_safe,explore_case,pregrant_fibers,replay,transitions,knowledge_fibers)
from model import verdict,oracle,background

MP={'schema':'MP','modes':['RLX','REL','ACQ','RLX']}
EXPECTED_CASES=(
 ('raw-eager','raw','eager',False,True),
 ('raw-receipt','raw','receipt',False,True),
 ('raw-cache-only','raw','cache_only',False,True),
 ('raw-stable-state','raw','stable_state',True,True),
 ('raw-pending-receipt','raw','pending_receipt',True,True),
 ('raw-safe-history','raw','safe_history',True,False),
 ('drain-receipt','drain','receipt',True,True),
 ('generation-receipt','generation','receipt',True,True),
 ('late-generation-receipt','late_generation','receipt',False,True),
 ('no-repair-pending-receipt','no_repair','pending_receipt',True,False))

def write_json(path,obj):path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')

def run_bridge(root:Path,out:Path)->dict:
    start=time.process_time();wall=time.monotonic()
    spec=json.loads((root/'inputs/bridge_cases.json').read_text())
    signature=tuple((r['id'],r['mechanism'],r['policy'],r['expected_safe'],r['expected_complete']) for r in spec['cases'])
    if signature!=EXPECTED_CASES:raise ValueError('bridge case selection changed')
    if spec['initial_old_fill']!=[0,1] or spec['program_modes']!=MP['modes']:
        raise ValueError('bridge initial choices or mapping changed')
    counts=Counter();plants=[];guards=[];cases=[];observations=[]
    for mech in MECHANISMS:
        states,edges=plant_graph(mech)
        if edges!=oracle_edges(mech):raise AssertionError('transition oracle mismatch: '+mech)
        # Check the finite DAG by removing all zero-indegree nodes.
        degree={s.code():0 for s in states}
        for _,_,t in edges:degree[t]+=1
        todo=[s for s,d in degree.items() if not d];visited=set()
        while todo:
            s=todo.pop();visited.add(s)
            for q,_,t in edges:
                if q==s:
                    degree[t]-=1
                    if degree[t]==0:todo.append(t)
        if len(visited)!=len(states):raise AssertionError('plant is cyclic')
        plants.append({'mechanism':mech,'states':sorted(s.code() for s in states),
            'edges':[list(e) for e in sorted(edges)],'state_count':len(states),'transition_count':len(edges),'acyclic':True})
        counts['plant_edge_obligations']+=len(edges)
        for s in sorted(states):
            if s.flag and s.phase==0:
                actual=all_continuations_safe(s,mech);formula=grant_formula(s,mech)
                if formula!=actual:raise AssertionError('grant guard mismatch')
                guards.append({'mechanism':mech,'state':s.code(),'universal_suffix_safe':actual,'formula_safe':formula})
                counts['grant_guard_obligations']+=1
    for spec_case in spec['cases']:
        result=explore_case(spec_case['mechanism'],spec_case['policy'])
        if result['safe']!=spec_case['expected_safe'] or result['complete']!=spec_case['expected_complete']:
            raise AssertionError(('bridge case prediction failed',spec_case['id']))
        if result['controller_nodes']>64 or result['controller_edges']>256:
            raise AssertionError('controlled-case dimension exceeded')
        for trace in result['traces']:
            s=replay(spec_case['mechanism'],trace['initial_old_pending'],trace['actions'])
            if s.code()!=trace['state_codes'][-1]:raise AssertionError('trace replay disagrees')
            edge_set=oracle_edges(spec_case['mechanism'])
            for q,a,t in zip(trace['state_codes'],trace['actions'],trace['state_codes'][1:]):
                if (q,a,t) not in edge_set:raise AssertionError('oracle rejects trace step')
            if trace['outcome']!='blocked':
                word=(1,int(trace['outcome']=='one'))
                primary=verdict(MP,word)['allowed'];comparison=oracle(MP,word)
                if primary!=comparison or primary!=(trace['outcome']=='one') or not background(MP,word):
                    raise AssertionError('operational-to-axiomatic mapping mismatch')
                trace['read_source_word']=list(word)
                trace['target_allowed']=primary
                counts['completed_trace_mapping_obligations']+=1
            else:
                trace['read_source_word']=None;trace['target_allowed']=None
            counts['maximal_trace_obligations']+=1
        cases.append({'id':spec_case['id'],'mechanism':spec_case['mechanism'],'policy':spec_case['policy'],**result})
        counts['case_prediction_obligations']+=1
    for mech,policy in [('raw','receipt'),('raw','pending_receipt'),('drain','receipt'),('generation','receipt')]:
        fs=pregrant_fibers(mech,policy)
        explicit={tuple(row['observation']):tuple(row['states']) for row in fs}
        if explicit!=knowledge_fibers(mech,policy):
            raise AssertionError('hidden-closure observation oracle mismatch')
        for row in fs:
            hist=row['observation']
            if mech=='raw' and policy=='receipt':expected='flag' in hist and hist.count('ack')>=2
            elif policy=='pending_receipt':expected='flag' in hist and 'ack:0' in hist
            else:expected='flag' in hist and 'ack' in hist
            if row['universally_safe_grant']!=expected:raise AssertionError('history characterization mismatch')
        observations.append({'mechanism':mech,'interface':policy,'fibers':fs})
        counts['history_obligations']+=len(fs)
    # A common visible prefix has a clean quiescent state and a latent hazard.
    good=replay('raw',0,('flag','ack'));bad=replay('raw',1,('flag','ack'))
    if not all_continuations_safe(good,'raw') or all_continuations_safe(bad,'raw'):
        raise AssertionError('indistinguishable readiness control failed')
    if [a for a,_ in transitions(good,'raw')]!=['grant']:
        raise AssertionError('clean branch is not quiescent except for grant')
    if replay('raw',1,('flag','ack','grant','fill','read0')).phase!=2:
        raise AssertionError('late-fill witness failed')
    counts['impossibility_certificate_obligations']+=1
    certificate={'mechanism':'raw','observation':['flag','ack'],
        'good':{'initial_old_pending':0,'prefix':['flag','ack'],'state':good.code()},
        'hazardous':{'initial_old_pending':1,'prefix':['flag','ack'],'state':bad.code()},
        'bad_suffix':['grant','fill','read0'],
        'minimum_maximum_prefix_length':2,
        'metric':'maximum of two dynamic prefix lengths after fixed source writes; initial old-fill choice is not a dynamic event',
        'quiescent_good_branch_only_enabled_action':'grant'}
    # Minimality is checked across every mixed raw history, not inferred from BFS success.
    lengths=[]
    for row in observations[0]['fibers']:
        if row['mixed_readiness']:
            yes=[p for p in row['prefixes'] if all_continuations_safe(State.decode(p['state']),'raw')]
            no=[p for p in row['prefixes'] if not all_continuations_safe(State.decode(p['state']),'raw')]
            lengths.extend(max(len(a['actions']),len(b['actions'])) for a in yes for b in no)
    if min(lengths)!=2:raise AssertionError('prefix-pair minimality mismatch')
    summary={'plants':[{k:p[k] for k in ('mechanism','state_count','transition_count','acyclic')} for p in plants],
        'cases':[{k:r[k] for k in ('id','mechanism','policy','controller_nodes','controller_edges','maximal_traces','zero_traces','one_traces','blocked_traces','max_dynamic_steps','safe','complete')} for r in cases],
        'counts':dict(counts),'counted_obligations':sum(counts.values()),
        'impossibility_certificate':certificate,
        'case_count':len(cases),'safe_and_complete_case_count':sum(r['safe'] and r['complete'] for r in cases),
        'transition_oracle_mismatches':0,'history_oracle_mismatches':0,'grant_formula_mismatches':0,'trace_mapping_mismatches':0,
        'scope':'One producer, one consumer, one release/acquire episode, one data line and at most one old fill. Exact enumerated abstract traces; not hardware timings or generic protocol coverage.',
        'counting_note':'One per retained plant edge, grant-enabled state, maximal case trace, completed trace map, history fiber, case prediction and paired impossibility certificate. Internal successor/reachability comparisons are not extra scientific instances.'}
    if summary['counted_obligations']+12113>100000:raise AssertionError('combined obligation limit exceeded')
    for name,data in [('bridge-plants.json',plants),('bridge-guards.json',guards),('bridge-cases.json',cases),('bridge-observations.json',observations),('bridge-summary.json',summary)]:
        write_json(out/name,data)
    write_json(out/'bridge-resources.json',{'cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,
        'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1,'network_requests':0,
        'input_bytes':(root/'inputs/bridge_cases.json').stat().st_size,'timing_scope':'bridge experiment after imports; RSS includes parent experiment high-water mark'})
    return summary
