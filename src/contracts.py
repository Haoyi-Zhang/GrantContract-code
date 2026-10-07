"""Exact observer synthesis for finite acyclic one-shot grant plants.

This module implements the constructive part of the handwritten theorem in
``proofs/observable-grants.md``.  It is a finite checker and synthesizer, not a
proof assistant and not a cache-coherence implementation.

A plant has uncontrollable edges labelled either by a visible string or by
``None`` (hidden), at most one outgoing grant edge per state, and a set of good
terminal states.  The reachable graph must be acyclic, pre- and post-grant
reachable regions must be phase-separated, good terminals must be post-grant,
and no state reachable after grant may offer another grant.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Hashable, Iterable, Mapping

State = Hashable
Label = str | None
Edge = tuple[State, Label, State]
GrantEdge = tuple[State, State]


@dataclass(frozen=True)
class OneShotPlant:
    """Finite explicit one-shot plant.

    ``uncontrollable`` includes both pre- and post-grant edges.  ``None`` is a
    hidden label; visible labels must be nonempty strings.  ``grants`` contains
    source/target pairs and may contain at most one pair per source.
    """

    initial: frozenset[State]
    uncontrollable: tuple[Edge, ...]
    grants: tuple[GrantEdge, ...]
    good_terminals: frozenset[State]

    def states(self) -> frozenset[State]:
        values: set[State] = set(self.initial) | set(self.good_terminals)
        for source, _, target in self.uncontrollable:
            values.add(source)
            values.add(target)
        for source, target in self.grants:
            values.add(source)
            values.add(target)
        return frozenset(values)


@dataclass(frozen=True)
class SynthesisResult:
    """Exact finite synthesis result represented by observer beliefs."""

    kernel: frozenset[State]
    observer_states: frozenset[frozenset[State]]
    observer_transitions: tuple[tuple[frozenset[State], str, frozenset[State]], ...]
    permitted_beliefs: frozenset[frozenset[State]]
    quiescent_violations: tuple[tuple[State, frozenset[State]], ...]

    @property
    def nonblocking_exists(self) -> bool:
        return not self.quiescent_violations


def _adjacency(plant: OneShotPlant) -> tuple[dict[State, list[tuple[Label, State]]], dict[State, State]]:
    uncontrollable: dict[State, list[tuple[Label, State]]] = {
        state: [] for state in plant.states()
    }
    for source, label, target in plant.uncontrollable:
        if label is not None and (not isinstance(label, str) or not label):
            raise ValueError("visible labels must be nonempty strings")
        uncontrollable[source].append((label, target))
    grants: dict[State, State] = {}
    for source, target in plant.grants:
        if source in grants:
            raise ValueError("each state may have at most one outgoing grant")
        grants[source] = target
    return uncontrollable, grants


def _reachable_all(plant: OneShotPlant, uncontrollable: Mapping[State, list[tuple[Label, State]]],
                   grants: Mapping[State, State]) -> frozenset[State]:
    seen = set(plant.initial)
    todo = deque(plant.initial)
    while todo:
        state = todo.popleft()
        targets = [target for _, target in uncontrollable[state]]
        if state in grants:
            targets.append(grants[state])
        for target in targets:
            if target not in seen:
                seen.add(target)
                todo.append(target)
    return frozenset(seen)


def _topological_order(states: Iterable[State], edges: Iterable[tuple[State, State]]) -> tuple[State, ...]:
    values = frozenset(states)
    indegree = {state: 0 for state in values}
    outgoing: dict[State, list[State]] = {state: [] for state in values}
    for source, target in edges:
        if source not in values or target not in values:
            continue
        outgoing[source].append(target)
        indegree[target] += 1
    todo = deque(state for state, degree in indegree.items() if degree == 0)
    order: list[State] = []
    while todo:
        state = todo.popleft()
        order.append(state)
        for target in outgoing[state]:
            indegree[target] -= 1
            if indegree[target] == 0:
                todo.append(target)
    if len(order) != len(values):
        raise ValueError("reachable one-shot plant must be acyclic")
    return tuple(order)


def synthesize(plant: OneShotPlant) -> SynthesisResult:
    """Compute the exact kernel, reachable observer, and nonblocking test.

    The implementation follows the paper construction:

    * reverse topological dynamic programming computes the universal
      good-completion kernel after a forced grant;
    * hidden closure plus visible successor construction builds the reachable
      belief automaton before grant;
    * a belief permits grant exactly when it is a subset of the kernel;
    * nonblocking exists exactly when no quiescent physical state occurs in an
      impermissible reachable belief.
    """
    if not plant.initial:
        raise ValueError("initial set must be nonempty")
    uncontrollable, grants = _adjacency(plant)
    reachable = _reachable_all(plant, uncontrollable, grants)
    for state in plant.good_terminals & reachable:
        if uncontrollable[state] or state in grants:
            raise ValueError("good terminals must have no outgoing edges")
    all_edges = [(source, target) for source in reachable
                 for _, target in uncontrollable[source] if target in reachable]
    all_edges.extend((source, target) for source, target in grants.items()
                     if source in reachable and target in reachable)
    order = _topological_order(reachable, all_edges)

    # Identify post-grant states.  A second grant in this region would violate
    # the one-shot premise rather than silently being treated as uncontrollable.
    post: set[State] = set()
    todo = deque(target for source, target in grants.items() if source in reachable)
    while todo:
        state = todo.popleft()
        if state in post:
            continue
        post.add(state)
        if state in grants:
            raise ValueError("a state reachable after grant offers another grant")
        todo.extend(target for _, target in uncontrollable[state])

    # Reachability without taking grant is a distinct semantic phase.  A
    # concrete state name may not denote both a pre- and post-grant state;
    # otherwise whether grant has occurred would be path-dependent rather than
    # represented in the plant state.  Good terminals are post-grant outcomes.
    pre_reachable: set[State] = set(plant.initial)
    todo = deque(plant.initial)
    while todo:
        state = todo.popleft()
        for _, target in uncontrollable[state]:
            if target not in pre_reachable:
                pre_reachable.add(target)
                todo.append(target)
    if pre_reachable & post:
        raise ValueError("pre- and post-grant reachable regions must be disjoint")
    if plant.good_terminals & pre_reachable:
        raise ValueError("good terminals must be reachable only after grant")

    # Universal good termination on the post-grant DAG.  A dead end is good
    # exactly when it belongs to good_terminals; every nonterminal state must
    # have at least one successor and all successors must be good.
    post_good: dict[State, bool] = {}
    for state in reversed(order):
        if state not in post:
            continue
        successors = [target for _, target in uncontrollable[state]]
        post_good[state] = (
            state in plant.good_terminals if not successors
            else all(post_good[target] for target in successors)
        )
    kernel = frozenset(
        source for source, target in grants.items()
        if source in reachable and post_good.get(target, False)
    )

    # The observer is built only from pre-grant uncontrollable behavior.
    def hidden_closure(seed: Iterable[State]) -> frozenset[State]:
        closed = set(seed)
        queue = deque(closed)
        while queue:
            source = queue.popleft()
            for label, target in uncontrollable[source]:
                if label is None and target not in closed:
                    closed.add(target)
                    queue.append(target)
        return frozenset(closed)

    initial_belief = hidden_closure(plant.initial)
    # Intern beliefs so each stored observer edge points to the canonical
    # frozenset already resident in the observer.  This makes the documented
    # O(N*n + R) observer-storage convention true rather than retaining an
    # equal-but-distinct target set on every edge.
    belief_intern = {initial_belief: initial_belief}
    queue = deque([initial_belief])
    observer_edges: set[tuple[frozenset[State], str, frozenset[State]]] = set()
    while queue:
        belief = queue.popleft()
        targets_by_label: dict[str, set[State]] = {}
        for source in belief:
            for label, target in uncontrollable[source]:
                if label is not None:
                    targets_by_label.setdefault(label, set()).add(target)
        for label in sorted(targets_by_label):
            candidate = hidden_closure(targets_by_label[label])
            target_belief = belief_intern.get(candidate)
            if target_belief is None:
                target_belief = candidate
                belief_intern[target_belief] = target_belief
                queue.append(target_belief)
            observer_edges.add((belief, label, target_belief))
    beliefs = set(belief_intern)

    permitted = frozenset(belief for belief in beliefs if belief <= kernel)
    violations: list[tuple[State, frozenset[State]]] = []
    for belief in beliefs:
        if belief in permitted:
            continue
        for state in belief:
            if not uncontrollable[state]:
                violations.append((state, belief))
    violations.sort(key=lambda item: (repr(item[0]), tuple(sorted(map(repr, item[1])))))
    observer_sorted = tuple(sorted(
        observer_edges,
        key=lambda edge: (
            tuple(sorted(map(repr, edge[0]))), edge[1],
            tuple(sorted(map(repr, edge[2]))),
        ),
    ))
    return SynthesisResult(
        kernel=kernel,
        observer_states=frozenset(beliefs),
        observer_transitions=observer_sorted,
        permitted_beliefs=permitted,
        quiescent_violations=tuple(violations),
    )
