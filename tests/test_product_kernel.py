"""Small owned regressions for the independent-line kernel proof.

These fixtures are abstract DAGs, not a multi-line coherence implementation.
They include the no-grant case that cannot be handled by choosing a bad suffix.
"""
from __future__ import annotations

from itertools import combinations, product
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from contracts import OneShotPlant, synthesize


def line(kind: str) -> OneShotPlant:
    if kind == "ineligible":
        return OneShotPlant(frozenset({"p"}), (), (), frozenset())
    successors = {"good": ("g",), "bad": ("b",), "mixed": ("g", "b")}[kind]
    return OneShotPlant(
        frozenset({"p"}),
        tuple(("t", None, target) for target in successors),
        (("p", "t"),),
        frozenset({"g"}) if "g" in successors else frozenset(),
    )


def joint(left: OneShotPlant, right: OneShotPlant) -> OneShotPlant:
    """A synchronous grant followed by independent asynchronous DAG steps."""
    start = ("p", "p")
    grants = [dict(component.grants) for component in (left, right)]
    if any("p" not in mapping for mapping in grants):
        return OneShotPlant(frozenset({start}), (), (), frozenset())
    target = tuple(mapping["p"] for mapping in grants)
    adjacency = []
    for component in (left, right):
        edges = {}
        for source, _, destination in component.uncontrollable:
            edges.setdefault(source, []).append(destination)
        adjacency.append(edges)
    seen, todo, edges, good = {target}, [target], [], set()
    while todo:
        state = todo.pop()
        if all(state[i] in component.good_terminals
               for i, component in enumerate((left, right))):
            good.add(state)
        for i in range(2):
            for destination in adjacency[i].get(state[i], ()):
                successor = tuple(destination if j == i else state[j] for j in range(2))
                edges.append((state, None, successor))
                if successor not in seen:
                    seen.add(successor)
                    todo.append(successor)
    return OneShotPlant(frozenset({start}), tuple(edges), ((start, target),), frozenset(good))


class ProductKernelTests(unittest.TestCase):
    def test_all_sixteen_tiny_component_pairs(self):
        for a, b in product(("ineligible", "good", "bad", "mixed"), repeat=2):
            left, right = line(a), line(b)
            expected = ("p" in synthesize(left).kernel and "p" in synthesize(right).kernel)
            self.assertEqual(("p", "p") in synthesize(joint(left, right)).kernel,
                             expected, msg=(a, b))

    def test_ineligible_component_has_no_bad_grant_suffix(self):
        plant = joint(line("ineligible"), line("good"))
        self.assertEqual(plant.grants, ())
        self.assertEqual(synthesize(plant).kernel, frozenset())

    def test_exact_projections_even_for_correlated_knowledge(self):
        words = tuple(product((0, 1), repeat=2))
        kernels = (frozenset(), frozenset({0}), frozenset({1}), frozenset({0, 1}))
        for size in range(1, len(words) + 1):
            for members in combinations(words, size):
                knowledge = frozenset(members)
                for w0, w1 in product(kernels, repeat=2):
                    coordinate_test = ({word[0] for word in knowledge} <= w0
                                       and {word[1] for word in knowledge} <= w1)
                    self.assertEqual(knowledge <= set(product(w0, w1)), coordinate_test)

    def test_separate_local_beliefs_can_lose_joint_information(self):
        joint_knowledge = {(0, 0)}
        safe = {0}
        self.assertTrue(joint_knowledge <= set(product(safe, safe)))
        less_informative_local_belief = {0, 1}
        self.assertFalse(less_informative_local_belief <= safe)


if __name__ == "__main__":
    unittest.main()
