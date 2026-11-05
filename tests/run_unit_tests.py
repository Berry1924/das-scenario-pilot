#!/usr/bin/env python3
"""Unit tests for src/daas_impl (stdlib unittest, no external deps).

Covers: CRC16/packet round-trip, VS4 TTC edge cases (zero/negative/very small
closing speed, very large distance, invalid distance, packet age, missing
vehicle state), VS3 trust gate, VS5 degradation state machine.

Run: python3 tests/run_unit_tests.py  (from repo root: src on sys.path)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl import packet as P
from daas_impl import ttc as T
from daas_impl import trust_gate as G
from daas_impl import degradation as D


class TestPacketCRC(unittest.TestCase):
    def test_known_crc16_ccitt(self):
        # Standard CRC16-CCITT (init 0xFFFF) check value for "123456789" is 0x29B1
        self.assertEqual(P.compute_crc16(b"123456789"), 0x29B1)

    def test_packet_roundtrip(self):
        pkt = P.V2VPacket(sender_id=1, seq_num=125, timestamp_ms=1000,
                          priority=P.PRIORITY_EMERGENCY, distance_m=12.5,
                          speed_mps=8.0, accel_mps2=-4.0).sign()
        raw = pkt.to_bytes()
        self.assertEqual(len(raw), 32)
        pkt2 = P.V2VPacket.from_bytes(raw)
        self.assertEqual(pkt2.crc16, pkt.crc16)
        self.assertEqual(pkt2.seq_num, 125)
        self.assertEqual(validate_result(pkt2), P.V2V_VALID_OK)

    def test_crc_mismatch_detected(self):
        pkt = P.V2VPacket(sender_id=1, seq_num=1, timestamp_ms=0).sign()
        raw = bytearray(pkt.to_bytes())
        raw[0x10] ^= 0x01  # flip a bit in distance
        pkt2 = P.V2VPacket.from_bytes(bytes(raw))
        self.assertEqual(validate_result(pkt2), P.V2V_ERR_CRC_MISMATCH)

    def test_bad_magic(self):
        raw = bytearray(P.V2VPacket(sender_id=1, seq_num=1, timestamp_ms=0).sign().to_bytes())
        raw[0] = 0x00
        with self.assertRaises(ValueError):
            P.V2VPacket.from_bytes(bytes(raw))

    def test_bounds_rejected(self):
        pkt = P.V2VPacket(sender_id=1, seq_num=1, timestamp_ms=0, distance_m=6000.0).sign()
        self.assertEqual(validate_result(pkt), P.V2V_ERR_OUT_OF_BOUNDS)
        pkt = P.V2VPacket(sender_id=1, seq_num=2, timestamp_ms=0, speed_mps=100.0).sign()
        self.assertEqual(validate_result(pkt), P.V2V_ERR_OUT_OF_BOUNDS)
        pkt = P.V2VPacket(sender_id=1, seq_num=3, timestamp_ms=0, accel_mps2=-50.0).sign()
        self.assertEqual(validate_result(pkt), P.V2V_ERR_OUT_OF_BOUNDS)

    def test_stale_timestamp(self):
        pkt = P.V2VPacket(sender_id=1, seq_num=1, timestamp_ms=0).sign()
        self.assertEqual(validate_result(pkt, current_time_ms=600), P.V2V_ERR_STALE_TIMESTAMP)
        self.assertEqual(validate_result(pkt, current_time_ms=500), P.V2V_VALID_OK)

    def test_sequence_validator(self):
        ok, dropped = P.validate_sequence(1, 0)
        self.assertTrue(ok)          # initial sync
        ok, dropped = P.validate_sequence(5, 2)
        self.assertTrue(ok)
        self.assertEqual(dropped, 2)  # seq 3,4 missing
        ok, _ = P.validate_sequence(2, 2)
        self.assertFalse(ok)          # duplicate
        ok, _ = P.validate_sequence(1, 2)
        self.assertFalse(ok)          # retrograde / replay


def validate_result(pkt, **kwargs):
    return P.validate_packet(pkt, **kwargs)


class TestTTC(unittest.TestCase):
    """VS4 required edge cases."""

    def test_zero_closing_speed(self):
        self.assertIsNone(T.compute_ttc(10.0, 0.0))       # no-closing state

    def test_negative_closing_speed(self):
        self.assertIsNone(T.compute_ttc(10.0, -5.0))      # diverging

    def test_very_small_closing_speed(self):
        self.assertIsNone(T.compute_ttc(10.0, 1e-6))      # below eps guard
        self.assertAlmostEqual(T.compute_ttc(10.0, 0.01), 1000.0)

    def test_normal_closing(self):
        self.assertAlmostEqual(T.compute_ttc(20.0, 10.0), 2.0)

    def test_very_large_distance(self):
        ttc = T.compute_ttc(4999.0, 1.0)
        self.assertAlmostEqual(ttc, 4999.0)
        # Risk assessment caps at SAFE due to distance thresholds
        a = T.assess_risk(4999.0, 1.0, T.RiskThresholds())
        self.assertEqual(a.risk_level, T.RISK_LEVEL_SAFE)

    def test_invalid_distance(self):
        self.assertIsNone(T.compute_ttc(-1.0, 5.0))
        self.assertIsNone(T.compute_ttc(float("nan"), 5.0))
        self.assertIsNone(T.compute_ttc(float("inf"), 5.0))

    def test_invalid_vrel(self):
        self.assertIsNone(T.compute_ttc(10.0, float("nan")))

    def test_missing_vehicle_state(self):
        # None distance / None v_rel treated as missing state -> no TTC
        self.assertIsNone(T.compute_ttc(None, 5.0))
        self.assertIsNone(T.compute_ttc(10.0, None))

    def test_risk_thresholds(self):
        th = T.RiskThresholds()
        a = T.assess_risk(3.0, 10.0, th)
        self.assertEqual(a.risk_level, T.RISK_LEVEL_CRITICAL)
        # TTC 0.6s at 6 m closing 10 m/s: TTC criticality takes precedence
        a = T.assess_risk(6.0, 10.0, th)
        self.assertEqual(a.risk_level, T.RISK_LEVEL_CRITICAL)
        a = T.assess_risk(20.0, 10.0, th)  # TTC 2.0s -> warning by TTC
        self.assertEqual(a.risk_level, T.RISK_LEVEL_WARNING)
        a = T.assess_risk(20.0, 2.0, th)   # TTC 10s, dist 20m -> safe
        self.assertEqual(a.risk_level, T.RISK_LEVEL_SAFE)

    def test_brake_forces_critical(self):
        a = T.assess_risk(100.0, 1.0, T.RiskThresholds(), brake_active=True)
        self.assertEqual(a.risk_level, T.RISK_LEVEL_CRITICAL)
        self.assertTrue(a.imminent_collision)


class TestTrustGate(unittest.TestCase):
    def _pkt(self, seq=1, ts=1000, dist=10.0, speed=5.0, accel=0.0):
        return P.V2VPacket(sender_id=1, seq_num=seq, timestamp_ms=ts,
                           distance_m=dist, speed_mps=speed, accel_mps2=accel).sign()

    def test_accepts_fresh_valid(self):
        g = G.TrustGate()
        d = g.ingest(self._pkt(seq=1, ts=1000), now_ms=1100)
        self.assertTrue(d.accepted)
        self.assertFalse(d.rejected)

    def test_rejects_duplicate(self):
        g = G.TrustGate()
        g.ingest(self._pkt(seq=1, ts=1000), now_ms=1050)
        d = g.ingest(self._pkt(seq=1, ts=1000), now_ms=1100)
        self.assertTrue(d.rejected)
        self.assertEqual(g.counts["rej_duplicate"], 1)

    def test_rejects_stale(self):
        g = G.TrustGate()
        d = g.ingest(self._pkt(seq=1, ts=400), now_ms=1000)  # age 600 > 500
        self.assertTrue(d.rejected)
        self.assertEqual(g.counts["rej_stale"], 1)

    def test_rejects_invalid_sequence(self):
        g = G.TrustGate()
        g.ingest(self._pkt(seq=5, ts=1000), now_ms=1050)
        d = g.ingest(self._pkt(seq=3, ts=1010), now_ms=1060)  # retrograde
        self.assertTrue(d.rejected)
        self.assertEqual(g.counts["rej_duplicate"], 1)  # counted as duplicate/replay

    def test_rejects_impossible_speed(self):
        g = G.TrustGate()
        d = g.ingest(self._pkt(seq=1, ts=1000, speed=90.0), now_ms=1050)
        self.assertTrue(d.rejected)
        self.assertEqual(g.counts["rej_bounds"], 1)

    def test_rejects_impossible_distance(self):
        g = G.TrustGate()
        d = g.ingest(self._pkt(seq=1, ts=1000, dist=-5.0), now_ms=1050)
        self.assertTrue(d.rejected)
        d = g.ingest(self._pkt(seq=2, ts=1010, dist=6000.0), now_ms=1060)
        self.assertTrue(d.rejected)

    def test_rejects_crc_corruption(self):
        g = G.TrustGate()
        pkt = self._pkt(seq=1, ts=1000)
        pkt.distance_m = 99.0  # mutate after signing -> CRC mismatch
        d = g.ingest(pkt, now_ms=1050)
        self.assertTrue(d.rejected)
        self.assertEqual(g.counts["rej_crc"], 1)

    def test_downweighted_not_rejected(self):
        # Emergency frames flagged inconsistent are accepted but downweighted
        g = G.TrustGate()
        pkt = self._pkt(seq=1, ts=1000)
        pkt.priority = P.PRIORITY_EMERGENCY
        pkt.sign()
        d = g.ingest(pkt, now_ms=1050)
        self.assertTrue(d.accepted)

    def test_multiple_peers_tracked_independently(self):
        g = G.TrustGate()
        p1 = P.V2VPacket(sender_id=1, seq_num=7, timestamp_ms=1000,
                         distance_m=10.0, speed_mps=5.0).sign()
        p2 = P.V2VPacket(sender_id=2, seq_num=3, timestamp_ms=1000,
                         distance_m=12.0, speed_mps=5.0).sign()
        self.assertTrue(g.ingest(p1, now_ms=1050).accepted)
        self.assertTrue(g.ingest(p2, now_ms=1060).accepted)
        self.assertEqual(len(g.peers), 2)


class TestDegradation(unittest.TestCase):
    def test_full_when_healthy(self):
        mon = D.DegradationMonitor()
        mon.record_peer_heartbeat(0)
        mon.record_sensor_ok(0)
        state = mon.update(100, None, None)
        self.assertEqual(state, D.FULL)

    def test_v2v_outage_after_watchdog(self):
        mon = D.DegradationMonitor()
        mon.record_peer_heartbeat(0)
        mon.record_sensor_ok(0)
        mon.update(100)
        mon.update(2000)
        # sensor kept healthy via explicit hook; only V2V times out
        state = mon.update(2501, None, True)
        self.assertEqual(state, D.V2V_DEGRADED)
        self.assertGreaterEqual(mon.fallback_triggers, 1)

    def test_recovery_on_heartbeat(self):
        mon = D.DegradationMonitor()
        mon.record_peer_heartbeat(0)
        mon.record_sensor_ok(0)
        mon.update(2600, None, True)  # degraded (V2V silent)
        mon.record_peer_heartbeat(2700)
        state = mon.update(2800, None, True)  # sensor still forced healthy
        self.assertEqual(state, D.FULL)
        self.assertGreaterEqual(mon.recoveries, 1)

    def test_sensor_dropout(self):
        mon = D.DegradationMonitor()
        mon.record_peer_heartbeat(0)
        mon.record_sensor_ok(0)
        mon.update(100)
        # sensor stops reporting: sensor_fresh_ms=500 default
        state = mon.update(700)
        self.assertEqual(state, D.SENSOR_DEGRADED)

    def test_both_degraded(self):
        mon = D.DegradationMonitor()
        mon.record_peer_heartbeat(0)
        mon.record_sensor_ok(0)
        mon.update(100)
        state = mon.update(3000)  # both timers expired
        self.assertEqual(state, D.BOTH_DEGRADED)

    def test_hazard_latch_window(self):
        mon = D.DegradationMonitor()
        mon.latch_hazard(1000)
        self.assertTrue(mon.hazard_latch_active(2000))    # within 1500 ms
        self.assertFalse(mon.hazard_latch_active(3000))   # expired

    def test_state_time_accounting(self):
        mon = D.DegradationMonitor()
        mon.record_peer_heartbeat(0)
        mon.record_sensor_ok(0)
        mon.update(1000, None, True)      # FULL (sensor forced healthy)
        mon.update(3000, None, True)      # V2V watchdog fires at 3000
        # FULL occupied 1000..3000
        self.assertAlmostEqual(mon.time_in_state_ms[D.FULL], 2000.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
