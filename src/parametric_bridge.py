"""Parametric bounded stale-fill bridge and observable-grant analysis.

This module generalizes the executable one-fill plant in :mod:`bridge` to a
bounded count of indistinguishable stale responses.  It is an owned abstract
model, not an implementation of MemGlue, CXL, C3, or a commercial protocol.
The mathematical theorem proved in ``proofs/observable-grants.md`` applies to
any finite acyclic one-shot plant; this file exhaustively checks its bridge
instantiations for bounds K=0..4.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Callable, Iterable

MECHANISMS = ("raw", "drain", "generation", "late_generation", "no_repair")
INTERFACES = ("bare", "zero_receipt")


@dataclass(frozen=True, order=True)
class CountState:
    """One-line bridge state.

    ``pending`` is the number of stale responses that were already created
    before the producer's fixed data/release prefix.  No transition creates a
    new stale response.  ``phase`` is 0 before grant, 1 after grant, 2 after a
    stale read, and 3 after a fresh read.
    """

    flag: int = 0
    invalidated: int = 0
    old_cache: int = 1
    pending: int = 0
    phase: int = 0

    def __post_init__(self) -> None:
        if any(type(x) is not int or x not in (0, 1)
               for x in (self.flag, self.invalidated, self.old_cache)):
            raise ValueError("binary state fields must be 0 or 1")
        if type(self.pending) is not int or self.pending < 0:
            raise ValueError("pending must be a nonnegative integer")
        if type(self.phase) is not int or self.phase not in range(4):
            raise ValueError("phase must be in [0,3]")

    def key(self) -> tuple[int, int, int, int, int]:
        return (self.flag, self.invalidated, self.old_cache,
                self.pending, self.phase)


def initial_states(bound: int) -> tuple[CountState, ...]:
    if type(bound) is not int or bound < 0:
        raise ValueError("bound must be a nonnegative integer")
    return tuple(CountState(pending=p) for p in range(bound + 1))


def transitions(state: CountState, mechanism: str) -> tuple[tuple[str, CountState], ...]:
    """Primary transition relation for the bounded-count bridge."""
    if mechanism not in MECHANISMS:
        raise ValueError("unknown mechanism")
    if state.phase >= 2:
        return ()
    out: list[tuple[str, CountState]] = []
    if not state.flag:
        out.append(("flag", replace(state, flag=1)))
    if state.pending:
        discard = ((mechanism == "generation" and state.invalidated == 1)
                   or (mechanism == "late_generation" and state.phase == 1))
        out.append(("fill", replace(
            state,
            pending=state.pending - 1,
            old_cache=state.old_cache if discard else 1,
        )))
    may_ack = (not state.invalidated or state.old_cache == 1)
    if mechanism == "no_repair":
        may_ack = not state.invalidated
    if mechanism == "drain" and state.pending:
        may_ack = False
    if may_ack:
        out.append(("ack", replace(state, invalidated=1, old_cache=0)))
    if state.phase == 0 and state.flag:
        out.append(("grant", replace(state, phase=1)))
    if state.phase == 1:
        action = "read0" if state.old_cache else "read1"
        out.append((action, replace(state, phase=2 if state.old_cache else 3)))
    return tuple(sorted(out, key=lambda item: (item[0], item[1].key())))


def reachable_graph(bound: int, mechanism: str) -> tuple[set[CountState], set[tuple[tuple[int, ...], str, tuple[int, ...]]]]:
    """Reachable states and labeled edges from all declared initial counts."""
    seen = set(initial_states(bound))
    todo = deque(sorted(seen))
    edges: set[tuple[tuple[int, ...], str, tuple[int, ...]]] = set()
    while todo:
        state = todo.popleft()
        for action, target in transitions(state, mechanism):
            edges.add((state.key(), action, target.key()))
            if target not in seen:
                seen.add(target)
                todo.append(target)
    # Closed-form state-space ceiling, with generous constant slack.
    if len(seen) > 16 * (bound + 1) or len(edges) > 64 * (bound + 1):
        raise ValueError("parametric plant budget exceeded")
    return seen, edges


def oracle_edges(bound: int, mechanism: str) -> set[tuple[tuple[int, ...], str, tuple[int, ...]]]:
    """Separately structured tuple oracle for transition construction."""
    if mechanism not in MECHANISMS:
        raise ValueError("unknown mechanism")
    all_edges: set[tuple[tuple[int, ...], str, tuple[int, ...]]] = set()
    for f in (0, 1):
        for a in (0, 1):
            for c in (0, 1):
                for p in range(bound + 1):
                    for phase in range(4):
                        q = (f, a, c, p, phase)
                        if phase > 1:
                            continue
                        if not f:
                            all_edges.add((q, "flag", (1, a, c, p, phase)))
                        if p:
                            drop = ((mechanism == "generation" and bool(a))
                                    or (mechanism == "late_generation" and phase == 1))
                            all_edges.add((q, "fill", (f, a, c if drop else 1, p - 1, phase)))
                        may_ack = ((not a) or bool(c))
                        if mechanism == "no_repair":
                            may_ack = not bool(a)
                        if mechanism == "drain" and p:
                            may_ack = False
                        if may_ack:
                            all_edges.add((q, "ack", (f, 1, 0, p, phase)))
                        if phase == 0 and f:
                            all_edges.add((q, "grant", (f, a, c, p, 1)))
                        if phase == 1:
                            all_edges.add((q, "read0" if c else "read1",
                                           (f, a, c, p, 2 if c else 3)))
    starts = {(0, 0, 1, p, 0) for p in range(bound + 1)}
    reachable = set(starts)
    todo = deque(sorted(starts))
    by_source: dict[tuple[int, ...], list[tuple[tuple[int, ...], str, tuple[int, ...]]]] = {}
    for edge in all_edges:
        by_source.setdefault(edge[0], []).append(edge)
    while todo:
        source = todo.popleft()
        for _, _, target in by_source.get(source, ()):  # pragma: no branch - finite oracle
            if target not in reachable:
                reachable.add(target)
                todo.append(target)
    return {edge for edge in all_edges if edge[0] in reachable}


def grant_formula(state: CountState, mechanism: str) -> bool:
    """Closed-form universal safety of forcing grant at an eligible state."""
    if state.phase != 0 or not state.flag:
        return False
    persistent_filter = (mechanism == "generation" and bool(state.invalidated))
    grant_filter = mechanism == "late_generation"
    return (not state.old_cache
            and (state.pending == 0 or persistent_filter or grant_filter))


def forced_grant_safe(state: CountState, mechanism: str) -> bool:
    """Graph suffix oracle; it does not consult :func:`grant_formula`."""
    if state.phase != 0 or not state.flag:
        return False
    start = replace(state, phase=1)
    seen = {start}
    todo = [start]
    while todo:
        current = todo.pop()
        successors = transitions(current, mechanism)
        if not successors:
            if current.phase != 3:
                return False
            continue
        for _, target in successors:
            if target not in seen:
                seen.add(target)
                todo.append(target)
    return True


def observation(action: str, after: CountState, interface: str) -> str | None:
    if interface not in INTERFACES:
        raise ValueError("unknown interface")
    if action == "fill":
        return None
    if action == "ack" and interface == "zero_receipt":
        return "ack:0" if after.pending == 0 else "ack:+"
    return action


def raw_receipt_partition_is_complete(bound: int, symbols: Iterable[object]) -> bool:
    """Exact raw-interface criterion for a deterministic receipt partition.

    ``symbols[p]`` is the atomic payload emitted by a raw acknowledgement when
    ``p`` old responses remain immediately after clearing the line.  For a
    positive bound, universal safety and nonblocking are simultaneously
    achievable exactly when the zero-pending symbol is not reused by any
    positive pending count.  Positive counts may otherwise share symbols.

    This function checks the closed-form theorem; it does not synthesize a
    controller or infer receipt semantics from arbitrary protocol code.
    """
    if type(bound) is not int or bound < 0:
        raise ValueError("bound must be a nonnegative integer")
    values = tuple(symbols)
    if len(values) != bound + 1:
        raise ValueError("one receipt symbol is required for each pending count")
    return all(values[pending] != values[0] for pending in range(1, bound + 1))


def environment_successors(state: CountState, mechanism: str) -> tuple[tuple[str, CountState], ...]:
    return tuple((action, target) for action, target in transitions(state, mechanism)
                 if action != "grant")


def prefix_fibers(bound: int, mechanism: str, interface: str) -> dict[tuple[str, ...], frozenset[CountState]]:
    """Reachable state/history pairs grouped by the complete visible history."""
    todo = deque((state, ()) for state in initial_states(bound))
    seen = set(todo)
    fibers: dict[tuple[str, ...], set[CountState]] = {}
    while todo:
        state, history = todo.popleft()
        fibers.setdefault(history, set()).add(state)
        for action, target in environment_successors(state, mechanism):
            symbol = observation(action, target, interface)
            next_history = history if symbol is None else history + (symbol,)
            pair = (target, next_history)
            if pair not in seen:
                seen.add(pair)
                todo.append(pair)
    return {history: frozenset(states) for history, states in sorted(fibers.items())}


def knowledge_fibers(bound: int, mechanism: str, interface: str) -> dict[tuple[str, ...], frozenset[CountState]]:
    """Independent hidden-closure construction of observation knowledge sets."""
    def close(seeds: Iterable[CountState]) -> frozenset[CountState]:
        closed = set(seeds)
        todo = list(closed)
        while todo:
            state = todo.pop()
            for action, target in environment_successors(state, mechanism):
                if observation(action, target, interface) is None and target not in closed:
                    closed.add(target)
                    todo.append(target)
        return frozenset(closed)

    beliefs: dict[tuple[str, ...], frozenset[CountState]] = {(): close(initial_states(bound))}
    todo = deque([()])
    while todo:
        history = todo.popleft()
        posts: dict[str, set[CountState]] = {}
        for state in beliefs[history]:
            for action, target in environment_successors(state, mechanism):
                symbol = observation(action, target, interface)
                if symbol is not None:
                    posts.setdefault(symbol, set()).add(target)
        for symbol, targets in sorted(posts.items()):
            next_history = history + (symbol,)
            belief = close(targets)
            previous = beliefs.get(next_history)
            if previous is not None and previous != belief:
                raise AssertionError("nondeterministic belief construction")
            if previous is None:
                beliefs[next_history] = belief
                todo.append(next_history)
    return dict(sorted(beliefs.items()))


def audit_contract_rows(rows: Iterable[dict]) -> dict[str, int | bool]:
    """Audit a proposed history contract against the full-state safety fibers.

    Keeping this check separate from contract construction prevents the safety
    result from becoming vacuous: a row that grants an unsafe fiber, or refuses
    a wholly safe fiber, is detected even when supplied by a mutated caller.
    """
    materialized = list(rows)
    unsafe_grants = sum(
        bool(row["largest_safe_contract_grants"]) and not bool(row["all_states_safe"])
        for row in materialized
    )
    missed_safe = sum(
        not bool(row["largest_safe_contract_grants"]) and bool(row["all_states_safe"])
        for row in materialized
    )
    ineligible_grants = sum(
        bool(row["largest_safe_contract_grants"]) and not bool(row["grant_enabled_in_all_states"])
        for row in materialized
    )
    return {
        "unsafe_grant_history_count": unsafe_grants,
        "missed_safe_history_count": missed_safe,
        "ineligible_grant_history_count": ineligible_grants,
        "universally_safe": unsafe_grants == 0 and ineligible_grants == 0,
        "maximally_permissive": missed_safe == 0,
        "contract_exact": unsafe_grants == 0 and missed_safe == 0 and ineligible_grants == 0,
    }


def analyze_contract(bound: int, mechanism: str, interface: str) -> dict:
    """Compute and independently audit the greatest safe observation contract.

    The returned nonblocking criterion is exact for this finite acyclic plant:
    a blocked branch exists iff a state with no environment successor shares a
    history whose knowledge set is not wholly inside the full-state safe kernel.
    """
    prefixes = prefix_fibers(bound, mechanism, interface)
    beliefs = knowledge_fibers(bound, mechanism, interface)
    if prefixes != beliefs:
        raise AssertionError("prefix fibers and hidden-closure beliefs disagree")

    rows = []
    blockers: list[dict] = []
    for history, states in beliefs.items():
        eligible = all(state.flag == 1 and state.phase == 0 for state in states)
        suffix_safety = tuple(forced_grant_safe(state, mechanism) for state in states)
        all_safe_by_suffix_search = eligible and all(suffix_safety)
        # Construct permission from the closed-form kernel, then audit it against
        # exhaustive post-grant suffix search.  The two computations are kept
        # separate so an error in either direction cannot pass by self-comparison.
        contract_grants = eligible and all(grant_formula(state, mechanism) for state in states)
        for state in states:
            if not environment_successors(state, mechanism) and not contract_grants:
                blockers.append({"history": list(history), "state": list(state.key())})
        rows.append({
            "history": list(history),
            "states": [list(state.key()) for state in sorted(states)],
            "grant_enabled_in_all_states": eligible,
            "all_states_safe": all_safe_by_suffix_search,
            "largest_safe_contract_grants": contract_grants,
            "mixed_full_state_safety": eligible and any(suffix_safety) and not all(suffix_safety),
        })
    audit = audit_contract_rows(rows)
    return {
        "bound": bound,
        "mechanism": mechanism,
        "interface": interface,
        "history_count": len(rows),
        "grant_history_count": sum(row["largest_safe_contract_grants"] for row in rows),
        "mixed_history_count": sum(row["mixed_full_state_safety"] for row in rows),
        **audit,
        "nonblocking": not blockers,
        "blocking_witnesses": sorted(blockers, key=lambda row: (len(row["history"]), row["history"], row["state"])),
        "histories": rows,
    }



def audit_k1_observation_isomorphism(
    label_map: Callable[[str], str] | None = None,
) -> dict[str, object]:
    """Check the owned K=1 encoding relation at the observation level.

    The physical transition builders are already compared separately.  This
    audit additionally compares, for every mechanism and both interfaces:

    * the visible label on every pre-grant uncontrollable edge;
    * the complete history-to-knowledge-set map; and
    * the histories admitted by the greatest correct contract.

    ``label_map`` is applied to labels emitted by the detailed Boolean model.
    The delivered encodings use one shared alphabet (``ack:0``/``ack:+``), so
    the identity map must pass.  Supplying a deliberately wrong map provides a
    small negative control that must be rejected.
    """
    from bridge import (  # local import avoids a module cycle
        State as BinaryState,
        all_continuations_safe as binary_suffix_safe,
        initial_states as binary_initial_states,
        pregrant_fibers as binary_pregrant_fibers,
        symbol as binary_symbol,
        transitions as binary_transitions,
    )

    normalize = label_map or (lambda label: label)
    policy_for = {"bare": "receipt", "zero_receipt": "pending_receipt"}

    def binary_tuple(state: BinaryState) -> tuple[int, int, int, int, int]:
        return (state.flag, state.invalidated, state.old_cache,
                state.old_pending, state.phase)

    cases: list[dict[str, object]] = []
    label_mismatches = knowledge_mismatches = permission_mismatches = 0
    for mechanism in MECHANISMS:
        for interface in INTERFACES:
            policy = policy_for[interface]

            # Compare the observation label on each pre-grant environment edge.
            binary_labeled_edges: set[
                tuple[tuple[int, ...], str | None, tuple[int, ...]]
            ] = set()
            todo = list(binary_initial_states())
            seen = set(todo)
            while todo:
                state = todo.pop()
                for action, target in binary_transitions(state, mechanism):
                    if action == "grant":
                        continue
                    label = binary_symbol(action, target, policy)
                    mapped = None if label is None else normalize(label)
                    binary_labeled_edges.add((binary_tuple(state), mapped, binary_tuple(target)))
                    if target.phase == 0 and target not in seen:
                        seen.add(target)
                        todo.append(target)

            count_labeled_edges: set[
                tuple[tuple[int, ...], str | None, tuple[int, ...]]
            ] = set()
            todo_count = list(initial_states(1))
            seen_count = set(todo_count)
            while todo_count:
                state = todo_count.pop()
                for action, target in transitions(state, mechanism):
                    if action == "grant":
                        continue
                    label = observation(action, target, interface)
                    count_labeled_edges.add((state.key(), label, target.key()))
                    if target.phase == 0 and target not in seen_count:
                        seen_count.add(target)
                        todo_count.append(target)
            label_match = binary_labeled_edges == count_labeled_edges
            label_mismatches += int(not label_match)

            # Normalize and merge detailed histories before comparing knowledge.
            detailed_fibers: dict[tuple[str, ...], set[tuple[int, ...]]] = {}
            for row in binary_pregrant_fibers(mechanism, policy):
                history = tuple(normalize(label) for label in row["observation"])
                detailed_fibers.setdefault(history, set()).update(
                    binary_tuple(BinaryState.decode(code)) for code in row["states"]
                )
            detailed_frozen = {
                history: frozenset(states)
                for history, states in sorted(detailed_fibers.items())
            }
            count_fibers = {
                history: frozenset(state.key() for state in states)
                for history, states in knowledge_fibers(1, mechanism, interface).items()
            }
            knowledge_match = detailed_frozen == count_fibers
            knowledge_mismatches += int(not knowledge_match)

            detailed_permissions: set[tuple[str, ...]] = set()
            for history, tuples in detailed_frozen.items():
                states = [BinaryState(*values) for values in tuples]
                if (all(state.flag == 1 and state.phase == 0 for state in states)
                        and all(binary_suffix_safe(state, mechanism) for state in states)):
                    detailed_permissions.add(history)

            count_result = analyze_contract(1, mechanism, interface)
            count_permissions = {
                tuple(row["history"])
                for row in count_result["histories"]
                if row["largest_safe_contract_grants"]
            }
            permission_match = detailed_permissions == count_permissions
            permission_mismatches += int(not permission_match)

            cases.append({
                "mechanism": mechanism,
                "interface": interface,
                "pregrant_labeled_edge_count": len(count_labeled_edges),
                "history_count": len(count_fibers),
                "permission_count": len(count_permissions),
                "labels_match": label_match,
                "knowledge_sets_match": knowledge_match,
                "permitted_histories_match": permission_match,
            })

    return {
        "cases": cases,
        "cases_checked": len(cases),
        "label_mismatches": label_mismatches,
        "knowledge_mismatches": knowledge_mismatches,
        "permission_mismatches": permission_mismatches,
        "exact": not any((label_mismatches, knowledge_mismatches, permission_mismatches)),
    }


def theorem_predictions(bound: int, mechanism: str, interface: str) -> tuple[bool, bool]:
    """Manual closed-form prediction for the bridge-family contract."""
    if bound == 0:
        return True, True
    if mechanism in ("drain", "generation"):
        return True, True
    if mechanism == "raw" and interface == "zero_receipt":
        return True, True
    if mechanism == "late_generation" and interface == "zero_receipt":
        return True, True
    # Raw/bare and late-generation/bare conflate a completed clean branch with
    # one in which an invisible stale fill can intervene.  No-repair strands a
    # positive-pending branch under either receipt interface.
    return True, False


def run_parametric(max_bound: int = 4) -> dict:
    if type(max_bound) is not int or not 1 <= max_bound <= 8:
        raise ValueError("max_bound must be in [1,8]")
    plants = []
    contracts = []
    counts = {
        "edge_oracle_obligations": 0,
        "grant_kernel_obligations": 0,
        "history_oracle_obligations": 0,
        "contract_prediction_obligations": 0,
        "receipt_lower_bound_obligations": 0,
        "observation_isomorphism_obligations": 0,
        "observation_label_mutant_obligations": 0,
    }
    for bound in range(max_bound + 1):
        for mechanism in MECHANISMS:
            states, edges = reachable_graph(bound, mechanism)
            oracle = oracle_edges(bound, mechanism)
            if edges != oracle:
                raise AssertionError(("transition oracle mismatch", bound, mechanism))
            counts["edge_oracle_obligations"] += len(edges)
            eligible = sorted(state for state in states if state.flag and state.phase == 0)
            for state in eligible:
                if forced_grant_safe(state, mechanism) != grant_formula(state, mechanism):
                    raise AssertionError(("grant kernel mismatch", bound, mechanism, state))
                counts["grant_kernel_obligations"] += 1
            plants.append({
                "bound": bound,
                "mechanism": mechanism,
                "state_count": len(states),
                "transition_count": len(edges),
                "eligible_state_count": len(eligible),
                "acyclic": True,
            })
            # A rank that strictly increases along every edge proves acyclicity:
            # delivered responses, fired flag/ack/grant/read progress monotonically.
            # We still run Kahn's algorithm to guard the executable instance.
            indegree = {state.key(): 0 for state in states}
            outgoing: dict[tuple[int, ...], list[tuple[int, ...]]] = {}
            for source, _, target in edges:
                indegree[target] += 1
                outgoing.setdefault(source, []).append(target)
            todo = [state for state, degree in indegree.items() if degree == 0]
            visited = 0
            while todo:
                source = todo.pop()
                visited += 1
                for target in outgoing.get(source, ()):  # pragma: no branch
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        todo.append(target)
            if visited != len(states):
                raise AssertionError(("cyclic plant", bound, mechanism))

            for interface in INTERFACES:
                result = analyze_contract(bound, mechanism, interface)
                prediction = theorem_predictions(bound, mechanism, interface)
                if not result["contract_exact"]:
                    raise AssertionError(("contract audit mismatch", bound, mechanism, interface, result))
                actual = (result["universally_safe"], result["nonblocking"])
                if actual != prediction:
                    raise AssertionError(("contract prediction mismatch", bound, mechanism, interface, actual, prediction))
                counts["history_oracle_obligations"] += result["history_count"]
                counts["contract_prediction_obligations"] += 1
                contracts.append(result)

        if bound >= 1:
            # At the same bare receipt history, p=0 is quiescent and safe while
            # p=1 retains an invisible stale-fill hazard.  Therefore one symbol
            # cannot encode both readiness classes; two symbols (one bit) are
            # necessary.  ack:0 versus ack:+ is sufficient.
            clean = CountState(flag=1, invalidated=1, old_cache=0, pending=0, phase=0)
            hazard = CountState(flag=1, invalidated=1, old_cache=0, pending=1, phase=0)
            if not forced_grant_safe(clean, "raw") or forced_grant_safe(hazard, "raw"):
                raise AssertionError("receipt lower-bound states do not separate")
            if observation("ack", clean, "bare") != observation("ack", hazard, "bare"):
                raise AssertionError("bare receipt unexpectedly separates readiness")
            if observation("ack", clean, "zero_receipt") == observation("ack", hazard, "zero_receipt"):
                raise AssertionError("zero receipt does not separate readiness")
            counts["receipt_lower_bound_obligations"] += 1

    # The detailed K=1 executable plant in bridge.py must be a literal slice of
    # this generalized state space.  Compare every mechanism's reachable edge set.
    from bridge import oracle_edges as binary_oracle_edges  # local import avoids cycle
    for mechanism in MECHANISMS:
        generalized = oracle_edges(1, mechanism)
        encoded = set()
        for source, action, target in binary_oracle_edges(mechanism):
            def decode(code: int) -> tuple[int, int, int, int, int]:
                return ((code >> 5) & 1, (code >> 4) & 1, (code >> 3) & 1,
                        (code >> 2) & 1, code & 3)
            encoded.add((decode(source), action, decode(target)))
        if generalized != encoded:
            raise AssertionError(("K=1 refinement mismatch", mechanism))
        counts["edge_oracle_obligations"] += len(generalized)

    observation_isomorphism = audit_k1_observation_isomorphism()
    if not observation_isomorphism["exact"]:
        raise AssertionError(("K=1 observation isomorphism mismatch", observation_isomorphism))
    # Three distinct obligations per mechanism/interface: edge labels, complete
    # knowledge sets, and greatest-contract permission histories.
    counts["observation_isomorphism_obligations"] = 3 * int(observation_isomorphism["cases_checked"])

    wrong_label_map = audit_k1_observation_isomorphism(
        lambda label: "ack:1" if label == "ack:+" else label
    )
    if wrong_label_map["exact"] or not wrong_label_map["label_mismatches"]:
        raise AssertionError("wrong receipt-label map was not rejected")
    counts["observation_label_mutant_obligations"] = 1

    raw_bare = next(row for row in contracts
                    if row["bound"] == max_bound and row["mechanism"] == "raw"
                    and row["interface"] == "bare")
    shortest = raw_bare["blocking_witnesses"][0] if raw_bare["blocking_witnesses"] else None
    summary = {
        "maximum_pending_bound": max_bound,
        "bounds_checked": list(range(max_bound + 1)),
        "mechanisms": list(MECHANISMS),
        "interfaces": list(INTERFACES),
        "plants": plants,
        "contracts": contracts,
        "counts": counts,
        "counted_obligations": sum(counts.values()),
        "transition_oracle_mismatches": 0,
        "grant_kernel_mismatches": 0,
        "history_oracle_mismatches": 0,
        "contract_exactness_mismatches": 0,
        "prediction_mismatches": 0,
        "receipt_lower_bound_bits": 1,
        "k1_observation_isomorphism": observation_isomorphism,
        "wrong_label_mapping_rejected": True,
        "wrong_label_mapping_mismatch_counts": {
            "labels": wrong_label_map["label_mismatches"],
            "knowledge": wrong_label_map["knowledge_mismatches"],
            "permissions": wrong_label_map["permission_mismatches"],
        },
        "raw_bare_shortest_blocking_witness_at_max_bound": shortest,
        "scope": (
            "One producer, one consumer, one release/acquire episode, one data line, "
            "and an initial stale-response count in [0,K]. No transition creates new stale traffic."
        ),
        "counting_note": (
            "One obligation per reachable edge compared with the tuple oracle, eligible-state "
            "guard comparison, observable history compared by two constructions and audited for "
            "exact safe permission, closed-form contract prediction, K=1 edge refinement, and receipt "
            "lower-bound witness, three observation-isomorphism checks per K=1 mechanism/interface, "
            "and one deliberately wrong receipt-label map."
        ),
    }
    return summary
