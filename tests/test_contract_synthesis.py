"""Tests for the generic one-shot observer synthesizer."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contracts import OneShotPlant, synthesize  # noqa: E402
from parametric_bridge import (  # noqa: E402
    CountState,
    MECHANISMS,
    INTERFACES,
    analyze_contract,
    knowledge_fibers,
    initial_states,
    observation,
    transitions,
)


def bridge_plant(bound: int, mechanism: str, interface: str) -> OneShotPlant:
    """Translate the owned bridge into the generic explicit plant."""
    seen = set(initial_states(bound))
    todo = list(seen)
    uncontrollable = []
    grants = []
    while todo:
        state = todo.pop()
        for action, target in transitions(state, mechanism):
            if action == "grant":
                grants.append((state, target))
            else:
                label = observation(action, target, interface) if state.phase == 0 else None
                uncontrollable.append((state, label, target))
            if target not in seen:
                seen.add(target)
                todo.append(target)
    good = frozenset(state for state in seen if state.phase == 3)
    return OneShotPlant(
        initial=frozenset(initial_states(bound)),
        uncontrollable=tuple(uncontrollable),
        grants=tuple(grants),
        good_terminals=good,
    )


class ContractSynthesisTests(unittest.TestCase):
    def test_generic_synthesis_matches_specialized_bridge(self) -> None:
        # One positive bound exercises hidden refill ambiguity while keeping this
        # unit test a small independent construction rather than a second study.
        for mechanism in MECHANISMS:
            for interface in INTERFACES:
                generic = synthesize(bridge_plant(1, mechanism, interface))
                specialized = analyze_contract(1, mechanism, interface)
                self.assertEqual(generic.nonblocking_exists, specialized["nonblocking"])
                specialized_beliefs = knowledge_fibers(1, mechanism, interface)
                self.assertEqual(generic.observer_states, set(specialized_beliefs.values()))
                specialized_permitted = {
                    belief for history, belief in specialized_beliefs.items()
                    if next(row for row in specialized["histories"]
                            if tuple(row["history"]) == history)["largest_safe_contract_grants"]
                }
                self.assertEqual(generic.permitted_beliefs, specialized_permitted)

    def test_hidden_closure_after_visible_receipt(self) -> None:
        result = synthesize(bridge_plant(1, "raw", "bare"))
        mixed = [belief for belief in result.observer_states
                 if CountState(1, 1, 0, 0, 0) in belief
                 and CountState(1, 1, 0, 1, 0) in belief]
        self.assertTrue(mixed)
        self.assertTrue(result.quiescent_violations)

    def test_hidden_only_alphabet_zero_still_processes_initial_closure(self) -> None:
        plant = OneShotPlant(
            initial=frozenset({"p0"}),
            uncontrollable=(("p0", None, "p1"),),
            grants=(("p0", "g0"), ("p1", "g1")),
            good_terminals=frozenset({"g0", "g1"}),
        )
        result = synthesize(plant)
        self.assertEqual(result.observer_states, frozenset({frozenset({"p0", "p1"})}))
        self.assertEqual(result.observer_transitions, ())

    def test_two_state_many_label_edges_are_all_stored(self) -> None:
        labels = tuple(f"ell-{index}" for index in range(32))
        plant = OneShotPlant(
            initial=frozenset({"u0"}),
            uncontrollable=tuple(("u0", label, "u1") for label in labels),
            grants=(("u0", "v0"), ("u1", "v1")),
            good_terminals=frozenset({"v0", "v1"}),
        )
        result = synthesize(plant)
        self.assertEqual(len(result.observer_states), 2)
        self.assertEqual(len(result.observer_transitions), 32)

    def test_rejects_nonterminal_good_state(self) -> None:
        plant = OneShotPlant(
            initial=frozenset({0}),
            uncontrollable=((1, None, 2),),
            grants=((0, 1),),
            good_terminals=frozenset({1, 2}),
        )
        with self.assertRaises(ValueError):
            synthesize(plant)


    def test_rejects_phase_overlap(self) -> None:
        plant = OneShotPlant(
            initial=frozenset({"pre", "shared"}),
            uncontrollable=(),
            grants=(("pre", "shared"),),
            good_terminals=frozenset(),
        )
        with self.assertRaisesRegex(ValueError, "regions must be disjoint"):
            synthesize(plant)

    def test_rejects_pregrant_good_terminal(self) -> None:
        plant = OneShotPlant(
            initial=frozenset({"done"}),
            uncontrollable=(),
            grants=(),
            good_terminals=frozenset({"done"}),
        )
        with self.assertRaisesRegex(ValueError, "only after grant"):
            synthesize(plant)

    def test_rejects_cycle(self) -> None:
        plant = OneShotPlant(
            initial=frozenset({"s"}),
            uncontrollable=(("s", None, "s"),),
            grants=(),
            good_terminals=frozenset(),
        )
        with self.assertRaises(ValueError):
            synthesize(plant)

    def test_rejects_second_grant(self) -> None:
        plant = OneShotPlant(
            initial=frozenset({0}),
            uncontrollable=((1, None, 2),),
            grants=((0, 1), (1, 2)),
            good_terminals=frozenset({2}),
        )
        with self.assertRaises(ValueError):
            synthesize(plant)


if __name__ == "__main__":
    unittest.main()
