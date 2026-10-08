# One-epoch operational bridge: model and complete manual arguments

This note is self-contained with the companion `finite-contracts.md` for the declared memory-model definitions. The arguments are manual mathematical proofs, not proof-assistant mechanization. The executable checks cover only the finite objects explicitly identified below. The observation and control constructions are not claimed as new general verification theory.

## Model, ownership, and initialization

One producer commits `Wx(1); Wy_release(1)`. One consumer is to execute `Ry_acquire(1); Rx(d)`. The dynamic plant begins after the two producer writes. A demand data miss after an acquire grant is guaranteed to obtain the producer's committed value one. This is an explicit local producer guarantee, not a derived directory-protocol invariant.

Initialization first creates x=y=0 and a consumer copy of old x. It optionally issues one background request that samples x=0 before the producer writes. The synthetic local grammar permits this redundant request even while an old line is resident. The response can be outstanding at the dynamic start. This setup is not asserted to be admitted by all real cache miss-status structures. The background request is not an architectural read in the MP program. No new old requests, writes or release epochs occur after initialization.

A state is `q=(f,a,c,p,t)`. The four bits mean new flag arrived, a receipt has occurred, old data resident, and one old background response pending. Phase t is 0 waiting, 1 granted, 2 completed with zero, or 3 completed with one. The two initial states are `(0,0,1,0,0)` and `(0,0,1,1,0)`. The integer encoding is `32*f + 16*a + 8*c + 4*p + t`. The ambient space has 64 states, not 64 reachable states. There are no transitions after completion.

Before completion the raw plant has these labeled transitions. Unmentioned fields are unchanged.

| Action | Enabled when | Update | Ownership |
|---|---|---|---|
| flag | f=0 | f=1 | Uncontrollable |
| fill | p=1 | p=0, c=1 | Uncontrollable; hidden |
| ack | a=0 or c=1 | a=1, c=0 | Uncontrollable |
| grant | f=1 and t=0 | t=1 | Sole controllable action |
| read0 | t=1 and c=1 | t=2 | Uncontrollable |
| read1 | t=1 and c=0 | t=3 | Uncontrollable |

Invalidation and receipt production are atomic. There is no separately modeled acknowledgment transport queue. A late fill can restore c=1 after an ack; this re-enables a repair ack. At most one fill means at most two acks. Trace termination is architectural program completion, not network draining.

The **drain** plant changes only ack's guard: it additionally requires p=0. It does not cancel the fill; delivery occurs first and the later ack clears its result. The **generation** plant changes fill: if a=1, delivery clears p without changing c; otherwise it sets c=1 as raw delivery does. Its old-response rejection latch is activated atomically with invalidation and remains active throughout the episode. This is a one-epoch abstract filter, not a claim about tag reuse, wraparound or a hardware tag encoding.

Two finite diagnostic mutations are supplied. **Late generation** drops a pending fill only when it arrives after grant, so a fill between ack and grant can still restore old data. **No repair** disables every ack after the first, even when a late fill has restored c=1. These mutations are not attributed to an external implementation.

The bare interface emits flag and ack and hides fill. The pending-bit interface emits flag and `ack:p`, with p sampled in the target of the atomic invalidation transition. A controller is a deterministic function of its visible history that enables or disables grant. It cannot force grant before another enabled action, stall the final read, issue another flush, poll for quiescence, or observe elapsed time. Optional idle steps reveal no additional information. Full-state and cache-only policies are privileged diagnostic baselines, not realizations of the bare interface.

## O1. Total completed-trace map and exact semantic decision

For every completed dynamic trace tau, define alpha(tau) by retaining the producer prefix, the acquire represented by grant, and the terminal data read. Erase all background requests, fills and invalidations. The flag read takes its source from the release write. The data read takes its source from initialization at t=2, and from Wx(1) at t=3. Program order is the fixed producer and consumer order; modification order places each initial write before its unique later write.

**Claim.** Alpha is a total function on completed traces, with image contained in MP outcomes 10 and 11. Both satisfy the declared semantic background. Alpha(tau) meets the strengthened read/write target exactly when tau ends with read1.

**Proof.** Every completed trace has exactly one grant and one terminal demand read; completion cannot occur without grant. The release source is fixed by the new-flag condition. The terminal phase uniquely selects the data source. Thus the mapping is defined uniquely for every completed trace. There is no cycle in program order union reads-from in either outcome. The two operations of each thread access different locations, so neither produces the background's same-thread reversed extended-coherence pair. In 10, the data write happens before the acquire through the preceding release, and hence before the final read; from-read returns from that old read to the data write. This violates coherence. In 11, initialization followed by producer writes, acquire and final read topologically orders all relevant edges. No coherence reversal or thin-air cycle exists. There are no SC operations, so the SC obligation is vacuous. QED.

Blocked prefixes have no terminal demand result and are not in alpha's domain. Assigning them a fabricated value would confuse nonblocking with safety. The map is a semantics of this owned plant, not a simulation from independently implemented hardware.

## O2. Exact full-state grant safety

For a reachable state with f=1 and t=0 in primary mechanism m, write

`G_m(q) = (c=0) and ((p=0) or (m=generation and a=1))`.

**Claim.** Every completed continuation after an immediate grant maps to a permitted execution if and only if G_m(q). Therefore the unique largest universally safe full-state grant rule admits precisely the eligible states satisfying G_m.

**Proof, sufficiency.** When c=p=0, no remaining action can create old resident data. Flag has no data effect and ack only clears data. If instead c=0, p=1, m=generation and a=1, the sole pending old response cannot install old data. Delivery removes the response and leaves c=0. In either situation c remains zero through the final read. O1 gives semantic safety.

**Proof, necessity.** If c=1, the scheduler may grant and immediately choose read0, before any invalidation. If c=0 but a pending fill remains effective, the scheduler may grant, fill, and read0, postponing invalidation. Both are finite legal schedules ending in a forbidden execution. Weak fairness cannot rule out an already completed finite violation. Thus any grant outside G_m admits a bad completion. All safe full-state rules are contained in G_m; sufficiency proves that G_m itself is safe. QED.

Eligibility is separate from safety; no claim is made about granting before the new flag arrives. The theorem is about the primary plants. The mutation predicates have finite suffix checks in the artifact but are not silently added to this theorem. A controller with power to stall the read or cancel old responses solves a different control problem.

## O3. Exact causal receipt realizations

**Claim.** On reachable waiting states, the following event-history rules are equivalent to the corresponding full-state eligible guard: raw waits for flag and an ack sampled with p=0; drain waits for flag and any ack; generation waits for flag and any ack.

**Proof.** A raw ack reporting p=0 establishes c=p=0 permanently, hence suffices. Conversely, suppose a reachable raw state has c=p=0. Since c initially equals one, some ack cleared it. If the last ack before this state had reported p=1, the fill responsible for changing p to zero would subsequently have set c=1. A further clearing ack would be required, contradicting that choice of last ack. Thus the history contains an ack reporting zero. In drain, every ack already requires p=0, so the same equivalence applies. In generation, the first ack clears c and makes all remaining old delivery ineffectual; conversely c cannot become zero without an ack. Persistent observed flag arrival supplies eligibility in all cases. QED.

The raw pending bit reports a modeled local response slot, not a prediction that a future request will never be created. The latter is excluded explicitly by initialization. The same bare ack name has different meanings in different plants; moving an invariant from message metadata to local protocol state does not eliminate that invariant.

## O4. Safety and completion under delivery and repair

**Claim.** The three observable policies in O3 have no reachable nonterminal sink. Every maximal nonstuttering run ends with read1. With idle steps, eventual completion holds under weak fairness for each continuously enabled flag, fill, ack, grant and read action.

**Proof.** In raw, p either starts zero or its single delivery eventually makes it zero. Clearing after the last fill establishes c=p=0 and emits a zero-pending receipt. If an ack preceded that fill, the repair guard c=1 enables this clearing. In drain, a pending fill must deliver before ack; after that ack the stable condition holds. In generation, the first ack establishes stability even if the physical response remains pending. Flag arrival eventually occurs in all three plants. Once stability and flag hold, grant is continuously enabled. After grant, a read is enabled and O2 makes its result one.

For the finite nonstuttering interpretation, flag, fill, grant and read each occur at most once, and ack at most twice. No path has more than six dynamic actions. Before stabilization a waiting state has a useful flag, fill or ack transition; after stabilization and flag it has grant. A granted state has a read transition. Thus there is no nonterminal sink and no infinite useful-action run. Adding idle steps requires weak fairness to prevent an enabled useful action from being postponed forever. QED.

This is eventual abstract program completion, not a real-time, cycle or packet bound. Missing raw repair can leave a pending-bit controller safe but stuck after a late fill. The retained no-repair mutation demonstrates that difference.

## O5. Bare-raw safety and nonblocking are incompatible

**Claim.** No deterministic controller observing only bare raw receipts and flag, with grant as its only controllable action, is both universally safe and nonblocking from both initial states. Any amount of history memory leaves this conclusion unchanged.

**Proof.** From initial p=0, execute flag, ack. This reaches q_good=(1,1,0,0,0), encoded 48. From initial p=1, the same two actions reach q_hazard=(1,1,0,1,0), encoded 52. Both produce the visible history (flag,ack). These environment actions cannot be disabled by the controller; an enabled grant need not preempt ack. In q_hazard, enabling grant permits grant,fill,read0 and therefore violates universal safety. The controller must disable grant after that visible history. It must make the same decision in q_good, where flag has arrived, no old fill is pending, and no dirty resident copy permits repair. Grant is the sole plant action. Disabling it makes q_good a nonterminal sink. Thus safety implies a nonblocking violation. Memory of identical histories cannot separate the states; fairness neither creates an absent action nor enables a disabled grant. QED.

This is a statement about an entire specified controller class, not merely a failed tested policy. It relies on the redundant old-request initialization, hidden fills, raw ack meaning and grant-only control. A different initial-state restriction, explicit quiescence notification, additional control or local response invariant invalidates a premise.

## O6. Bare-history boundary, one receipt bit, and prefix minimality

**Claim.** The largest safe bare-raw history grant rule requires an observed flag and at least two receipts. It is blocking. With raw timing unchanged, one pending bit per receipt is sufficient for safe nonblocking operation, while zero extra receipt bits are insufficient in the fixed interface model.

**Proof.** Before any receipt, an old resident copy is possible. After exactly one receipt, an observation-equivalent prefix may still have p=1, irrespective of whether flag occurred before or after that receipt. Hidden delivery may instead already have restored c=1. Hence granting after zero or one receipt is not universally safe. Two receipts require the sole old fill to have arrived between them: after the first receipt c=0,a=1, and only fill can enable another receipt. The second clears c with p=0 permanently. Thus two receipts and flag suffice and give every safe bare-history grant. O5 proves this rule cannot be nonblocking. O3 and O4 give a one-bit realization with raw timing unchanged, proving the stated zero-versus-one separation. QED.

Drain and generation use bare receipts but change plant semantics; they do not contradict the fixed-raw-timing lower bound. Generation still needs persistent local state and old-response classification. This result is unrelated to the arbitrary-subset one-message bit bound in the companion finite note.

For the paired certificate metric, minimize the maximum length of the two dynamic prefixes after the fixed producer writes. Any grant-eligible safe state requires both flag and an invalidation because c starts one and only ack clears it. These are distinct actions, so length at least two is necessary. O5 exhibits two length-two prefixes, proving minimality. Setup request count, total program size and hardware transaction length are not minimized.

## O7. Exact knowledge under hidden fills

Remove grant edges and restrict to waiting states. Let cl(X) be all states reachable from X by zero or more hidden fill transitions. For visible symbol sigma, post_sigma(X) contains the targets of environment transitions from members of X that emit sigma. In the pending-bit interface, an ack's class is sampled in its target and emitted in the shared alphabet `ack:0` or `ack:+`. Define K(epsilon)=cl(Q0), and K(o sigma)=cl(post_sigma(K(o))). Empty sets represent infeasible histories.

**Claim.** K(o) is exactly the set of endpoints of environment-only prefixes whose visible history is o. A history at which all its states are grant eligible is safe for grant exactly when every member satisfies the full-state guard.

**Proof.** The empty visible history consists only of zero or more hidden transitions, giving the base case. A prefix with visible history o sigma splits into a prefix with visible history o, one sigma-emitting transition, and zero or more hidden transitions. By induction its endpoint lies in the recurrence. Conversely, every state in that recurrence has exactly such a concatenated witnessing prefix, using the induction hypothesis for its predecessor. This proves equality in both directions. For grant, each member's witness is a possible environment prefix because those actions are uncontrollable. An unsafe member has O2's bad suffix, while universal full-state safety supplies O2 for every possible member. Flag is visible and persistent, so eligibility is constant within any feasible pre-grant history. QED.

The final closure matters. For raw history (flag,ack), the knowledge set contains not only states 48 and 52, but state 56=(1,1,1,0,0) reached when a hidden fill follows ack. A check of the cache only at receipt time omits this possible endpoint. In drain there is no remaining old fill; in generation a hidden fill cannot reinstall it; after raw ack:0 the same stability holds. No conclusion about controller-state minimality follows from this recurrence. Nonblocking still needs O4 or may fail as in O5.

## O8. Independent finite data lines in one release episode

Let R be a finite set of distinct data lines. A single producer writes one new value to each before one release; the consumer reads every line after the matching acquire. Each line has the producer freshness guarantee and a primary consumer mechanism above. Per-line states and responses are independent, with no later old-request creation or shared queue constraints.

**Claim.** Granting after the flag is universally safe for all these data reads iff the conjunction over j in R of G_mj(q_j) holds. Per-line receipt realizations preserve eventual completion under the same finite-delivery and repair assumptions.

**Proof.** If all conjuncts hold, O2's stability invariant applies to each line and no transition of another line can recreate an old value there. Thus every read is new. If a conjunct fails, choose that line. Earlier reads either already return old, proving failure, or may finish while postponing clearing of the selected line. At that line, a resident old value can be read directly or an effective old response delivered just before the read. This is a finite legal violation. For progress, each of finitely many independent components eventually stabilizes as in O4; the conjunction and flag then remain true and grant and all finite reads eventually occur.

Semantically each data write happens before its corresponding post-acquire read. An old read creates the same hb/fr reversal as MP. When all reads are new, initialization, producer writes, release, acquire and consumer reads form a topological order of the relevant edges. No SC event occurs. QED.

This is an ordinary independent-product proof. It does not cover shared queues, concurrent writers, recurrent releases or cross-line responses. The executable artifact enumerates only the single-line plants; there is no multi-line product experiment or mechanical general proof.

## Finite evidence and its limits

The retained primary and mutation plants have, respectively, 20/30, 12/15, 16/24, 20/30 and 20/27 reachable states/edges. Dataclass successor construction and an integer/bit-operation edge oracle agree on all 126 edge entries. Twenty-two eligible-state suffix checks agree with the implemented guards. Ten mechanism/controller cases retain 140 maximal paths, including 132 completed paths and eight blocked paths. Both event-graph implementations agree on every completed path's semantic map. For all five mechanisms and both interfaces, visible pre-grant labels, complete history-to-knowledge maps, and greatest-contract permissions agree between the detailed and count encodings; a wrong `ack:+`/`ack:1` map is rejected. The oracles share specification and authorship and are not independent external verification.

All exact inputs and per-path/per-state outputs are in the standalone repository. The package contains 83 deterministic tests and eleven stable scientific outputs. Its complete Ubuntu 24.04 replay regenerated 18,486 counted obligations, including 1,188 correctness checks and 672 executed nonblocking checks. The separate `verify.py` command compares parsed outputs and local ledger structure; it does not rerun the scientific analyses or validate upstream sources. Unit tests, replay and manuscript builds are separate checks. The finite event-graph evidence does not measure workload frequency, hardware performance or industrial-protocol behavior.

## Attribution and related-work boundary

The declared memory target is based on Lahav et al., *Repairing Sequential Consistency in C/C++11* (2017), DOI 10.1145/3062341.3062352, and Cleaveland and Trippel's strengthened target in *Memory Consistency Model-Aware Cache Coherence for Heterogeneous Hardware* (2024), DOI 10.34727/2024/isbn.978-3-85448-065-5_22. The owned transition grammar and proofs above are not their implementations.

The observation limitation is an instance of established partial-observation control; Goorden and Reniers (2024), DOI 10.1016/j.ifacol.2024.07.020, is relevant context. Broader heterogeneous composition and concrete bridge assurance already appear in the PLDI 2026 foundation (10.1145/3808350), C3 (10.1109/HPCA68181.2026.11408469), vCXLGen (10.1145/3779212.3790245), and the August 2026 ShimGen preprint (arXiv:2608.05965v1). No source code from those projects was integrated or run. This note does not establish priority over those works, refute their protocols or replace their evidence. The external-resource ledger records actual reading scope rather than claiming complete full-paper calibration.
