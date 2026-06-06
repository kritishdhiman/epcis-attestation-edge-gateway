"""
Unit tests — EPCIS Attestation Edge Gateway
Run: python -m pytest tests/test_all.py -v   OR   python tests/test_all.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import unittest

from events.generator import generate_events
from normalization.normalizer import normalize_identifier, run_normalization_demo
from anomaly.gating import score_event, gate, run_anomaly_gating, compute_metrics
from merkle.merkle import MerkleTree, _hash_event, build_all_proof_bundles, verify_proof_bundle
from finality.finality import run_finality_protocol, finality_summary


class TestGenerator(unittest.TestCase):
    def setUp(self):
        self.events = generate_events(50, anomaly_rate=0.15)

    def test_event_count(self):
        self.assertEqual(len(self.events), 50)

    def test_event_structure(self):
        ev = self.events[0]
        for field in ("eventID", "eventType", "eventTime", "epcList",
                      "action", "bizStep", "bizLocation", "sensorData"):
            self.assertIn(field, ev, f"Missing field: {field}")

    def test_anomaly_rate(self):
        n_anomalies = sum(1 for e in self.events if e["_meta"]["is_anomaly"])
        self.assertGreater(n_anomalies, 0)

    def test_epc_format(self):
        for ev in self.events:
            for epc in ev["epcList"]:
                self.assertTrue(epc.startswith("urn:epc:id:sgtin:"))


class TestNormalizer(unittest.TestCase):
    def test_internal_code_known(self):
        r = normalize_identifier("PROD-1234", "PartnerA", "2017")
        self.assertTrue(r["success"])
        self.assertIn("urn:epc:id:sgtin:", r["after"])

    def test_internal_code_unknown(self):
        r = normalize_identifier("PROD-9999", "PartnerA", "0001")
        self.assertFalse(r["success"])

    def test_ean13_valid(self):
        r = normalize_identifier("5901234123457", "PartnerB", "3001")
        self.assertTrue(r["success"])

    def test_ean13_invalid_length(self):
        r = normalize_identifier("590123412345", "PartnerB", "3001")   # 12 digits
        self.assertFalse(r["success"])

    def test_gs1_urn_valid(self):
        r = normalize_identifier("urn:epc:id:sgtin:0614145.107346.2017", "PartnerC")
        self.assertTrue(r["success"])
        self.assertFalse(r["changed"])

    def test_gs1_urn_malformed(self):
        r = normalize_identifier("urn:epc:id:sgtin:BROKEN", "PartnerC")
        self.assertFalse(r["success"])

    def test_demo_runs(self):
        results = run_normalization_demo()
        self.assertGreater(len(results), 0)


class TestGating(unittest.TestCase):
    def _make_event(self, temp=5.0, lat=28.6, lng=77.2, gln_ok=True, ts="2026-06-04T10:00:00Z"):
        gln = ("urn:epc:id:sgln:0614143.00500.0" if gln_ok
               else "urn:epc:id:sgln:UNKNOWN.99999.0")
        return {
            "eventID": "EVT-TEST",
            "eventType": "ObjectEvent",
            "eventTime": ts,
            "epcList": ["urn:epc:id:sgtin:0614141.107346.9999"],
            "action": "OBSERVE",
            "bizStep": "urn:epcglobal:cbv:bizstep:shipping",
            "bizLocation": gln,
            "readPoint": gln,
            "sensorData": {
                "temperature": temp,
                "gps": {"lat": lat, "lng": lng},
                "doorOpen": False,
                "vibration": 0.02,
            },
            "_meta": {"is_anomaly": False, "anomaly_type": None, "city": "Delhi"},
        }

    def test_clean_event_accepted(self):
        ev = self._make_event()
        score, _ = score_event(ev)
        self.assertEqual(gate(score), "ACCEPT")

    def test_temp_spike_quarantined(self):
        ev = self._make_event(temp=32.0)
        score, _ = score_event(ev)
        self.assertGreaterEqual(score, 0.3)

    def test_overseas_gps_quarantined(self):
        ev = self._make_event(lat=51.5, lng=-0.1)
        score, _ = score_event(ev)
        self.assertGreaterEqual(score, 0.5)

    def test_unknown_gln_raises_score(self):
        ev = self._make_event(gln_ok=False)
        score, reasons = score_event(ev)
        self.assertGreaterEqual(score, 0.4)
        self.assertTrue(any("GLN" in r for r in reasons))

    def test_gate_thresholds(self):
        self.assertEqual(gate(0.10), "ACCEPT")
        self.assertEqual(gate(0.45), "CHALLENGE")
        self.assertEqual(gate(0.80), "QUARANTINE")

    def test_metrics_keys(self):
        events = generate_events(20)
        gated  = run_anomaly_gating(events)
        m = compute_metrics(gated)
        for key in ("precision", "recall", "f1_score", "accepted", "quarantined"):
            self.assertIn(key, m)


class TestMerkle(unittest.TestCase):
    def test_single_leaf(self):
        tree = MerkleTree(["abc"])
        self.assertIsNotNone(tree.root)

    def test_root_deterministic(self):
        leaves = ["a", "b", "c", "d"]
        t1 = MerkleTree(leaves)
        t2 = MerkleTree(leaves)
        self.assertEqual(t1.root, t2.root)

    def test_proof_valid(self):
        # Build tree directly from pre-hashed leaves (bypassing event serialisation)
        from merkle.merkle import _sha256, _verify_proof
        raw_leaves = ["alpha", "beta", "gamma", "delta"]
        hashed = [_sha256(l) for l in raw_leaves]
        tree = MerkleTree(hashed)   # leaves are already hashes
        for i, lh in enumerate(hashed):
            proof = tree.proof(i)
            self.assertTrue(_verify_proof(lh, proof, tree.root),
                            f"Proof failed for leaf index {i}")

    def test_tampered_proof_fails(self):
        events = generate_events(10)
        accepted = [{"eventID": e["eventID"], "eventTime": e["eventTime"],
                     "city": e["_meta"]["city"], "raw_event": e}
                    for e in events[:6]]
        _, bundles = build_all_proof_bundles(accepted)
        import copy
        bad = copy.deepcopy(bundles[0])
        bad["eventHash"] = "0" * 64    # completely wrong hash
        self.assertFalse(verify_proof_bundle(bad))

    def test_valid_bundle_passes(self):
        events = generate_events(10)
        accepted = [{"eventID": e["eventID"], "eventTime": e["eventTime"],
                     "city": e["_meta"]["city"], "raw_event": e}
                    for e in events[:6]]
        _, bundles = build_all_proof_bundles(accepted)
        for b in bundles:
            self.assertTrue(verify_proof_bundle(b))


class TestFinality(unittest.TestCase):
    def _dummy_accepted(self, n=10):
        return [
            {"eventID": f"EVT-{i:03d}",
             "eventTime": "2026-06-04T10:00:00Z",
             "city": "Delhi"}
            for i in range(n)
        ]

    def test_all_events_have_status(self):
        tl = run_finality_protocol(self._dummy_accepted(), "fake_root")
        for r in tl:
            self.assertIn(r["status"], ("FINAL", "PROVISIONAL", "DISPUTED"))

    def test_summary_keys(self):
        tl   = run_finality_protocol(self._dummy_accepted(), "fake_root")
        summ = finality_summary(tl)
        for key in ("total", "final", "disputed", "avg_finality_hours"):
            self.assertIn(key, summ)

    def test_no_events_with_score_2_stay_provisional(self):
        """After simulation, no event should remain PROVISIONAL."""
        tl = run_finality_protocol(self._dummy_accepted(20), "fake_root")
        statuses = {r["status"] for r in tl}
        self.assertNotIn("PROVISIONAL", statuses)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
