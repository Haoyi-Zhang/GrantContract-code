#!/usr/bin/env python3
"""Self-check retained output values and local ledger structure.

This command does not recompute the contract synthesizer or meta-oracle and does
not contact external sources.  Use ``reproduce.py`` or the unit tests for fresh
computation, then point this script at the newly produced output directory.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
STABLE = (
    "graphs.csv", "observations.csv", "summary.json", "witnesses.json",
    "bridge-plants.json", "bridge-guards.json", "bridge-cases.json",
    "bridge-observations.json", "bridge-summary.json",
    "parametric-summary.json", "metaoracle-summary.json",
)


def check_reference_ledger_structure() -> int:
    """Check only the delivered reference ledger's local schema/invariants."""
    with (ROOT / "reference_audit.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    keys = [row.get("key", "") for row in rows]
    if not 30 <= len(rows) <= 45 or not all(keys) or len(keys) != len(set(keys)):
        raise ValueError("reference ledger must contain 30--45 unique nonempty keys")
    if any(row.get("status") != "PASS" for row in rows):
        raise ValueError("reference ledger records a non-PASS local status")
    tc_rows = [row for row in rows
               if row.get("venue", "").startswith("IEEE Transactions on Computers")]
    if len(tc_rows) != 12:
        raise ValueError("reference ledger does not contain twelve TC calibration papers")
    expected = {
        "heterogen": ("HPCA 2022", "756-771", "10.1109/HPCA53966.2022.00061"),
        "disco": ("IEEE Transactions on Computers 72(4)", "1163-1177",
                  "10.1109/TC.2022.3193624"),
        "tardis": ("PACT 2015", "227-240", "10.1109/PACT.2015.12"),
    }
    by_key = {row["key"]: row for row in rows}
    for key, triple in expected.items():
        row = by_key.get(key, {})
        actual = (row.get("venue"), row.get("pages_or_article"),
                  row.get("doi_or_identifier"))
        if actual != triple:
            raise ValueError(f"locked reference-ledger metadata regressed: {key}")
    if by_key.get("rc11corrigendum", {}).get("venue") != "Author-issued corrigendum":
        raise ValueError("RC11 corrigendum record missing or misclassified")
    synapse = by_key.get("synapse", {})
    if (synapse.get("venue"), synapse.get("pages_or_article")) != (
        "MICRO 2026 (accepted)", "to appear"
    ):
        raise ValueError("accepted-work ledger metadata missing or overstated")
    dois = [row["doi_or_identifier"].lower() for row in rows
            if row.get("doi_or_identifier", "").startswith("10.")]
    if len(dois) != len(set(dois)):
        raise ValueError("duplicate DOI in reference ledger")
    return len(rows)


def check_public_protocol_ledger_structure() -> int:
    """Check the pinned local source-fact ledger, not the upstream repository."""
    with (ROOT / "public_protocol_audit.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 5 or len({row.get("fact_id") for row in rows}) != 5:
        raise ValueError("public-source ledger must contain five unique facts")
    commit = "0c5c6d8e06ecf1a1d6fed3e6097e496850306dc0"
    if any(row.get("commit") != commit for row in rows):
        raise ValueError("public-source ledger is not pinned to the declared commit")
    if any("not a lift" not in row.get("scope_limit", "").lower() for row in rows):
        raise ValueError("public-source ledger contains an unbounded lifting claim")
    joined = " ".join(row.get("concrete_fact", "") for row in rows)
    for token in ("ACK", "ALL_ACKS", "NumIntPendingAcks", "zero"):
        if token not in joined:
            raise ValueError("public-source ledger missing required local anchor: " + token)
    return len(rows)


def load(path: Path) -> Any:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check_parametric_summary(summary: dict[str, Any]) -> None:
    counts = summary.get("counts", {})
    if summary.get("counted_obligations") != sum(counts.values()):
        raise ValueError("parametric counted-obligation summary is internally inconsistent")
    for key in (
        "transition_oracle_mismatches", "grant_kernel_mismatches",
        "history_oracle_mismatches", "contract_exactness_mismatches",
        "prediction_mismatches",
    ):
        if summary.get(key) != 0:
            raise ValueError("retained parametric summary reports a mismatch: " + key)
    contracts = summary.get("contracts", [])
    if len(contracts) != 50 or any(not row.get("contract_exact") for row in contracts):
        raise ValueError("retained parametric contract rows are incomplete or non-exact")
    if any(row.get("unsafe_grant_history_count") or row.get("missed_safe_history_count")
           or row.get("ineligible_grant_history_count") for row in contracts):
        raise ValueError("retained contract rows report a safety/eligibility/maximality defect")
    iso = summary.get("k1_observation_isomorphism", {})
    if not iso.get("exact") or iso.get("cases_checked") != 10:
        raise ValueError("retained K=1 observation-isomorphism summary is not exact")
    if not summary.get("wrong_label_mapping_rejected"):
        raise ValueError("retained wrong-label negative control was not rejected")


def check_metaoracle_summary(summary: dict[str, Any]) -> None:
    for key in (
        "kernel_mismatches", "observer_mismatches",
        "greatest_contract_mismatches", "nonblocking_mismatches",
        "receipt_plant_mismatches",
    ):
        if summary.get(key) != 0:
            raise ValueError("retained meta-oracle summary reports a mismatch: " + key)
    if summary.get("plants_checked") != 486 or summary.get("receipt_partitions_checked") != 75:
        raise ValueError("retained meta-oracle universe size regressed")
    counted = (4 * summary["plants_checked"] + summary["contract_candidates_checked"]
               + summary["nonblocking_candidates_checked"]
               + summary["receipt_partitions_checked"] + 6 + 2)
    if summary.get("counted_obligations") != counted:
        raise ValueError("meta-oracle executed-call accounting is inconsistent")
    rows = summary.get("receipt_partition_results", [])
    if len(rows) != 75 or any(not row.get("exact") for row in rows):
        raise ValueError("retained explicit receipt-plant rows are incomplete or non-exact")
    if not summary.get("existential_mutant_counterexamples") \
            or not summary.get("eligibility_mutant_counterexamples"):
        raise ValueError("retained meta-oracle summary did not kill required mutants")
    lifting = summary.get("lifting_counterexample", {})
    if not (lifting.get("L1_through_L4") and lifting.get("actual_grant_safety")
            and not lifting.get("L6") and not lifting.get("full_correctness")):
        raise ValueError("retained L1--L4 eligibility counterexample is malformed")
    if not summary.get("complexity_sanity", {}).get("exact"):
        raise ValueError("retained complexity sanity cases are not exact")


def check_resource_record(output: Path) -> None:
    record = json.loads((output / "resources.json").read_text(encoding="utf-8"))
    if record.get("workers") != 1:
        raise ValueError("resource record does not declare one worker")
    if not 0 <= float(record.get("cpu_seconds", -1)) < 120:
        raise ValueError("resource CPU record is outside the runner limit")
    if not 0 <= int(record.get("peak_rss_kib", -1)) < int(2.5 * 1024 * 1024):
        raise ValueError("resource RSS record is outside the runner limit")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reference_count = check_reference_ledger_structure()
    source_fact_count = check_public_protocol_ledger_structure()
    for name in STABLE:
        candidate = args.output / name
        retained = ROOT / "results" / name
        if load(candidate) != load(retained):
            raise ValueError("retained-value mismatch: " + name)

    check_parametric_summary(load(args.output / "parametric-summary.json"))
    check_metaoracle_summary(load(args.output / "metaoracle-summary.json"))
    check_resource_record(args.output)
    print(
        "PASS: parsed values for eleven retained outputs match; local summary "
        f"invariants, {reference_count}-record reference-ledger structure, and "
        f"{source_fact_count}-fact public-source-ledger structure pass. This "
        "command does not recompute contracts/meta-oracles or validate external sources."
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print("verification failed: " + str(error), file=sys.stderr)
        sys.exit(2)
