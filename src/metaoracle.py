"""Independent exhaustive meta-oracle for tiny one-shot grant plants.

The production synthesizer in :mod:`contracts` computes the good-completion
kernel by reverse DAG evaluation and then builds a hidden-closure observer.
This module attacks that implementation with a differently structured oracle:
it enumerates all visible histories, all observation contracts, and all
maximal controlled paths for a fixed, explicitly declared universe of 486
two-pre-state/two-post-state plants.

The enumeration is finite corroboration, not a machine-checked proof of the
general theorem.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Iterable, Iterator

from contracts import OneShotPlant, synthesize
from lifting_counterexample import evaluate_l1_l4_counterexample

PRE = ("p0", "p1")
POST = ("t0", "t1")
VISIBLE = "a"


def _powerset(values: tuple[object, ...]) -> Iterator[frozenset[object]]:
    for size in range(len(values) + 1):
        for chosen in combinations(values, size):
            yield frozenset(chosen)


def _rgs_partitions(length: int) -> Iterator[tuple[int, ...]]:
    """Canonical set partitions as restricted-growth strings."""
    if length == 0:
        yield ()
        return

    def rec(prefix: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
        if len(prefix) == length:
            yield prefix
            return
        for value in range(max(prefix) + 2):
            yield from rec(prefix + (value,))

    yield from rec((0,))


def enumerate_plants() -> Iterator[OneShotPlant]:
    """Enumerate the declared 486-plant meta-oracle universe.

    * initial sets are every nonempty subset of ``{p0,p1}``;
    * the only possible pre-grant edge is absent, hidden, or visible ``a``;
    * each pre state has no grant or grants to one of two post states;
    * the only possible post edge ``t0 -> t1`` is absent or hidden;
    * good terminals are any subset of the actual post dead ends.

    State names keep pre- and post-grant regions disjoint.  All generated
    graphs are acyclic and satisfy the one-shot structural premise.
    """
    initial_sets = tuple(s for s in _powerset(PRE) if s)
    pre_edge_modes: tuple[str | None, ...] = ("absent", None, VISIBLE)
    grant_options: tuple[str | None, ...] = (None, *POST)
    for initial, pre_mode, grants_by_source, post_edge_present in product(
        initial_sets,
        pre_edge_modes,
        product(grant_options, repeat=len(PRE)),
        (False, True),
    ):
        uncontrollable: list[tuple[str, str | None, str]] = []
        if pre_mode != "absent":
            uncontrollable.append((PRE[0], pre_mode, PRE[1]))
        if post_edge_present:
            uncontrollable.append((POST[0], None, POST[1]))
        grants = tuple(
            (source, target)
            for source, target in zip(PRE, grants_by_source)
            if target is not None
        )
        dead_post = (POST[1],) if post_edge_present else POST
        for good in _powerset(dead_post):
            yield OneShotPlant(
                initial=frozenset(initial),
                uncontrollable=tuple(uncontrollable),
                grants=grants,
                good_terminals=frozenset(good),
            )


def _maps(plant: OneShotPlant):
    adjacency = {state: [] for state in plant.states()}
    for source, label, target in plant.uncontrollable:
        adjacency[source].append((label, target))
    grants = dict(plant.grants)
    return adjacency, grants


def _history_fibers(plant: OneShotPlant) -> dict[tuple[str, ...], frozenset[object]]:
    """Enumerate reachable pre-grant state/history pairs without subset DP.

    The walk never takes a grant edge.  Phase separation in :class:`OneShotPlant`
    therefore keeps it in the pre-grant region for both the tiny generic plants
    and the receipt-labelled raw bridge plants constructed below.
    """
    adjacency, _ = _maps(plant)
    todo = [(state, ()) for state in plant.initial]
    seen = set(todo)
    fibers: dict[tuple[str, ...], set[object]] = {}
    while todo:
        state, history = todo.pop()
        fibers.setdefault(history, set()).add(state)
        for label, target in adjacency[state]:
            next_history = history if label is None else history + (label,)
            pair = (target, next_history)
            if pair not in seen:
                seen.add(pair)
                todo.append(pair)
    return {history: frozenset(states) for history, states in fibers.items()}


def _terminal_endpoints(start: str, adjacency: dict[str, list[tuple[str | None, str]]]) -> tuple[str, ...]:
    endpoints: list[str] = []
    todo = [start]
    while todo:
        state = todo.pop()
        successors = [target for _, target in adjacency[state]]
        if successors:
            todo.extend(successors)
        else:
            endpoints.append(state)
    return tuple(endpoints)


def _safe_grant_states(
    plant: OneShotPlant, reachable_pre: Iterable[str]
) -> frozenset[str]:
    adjacency, grants = _maps(plant)
    reachable = frozenset(reachable_pre)
    return frozenset(
        state
        for state, target in grants.items()
        if state in reachable
        and all(endpoint in plant.good_terminals
                for endpoint in _terminal_endpoints(target, adjacency))
    )


def _contract_correct(
    contract: frozenset[tuple[str, ...]],
    fibers: dict[tuple[str, ...], frozenset[str]],
    safe_states: frozenset[str],
) -> bool:
    # A permission is a command at an observation history.  It is correct only
    # when grant exists and good-completes in every physical state in the fiber.
    return all(fibers[history] <= safe_states for history in contract)


def _contract_nonblocking(
    plant: OneShotPlant,
    contract: frozenset[tuple[str, ...]],
) -> bool:
    adjacency, grants = _maps(plant)
    memo: dict[tuple[str, tuple[str, ...], bool], bool] = {}

    def all_maximal_good(state: str, history: tuple[str, ...], post_grant: bool) -> bool:
        key = (state, history, post_grant)
        if key in memo:
            return memo[key]
        successors: list[tuple[str, tuple[str, ...], bool]] = []
        for label, target in adjacency[state]:
            next_history = history
            if not post_grant and label is not None:
                next_history = history + (label,)
            successors.append((target, next_history, post_grant))
        if not post_grant and history in contract and state in grants:
            successors.append((grants[state], history, True))
        if not successors:
            result = state in plant.good_terminals
        else:
            result = all(all_maximal_good(*successor) for successor in successors)
        memo[key] = result
        return result

    return all(all_maximal_good(state, (), False) for state in plant.initial)


def _all_contracts(histories: tuple[tuple[str, ...], ...]) -> Iterator[frozenset[tuple[str, ...]]]:
    yield from _powerset(histories)


def _raw_receipt_plant(bound: int, partition: tuple[int, ...]) -> OneShotPlant:
    """Construct the actual raw-timing plant labelled by a receipt partition.

    This constructor intentionally does not call the closed-form receipt helper.
    ``partition[p]`` is the receipt class emitted when ``p`` old responses remain
    after the atomic clear/sample step.
    """
    if type(bound) is not int or bound < 0:
        raise ValueError("bound must be a nonnegative integer")
    if len(partition) != bound + 1:
        raise ValueError("partition must provide one class per pending count")

    initial = frozenset((0, 0, 1, pending, 0) for pending in range(bound + 1))
    seen = set(initial)
    todo = list(initial)
    uncontrollable: list[tuple[object, str | None, object]] = []
    grants: list[tuple[object, object]] = []
    while todo:
        f, a, c, pending, phase = state = todo.pop()
        successors: list[tuple[str, object]] = []
        if phase < 2:
            if not f:
                successors.append(("flag", (1, a, c, pending, phase)))
            if pending:
                successors.append(("fill", (f, a, 1, pending - 1, phase)))
            if (not a) or c:
                successors.append(("ack", (f, 1, 0, pending, phase)))
            if phase == 0 and f:
                successors.append(("grant", (f, a, c, pending, 1)))
            if phase == 1:
                successors.append(("read0" if c else "read1",
                                   (f, a, c, pending, 2 if c else 3)))
        for action, target in successors:
            if action == "grant":
                grants.append((state, target))
            else:
                if phase == 0:
                    if action == "fill":
                        label = None
                    elif action == "ack":
                        label = f"ack:{partition[pending]}"
                    else:
                        label = action
                else:
                    label = None
                uncontrollable.append((state, label, target))
            if target not in seen:
                seen.add(target)
                todo.append(target)

    good = frozenset(state for state in seen if state[-1] == 3)
    return OneShotPlant(
        initial=initial,
        uncontrollable=tuple(uncontrollable),
        grants=tuple(grants),
        good_terminals=good,
    )


def evaluate_receipt_partition_plant(bound: int, partition: tuple[int, ...]) -> dict[str, object]:
    """Evaluate one rho-labelled raw plant without the closed-form helper."""
    plant = _raw_receipt_plant(bound, partition)
    fibers = _history_fibers(plant)
    histories = tuple(sorted(fibers, key=lambda h: (len(h), h)))
    reachable_pre = frozenset(state for states in fibers.values() for state in states)
    safe_states = _safe_grant_states(plant, reachable_pre)
    safe_histories = frozenset(
        history for history, states in fibers.items() if states <= safe_states
    )

    adjacency, _ = _maps(plant)
    quiescent_pairs = [
        (state, history)
        for history, states in fibers.items()
        for state in states
        if not adjacency[state]
    ]
    direct_nonblocking_exists = all(
        fibers[history] <= safe_states for state, history in quiescent_pairs
    )
    direct_path_nonblocking = _contract_nonblocking(plant, safe_histories)

    generic = synthesize(plant)
    generic_permissions = frozenset(
        history for history, belief in fibers.items()
        if belief in generic.permitted_beliefs
    )
    zero_isolated = all(
        partition[pending] != partition[0]
        for pending in range(1, bound + 1)
    )
    exact = all((
        direct_nonblocking_exists == direct_path_nonblocking,
        generic.kernel == safe_states,
        generic.observer_states == frozenset(fibers.values()),
        generic_permissions == safe_histories,
        generic.nonblocking_exists == direct_nonblocking_exists,
        direct_nonblocking_exists == zero_isolated,
    ))
    first_blocker = None
    if not direct_nonblocking_exists:
        candidates = [
            (history, state)
            for state, history in quiescent_pairs
            if not fibers[history] <= safe_states
        ]
        if candidates:
            history, state = min(candidates, key=lambda item: (len(item[0]), item[0], repr(item[1])))
            first_blocker = {
                "history": list(history),
                "state": list(state),
                "fiber_size": len(fibers[history]),
            }
    return {
        "bound": bound,
        "partition": list(partition),
        "zero_isolated": zero_isolated,
        "direct_nonblocking_exists": direct_nonblocking_exists,
        "direct_path_nonblocking": direct_path_nonblocking,
        "generic_nonblocking_exists": generic.nonblocking_exists,
        "history_count": len(histories),
        "observer_state_count": len(generic.observer_states),
        "safe_history_count": len(safe_histories),
        "first_blocker": first_blocker,
        "exact": exact,
    }


def _complexity_sanity_cases() -> dict[str, object]:
    """Exercise the s=0 and large-alphabet edge/storage corner cases."""
    hidden_only = OneShotPlant(
        initial=frozenset({"p0"}),
        uncontrollable=(("p0", None, "p1"),),
        grants=(("p0", "g0"), ("p1", "g1")),
        good_terminals=frozenset({"g0", "g1"}),
    )
    hidden_result = synthesize(hidden_only)

    labels = tuple(f"ell-{index}" for index in range(32))
    multi_label = OneShotPlant(
        initial=frozenset({"u0"}),
        uncontrollable=tuple(("u0", label, "u1") for label in labels),
        grants=(("u0", "v0"), ("u1", "v1")),
        good_terminals=frozenset({"v0", "v1"}),
    )
    multi_result = synthesize(multi_label)
    result = {
        "hidden_only": {
            "visible_alphabet_size": 0,
            "pregrant_edge_count": 1,
            "observer_state_count": len(hidden_result.observer_states),
            "observer_edge_count": len(hidden_result.observer_transitions),
            "initial_belief_size": len(next(iter(hidden_result.observer_states))),
        },
        "two_state_multi_label": {
            "visible_alphabet_size": len(labels),
            "pregrant_edge_count": len(labels),
            "observer_state_count": len(multi_result.observer_states),
            "observer_edge_count": len(multi_result.observer_transitions),
        },
    }
    expected = {
        "hidden_only": (0, 1, 1, 0, 2),
        "two_state_multi_label": (32, 32, 2, 32),
    }
    actual_hidden = (
        result["hidden_only"]["visible_alphabet_size"],
        result["hidden_only"]["pregrant_edge_count"],
        result["hidden_only"]["observer_state_count"],
        result["hidden_only"]["observer_edge_count"],
        result["hidden_only"]["initial_belief_size"],
    )
    actual_multi = (
        result["two_state_multi_label"]["visible_alphabet_size"],
        result["two_state_multi_label"]["pregrant_edge_count"],
        result["two_state_multi_label"]["observer_state_count"],
        result["two_state_multi_label"]["observer_edge_count"],
    )
    result["exact"] = (
        actual_hidden == expected["hidden_only"]
        and actual_multi == expected["two_state_multi_label"]
    )
    return result


@dataclass(frozen=True)
class MetaOracleSummary:
    plants_checked: int
    contract_candidates_checked: int
    nonblocking_candidates_checked: int
    receipt_partitions_checked: int
    kernel_mismatches: int
    observer_mismatches: int
    greatest_contract_mismatches: int
    nonblocking_mismatches: int
    existential_mutant_counterexamples: int
    eligibility_mutant_counterexamples: int
    plants_with_nonblocking_contract: int
    first_existential_mutant_witness: dict[str, object] | None
    receipt_partitions_by_bound: dict[str, int]
    receipt_plant_mismatches: int
    receipt_partition_results: tuple[dict[str, object], ...]
    lifting_counterexample: dict[str, object]
    complexity_sanity: dict[str, object]

    @property
    def counted_obligations(self) -> int:
        return (
            self.plants_checked * 4
            + self.contract_candidates_checked
            + self.nonblocking_candidates_checked
            + self.receipt_partitions_checked
            + 6  # L1--L4, L6 failure, and full-correctness failure
            + 2  # hidden-only and multi-label complexity sanity families
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "universe": {
                "pre_states": list(PRE),
                "post_states": list(POST),
                "initial_sets": "all nonempty subsets of the two pre states",
                "pre_edge": "p0->p1 absent, hidden, or visible a",
                "grant_options": "none, t0, or t1 independently at each pre state",
                "post_edge": "t0->t1 absent or hidden",
                "good_terminals": "every subset of actual post dead ends",
            },
            "plants_checked": self.plants_checked,
            "contract_candidates_checked": self.contract_candidates_checked,
            "nonblocking_candidates_checked": self.nonblocking_candidates_checked,
            "receipt_partitions_checked": self.receipt_partitions_checked,
            "receipt_partitions_by_bound": self.receipt_partitions_by_bound,
            "receipt_plant_mismatches": self.receipt_plant_mismatches,
            "receipt_partition_results": list(self.receipt_partition_results),
            "lifting_counterexample": self.lifting_counterexample,
            "complexity_sanity": self.complexity_sanity,
            "kernel_mismatches": self.kernel_mismatches,
            "observer_mismatches": self.observer_mismatches,
            "greatest_contract_mismatches": self.greatest_contract_mismatches,
            "nonblocking_mismatches": self.nonblocking_mismatches,
            "existential_mutant_counterexamples": self.existential_mutant_counterexamples,
            "eligibility_mutant_counterexamples": self.eligibility_mutant_counterexamples,
            "plants_with_nonblocking_contract": self.plants_with_nonblocking_contract,
            "first_existential_mutant_witness": self.first_existential_mutant_witness,
            "counted_obligations": self.counted_obligations,
            "scope": (
                "Exhaustive finite meta-check over the declared two-pre/two-post-state universe, "
                "plus 75 explicitly receipt-labelled raw plants through K=4; not a proof of the "
                "arbitrary finite theorem and not a protocol evaluation."
            ),
        }


def run_metaoracle(max_receipt_bound: int = 4) -> dict[str, object]:
    if type(max_receipt_bound) is not int or not 0 <= max_receipt_bound <= 7:
        raise ValueError("max_receipt_bound must be in [0,7]")

    plants_checked = contract_candidates = nonblocking_candidates = 0
    kernel_mismatches = observer_mismatches = 0
    greatest_mismatches = nonblocking_mismatches = 0
    existential_counterexamples = eligibility_counterexamples = 0
    nonblocking_plants = 0
    first_witness: dict[str, object] | None = None

    for index, plant in enumerate(enumerate_plants()):
        plants_checked += 1
        fibers = _history_fibers(plant)
        histories = tuple(sorted(fibers, key=lambda h: (len(h), h)))
        reachable_pre = frozenset(state for states in fibers.values() for state in states)
        safe_states = _safe_grant_states(plant, reachable_pre)
        safe_histories = frozenset(
            history for history, states in fibers.items() if states <= safe_states
        )

        result = synthesize(plant)
        kernel_mismatches += int(result.kernel != safe_states)
        observer_mismatches += int(result.observer_states != frozenset(fibers.values()))
        observer_permission_histories = frozenset(
            history for history, belief in fibers.items()
            if belief in result.permitted_beliefs
        )
        greatest_mismatches += int(observer_permission_histories != safe_histories)

        correct_contracts: list[frozenset[tuple[str, ...]]] = []
        any_nonblocking = False
        for contract in _all_contracts(histories):
            contract_candidates += 1
            correct = _contract_correct(contract, fibers, safe_states)
            if correct:
                correct_contracts.append(contract)
                nonblocking_candidates += 1
                any_nonblocking |= _contract_nonblocking(plant, contract)
        if not correct_contracts or safe_histories not in correct_contracts:
            greatest_mismatches += 1
        elif any(not contract <= safe_histories for contract in correct_contracts):
            greatest_mismatches += 1
        if any_nonblocking:
            nonblocking_plants += 1
        nonblocking_mismatches += int(any_nonblocking != result.nonblocking_exists)

        existential_histories = frozenset(
            history for history, states in fibers.items() if states & safe_states
        )
        bad_existential = existential_histories - safe_histories
        if bad_existential:
            existential_counterexamples += 1
            if first_witness is None:
                history = min(bad_existential, key=lambda h: (len(h), h))
                first_witness = {
                    "plant_index": index,
                    "history": list(history),
                    "fiber": sorted(fibers[history]),
                    "safe_states_in_fiber": sorted(fibers[history] & safe_states),
                    "unsafe_states_in_fiber": sorted(fibers[history] - safe_states),
                }

        # Eligibility is not optional: treating a state without a physical grant
        # as vacuously safe creates permissions that the exact command semantics
        # forbids.  This mutant ignores such states.
        _, grant_map = _maps(plant)
        vacuous_histories = frozenset(
            history
            for history, states in fibers.items()
            if all(state not in grant_map or state in safe_states for state in states)
        )
        if vacuous_histories - safe_histories:
            eligibility_counterexamples += 1

    receipt_counts: dict[str, int] = {}
    receipt_checked = 0
    receipt_rows: list[dict[str, object]] = []
    receipt_plant_mismatches = 0
    for bound in range(max_receipt_bound + 1):
        count = 0
        for partition in _rgs_partitions(bound + 1):
            row = evaluate_receipt_partition_plant(bound, partition)
            receipt_rows.append(row)
            receipt_plant_mismatches += int(not bool(row["exact"]))
            count += 1
        receipt_counts[str(bound)] = count
        receipt_checked += count

    lifting = evaluate_l1_l4_counterexample()
    complexity = _complexity_sanity_cases()

    summary = MetaOracleSummary(
        plants_checked=plants_checked,
        contract_candidates_checked=contract_candidates,
        nonblocking_candidates_checked=nonblocking_candidates,
        receipt_partitions_checked=receipt_checked,
        kernel_mismatches=kernel_mismatches,
        observer_mismatches=observer_mismatches,
        greatest_contract_mismatches=greatest_mismatches,
        nonblocking_mismatches=nonblocking_mismatches,
        existential_mutant_counterexamples=existential_counterexamples,
        eligibility_mutant_counterexamples=eligibility_counterexamples,
        plants_with_nonblocking_contract=nonblocking_plants,
        first_existential_mutant_witness=first_witness,
        receipt_partitions_by_bound=receipt_counts,
        receipt_plant_mismatches=receipt_plant_mismatches,
        receipt_partition_results=tuple(receipt_rows),
        lifting_counterexample=lifting,
        complexity_sanity=complexity,
    )
    if any((kernel_mismatches, observer_mismatches, greatest_mismatches,
            nonblocking_mismatches, receipt_plant_mismatches)):
        raise AssertionError(summary.as_dict())
    if not existential_counterexamples or not eligibility_counterexamples:
        raise AssertionError("meta-oracle universe failed to kill required mutants")
    if not (lifting["L1_through_L4"] and lifting["actual_grant_safety"]
            and not lifting["L6"] and not lifting["full_correctness"]):
        raise AssertionError(("lifting counterexample failed", lifting))
    if not complexity["exact"]:
        raise AssertionError(("complexity sanity failed", complexity))
    return summary.as_dict()
