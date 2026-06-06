"""
MODULE 5 — Conditional Finality Protocol
Simulates 2-stage blockchain commitment:
  Stage 1 → PROVISIONAL  (Merkle root written immediately)
  Stage 2 → FINAL        (after corroboration score ≥ 2)
             DISPUTED     (no corroboration after 24 h)
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List


# Simulated local blockchain ledger (dict-based, no real chain needed)
_LEDGER: Dict[str, Dict] = {}


def _write_provisional(event_id: str, merkle_root: str, event_time: str) -> None:
    """Write a provisional entry to the simulated ledger."""
    _LEDGER[event_id] = {
        "merkleRoot":   merkle_root,
        "status":       "PROVISIONAL",
        "provisionalAt": event_time,
        "finalAt":      None,
        "corroboration_score": 0,
        "corroboration_sources": [],
    }


def _corroborate(event_id: str, source: str, score_add: int) -> None:
    """Add a corroboration signal to an existing ledger entry."""
    if event_id not in _LEDGER:
        return
    entry = _LEDGER[event_id]
    entry["corroboration_score"] += score_add
    entry["corroboration_sources"].append(source)


def _promote_or_dispute(event_id: str, event_time: str, sim_hours_offset: float) -> None:
    """
    Decide FINAL vs DISPUTED based on corroboration score
    and simulated elapsed time.
    """
    entry = _LEDGER[event_id]
    score = entry["corroboration_score"]
    base  = datetime.strptime(event_time, "%Y-%m-%dT%H:%M:%SZ")
    final_time = base + timedelta(hours=sim_hours_offset)

    if score >= 2:
        entry["status"]  = "FINAL"
        entry["finalAt"] = final_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        entry["status"]  = "DISPUTED"
        entry["finalAt"] = final_time.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Corroboration simulation ───────────────────────────────────────────────────

def _simulate_corroboration(event_id: str, event_time: str) -> Dict:
    """
    Randomly simulate corroboration signals for an event.
    Returns the final ledger entry.
    """
    random.seed(hash(event_id) % (2 ** 32))

    # Source 1: Partner co-attestation (70 % chance)
    if random.random() < 0.70:
        _corroborate(event_id, "partner_attestation", 1)

    # Source 2: Sensor data cross-check (75 % chance)
    if random.random() < 0.75:
        _corroborate(event_id, "sensor_cross_check", 1)

    # Source 3: SLA milestone / delivery confirmation (50 % chance)
    if random.random() < 0.50:
        _corroborate(event_id, "sla_milestone", 1)

    # Simulated time offset (hours until finality decision)
    hours_elapsed = random.uniform(0.5, 25.0)
    _promote_or_dispute(event_id, event_time, hours_elapsed)

    return _LEDGER[event_id]


# ── Public API ────────────────────────────────────────────────────────────────

def run_finality_protocol(accepted_events: List[Dict], merkle_root: str) -> List[Dict]:
    """
    For each accepted event:
      1. Write PROVISIONAL to ledger
      2. Simulate corroboration
      3. Promote to FINAL or DISPUTED
    Returns a list of timeline records.
    """
    _LEDGER.clear()
    timeline = []

    for ev in accepted_events:
        eid   = ev["eventID"]
        etime = ev["eventTime"]

        # Stage 1 — Provisional write
        _write_provisional(eid, merkle_root, etime)

        # Stage 2 — Corroboration + finality
        entry = _simulate_corroboration(eid, etime)

        timeline.append({
            "eventID":             eid,
            "eventTime":           etime,
            "city":                ev["city"],
            "provisionalAt":       entry["provisionalAt"],
            "finalAt":             entry["finalAt"],
            "status":              entry["status"],
            "corroboration_score": entry["corroboration_score"],
            "corroboration_sources": entry["corroboration_sources"],
        })

    return timeline


def finality_summary(timeline: List[Dict]) -> Dict:
    """Aggregate stats over the finality timeline."""
    total      = len(timeline)
    final      = sum(1 for r in timeline if r["status"] == "FINAL")
    provisional = sum(1 for r in timeline if r["status"] == "PROVISIONAL")
    disputed   = sum(1 for r in timeline if r["status"] == "DISPUTED")

    # Average provisional→final delay (hours)
    delays = []
    for r in timeline:
        if r["status"] == "FINAL" and r["finalAt"]:
            t0 = datetime.strptime(r["provisionalAt"], "%Y-%m-%dT%H:%M:%SZ")
            t1 = datetime.strptime(r["finalAt"],       "%Y-%m-%dT%H:%M:%SZ")
            delays.append((t1 - t0).total_seconds() / 3600)

    avg_delay = round(sum(delays) / len(delays), 2) if delays else 0.0

    return {
        "total":       total,
        "final":       final,
        "provisional": provisional,
        "disputed":    disputed,
        "avg_finality_hours": avg_delay,
        "final_pct":   round(final / total * 100, 1) if total else 0,
    }


if __name__ == "__main__":
    dummy = [
        {"eventID": f"EVT-{i:03d}", "eventTime": "2026-06-04T10:00:00Z", "city": "Delhi"}
        for i in range(10)
    ]
    tl  = run_finality_protocol(dummy, merkle_root="abc123fake")
    summ = finality_summary(tl)
    print(summ)
    for t in tl[:5]:
        print(f"  {t['eventID']} → {t['status']}  (corr={t['corroboration_score']})")
