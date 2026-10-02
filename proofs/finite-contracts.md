# Finite observation contracts: statements, proofs, and boundaries

These are handwritten mathematical arguments for explicitly stated finite models. The accompanying Python programs test finite instances; they are not a proof-assistant mechanization. The elementary quotient, hitting-set, rectangularity, and injectivity arguments are not claimed as new general theorems.

## Definitions

Fix one public program, including operation kinds, memory orders, thread topology, and addresses. Let U be its finite, background-admissible completed executions. Let S be the subset meeting the declared strengthened-RC11 fragment. An observation is a total function h: U -> O, where O = h(U) contains only feasible observations. A contract C is a subset of O. It is sound when every x in U with h(x) in C lies in S. Weakest means least restrictive, hence largest under inclusion. It is exact when x is in S if and only if h(x) is in C for every x in U.

These quantifiers are over all completions in this fixed U. They are not automatically quantifiers over the traces of a particular safe implementation. Neither prefixes, scheduling choices, uncontrollable actions nor progress conditions occur in this definition.

## T1. Most permissive sound classification and exactness

Let B = U \ S. Then C* = h(U) \ h(B) is the unique largest sound contract. An exact observable contract exists if and only if h(S) and h(B) are disjoint. Equivalently, no observation fiber contains both a good and a bad execution.

Proof. If h(x) is in C*, it is not the observation of any member of B, so x cannot be bad. Thus C* is sound. If C is sound and contains o in h(B), choose b in B with h(b)=o; then C accepts b, a contradiction. Hence C is contained in C*. For exactness, if h(S) and h(B) are disjoint, every good execution's observation belongs to C*, while soundness excludes every bad execution. Conversely, a good g and a bad b with the same observation force an exact classifier to both accept and reject that observation. This is impossible. The empty U case is vacuous. QED.

For the message-passing truth table with outcome (flag,data), S = {00,01,11}. Observing flag alone gives a mixed fiber {10,11}; C* accepts only flag=0. The safe execution 11 is necessarily rejected under universal-completion soundness. A system whose only outcome is 11 could still be safe: the theorem does not say otherwise.

An existential classifier h(S) accepts any fiber containing a good completion. It is an overapproximation useful for some analyses, but it is not a sound acceptance policy for all concrete executions.

## T2. Exact field selection

Suppose each execution is identified by r Boolean read-source fields. An observation mask M keeps a subset of these fields. For each good g and bad b define D(g,b) = {j : g_j differs from b_j}. Then M is exact if and only if M intersects every D(g,b).

Proof. Projection onto M equates g and b exactly when their fields agree at every position in M, which is equivalent to M intersect D(g,b) being empty. Apply T1 to every good/bad pair. QED.

Thus all inclusion-minimal exact masks are the inclusion-minimal hitting sets of this finite difference family. This characterization is a standard reduction, not a claimed new optimization algorithm. In the artifact, r<=4 permits complete enumeration of all masks rather than invoking a SAT/SMT solver.

## T3. A complete explanation for the retained nonconstant profiles

Let U={0,1}^r, r>=1, and S=U\{b} for one forbidden word b. Only the full mask is exact. For a mask of m observed positions, C* rejects precisely the fiber of b, containing 2^(r-m) words. It therefore rejects 2^(r-m)-1 safe words. There are 2^r-1 inexact masks, and each has a good/bad indistinguishable pair at Hamming distance one.

Proof. The full mask is injective. Every proper mask omits a position j; flip only b_j to obtain a distinct safe word g with the same observation. This proves inexactness and a distance-one witness. The fiber fixes m bits and leaves r-m arbitrary, so it has the stated cardinality. All other fibers contain only safe words. Distinct words have distance at least one, establishing the claimed minimum within U. QED.

Finite checking establishes the hypotheses of T3 for each of the 29 nonconstant retained profiles. It does not establish those hypotheses for arbitrary coherence programs. The other 241 profiles are all safe after background admission. Fifteen CoRR executions are removed by the background filter, so a full Boolean-cube assumption would be wrong for those profiles.

## T4. Independent predicates and rectangularity

Let X,Y be finite local observation alphabets, assume every pair in XxY is feasible, and let S be the safe relation. An exact conjunction A(x) and B(y) exists if and only if S is rectangular, namely S=projection_X(S) x projection_Y(S), with the usual empty-set convention.

Proof. Any conjunction accepts precisely A x B, which is a rectangle. A nonempty rectangle equals the product of its projections. Conversely, if S equals that product, its two projections define an exact conjunction. The empty relation is represented by an empty factor. QED.

For S={00,01,11}, the two maximal nonempty safe rectangles are {0}x{0,1} and {0,1}x{1}. A rectangle containing both 00 and 11 must also contain 10 and is unsound. Every nonempty safe rectangle is contained in one of the displayed rectangles: if its first factor contains 1 its second factor cannot contain 0; otherwise the first factor is {0}. These two maxima are incomparable, so there is no greatest nonempty sound factored contract under componentwise inclusion. This is a static two-predicate result, not a decentralized controller theorem. Restricted feasible pairs require a different statement.

## T5. Exact one-message dependency summaries

Fix k independently named writes. A sender knows an arbitrary required subset R of [k]. A receiver knows an arbitrary available subset T. The sender sends a deterministic message f(R), and a fixed receiver must decide R subset T from that message and T, correctly for all pairs. No other history, side information about R, extra rounds, implicit ordering assumptions or timing channel is available. Then f is injective. Consequently the message alphabet has at least 2^k elements and a fixed-length binary encoding needs at least k bits. Sending the characteristic vector meets the bound.

Proof. Suppose distinct R and R' have the same message. If R' is not a subset of R, set T=R. Then R subset T is true and R' subset T is false. Otherwise R' is a proper subset of R; choose T=R'. The two answers again differ. The receiver sees identical input (the shared message,T), a contradiction. There are 2^k required subsets, giving the alphabet and bit bounds. QED.

Taking only the largest required identifier and testing whether it is present is unsound: R={1,2}, T={2} is a counterexample. Requiring the entire prefix through that identifier is sound because it contains R, but is not exact: R={2}, T={2} is unnecessarily rejected. This argument is not a lower bound on a stateful coherence protocol. In particular, it is not a counterexample to MemGlue's seen identifiers, timestamps, sets and ordering invariants.

## T6. Conditional transfer to an operational system

Let T be the completed traces of an operational system, and let alpha:T->U be a total semantic map. Let the operationally available observation H satisfy H=h composed with alpha. If every trace t satisfies H(t) in C*, then alpha(T) is a subset of S.

Proof. For each t, alpha(t) is in U and its observation is in C*. Soundness in T1 implies alpha(t) is in S. QED.

This remains a conditional implication for an arbitrary operational system. The companion proof note, operational-bridge.md, now constructs a particular one-epoch plant, total completed-trace map, causal grant rule and nonblocking argument. Its grant observations are prefixes, not the completed observations in T6. That restricted construction does not establish an abstraction or simulation from a separately implemented cache hierarchy and does not discharge T6 for unspecified protocols.

## Semantic target and checker equivalence

Each retained location has one initial write of 0 and one noninitial write of 1. There are atomic reads and writes only, no fences, RMWs, nonatomics or release sequences with additional writes. A read-source bit chooses exactly one of these two writes. sb is strict within-thread order; rf is the chosen write-to-read relation; mo orders the initial write before the noninitial write; fr = inverse(rf);mo. sw contains rf edges from a release/SC write to an acquire/SC read. Initial writes happen before all noninitial events.

Define hb=(sb union sw union init-before)^+ and eco=(rf union mo union fr)^+. The target requires: no cycle in sb union rf; no pair (a,b) in hb whose inverse (b,a) is in eco; and no cycle in the SC-endpoint restriction of hb union mo union fr.

RC11 coherence is often written irreflexive(hb;eco?), with eco? reflexive. The omitted identity branch amounts to hb acyclicity. In this fragment a cycle of hb cannot enter an initial event, and sw is a subset of rf. Any noninitial hb cycle therefore induces a cycle of sb union rf, which the no-thin-air condition already forbids. Hence the implementation's reversed-pair test is equivalent to this coherence condition when combined with NTA. RMW atomicity is vacuous here.

The original no-fence RC11 comparison instead restricts to SC endpoints the relation sb union (sb_different-location;hb;sb_different-location) union hb_same-location union mo union fr. Its sb, sandwich and same-location hb terms are all subsets of hb. Therefore the strengthened target implies this original-RC11 specialization. The converse need not hold; the three retained mixed-SC controls expose the distinction.

For the control with writes Wx,Wy both SC, reads Rx_acq;Ry_SC on one reader and Ry_acq;Rx_SC on the other, the read word 1010 satisfies coherence and NTA. In the strengthened SC relation, the edges Wx hb Ry_SC fr Wy hb Rx_SC fr Wx form a cycle. In the original relation the non-SC acquire reads remove those cross-location hb links from the SC restriction. The remaining SC edges are acyclic. This is a known IRIW-acq-sc shape, not a newly discovered memory-model counterexample. Two single-acquire-to-SC promotions also separate the targets and are retained as development controls.

The finite background U requires NTA and no inverse-eco pair in sb. This is a declared local-looking semantic admission condition, not a proved cluster invariant. It changes the quantification domain and must not be silently inferred from hardware labels.
