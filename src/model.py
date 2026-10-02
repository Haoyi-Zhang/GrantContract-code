"""Finite read/write event-graph model, not an implementation of a cache protocol.

All data locations have one non-initial write. No fences, RMW, non-atomic
accesses, address dependencies, compiler mapping, or operational bridge LTS.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from typing import Iterable

@dataclass(frozen=True)
class Event:
    name: str
    thread: int
    index: int
    kind: str
    loc: str
    mode: str

SCHEMAS: dict[str, tuple[tuple[tuple[str, str], ...], ...]] = {
    'CoRR': ((('W','x'),), (('R','x'),('R','x'))),
    'MP': ((('W','x'),('W','y')), (('R','y'),('R','x'))),
    'SB': ((('W','x'),('R','y')), (('W','y'),('R','x'))),
    'WRC': ((('W','x'),), (('R','x'),('W','y')), (('R','y'),('R','x'))),
    'IRIW': ((('W','x'),), (('W','y'),), (('R','x'),('R','y')), (('R','y'),('R','x'))),
}

def programs() -> Iterable[dict]:
    """Two binary families, then three designated mixed-SC semantic controls.

    The mixed controls are development diagnostics, not a held-out benchmark.
    """
    for schema, threads in SCHEMAS.items():
        kinds = [k for t in threads for k, _ in t]
        for family in ('RA','SC'):
            for bits in product((0,1), repeat=len(kinds)):
                if family == 'SC' and not any(bits):
                    continue
                modes = [('SC' if family == 'SC' else ('REL' if k=='W' else 'ACQ'))
                         if bit else 'RLX' for k, bit in zip(kinds, bits)]
                yield {'id': f'{schema}-{family}-'+''.join(map(str,bits)),
                       'schema': schema, 'family': family, 'modes': modes}

    # Published IRIW-acq-sc topology and its two single-acquire-to-SC
    # strengthenings. Development controls, not a held-out benchmark.
    for digits in ('221212', '221222', '222212'):
        kinds = [k for t in SCHEMAS['IRIW'] for k, _ in t]
        modes = [('RLX', 'REL' if k=='W' else 'ACQ', 'SC')[int(d)]
                 for k, d in zip(kinds, digits)]
        yield {'id': 'IRIW-MIX-'+digits, 'schema': 'IRIW',
               'family': 'MIXED_CONTROL', 'modes': modes}

def build_events(case: dict) -> tuple[Event, ...]:
    if case.get('schema') not in SCHEMAS:
        raise ValueError('unknown schema')
    specs = SCHEMAS[case['schema']]
    flat = [(t,i,k,l) for t, ops in enumerate(specs) for i,(k,l) in enumerate(ops)]
    if len(case.get('modes',[])) != len(flat):
        raise ValueError('one mode is required per event')
    events=[]
    for j, ((t,i,k,l), mode) in enumerate(zip(flat, case['modes'])):
        if mode not in ({'RLX','REL','SC'} if k=='W' else {'RLX','ACQ','SC'}):
            raise ValueError('invalid mode for event kind')
        events.append(Event(f'e{j}',t,i,k,l,mode))
    return tuple(events)

def base_relations(case: dict, reads: tuple[int,...]) -> dict:
    es=build_events(case)
    rs=[e for e in es if e.kind=='R']
    if len(reads)!=len(rs) or any(type(x) is not int or x not in (0,1) for x in reads):
        raise ValueError('read sources must be exactly one binary integer per read')
    locs=sorted({e.loc for e in es})
    nodes=tuple(Event('i_'+l,-1,j,'W',l,'INIT') for j,l in enumerate(locs))+es
    writers={e.loc:e.name for e in es if e.kind=='W'}
    if len(writers)!=sum(e.kind=='W' for e in es):
        raise ValueError('only one non-initial write per location is supported')
    sb={(a.name,b.name) for a in es for b in es if a.thread==b.thread and a.index<b.index}
    init={(a.name,b.name) for a in nodes if a.mode=='INIT' for b in es}
    rf={(writers[r.loc] if value else 'i_'+r.loc,r.name) for r,value in zip(rs,reads)}
    mo={('i_'+l,writers[l]) for l in locs}
    fr={(r.name,writers[r.loc]) for r,value in zip(rs,reads) if not value}
    byname={e.name:e for e in nodes}
    sw={(w,r) for w,r in rf if byname[w].mode in ('REL','SC') and byname[r].mode in ('ACQ','SC')}
    return {'nodes': nodes, 'sb':sb,'init':init,'rf':rf,'mo':mo,'fr':fr,'sw':sw}

def closure(names: tuple[str,...], edges: set[tuple[str,str]]) -> set[tuple[str,str]]:
    """Boolean Floyd-Warshall; no reflexive edges added by convention."""
    ix={x:i for i,x in enumerate(names)}
    m=[[False]*len(names) for _ in names]
    for a,b in edges: m[ix[a]][ix[b]]=True
    for k in range(len(names)):
        for i in range(len(names)):
            if m[i][k]:
                for j in range(len(names)): m[i][j] = m[i][j] or m[k][j]
    return {(a,b) for i,a in enumerate(names) for j,b in enumerate(names) if m[i][j]}

def compose(a: set[tuple[str,str]], b: set[tuple[str,str]]) -> set[tuple[str,str]]:
    return {(x,z) for x,y in a for yy,z in b if y==yy}

def verdict(case: dict, reads: tuple[int,...], *, mutant: str|None=None) -> dict:
    rel=base_relations(case,reads)
    ns=tuple(e.name for e in rel['nodes'])
    hb=closure(ns,rel['sb']|rel['init']|(set() if mutant=='omit_sw' else rel['sw']))
    eco=closure(ns,rel['mo']|rel['rf']|rel['fr'])
    nta=closure(ns,rel['sb']|rel['rf'])
    sc={e.name for e in rel['nodes'] if e.mode=='SC'}
    psc={(a,b) for a,b in hb|rel['mo']|rel['fr'] if a in sc and b in sc}
    coher=sorted((a,b) for a,b in hb if (b,a) in eco)
    nta_cycle=sorted(a for a in ns if (a,a) in nta)
    pscplus=closure(ns,psc)
    sc_cycle=[] if mutant=='omit_sc' else sorted(a for a in ns if (a,a) in pscplus)
    if mutant=='acyclic_hb_eco':
        union=closure(ns,hb|eco)
        coher=[(a,a) for a in ns if (a,a) in union]
    return {'allowed': not(coher or nta_cycle or sc_cycle), 'coherence':coher,
            'no_thin_air':nta_cycle,'sc':sc_cycle,
            'vertices':len(ns),'base_edges':sum(len(rel[k]) for k in ('sb','init','rf','mo','fr','sw'))}

def oracle(case: dict, reads: tuple[int,...], *, original_rc11: bool=False) -> bool:
    """Separately structured DFS oracle; intentionally rebuilds all relations.

    Not an independent external implementation: authored with the primary checker.
    It shares the declarative program parser but not relation-building/check logic.
    """
    events=build_events(case)
    loads=[e for e in events if e.kind=='R']
    if len(loads)!=len(reads) or any(type(b) is not int or b not in (0,1) for b in reads):
        raise ValueError('invalid read assignment')
    locs=sorted({e.loc for e in events})
    names=[f'init:{l}' for l in locs]+[e.name for e in events]
    by_name={e.name:e for e in events}
    addr={f'init:{l}':l for l in locs}|{e.name:e.loc for e in events}
    po=set()
    for t in range(len(SCHEMAS[case['schema']])):
        seq=[e for e in events if e.thread==t]
        for i,a in enumerate(seq):
            for b in seq[i+1:]: po.add((a.name,b.name))
    initial={(f'init:{l}',e.name) for l in locs for e in events}
    source={}
    sync=set()
    for r,bit in zip(loads,reads):
        w=next(e for e in events if e.kind=='W' and e.loc==r.loc)
        source[r.name]=w.name if bit else f'init:{r.loc}'
        if bit and w.mode in ('REL','SC') and r.mode in ('ACQ','SC'):
            sync.add((w.name,r.name))
    rf={(w,r) for r,w in source.items()}
    co={(f'init:{w.loc}',w.name) for w in events if w.kind=='W'}
    rb=set()
    for r in loads:
        for a,b in co:
            if source[r.name]==a: rb.add((r.name,b))
    def paths(edges):
        successors={n:[] for n in names}
        for a,b in edges: successors[a].append(b)
        answer=set()
        for a in names:
            seen=set(); todo=list(successors[a])
            while todo:
                b=todo.pop()
                if b not in seen:
                    seen.add(b); todo.extend(successors[b])
            answer.update((a,b) for b in seen)
        return answer
    if any(a==b for a,b in paths(po|rf)): return False
    happens=paths(po|sync|initial)
    extended=paths(co|rf|rb)
    for a,b in happens:
        if (b,a) in extended: return False
    order=happens|co|rb
    if original_rc11:
        nonloc={(a,b) for a,b in po if addr[a]!=addr[b]}
        sandwiches={(a,d) for a,b in nonloc for c,d in nonloc if (b,c) in happens}
        order=po|sandwiches|{(a,b) for a,b in happens if addr[a]==addr[b]}|co|rb
    order={(a,b) for a,b in order if a in by_name and b in by_name
           and by_name[a].mode=='SC' and by_name[b].mode=='SC'}
    return not any(a==b for a,b in paths(order))

def background(case: dict, reads: tuple[int,...]) -> bool:
    """Declared background: NTA and same-thread coherence, not a protocol proof."""
    r=base_relations(case,reads); names=tuple(e.name for e in r['nodes'])
    nta=closure(names,r['sb']|r['rf'])
    eco=closure(names,r['mo']|r['rf']|r['fr'])
    return not any(a==b for a,b in nta) and not any((b,a) in eco for a,b in r['sb'])
