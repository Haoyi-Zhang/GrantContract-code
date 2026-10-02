"""Owned one-epoch protocol model; not MemGlue/MSI or a hardware implementation.

Producer data=1 then release flag=1 have already committed. The consumer has an
old resident data line and zero or one old response sampled before those writes.
No new old response can be created. An invalidation clears the line; one late
response may repopulate it. Only acquire grant is controllable. The final demand
read is uncontrollable and a miss obtains the current producer value, one.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, replace
from itertools import product
from typing import Iterable

MECHANISMS=('raw','drain','generation','late_generation','no_repair')
POLICIES=('eager','receipt','cache_only','stable_state','pending_receipt','safe_history')

@dataclass(frozen=True,order=True)
class State:
    flag: int=0
    invalidated: int=0
    old_cache: int=1
    old_pending: int=0
    phase: int=0

    def __post_init__(self):
        if any(type(x) is not int or x not in (0,1) for x in (self.flag,self.invalidated,self.old_cache,self.old_pending)):
            raise ValueError('state flags must be binary integers')
        if type(self.phase) is not int or self.phase not in range(4):
            raise ValueError('phase must be an integer in [0,3]')

    def code(self)->int:
        return self.flag*32+self.invalidated*16+self.old_cache*8+self.old_pending*4+self.phase

    @classmethod
    def decode(cls,code:int)->State:
        if type(code) is not int or not 0<=code<64: raise ValueError('invalid state code')
        return cls((code>>5)&1,(code>>4)&1,(code>>3)&1,(code>>2)&1,code&3)


def initial_states()->tuple[State,State]:
    return State(old_pending=0),State(old_pending=1)


def transitions(s:State,mechanism:str)->tuple[tuple[str,State],...]:
    if mechanism not in MECHANISMS: raise ValueError('unknown mechanism')
    if s.phase>=2: return ()
    out=[]
    if not s.flag: out.append(('flag',replace(s,flag=1)))
    if s.old_pending:
        discard=(mechanism=='generation' and s.invalidated==1) or (mechanism=='late_generation' and s.phase==1)
        out.append(('fill',replace(s,old_pending=0,old_cache=s.old_cache if discard else 1)))
    invalidate=(not s.invalidated or s.old_cache==1)
    if mechanism=='no_repair': invalidate=not s.invalidated
    if mechanism=='drain' and s.old_pending: invalidate=False
    if invalidate: out.append(('ack',replace(s,invalidated=1,old_cache=0)))
    if s.phase==0 and s.flag: out.append(('grant',replace(s,phase=1)))
    if s.phase==1:
        out.append(('read0' if s.old_cache else 'read1',replace(s,phase=2 if s.old_cache else 3)))
    return tuple(sorted(out))


def oracle_edges(mechanism:str)->set[tuple[int,str,int]]:
    """Separate integer-encoded transition oracle, not a call to transitions.

    It intentionally shares the stated state meanings, but not dataclass updates
    or the primary transition builder. Same authorship is not independence.
    """
    if mechanism not in MECHANISMS: raise ValueError('unknown mechanism')
    edges=set()
    for n in range(64):
        f=(n&32)!=0; a=(n&16)!=0; c=(n&8)!=0; p=(n&4)!=0; t=n&3
        if t>1: continue
        if not f: edges.add((n,'flag',n|32))
        if p:
            drop=(mechanism=='generation' and a) or (mechanism=='late_generation' and t==1)
            target=n&~4
            if not drop: target|=8
            edges.add((n,'fill',target))
        may_clear=((not a) if mechanism=='no_repair' else ((not a) or c))
        if may_clear and not (mechanism=='drain' and p):
            edges.add((n,'ack',(n|16)&~8))
        if t==0 and f: edges.add((n,'grant',n|1))
        if t==1: edges.add((n,'read0' if c else 'read1',(n&~3)|(2 if c else 3)))
    reachable={8,12}; todo=deque(sorted(reachable))
    while todo:
        n=todo.popleft()
        for source,_,target in edges:
            if source==n and target not in reachable:
                reachable.add(target);todo.append(target)
    return {edge for edge in edges if edge[0] in reachable}


def plant_graph(mechanism:str)->tuple[set[State],set[tuple[int,str,int]]]:
    seen=set(initial_states()); todo=deque(sorted(seen)); edges=set()
    while todo:
        s=todo.popleft()
        for action,target in transitions(s,mechanism):
            edges.add((s.code(),action,target.code()))
            if target not in seen: seen.add(target);todo.append(target)
    if len(seen)>64 or len(edges)>256: raise ValueError('plant budget exceeded')
    return seen,edges


def grant_formula(s:State,mechanism:str)->bool:
    """Universal post-grant safety, for a reachable, grant-enabled state only."""
    if s.phase!=0 or not s.flag: return False
    killed=(mechanism=='generation' and s.invalidated) or mechanism=='late_generation'
    return not s.old_cache and (not s.old_pending or bool(killed))


def all_continuations_safe(s:State,mechanism:str)->bool:
    """Exhaustive suffix oracle after a forced grant; no formula is consulted."""
    if s.phase!=0 or not s.flag: return False
    seen={replace(s,phase=1)};todo=list(seen)
    while todo:
        q=todo.pop()
        if q.phase==2:return False
        for _,target in transitions(q,mechanism):
            if target not in seen:seen.add(target);todo.append(target)
    return True


def symbol(action:str,after:State,policy:str)->str|None:
    if policy not in POLICIES:raise ValueError('unknown policy')
    if action=='fill':return None
    if action=='ack' and policy=='pending_receipt':
        return 'ack:0' if after.old_pending==0 else 'ack:+'
    return action


def grant_allowed(s:State,history:tuple[str,...],mechanism:str,policy:str)->bool:
    if policy not in POLICIES:raise ValueError('unknown policy')
    if not s.flag or s.phase!=0:return False
    if policy=='eager':return True
    if policy=='receipt':return 'ack' in history
    if policy=='cache_only':return not s.old_cache
    if policy=='stable_state':return grant_formula(s,mechanism)
    if policy=='pending_receipt':return 'ack:0' in history
    # This rule is separately checked against every reachable raw bare history.
    return history.count('ack')>=2


def controlled_transitions(node,mechanism:str,policy:str):
    s,history=node;out=[]
    for action,target in transitions(s,mechanism):
        if action=='grant' and not grant_allowed(s,history,mechanism,policy):continue
        obs=symbol(action,target,policy)
        out.append((action,(target,history if obs is None else history+(obs,))))
    return tuple(out)


def explore_case(mechanism:str,policy:str)->dict:
    """Retain every maximal labelled path, not merely counts or a random trace."""
    if mechanism not in MECHANISMS or policy not in POLICIES:raise ValueError('unknown case')
    nodes=set();edges=set();traces=[]
    def walk(node,initial_pending,actions,codes):
        if len(actions)>48:raise ValueError('trace depth budget exceeded')
        nodes.add(node)
        nxt=controlled_transitions(node,mechanism,policy)
        if not nxt:
            state,history=node
            traces.append({'initial_old_pending':initial_pending,'actions':list(actions),
                'state_codes':list(codes),'observations':list(history),
                'outcome':'zero' if state.phase==2 else 'one' if state.phase==3 else 'blocked'})
            return
        for action,target in nxt:
            edges.add((node,action,target))
            walk(target,initial_pending,actions+(action,),codes+(target[0].code(),))
    for s in initial_states():walk((s,()),s.old_pending,(),(s.code(),))
    traces.sort(key=lambda row:(row['initial_old_pending'],row['actions']))
    zero=[r for r in traces if r['outcome']=='zero'];blocked=[r for r in traces if r['outcome']=='blocked']
    def shortest(rows):
        return min(rows,key=lambda r:(len(r['actions']),r['initial_old_pending'],r['actions'])) if rows else None
    # All paths are finite because flag/old fill/grant/read fire at most once and
    # acknowledgement at most twice. Histories are part of controlled nodes.
    return {'controller_nodes':len(nodes),'controller_edges':len(edges),
        'maximal_traces':len(traces),'zero_traces':len(zero),'one_traces':len(traces)-len(zero)-len(blocked),
        'blocked_traces':len(blocked),'max_dynamic_steps':max(len(r['actions']) for r in traces),
        'safe':not zero,'complete':not blocked,'shortest_bad':shortest(zero),
        'shortest_blocked':shortest(blocked),'traces':traces}


def pregrant_fibers(mechanism:str,policy:str)->list[dict]:
    """Every environment-only prefix, grouped by its complete visible history."""
    fibers={}
    def walk(s,history,actions,initial_pending):
        key=history
        fibers.setdefault(key,[]).append((s,actions,initial_pending))
        for action,target in transitions(s,mechanism):
            if action=='grant':continue
            obs=symbol(action,target,policy)
            walk(target,history if obs is None else history+(obs,),actions+(action,),initial_pending)
    for s in initial_states():walk(s,(),(),s.old_pending)
    result=[]
    for history,members in sorted(fibers.items()):
        states=sorted({s for s,_,_ in members})
        enabled=all(s.flag==1 for s in states)
        safe=[s for s in states if all_continuations_safe(s,mechanism)] if enabled else []
        robust=enabled and len(safe)==len(states)
        result.append({'observation':list(history),'states':[s.code() for s in states],
            'grant_enabled':enabled,'universally_safe_grant':robust,
            'mixed_readiness':bool(safe) and len(safe)<len(states),
            'prefixes':[{'initial_old_pending':p,'actions':list(a),'state':s.code()} for s,a,p in members]})
    return result


def replay(mechanism:str,initial_pending:int,actions:Iterable[str])->State:
    if type(initial_pending) is not int or initial_pending not in (0,1):raise ValueError('bad initial choice')
    s=State(old_pending=initial_pending)
    for action in actions:
        targets=[t for a,t in transitions(s,mechanism) if a==action]
        if len(targets)!=1:raise ValueError('illegal action: '+str(action))
        s=targets[0]
    return s


def knowledge_fibers(mechanism: str, policy: str) -> dict[tuple[str, ...], tuple[int, ...]]:
    """A second history construction by hidden closure, not prefix enumeration.

    Only environment actions before grant are considered. Each observation step
    unions all possible successor states, then includes every hidden old-fill
    delivery. This independently checks that a receipt fiber includes a refill
    that may occur after the last visible event and before the decision.
    """
    if mechanism not in MECHANISMS or policy not in POLICIES:
        raise ValueError('unknown mechanism or observation policy')

    def close(seeds: Iterable[State]) -> frozenset[State]:
        seen = set(seeds)
        todo = list(seen)
        while todo:
            state = todo.pop()
            for action, target in transitions(state, mechanism):
                if action == 'grant':
                    continue
                if symbol(action, target, policy) is None and target not in seen:
                    seen.add(target)
                    todo.append(target)
        return frozenset(seen)

    beliefs = {(): close(initial_states())}
    todo = deque([()])
    while todo:
        history = todo.popleft()
        posts: dict[str, set[State]] = {}
        for state in beliefs[history]:
            for action, target in transitions(state, mechanism):
                if action == 'grant':
                    continue
                obs = symbol(action, target, policy)
                if obs is not None:
                    posts.setdefault(obs, set()).add(target)
        for obs, targets in sorted(posts.items()):
            nxt = history + (obs,)
            if len(nxt) > 48 or len(beliefs) >= 1000:
                raise ValueError('observation construction budget exceeded')
            belief = close(targets)
            if nxt in beliefs and beliefs[nxt] != belief:
                raise AssertionError('inconsistent deterministic belief construction')
            if nxt not in beliefs:
                beliefs[nxt] = belief
                todo.append(nxt)
    return {h: tuple(sorted(s.code() for s in states)) for h, states in sorted(beliefs.items())}
