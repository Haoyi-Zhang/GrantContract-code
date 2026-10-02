# Pinned public-protocol source audit

This note records the narrow source-level observation used in the manuscript.
It is not a verification or execution of vCXLGen and it does not discharge the
paper's lifting obligations.

## Immutable source identity

- Repository: `TUM-DSE/vCXLGen`
- Commit: `0c5c6d8e06ecf1a1d6fed3e6097e496850306dc0`
- Audited files and blob identifiers are listed in
  `../public_protocol_audit.csv`.
- The source files were inspected through GitHub at the pinned commit.  They
  were not copied into this artifact or executed.
- The inspected SLICC files carry ARM/gem5 BSD-style notices.  The repository's
  top-level MIT license therefore must not be used to erase file-local notices.

## Supported observation

The audited path distinguishes three concrete notions:

1. an individual `ACK`/`IntAck` response;
2. a transaction-buffer count `NumIntPendingAcks`; and
3. a distinct `ALL_ACKS` trigger that is emitted only after a zero test and is
   consumed by a later completion transition.

This supports only the qualitative statement that a public coherence model can
represent aggregate readiness separately from receipt of one acknowledgment.
It is useful because the paper's counterexample attacks precisely the
conflation of those notions.

## What the audit does not support

The audit does **not** show that `NumIntPendingAcks` equals the set of responses
that can reinstall pre-release data.  It does not establish that the set is
frozen, that clearing and sampling are atomic, that identifiers cannot alias,
that a clean miss is fresh, or that grant is enabled whenever the abstract
contract permits.  Consequently it does not discharge L1--L6, validate any
vCXLGen protocol against the paper's theorem, or justify a performance claim.

Each row of `public_protocol_audit.csv` carries this limitation explicitly so a
future edit cannot silently promote the qualitative anchor into a concrete
refinement result.
