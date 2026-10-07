"""Portable, finite observer regression; no historical implementation copy.

Run directly, separately from the retained test_*.py suite. The literal reference
enumerates physical prefixes and terminal suffixes, not subset transitions.
snapshot() supports fresh-interpreter comparisons of actual before/current code.
Only repository-relative imports/data are used; no timing or files are produced.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contracts import OneShotPlant, SynthesisResult, synthesize
import metaoracle
import parametric_bridge as bridge


def belief_key(belief):
    return tuple(sorted(map(repr, belief)))


def literal_result(plant):
    """Enumerate every finite pre-grant path prefix and every grant suffix.

    This reference is only for valid acyclic one-shot fixtures. No hidden-closure,
    observer-queue, target-grouping or implementation adjacency helper is used.
    Repeated physical paths are deliberately enumerated rather than memoized.
    """
    prefixes = []

    def visit(state, history):
        prefixes.append((state, history))
        for source, label, target in plant.uncontrollable:
            if source == state:
                visit(target, history if label is None else history + (label,))

    for state in plant.initial:
        visit(state, ())
    histories = {history for _, history in prefixes}
    fibers = {
        history: frozenset(state for state, seen in prefixes if seen == history)
        for history in histories
    }

    def endpoints(state):
        outgoing = [target for source, _, target in plant.uncontrollable
                    if source == state]
        if not outgoing:
            return [state]
        return [end for target in outgoing for end in endpoints(target)]

    reachable_pre = {state for state, _ in prefixes}
    kernel = frozenset(
        source for source, target in plant.grants
        if source in reachable_pre
        and all(end in plant.good_terminals for end in endpoints(target))
    )
    beliefs = frozenset(fibers.values())
    permitted = frozenset(
        belief for belief in beliefs if all(state in kernel for state in belief)
    )
    # Exact public output ordering, not a reconstruction of the observer loop.
    edges = {
        (fibers[history[:-1]], history[-1], fibers[history])
        for history in histories if history
    }
    violations = {
        (state, belief) for belief in beliefs if belief not in permitted
        for state in belief
        if not any(source == state for source, _, _ in plant.uncontrollable)
    }
    return SynthesisResult(
        kernel, beliefs,
        tuple(sorted(edges, key=lambda edge: (
            belief_key(edge[0]), edge[1], belief_key(edge[2])))),
        permitted,
        tuple(sorted(violations, key=lambda item: (repr(item[0]), belief_key(item[1])))),
    )


def tiny_plants():
    # Every absent/hidden/a/b choice on the three forward pre edges, crossed
    # with every grant-eligibility subset: 4^3 * 2^3 = 512 declared plants.
    absent = object()
    for labels in itertools.product((absent, None, "a", "b"), repeat=3):
        edges = tuple((source, label, target)
                      for (source, target), label in zip(
                          (("p0", "p1"), ("p0", "p2"), ("p1", "p2")), labels)
                      if label is not absent)
        for mask in range(8):
            # p1 has a branching good/bad grant suffix, so eligibility alone
            # never licenses it. p2 has a bad terminal; p0 has a good terminal.
            yield OneShotPlant(
                frozenset({"p0"}),
                edges + (("branch", None, "good"), ("branch", None, "bad")),
                tuple((state, target) for index, (state, target) in enumerate(
                    (("p0", "good"), ("p1", "branch"), ("p2", "bad")))
                    if mask & (1 << index)),
                frozenset({"good"}),
            )


def boundary_plants():
    yield OneShotPlant(
        frozenset({"p0"}),
        (("p0", None, "p1"), ("p0", "z", "p2"),
         ("p1", "a", "p2"), ("p1", "z", "p2"),
         ("p1", "a", "p2"), ("p2", None, "p3"),
         ("unreachable", "absent-label", "other"),
         ("post", "post-label", "good")),
        (("p0", "post"), ("p1", "post"), ("p2", "post"), ("p3", "post")),
        frozenset({"good"}),
    )
    yield OneShotPlant(frozenset({"p0"}), (("p0", None, "p1"),),
                       (("p0", "g0"), ("p1", "g1")), frozenset({"g0", "g1"}))
    yield OneShotPlant(
        frozenset({"p0"}),
        tuple(("p0", f"ell-{index}", "p1") for index in range(32)),
        (("p0", "g0"), ("p1", "g1")), frozenset({"g0", "g1"}),
    )


def owned_bridge_plant(bound, mechanism, interface):
    """Convert the owned physical relation, without importing another test."""
    initial = frozenset(bridge.initial_states(bound))
    seen = set(initial)
    pending = list(initial)
    edges, grants = [], []
    while pending:
        state = pending.pop()
        for action, target in bridge.transitions(state, mechanism):
            if action == "grant":
                grants.append((state, target))
            else:
                label = bridge.observation(action, target, interface) if state.phase == 0 else None
                edges.append((state, label, target))
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return OneShotPlant(initial, tuple(edges), tuple(grants),
                        frozenset(state for state in seen if state.phase == 3))


def receipt_plants():
    for bound in range(5):
        for partition in metaoracle._rgs_partitions(bound + 1):
            yield metaoracle._raw_receipt_plant(bound, partition)


def bridge_plants():
    for bound in range(5):
        for mechanism in bridge.MECHANISMS:
            for interface in bridge.INTERFACES:
                yield owned_bridge_plant(bound, mechanism, interface)


def encode_result(result):
    return {
        "kernel": sorted(map(repr, result.kernel)),
        "observer_states": [list(belief_key(belief)) for belief in
                            sorted(result.observer_states, key=belief_key)],
        "observer_transitions": [[list(belief_key(source)), label, list(belief_key(target))]
                                 for source, label, target in result.observer_transitions],
        "permitted_beliefs": [list(belief_key(belief)) for belief in
                             sorted(result.permitted_beliefs, key=belief_key)],
        "quiescent_violations": [[repr(state), list(belief_key(belief))]
                                 for state, belief in result.quiescent_violations],
        "nonblocking_exists": result.nonblocking_exists,
    }


def rejected_inputs():
    plants = [
        ("empty-initial", OneShotPlant(frozenset(), (), (), frozenset())),
        ("cycle", OneShotPlant(frozenset({0}), ((0, None, 0),), (), frozenset())),
        ("phase-overlap", OneShotPlant(frozenset({0, 1}), (), ((0, 1),), frozenset())),
        ("pregrant-good", OneShotPlant(frozenset({0}), (), (), frozenset({0}))),
        ("second-grant", OneShotPlant(frozenset({0}), (), ((0, 1), (1, 2)), frozenset({2}))),
        ("nonterminal-good", OneShotPlant(frozenset({0}), ((1, None, 2),),
                                         ((0, 1),), frozenset({1, 2}))),
        ("empty-label", OneShotPlant(frozenset({0}), ((8, "", 9),), (), frozenset())),
        ("nonstring-label", OneShotPlant(frozenset({0}), ((8, 1, 9),), (), frozenset())),
        ("duplicate-grant", OneShotPlant(frozenset({0}), (), ((8, 9), (8, 9)), frozenset())),
    ]
    calls = [(name, lambda plant=plant: synthesize(plant)) for name, plant in plants]
    for bound in (-1, 8, True):
        calls.append((f"meta-cap-{bound!r}", lambda bound=bound: metaoracle.run_metaoracle(bound)))
    for bound in (0, 9, True):
        calls.append((f"bridge-cap-{bound!r}", lambda bound=bound: bridge.run_parametric(bound)))
    return calls


def rejection_records():
    records = []
    for name, call in rejected_inputs():
        try:
            call()
        except ValueError as error:
            records.append([name, type(error).__name__, str(error)])
        else:
            raise AssertionError(f"unsupported input accepted: {name}")
    return records


def parsed(value):
    return json.loads(json.dumps(value))


def snapshot():
    return {
        "tiny": [encode_result(synthesize(plant)) for plant in tiny_plants()],
        "boundary": [encode_result(synthesize(plant)) for plant in boundary_plants()],
        "generic": [encode_result(synthesize(plant)) for plant in metaoracle.enumerate_plants()],
        "receipt": [encode_result(synthesize(plant)) for plant in receipt_plants()],
        "bridge": [encode_result(synthesize(plant)) for plant in bridge_plants()],
        "rejected": rejection_records(),
        "metaoracle_output": parsed(metaoracle.run_metaoracle(4)),
        "parametric_output": parsed(bridge.run_parametric(4)),
    }


class VisibleGroupingRegression(unittest.TestCase):
    def assert_literal(self, plant):
        actual = synthesize(plant)
        self.assertEqual(actual, literal_result(plant))
        residents = {belief: belief for belief in actual.observer_states}
        for source, _, target in actual.observer_transitions:
            self.assertIs(source, residents[source])
            self.assertIs(target, residents[target])
        return actual

    def test_literal_tiny_complete_results(self):
        plants = list(tiny_plants())
        self.assertEqual(len(plants), 512)
        for index, plant in enumerate(plants):
            with self.subTest(index=index):
                self.assert_literal(plant)

    def test_owned_full_results_and_boundaries(self):
        for expected, plants in ((486, metaoracle.enumerate_plants()),
                                 (75, receipt_plants()), (50, bridge_plants())):
            count = 0
            for plant in plants:
                self.assert_literal(plant)
                count += 1
            self.assertEqual(count, expected)
        boundary = [self.assert_literal(plant) for plant in boundary_plants()]
        self.assertEqual([label for _, label, _ in boundary[0].observer_transitions], ["a", "z"])
        self.assertEqual(boundary[1].observer_transitions, ())
        self.assertEqual(len(boundary[2].observer_transitions), 32)
        self.assertTrue(any(synthesize(plant).quiescent_violations for plant in bridge_plants()))

    def test_structural_rejections_and_dependent_caps(self):
        records = rejection_records()
        self.assertEqual(len(records), 15)
        self.assertTrue(all(kind == "ValueError" and message for _, kind, message in records))
        # Generic synthesis has no numeric cap API; these retain existing
        # dependent input-range guards, not a newly claimed plant-size cap.
        self.assertTrue(all(message == "max_receipt_bound must be in [0,7]"
                            for name, _, message in records if name.startswith("meta-cap")))
        self.assertTrue(all(message == "max_bound must be in [1,8]"
                            for name, _, message in records if name.startswith("bridge-cap")))

    def test_complete_retained_pure_outputs_and_counters(self):
        for filename, current in (
            ("metaoracle-summary.json", metaoracle.run_metaoracle(4)),
            ("parametric-summary.json", bridge.run_parametric(4)),
        ):
            with (ROOT / "results" / filename).open(encoding="utf-8") as source:
                self.assertEqual(parsed(current), json.load(source))


if __name__ == "__main__":
    unittest.main()
