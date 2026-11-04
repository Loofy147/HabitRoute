"""Focused tests for the capacity-pruning policy.

The full habit_refine dependency is included and imported by habit_system.
Run with: python -m unittest -v test_habit_utility.py
"""
import unittest
import habit_system as hs


def insert(lib, key, path, n_exec=0, n_ok=0, uses=0):
    lib.h[key] = {
        "acts": key[1], "path": path,
        "n_exec": n_exec, "n_ok": n_ok, "uses": uses,
    }
    lib.adj.setdefault(path[0], []).append(key)


class StepSavingsTests(unittest.TestCase):
    def test_legacy_usage_metric_still_rewards_frequency(self):
        lib = hs.LibS(None, "utility", __import__("numpy").random.default_rng(1), 0.1, False)
        high = {"uses": 100, "n_ok": 100, "n_exec": 100}
        low = {"uses": 1, "n_ok": 1, "n_exec": 1}
        self.assertGreater(lib.util(high), lib.util(low))

    def test_steps_saved_outweigh_raw_usage(self):
        np = __import__("numpy")
        lib = hs.LibS(1, "savings", np.random.default_rng(2), 0.1, False)
        detour = (0, (4, 5, 6, 7))
        shorter = (0, (1, 2))
        insert(lib, detour, (0, 4, 5, 6, 3), n_exec=100, n_ok=100, uses=100)
        insert(lib, shorter, (0, 2, 3), n_exec=1, n_ok=1, uses=1)
        self.assertGreater(lib.step_savings(shorter), lib.step_savings(detour))

    def test_capacity_pruning_keeps_shorter_verified_route(self):
        np = __import__("numpy")
        lib = hs.LibS(1, "savings", np.random.default_rng(3), 0.1, False)
        detour = (0, (4, 5, 6, 7))
        shorter = (0, (1, 2))
        insert(lib, detour, (0, 4, 5, 6, 3), n_exec=100, n_ok=100, uses=100)
        insert(lib, shorter, (0, 2, 3), n_exec=1, n_ok=1, uses=1)
        lib.prune(set())
        self.assertEqual(set(lib.h), {shorter})
        self.assertEqual(lib.check(), [])

    def test_unique_route_gets_coverage_credit(self):
        np = __import__("numpy")
        lib = hs.LibS(None, "savings", np.random.default_rng(4), 0.1, False)
        key = (0, (9,))
        insert(lib, key, (0, 1))
        self.assertGreater(lib.step_savings(key), 0)

    def test_known_bad_route_gets_no_value(self):
        np = __import__("numpy")
        lib = hs.LibS(None, "savings", np.random.default_rng(5), 0.1, False)
        key = (0, (9,))
        insert(lib, key, (0, 1), n_exec=2, n_ok=0)
        lib.es[(0, 9)] = [2, 2]
        self.assertEqual(lib.step_savings(key), 0.0)


    def test_coverage_weight_is_configurable(self):
        np = __import__("numpy")
        def score(weight):
            lib = hs.LibS(None, "savings", np.random.default_rng(6), 0.1, False, coverage_weight=weight)
            key = (0, (8,))
            insert(lib, key, (0, 1))
            return lib.step_savings(key)
        self.assertGreater(score(4.0), score(1.0))

    def test_savings_policy_default_coverage_weight_uses_sensitivity_result(self):
        np = __import__("numpy")
        lib = hs.LibS(None, "savings", np.random.default_rng(7), 0.1, False)
        self.assertEqual(lib.coverage_weight, 0.5)

    def test_agent_default_remains_legacy_utility_policy(self):
        import inspect
        self.assertEqual(inspect.signature(hs.AgS).parameters["policy"].default, "utility")
        self.assertEqual(inspect.signature(hs.AgS).parameters["coverage_weight"].default, 0.5)

    def test_policy_is_deterministic_for_same_seed(self):
        np = __import__("numpy")
        def run():
            lib = hs.LibS(2, "savings", np.random.default_rng(88), 0.1, False)
            rows = [
                ((0, (1, 2)), (0, 4, 9)),
                ((0, (3, 4, 5)), (0, 5, 6, 9)),
                ((0, (6, 7, 8, 9)), (0, 7, 8, 10, 9)),
            ]
            for key, path in rows:
                insert(lib, key, path, n_exec=4, n_ok=4, uses=4)
            lib.prune(set())
            return tuple(sorted(lib.h)), lib.check()
        self.assertEqual(run(), run())

    def test_original_and_new_selftests(self):
        self.assertEqual(hs.selftest(), [22, 22])


if __name__ == "__main__":
    unittest.main()
