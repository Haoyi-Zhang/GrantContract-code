import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parametric_bridge import (CountState, analyze_contract,
                               audit_contract_rows, audit_k1_observation_isomorphism,
                               forced_grant_safe, grant_formula, observation,
                               oracle_edges, reachable_graph, run_parametric,
                               transitions)


class ParametricBridgeTests(unittest.TestCase):
    def test_primary_and_tuple_oracles(self):
        for bound in range(5):
            for mechanism in ("raw", "drain", "generation", "late_generation", "no_repair"):
                _, edges = reachable_graph(bound, mechanism)
                self.assertEqual(edges, oracle_edges(bound, mechanism))

    def test_exact_full_state_kernel(self):
        for bound in range(5):
            for mechanism in ("raw", "drain", "generation", "late_generation", "no_repair"):
                states, _ = reachable_graph(bound, mechanism)
                for state in states:
                    if state.flag and state.phase == 0:
                        self.assertEqual(forced_grant_safe(state, mechanism),
                                         grant_formula(state, mechanism))

    def test_one_bit_receipt_separates_raw_readiness(self):
        clean = CountState(flag=1, invalidated=1, old_cache=0, pending=0)
        hazard = CountState(flag=1, invalidated=1, old_cache=0, pending=1)
        self.assertTrue(forced_grant_safe(clean, "raw"))
        self.assertFalse(forced_grant_safe(hazard, "raw"))
        self.assertEqual(observation("ack", clean, "bare"),
                         observation("ack", hazard, "bare"))
        self.assertNotEqual(observation("ack", clean, "zero_receipt"),
                            observation("ack", hazard, "zero_receipt"))


    def test_contract_audit_detects_unsafe_and_nonmaximal_rows(self):
        unsafe = audit_contract_rows([{
            "largest_safe_contract_grants": True,
            "all_states_safe": False,
            "grant_enabled_in_all_states": True,
        }])
        self.assertFalse(unsafe["universally_safe"])
        self.assertFalse(unsafe["contract_exact"])
        self.assertEqual(unsafe["unsafe_grant_history_count"], 1)

        nonmaximal = audit_contract_rows([{
            "largest_safe_contract_grants": False,
            "all_states_safe": True,
            "grant_enabled_in_all_states": True,
        }])
        self.assertTrue(nonmaximal["universally_safe"])
        self.assertFalse(nonmaximal["maximally_permissive"])
        self.assertFalse(nonmaximal["contract_exact"])
        self.assertEqual(nonmaximal["missed_safe_history_count"], 1)

    def test_constructed_contracts_pass_explicit_audit(self):
        for bound in range(5):
            for mechanism in ("raw", "drain", "generation", "late_generation", "no_repair"):
                for interface in ("bare", "zero_receipt"):
                    result = analyze_contract(bound, mechanism, interface)
                    self.assertTrue(result["contract_exact"])
                    self.assertTrue(result["universally_safe"])
                    self.assertTrue(result["maximally_permissive"])
                    self.assertEqual(result["unsafe_grant_history_count"], 0)
                    self.assertEqual(result["missed_safe_history_count"], 0)
                    self.assertEqual(result["ineligible_grant_history_count"], 0)

    def test_contract_characterizations(self):
        for bound in range(1, 5):
            self.assertFalse(analyze_contract(bound, "raw", "bare")["nonblocking"])
            self.assertTrue(analyze_contract(bound, "raw", "zero_receipt")["nonblocking"])
            self.assertTrue(analyze_contract(bound, "drain", "bare")["nonblocking"])
            self.assertTrue(analyze_contract(bound, "generation", "bare")["nonblocking"])
            self.assertFalse(analyze_contract(bound, "late_generation", "bare")["nonblocking"])
            self.assertTrue(analyze_contract(bound, "late_generation", "zero_receipt")["nonblocking"])
            self.assertFalse(analyze_contract(bound, "no_repair", "zero_receipt")["nonblocking"])

    def test_no_new_stale_traffic(self):
        state = CountState(flag=1, invalidated=1, old_cache=0, pending=0)
        self.assertNotIn("fill", [action for action, _ in transitions(state, "raw")])


    def test_k1_observation_isomorphism_checks_labels_beliefs_and_permissions(self):
        result = audit_k1_observation_isomorphism()
        self.assertTrue(result["exact"])
        self.assertEqual(result["cases_checked"], 10)
        self.assertEqual(result["label_mismatches"], 0)
        self.assertEqual(result["knowledge_mismatches"], 0)
        self.assertEqual(result["permission_mismatches"], 0)

    def test_wrong_receipt_label_map_is_rejected(self):
        result = audit_k1_observation_isomorphism(
            lambda label: "ack:1" if label == "ack:+" else label
        )
        self.assertFalse(result["exact"])
        self.assertGreater(result["label_mismatches"], 0)
        self.assertTrue(
            result["knowledge_mismatches"] > 0
            or result["permission_mismatches"] > 0
        )

    def test_complete_bounded_study(self):
        result = run_parametric(4)
        self.assertEqual(result["receipt_lower_bound_bits"], 1)
        self.assertEqual(result["transition_oracle_mismatches"], 0)
        self.assertEqual(result["grant_kernel_mismatches"], 0)
        self.assertEqual(result["history_oracle_mismatches"], 0)
        self.assertEqual(result["contract_exactness_mismatches"], 0)
        self.assertEqual(result["prediction_mismatches"], 0)
        self.assertTrue(all(contract["contract_exact"] for contract in result["contracts"]))


if __name__ == "__main__":
    unittest.main()
