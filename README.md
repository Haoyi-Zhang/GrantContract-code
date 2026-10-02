# Weakest Observable Grant Contracts — artifact

This repository is the executable companion to **Weakest Observable Grant Contracts for Bounded Coherence Bridges**. It contains an owned finite model, a generic observer synthesizer for the declared one-shot plant class, two bridge encodings, retained deterministic outputs, proof notes, tests, and source/claim ledgers.

## Result and scope

For a finite acyclic plant with one irreversible controllable `grant`, let `W` be the states from which forced grant universally terminates in a declared good state, and let `K(h)` be the physical states compatible with visible history `h`. The unique greatest correct observation-based contract is

```text
C* = { reachable h | K(h) is a subset of W }.
```

A correct nonblocking contract exists exactly when every reachable environment-quiescent pair `(q,h)` has `K(h) subset W`. `src/contracts.py` implements the finite constructive algorithm: reverse-DAG kernel computation, hidden-closure observer construction, greatest permission, and the exact quiescence test. It rejects cyclic inputs, phase overlap, pre-grant or nonterminal good states, and a second grant rather than applying an inapplicable theorem.

The bounded bridge fixes one producer, one consumer, one release/acquire episode, one data line, one final demand read, one controllable grant, and an initial old-response count in `[0,K]`. No transition creates new stale traffic. For raw acknowledgment timing and any deterministic receipt map `rho`, a correct nonblocking contract exists exactly when the symbol `rho(0)` is not reused for any positive pending count. Thus two receipt classes are necessary and sufficient for `K>=1`; the bit `[p=0]` is a matching implementation. Drain-before-acknowledge and persistent generation filtering establish the same stable fact inside the mechanism.

The detailed Boolean `K=1` encoding and the parameterized count encoding are separately implemented but share authorship and mathematical premises. Both use `ack:0`/`ack:+`; for all five mechanisms and two interfaces, labeled edges, history-to-knowledge maps, and greatest-contract permissions agree, while a wrong label map is rejected. A separate executable counterexample shows that L1--L4 guarantee only good completion for concrete grants that occur; L6 is also required for statewise correctness eligibility. No CXL, MemGlue, C3, vCXLGen, ShimGen, Synapse, commercial hierarchy, recurrent protocol, or full C11 implementation is claimed to satisfy the theorem premises.

## Retained evidence

The retained scientific outputs contain:

- 25 parameterized plants and 50 greatest contracts for `K=0,...,4`;
- 2,024 parameterized transition, kernel, knowledge, prediction, receipt, observation-isomorphism, and wrong-label checks, with no reported mismatch;
- a meta-oracle covering 486 generic plants and all 1,188 contracts by direct maximal-path semantics, plus 75 actual `rho`-labelled raw plants checked without the closed-form helper; zero disagreement and targeted quantifier/eligibility mutants killed;
- five detailed `K=1` plants, ten controlled cases, 140 maximal paths, 132 completed paths, and eight blocked paths;
- 270 completed-event profiles, 2,892 candidates, 2,877 background-admitted graphs, 2,848 target-good graphs, and 199 minimum source-word certificates;
- explicit unsafe-grant and missed-safe-grant mutants, distinct operational failure signatures, and semantic target mutations.

These are exhaustive results only inside the retained finite universes. They are not probabilities, workload coverage, hardware error rates, latency, throughput, or a proof by induction from `K<=4`.

## Validation commands

The documented execution path is Linux or WSL. This package was validated on x86-64 Linux 6.18.44, glibc 2.41, and CPython 3.13.5. Native Windows Python is unsupported because `reproduce.py` imports POSIX `resource`; `peak_rss_kib` is Linux `ru_maxrss` in KiB. The scientific code uses one worker, no randomness, no network, no solver, no model API, no GPU, and no private data.

From the repository root:

```sh
python -m unittest discover -s tests -v
python verify.py --output results
```

The current suite contains **78 deterministic tests** and really recomputes the contract/meta-oracle cases exercised by those tests. `verify.py --output results` is narrower: it compares parsed values for eleven retained outputs and checks summary invariants plus local reference/public-source ledger structure. It does **not** rerun synthesis, rederive result flags, or validate upstream sources.

A fresh full replay is available as a separate action:

```sh
python reproduce.py --output reproduced
python verify.py --output reproduced
```

`reproduced` must not exist or must be empty. `reproduce.py` performs the complete fresh 19,002-obligation computation; the following `verify.py` invocation compares its parsed outputs with the retained set. It does not mechanize the handwritten general proofs, make same-authorship implementations independent, or discharge a simulation for a real protocol.

## Repository map

| Path | Role |
|---|---|
| `src/contracts.py` | Generic exact synthesis for explicit finite acyclic one-shot grant plants |
| `src/parametric_bridge.py` | Counted-response plants, exact kernels, knowledge sets, contracts, modeled taxonomy, and receipt partition helper |
| `src/metaoracle.py` | Direct-path oracle for 486 generic plants; 75 explicit receipt-labelled plants; lifting and complexity sanity witnesses |
| `src/bridge.py` | Detailed `K=1` physical plants, policies, complete paths, and observation fibers |
| `src/bridge_study.py` | Detailed path summaries, MP trace maps, suffix checks, and paired witnesses |
| `src/model.py` | Finite read/write event-graph construction and separately structured semantic oracle |
| `src/observe.py` | Completed-observation fibers, exact masks, hitting sets, and rectangularity diagnostics |
| `proofs/observable-grants.md` | General contract, nonblocking, monotonicity, lifting, receipt, taxonomy, and product proofs |
| `proofs/operational-bridge.md` | Detailed `K=1` transition, progress, and MP mapping argument |
| `proofs/finite-contracts.md` | Completed-outcome quotient and information diagnostics |
| `tests/` | 78 deterministic regression, mutation, synthesis, ledger-structure, and metadata tests |
| `results/` | Retained stable outputs plus resource, reproduction, and accounting records |
| `claim_evidence_ledger.csv` | Claim-to-proof/check/result traceability |
| `reference_audit.csv` | 33 cited records: 31 scholarly works, one author corrigendum, and one pinned public artifact |
| `public_protocol_audit.csv` | Five immutable source facts and explicit non-lifting boundaries for the vCXLGen audit |
| `external_resources.csv` | Scholarly, official, and public-artifact source inventory with integration boundaries |

The eleven stable result files are:

```text
graphs.csv
observations.csv
summary.json
witnesses.json
bridge-plants.json
bridge-guards.json
bridge-cases.json
bridge-observations.json
bridge-summary.json
parametric-summary.json
metaoracle-summary.json
```

Resource and campaign records are intentionally excluded from stable-value equality because timings vary and the campaign history is noncompliant.

## Reproducibility and campaign accounting

The retained outputs contain 19,002 declared finite obligations. The final one-process replay measured 0.8083 process-CPU seconds after imports, 0.8083 seconds wall time, and 98,348 KiB (about 96.04 MiB) Linux peak RSS. These are checker costs, not architecture measurements.

The cumulative campaign ceiling was not satisfied. The original 100,000-obligation ceiling was exceeded, and a later prospective 160,000 ceiling was also exceeded. The documented conservative lower bound is updated after every identifiable full-universe invocation; partial test invocations were not all individually metered, so no exact all-in total or remaining reserve is asserted. This repair required one fresh 19,002-obligation replay; the resulting lower bound and continuing noncompliance are recorded without treating fast runtime as a waiver. See `results/campaign-accounting.json`.

## Provenance and license

Project-specific source is MIT-licensed. External papers and public artifacts are cited or inventoried but not redistributed. The public vCXLGen artifact is inspected only as qualitative evidence that one model path separates ordinary ACK, pending-ack state, a zero-tested ALL_ACKS trigger, and later completion. File-local notices are preserved in the audit; no upstream source is redistributed, modified, benchmarked, or claimed to satisfy this model.

ChatGPT (GPT-5.6 Sol Pro) was used substantively for mathematics, implementation, finite checking, literature comparison, figures, tables, and drafting. The named human authors remain responsible for independent verification, authorship eligibility, originality, disclosure, and any external use. No submission, acceptance, or independent peer review is asserted.
