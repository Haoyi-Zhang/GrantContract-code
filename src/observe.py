"""Exact classification contracts for complete finite observations, not controllers."""
from __future__ import annotations
from itertools import product

def project(outcome: tuple[int,...], mask: int) -> tuple[int,...]:
    if mask < 0 or mask >= 1 << len(outcome): raise ValueError('mask out of range')
    return tuple(b for i,b in enumerate(outcome) if mask & (1<<i))

def contract(rows: list[tuple[tuple[int,...],bool]], mask: int) -> dict:
    fibers={}
    for out,good in rows:
        fibers.setdefault(project(out,mask),[]).append((out,good))
    accepted=[]; mixed=[]; losses=0; unsafe=0
    for obs, members in sorted(fibers.items()):
        goods=[out for out,g in members if g]
        bads=[out for out,g in members if not g]
        if goods and not bads: accepted.append(obs)
        if goods and bads:
            mixed.append({'observation':obs,'good':min(goods),'bad':min(bads)})
            losses+=len(goods)
            unsafe+=len(bads)
    return {'accepted':accepted,'mixed':mixed,'false_rejections':losses,
            'existential_false_acceptances':unsafe,'exact':not mixed,
            'fibers':len(fibers)}

def separation_edges(rows: list[tuple[tuple[int,...],bool]]) -> set[int]:
    return {sum((a!=b)<<i for i,(a,b) in enumerate(zip(g,bad)))
            for g,yes in rows if yes for bad,no in rows if not no}

def minimal_masks(rows: list[tuple[tuple[int,...],bool]]) -> list[int]:
    edges=separation_edges(rows)
    n=len(rows[0][0])
    good=[m for m in range(1<<n) if all(m&e for e in edges)]
    return [m for m in good if not any(k!=m and k&m==k for k in good)]

def maximal_rectangles(safe: set[tuple[int,int]]) -> list[tuple[tuple[int,...],tuple[int,...]]]:
    """Enumerate nonempty factored contracts over two binary interfaces."""
    subsets=((0,),(1,),(0,1))
    rects=[(a,b) for a,b in product(subsets,repeat=2) if set(product(a,b))<=safe]
    return [r for r in rects if not any(r!=s and set(r[0])<=set(s[0])
                                     and set(r[1])<=set(s[1]) for s in rects)]
