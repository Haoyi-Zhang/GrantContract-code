"""Executable counterexample separating L1--L4 grant safety from correctness.

The paper's concrete-contract correctness definition requires grant eligibility in
*every* concrete state compatible with an admitted visible history.  The four
simulation obligations L1--L4 only constrain initial mapping, concrete steps,
concrete grants that actually occur, and post-grant completion.  They do not
force a concrete grant to exist at every state whose abstraction is grantable.

This module encodes the smallest example used in the proof note.  It is a finite
executable sanity check, not a proof assistant development.
"""
from __future__ import annotations

from collections import deque


def evaluate_l1_l4_counterexample() -> dict[str, object]:
    """Return the independently checked three-state concrete counterexample.

    Abstract plant::

        q --grant--> g       with g good

    Concrete plant::

        s0 --hidden--> s1 --grant--> gB       with gB good

    Both ``s0`` and ``s1`` abstract to ``q``; ``gB`` abstracts to ``g``.  The
    hidden concrete step is matched by an empty abstract path and rank 1 -> 0.
    Thus L1--L4 hold and every concrete grant that actually occurs completes
    well, but the empty-history concrete knowledge set contains ineligible s0.
    """
    abstract_initial = frozenset({"q"})
    abstract_grants = {"q": "g"}
    abstract_good = frozenset({"g"})
    abstract_uncontrollable: dict[str, tuple[tuple[str | None, str], ...]] = {
        "q": (),
        "g": (),
    }

    concrete_initial = frozenset({"s0"})
    concrete_hidden = (("s0", "s1"),)
    concrete_grants = {"s1": "gB"}
    concrete_good = frozenset({"gB"})
    concrete_post: dict[str, tuple[str, ...]] = {"gB": ()}

    alpha = {"s0": "q", "s1": "q", "gB": "g"}
    rank = {"s0": 1, "s1": 0}

    # L1: concrete initials map to allowed abstract initials.
    l1 = all(alpha[state] in abstract_initial for state in concrete_initial)

    # L2: the only concrete hidden step is matched by an empty abstract path;
    # because the match is empty, the declared natural rank must decrease.
    l2_checks = []
    for source, target in concrete_hidden:
        empty_abstract_match = alpha[source] == alpha[target]
        rank_decreases = rank[target] < rank[source]
        l2_checks.append(empty_abstract_match and rank_decreases)
    l2 = all(l2_checks)

    # L3: each concrete grant maps to the abstract grant edge.
    l3 = all(
        abstract_grants.get(alpha[source]) == alpha[target]
        for source, target in concrete_grants.items()
    )

    # L4: the sole concrete post-grant suffix is the finite terminal gB; its
    # image g is a maximal good abstract suffix and gB has the declared outcome.
    l4_checks = []
    for source, target in concrete_grants.items():
        concrete_suffix_finite = concrete_post[target] == ()
        abstract_target = alpha[target]
        abstract_suffix_maximal = not abstract_uncontrollable[abstract_target]
        abstract_terminal_good = abstract_target in abstract_good
        concrete_outcome_good = target in concrete_good
        l4_checks.append(
            concrete_suffix_finite
            and abstract_suffix_maximal
            and (not abstract_terminal_good or concrete_outcome_good)
        )
    l4 = all(l4_checks)

    # Hidden closure of the concrete initial state at visible history epsilon.
    epsilon_knowledge = set(concrete_initial)
    todo = deque(concrete_initial)
    by_source: dict[str, list[str]] = {}
    for source, target in concrete_hidden:
        by_source.setdefault(source, []).append(target)
    while todo:
        source = todo.popleft()
        for target in by_source.get(source, ()):  # finite acyclic graph
            if target not in epsilon_knowledge:
                epsilon_knowledge.add(target)
                todo.append(target)

    abstract_epsilon_knowledge = frozenset(alpha[state] for state in epsilon_knowledge)
    abstract_cstar_enables = (
        abstract_epsilon_knowledge == frozenset({"q"})
        and abstract_grants.get("q") == "g"
        and "g" in abstract_good
    )

    concrete_eligible = frozenset(concrete_grants)
    ineligible_in_epsilon = frozenset(epsilon_knowledge) - concrete_eligible

    # L6 fails because the abstract contract enables at q while s0 has no grant.
    l6 = all(
        state in concrete_eligible
        for state in epsilon_knowledge
        if abstract_cstar_enables
    )

    # L1--L4 do ensure safety of grants that actually exist and are taken.
    actual_grant_safety = all(
        target in concrete_good and alpha[target] in abstract_good
        for target in concrete_grants.values()
    )

    # Full statewise correctness additionally requires eligibility at every
    # concrete member of the admitted history fiber.
    full_correct = (
        abstract_cstar_enables
        and not ineligible_in_epsilon
        and actual_grant_safety
    )

    return {
        "abstract": {
            "initial": sorted(abstract_initial),
            "grant": ["q", "g"],
            "good_terminal": "g",
        },
        "concrete": {
            "initial": sorted(concrete_initial),
            "hidden_step": ["s0", "s1"],
            "grant": ["s1", "gB"],
            "good_terminal": "gB",
        },
        "alpha": alpha,
        "rank": rank,
        "epsilon_knowledge": sorted(epsilon_knowledge),
        "abstract_epsilon_knowledge": sorted(abstract_epsilon_knowledge),
        "ineligible_in_epsilon": sorted(ineligible_in_epsilon),
        "abstract_cstar_enables": abstract_cstar_enables,
        "L1": l1,
        "L2": l2,
        "L3": l3,
        "L4": l4,
        "L1_through_L4": all((l1, l2, l3, l4)),
        "L6": l6,
        "actual_grant_safety": actual_grant_safety,
        "full_correctness": full_correct,
        "validation_status": "finite executable counterexample",
        "interpretation": (
            "L1--L4 prove good completion for concrete grants that actually occur, "
            "but do not supply grant eligibility at every concrete state in an admitted fiber."
        ),
    }
