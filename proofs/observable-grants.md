# Observable grant contracts for finite one-shot bridges

This file gives the complete mathematical argument used by the main paper.  It
is a handwritten proof, not a mechanized proof.  The executable studies check
finite instances and two separately structured constructions; they do not
prove the theorem for all finite plants.

## 1. One-shot plant

A **one-shot grant plant** is a tuple

\[
P=(Q,Q_0,E_u,E_g,G),
\]

where:

* `Q` is a finite set of states and `Q_0` is a nonempty set of initial states;
* `E_u` is the set of uncontrollable labeled edges;
* `E_g` is the set of controllable `grant` edges;
* every state has at most one outgoing grant edge;
* a grant edge occurs at most once on a path, and every edge after it is
  uncontrollable;
* states reachable without grant and states reachable after grant are disjoint;
* every reachable state in `G` is a post-grant terminal; and
* `G` is the set of good terminal states.

The reachable graph is acyclic.  Phase separation makes whether grant has
occurred a property of the state rather than of an unrecorded path prefix.  This assumption is appropriate to the bounded
single-epoch episode studied here; a cyclic protocol requires a fairness/game
formulation and is outside this theorem.

A pre-grant state is **eligible** when it has an outgoing grant edge.  For an
eligible state `q`, let `Post(q)` be all maximal suffixes beginning with its
forced grant edge.  Define the full-state good-completion kernel

\[
W=\{q\mid q\text{ is eligible and every suffix in }Post(q)
              \text{ terminates in }G\}.
\]

Thus membership in `W` includes both the declared refinement outcome and
post-grant completion.  In the bridge instance, a good terminal is a fresh
read; a stale read is bad, and there is no post-grant deadlock.

## 2. Partial observation

Let `Sigma` be the finite visible alphabet.  Each uncontrollable pre-grant edge
has either a symbol in `Sigma` or the hidden symbol `epsilon`.  For a visible
history `h`, the **knowledge set** `K(h)` contains exactly the pre-grant states
reachable from `Q_0` by an uncontrollable path whose visible projection is `h`.
Only histories with nonempty knowledge sets are considered.

An observation-based grant contract is a set `C` of histories.  Its
controlled graph retains every uncontrollable edge.  At a pair `(q,h)` with
`q in K(h)`, it additionally retains the outgoing grant edge exactly when
`h in C`.  Enabling grant does not preempt or suppress an uncontrollable action;
all interleavings in the retained graph remain possible.  The controller cannot
distinguish states within `K(h)`.

A contract is **correct** when, for every plant-reachable pre-grant pair
`(q,h)` with `q in K(h)`, membership `h in C` implies that grant is eligible at
`q` and every resulting maximal suffix terminates in `G`.  This is a statewise
interface contract: it quantifies over every physical state compatible with a
history, including pairs that a particular controller might avoid only by
taking an earlier grant.  A contract is **nonblocking** when every maximal path
of the controlled graph terminates in `G`.  Because the plant is finite and
acyclic, a pre-grant controlled path is maximal precisely when it reaches a
state with no uncontrollable successor and with grant disabled.

## 3. Greatest correct contract

Let `H={h | K(h) is nonempty}` be the reachable visible histories and define

\[
C^*=\{h\in H\mid K(h)\subseteq W\}.
\]

Contracts are subsets of `H`; adding unreachable words is therefore not a
spurious source of distinct “larger” contracts.

### Theorem 1 (exact observable grant contract)

`C*` is correct and is the unique greatest correct observation-based grant
contract under set inclusion.

**Proof.**  If `h in C*`, every possible current state is in `W`; grant is
eligible in each such state and every post-grant maximal suffix reaches `G`.
Hence `C*` is correct.

Let `C` be any correct observation-based contract and suppose `h in C`.  The
controller enables grant for every `q in K(h)`, since all those states share the
same visible history.  Correctness therefore requires every such `q` to be in
`W`, so `K(h) subseteq W` and `h in C*`.  Thus `C subseteq C*`.  Since `C*` is
itself correct, it is the unique greatest correct contract.  QED.

Calling this the **weakest condition** and the **greatest permission** describes
the same order: no correct contract can admit a history excluded by `C*`.

### Constructive finite synthesis

For an explicit acyclic plant, the theorem gives a direct algorithm rather than
only an existence result.

1. Remove unreachable states and topologically order the reachable graph.
2. Evaluate the post-grant DAG in reverse order.  A terminal is good exactly
   when it lies in `G`; a nonterminal post-grant state is good exactly when all
   of its uncontrollable successors are good.  An eligible pre-grant state lies
   in `W` exactly when the target of its grant edge is good.
3. Precompute hidden closure.  Starting from `cl(Q0)`, construct the reachable
   observer subsets with
   `Step(X,sigma)=cl(post_sigma(X))` for each visible symbol.
4. Mark an observer subset `X` grantable exactly when `X subseteq W`.
5. The exact nonblocking test scans every reachable observer subset `X` and
   every `q in X` with no uncontrollable successor.  It succeeds exactly when
   every such `X` is grantable.

Let `n` be the reachable pre-grant state count and `m` all reachable
pre-grant uncontrollable edges, hidden and visible.  Let `n_post,m_post` be the
post-grant state/edge counts, `g` the grant-edge count, `s=|Sigma|`, `N` the
number of reachable observer beliefs (`N <= 2^n`), `R <= N*s` the number of
stored observer edges, and `V <= N*n` the number of returned quiescent-violation
pairs.  The delivered implementation scans the global alphabet at each belief,
interns each belief once, materializes both returned lists, and sorts them
deterministically.  With `B=n+n_post+m+m_post+g+s*log(s+1)`, conservative bounds
for this implementation are

`O(B + N*s*(n+m) + (R+V)*n*log(N*s+n+1))` time and
`O(B + N*n + R + V) = O(B + N*n + R)` space.

The `B` term includes initial hidden closure and pre-grant processing even when
`s=0`.  Belief residency is charged once through canonical interning; observer
edges reference resident beliefs, while the explicit violation list contributes
`V`.  Sorting either output may compare belief keys of size at most `n`.  A
streaming interface could avoid these returned lists, but that is not the
delivered Python behavior.  A hidden-only two-state plant and a two-state/
32-label family exercise the `s=0` and large-alphabet edge/storage corners.  The
exponential worst case remains the usual subset-observer cost.
`src/contracts.py` rejects cyclic, phase-overlapping, pre-grant-good, or
multi-grant inputs.

### Exhaustive tiny-plant meta-oracle

`src/metaoracle.py` attacks the implementation with a differently structured
brute-force oracle.  It enumerates a declared universe of 486 acyclic generic
plants with two pre-grant and two post-grant states, all 1,188 contracts over
their reachable histories, and every maximal controlled path.  Direct path
semantics compares the synthesized kernel, observer, greatest contract, and
nonblocking decision.  Separately, each of the 75 canonical receipt partitions
through bound four is used to construct an actual raw-timing plant whose ack
edges are labelled by that partition; direct history/path analysis and the
generic observer agree without calling the closed-form receipt helper.  The
meta-oracle also records the finite L1--L4 eligibility counterexample and the
`s=0`/32-label complexity sanity families.  Existential-fiber and
ignored-eligibility mutants are rejected on 64 and 180 generic plants.  These
checks are finite corroboration, not a proof of the arbitrary finite theorem.

## 4. Exact feasibility of safety plus completion

For a pre-grant state `q`, write `Env(q)` for its uncontrollable successors.
A reachable pair `(q,h)` is **environment-quiescent** when `q in K(h)` and
`Env(q)` is empty.

### Theorem 2 (necessary and sufficient nonblocking criterion)

A correct nonblocking observation-based contract exists if and only if

\[
\forall (q,h)\text{ reachable and environment-quiescent},\quad K(h)\subseteq W.
\tag{NB}
\]

When (NB) holds, `C*` is the greatest correct nonblocking contract.  When (NB)
fails, no correct observation-based contract is nonblocking.

**Proof.**  Assume (NB).  Consider a maximal path under `C*`.  If it has already
granted, Theorem 1 and the definition of `W` make it terminate in `G`.  If it
has not granted, acyclicity prevents an infinite uncontrollable continuation.
Its last pre-grant pair `(q,h)` is therefore environment-quiescent.  By (NB),
`h in C*`, so grant is enabled, contradicting maximality.  Hence every maximal
path grants and terminates in `G`; `C*` is nonblocking.

Conversely, suppose (NB) fails at `(q,h)`.  Then `K(h)` is not a subset of `W`.
By Theorem 1 every correct contract is a subset of `C*`, so every correct
contract disables grant at `h`.  The actual state `q` has no uncontrollable
successor.  The controlled path to `(q,h)` is therefore maximal and does not
reach `G`.  Every correct contract blocks on that branch.  QED.

This theorem separates two repair directions.  A mechanism change can enlarge
`W` (for example, persistent generation filtering), while an interface change
can refine `K(h)` (for example, a pending-zero receipt).  Either may turn (NB)
from false to true.

## 5. Bounded stale-fill bridge instance

Fix a bound `K >= 0`.  An initial state contains an old resident cache line and
an unknown number `p in {0,...,K}` of stale responses created before the fixed
producer data/release prefix.  No transition creates new stale traffic.  The
state is

\[
q=(f,a,c,p,t),
\]

where `f` records flag delivery, `a` records invalidation acknowledgment, `c`
records an old resident value, `p` counts old responses still pending, and `t` is the pre-grant/post-grant/terminal
phase.  A hidden fill decreases `p` and normally sets `c=1`; an acknowledgment
sets `a=1,c=0`; grant changes the phase; and the final demand read returns zero
iff `c=1`.  A miss returns the producer's fresh value one.

The five local mechanisms are:

1. **raw**: fills always install; a repair acknowledgment is available whenever
   old data is resident;
2. **drain**: acknowledgment is disabled until `p=0`;
3. **generation**: acknowledgment atomically enables a persistent rule that
   discards every remaining stale fill;
4. **late generation**: the discard rule starts only at grant; and
5. **no repair**: only the first acknowledgment can occur.

### Lemma 3 (full-state kernel)

At a reachable grant-eligible state, forced grant good-completes exactly when

\[
\neg c\ \land\
\bigl(p=0\ \lor\ (m=\mathsf{generation}\land a)\ \lor\
                m=\mathsf{late\mbox{-}generation}\bigr).
\tag{1}
\]

**Proof.**  Resident old data (`c=1`) can be read immediately after grant, so
`not c` is necessary.  If `p>0` and neither persistent nor grant-time filtering
is active, a stale fill can install old data before the read, so the
parenthesized condition is necessary.  Conversely, if `c=0` and `p=0`, no old
value can reappear.  If persistent generation filtering is already active, or
late-generation filtering activates with the forced grant, every remaining
stale fill is discarded.  The uncontrollable read then returns one.  QED.

The primary transition builder and a separately structured tuple oracle agree
on every reachable edge for `K=0,...,4`; a suffix search agrees with (1) on
every eligible state.  Those are finite checks of this instance, not the proof
above.

## 6. Receipt theorems

A **bare** interface exposes `flag` and `ack` but hides fills.  More generally,
let a deterministic raw receipt map

\[
\rho:\{0,\ldots,K\}\to O
\]

emit `ack:rho(p)` atomically after the acknowledgment has cleared the line,
where `p` is the number of old responses still pending at that instant.  Grant
is a later action, so a hidden fill may intervene.  The zero receipt is the
special case with one symbol for `p=0` and one for every `p>0`.

### Theorem 4 (exact raw receipt partition)

For `K=0`, every receipt map admits a correct nonblocking contract.  For every
`K>=1`, raw timing with grant as the only controllable action admits a correct
nonblocking observation-based contract if and only if

\[
\rho(0)\notin \rho(\{1,\ldots,K\}).
\tag{2}
\]

Thus the zero-pending state must form its own receipt class; positive counts may
be partitioned arbitrarily.

**Proof (necessity).**  Suppose `rho(p)=rho(0)` for some positive `p`.  Compare
the zero-count and `p`-count initial branches.  Execute one acknowledgment and
deliver the flag in the same visible order.  The zero branch reaches

\[
q_0=(1,1,0,0,0),
\]

which is environment-quiescent and lies in `W`.  The positive branch reaches

\[
q_p=(1,1,0,p,0),
\]

with the same receipt symbol.  It is outside `W`: after grant, one of the
pending responses may install old data before the read.  Hence the shared
knowledge set is not contained in `W` while containing quiescent `q_0`.
Criterion (NB) fails, so no correct contract is nonblocking.

**Proof (sufficiency).**  Grant after the flag and the most recent receipt whose
symbol is `rho(0)`.  By (2), that atomic receipt certifies `p=0`; the same step
clears `c`, so the full-state kernel condition holds and remains stable.  On any
branch not yet producing `rho(0)`, either the flag is still enabled, a pending
fill is enabled, or a useful acknowledgment/repair is enabled after an installing
fill.  Every fill strictly decreases `p`, and raw repair clears the line.
Consequently every maximal finite branch eventually emits `rho(0)`, receives
the flag, grants, and reads one.  The episode is acyclic, so no other infinite
avoidance is possible.  QED.

### Corollary 5 (tight one-bit interface)

For every `K>=1`, at least two receipt symbols are necessary, and the bit
`[p=0]` is sufficient.  This is a lower bound on the declared receipt partition,
not on all metadata or messages of an arbitrary stateful protocol.

A bare receipt is the constant map and violates (2), which recovers the raw
impossibility theorem for every positive bound.  The greatest correct bare
history may wait for `K+1` acknowledgments, but branches starting with fewer
than `K` responses become quiescent before that history and therefore block.

### Corollary 6 (mechanism/interface alternatives)

For every finite `K`:

* drain plus a bare receipt is correct and nonblocking because the receipt is
  withheld until `p=0`;
* generation plus a bare receipt is correct and nonblocking because the receipt
  activates persistent rejection and thereby enlarges `W`;
* late generation has the same receipt-partition requirement as raw timing,
  because it cannot remove an old value installed between receipt and grant;
* no-repair remains blocking for positive initial counts even with an exact
  zero receipt, because information cannot create the missing recovery edge.

These statements follow from (1), the knowledge sets, and criterion (NB).  The
executable study checks the five named mechanisms and two representative
interfaces for `K=0,...,4`; the arbitrary receipt-map statement above is proved
symbolically rather than inferred from those two interfaces.

### Useful-action envelope

Fix an initial pending count `r`.  Every maximal completing path contains one
flag, one grant, and one read.  Raw plus a zero receipt and drain plus a bare
receipt must consume all `r` responses before their grant-enabling receipt.
Drain has one acknowledgment and therefore `r+4` useful actions.  Raw has
between one and `r+1` acknowledgments, giving between `r+4` and `2r+4` useful
actions; delaying the first acknowledgment gives the lower extreme, while
acknowledging first and repairing after every installing fill gives the upper.

Generation plus a bare receipt has one acknowledgment but need not deliver all
old responses before the terminal read.  Once the receipt has activated
persistent rejection, the read may occur after any delivered prefix
`d in {0,...,r}`; its useful-action total is therefore `d+4`, with range
`4,...,r+4`.  This distinction is important: undelivered responses are safe
because they are ineffective, not because they have been consumed.  The
regression suite checks both `d=0` and `d=1` in the detailed `K=1` model.

## 7. Product of independent lines

Consider a synchronous joint grant into the asynchronous product of finitely
many finite acyclic line plants.  Assume each post-grant step changes only one
component, neither changes another component's state nor disables its steps,
every maximal component suffix is finite, and a joint terminal is good exactly
when all component terminals are fresh.  Then the full-state kernel is the
cartesian product of the per-line kernels.  If every component lies in its
kernel, every finite interleaving projects to good maximal component suffixes.
If one component lies outside its kernel, choose a bad maximal component
suffix and complete the other independent finite components around it; the
result is a maximal joint suffix with a bad terminal.  Equivalently, the grant
predicate is the conjunction of the per-line guards.  Theorem 1 still applies
to the product knowledge set;
it does not license replacing correlated knowledge by independent marginal
predicates.  A single aggregate readiness bit can be sufficient only when its
atomic semantics certifies that every required line is in its kernel.  The
separate finite-contract proof explains why arbitrary dependency subsets need
more information than a largest-identifier or prefix summary.

## 8. Conditional lifting to a concrete bridge

The plant theorem becomes a protocol theorem only after a concrete-to-abstract
simulation is discharged.  Let `B` be a concrete one-epoch bridge with the same
visible alphabet and one controllable grant.  For abstract states `q,q'`, write
`q ==sigma=> q'` for an uncontrollable abstract path whose visible projection is
`sigma` (either one symbol or the empty word).  Let `alpha` map reachable
concrete states to `Q`, and let `r` be a natural-valued rank on concrete
pre-grant states.  The required obligations are:

1. **Initiality.** Every concrete initial state maps into `Q0`.
2. **Observation-preserving weak simulation.**  Every concrete uncontrollable
   pre-grant step `s -ell-> s'` is matched by
   `alpha(s) ==proj(ell)=> alpha(s')`.  If the matching abstract path is empty,
   then `r(s') < r(s)`.  Thus an infinite concrete path cannot be hidden as
   infinite zero-step stutter.
3. **Grant preservation.**  Every concrete grant step maps to the unique
   abstract grant edge from the current image.
4. **Maximal post-grant refinement.**  Every maximal concrete suffix after
   grant is finite, maps to a maximal abstract post-grant suffix, and an
   abstract terminal in `G` implies the declared concrete refinement outcome.
   A concrete post-grant dead end or divergence may not be erased.
5. **Quiescence reflection.**  If a reachable concrete pre-grant state has no
   uncontrollable successor, its abstract image has none.
6. **Grant reflection.**  If the abstract image has its grant edge and the
   contract enables it, the corresponding concrete grant is enabled and maps
   to that edge.

### Small counterexample: obligations 1--4 do not imply eligibility

Take the abstract plant `q --grant--> g`, with `g` good.  Take the concrete
plant `s0 --hidden--> s1 --grant--> gB`, with `gB` good,
`alpha(s0)=alpha(s1)=q`, `alpha(gB)=g`, and rank `r(s0)=1`, `r(s1)=0`.
Initiality, weak simulation, grant preservation, and maximal post-grant
refinement all hold.  Nevertheless the concrete epsilon-history knowledge set
is `{s0,s1}` and `s0` has no concrete grant.  Thus obligations 1--4 prove good
completion only for concrete grants that actually occur; they do not establish
the eligibility clause of the statewise correctness definition.
`src/lifting_counterexample.py` checks this finite witness independently.

### Theorem 7 (conditional refinement rule)

Under obligations 1--4, every concrete grant that actually occurs at a
`C*`-admitted history has a finite good completion.  Under obligations 1--4
and 6, the induced concrete observation contract is correct.  If obligation 5,
criterion (NB), and the same obligation 6 also hold, it is nonblocking.

**Proof.**  Obligations 1--2 and induction over a concrete pre-grant prefix put
its image in the abstract knowledge set for the same visible history.  If `C*`
admits the history, every possible image lies in `W`.  For any concrete grant
that actually occurs, obligations 3--4 transfer every concrete maximal
post-grant suffix to a finite good abstract suffix and then to the declared
concrete outcome.  This is actual-grant safety.

For full correctness, fix any concrete state compatible with an admitted
history.  Its abstract image is grantable in `W`; obligation 6 supplies the
matching concrete grant, and the preceding actual-grant argument supplies its
good completion.

For nonblocking, consider an infinite concrete pre-grant path.  Every nonempty
matching abstract segment advances in the finite acyclic abstract plant, so
only finitely many such segments can occur.  All later concrete steps would
match empty abstract paths, but obligation 2 would make the natural rank
strictly decrease forever, a contradiction.  Therefore a maximal concrete
pre-grant path is finite.  At its last state, obligation 5 gives an abstract
environment-quiescent state at the same history.  Criterion (NB) admits that
history, and obligation 6 enables a concrete grant, contradicting maximality.
QED.

### Proposition 8 (owned `K=1` encoding isomorphism)

For each of the five local mechanisms and either receipt interface, the detailed
Boolean model in `src/bridge.py` is label-preserving isomorphic to the `K=1`
slice of `src/parametric_bridge.py` under

\[
\beta(f,a,c,p,t)=(f,a,c,p,t).
\]

The map is a bijection on reachable states.  Both encodings now emit the shared
receipt alphabet `ack:0`,`ack:+`.  Equivalently, for the earlier detailed
spelling define `lambda(ack:1)=ack:+` and let `lambda` be identity on all other
labels.  Under this map the isomorphism preserves and reflects every
uncontrollable edge, grant edge, complete visible history, knowledge set,
greatest-contract permission, good terminal, and quiescent state.  Hence all
six obligations hold with no stutter.

**Proof.**  The initial sets are the two tuples with `p=0` and `p=1`.  A case
split over flag, fill, acknowledgment, grant, and read shows identical guards
and field updates in both encodings for each mechanism.  Receipt labels are
determined by the target `p` under the shared alphabet (or by `lambda` under
the legacy spelling).  The artifact compares all visible pre-grant labels, the
complete history-to-knowledge maps, and the admitted-history sets for five
mechanisms and two interfaces.  A deliberately wrong map from `ack:+` to
`ack:1` is rejected.  The same edge correspondence preserves terminal phase,
grant availability, and quiescence.  QED.

This proposition closes the lifting rule for two owned encodings and supports
the MP trace map.  It is not a simulation from CXL, MemGlue, C3, vCXLGen,
ShimGen, Synapse, or a commercial hierarchy.

## 9. Scope and failure conditions

The proofs require the declared initial uncertainty, no creation of new stale
traffic, a single irreversible grant, finite acyclicity, uncontrollable delivery
and read, atomic receipt sampling, and the specified repair/filter semantics.
They do not establish a simulation from a particular industrial coherence
protocol, a cyclic liveness theorem, timing performance, or universal C11
coherence.  A change to any premise requires a new kernel, knowledge analysis,
and, for concrete use, a new discharge of the simulation obligations above.
