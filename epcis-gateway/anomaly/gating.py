"""
MODULE 3 — Adaptive Anomaly Gating Engine
Scores each EPCIS event 0.0–1.0 and gates it:
  < 0.3  → ACCEPT
  0.3–0.6 → CHALLENGE
  > 0.6  → QUARANTINE
"""

import math
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# ── Thresholds ────────────────────────────────────────────────────────────────
COLD_CHAIN_TEMP_MIN = 2.0    # °C
COLD_CHAIN_TEMP_MAX = 8.0    # °C
VIBRATION_MAX      = 0.10    # g-force

# Known valid GLNs (whitelist)
KNOWN_GLNS = {
    "urn:epc:id:sgln:0614141.00729.0",
    "urn:epc:id:sgln:0614142.00100.0",
    "urn:epc:id:sgln:0614143.00500.0",
    "urn:epc:id:sgln:0614144.00800.0",
    "urn:epc:id:sgln:0614145.01200.0",
}

# Expected India bounding box
INDIA_LAT_MIN, INDIA_LAT_MAX = 8.0,  37.0
INDIA_LNG_MIN, INDIA_LNG_MAX = 68.0, 97.5

# Route waypoint sequence (ordered lat/lng)
ROUTE_WAYPOINTS = [
    (30.7333, 76.7794),   # Chandigarh
    (30.3782, 76.7767),   # Ambala
    (28.6139, 77.2090),   # Delhi
    (18.5204, 73.8567),   # Pune
    (19.0760, 72.8777),   # Mumbai
]
MAX_STEP_KM = 600.0       # max reasonable km between consecutive events


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def score_event(
    event: Dict,
    prev_event: Optional[Dict] = None,
) -> Tuple[float, List[str]]:
    """
    Returns (risk_score, [reasons]) for a single EPCIS event.
    Scores are CAPPED at 1.0.
    """
    score = 0.0
    reasons: List[str] = []
    sensor = event.get("sensorData", {})

    # ── Temperature ──────────────────────────────────────────────────────────
    temp = sensor.get("temperature", 5.0)
    if not (COLD_CHAIN_TEMP_MIN <= temp <= COLD_CHAIN_TEMP_MAX):
        delta = max(abs(temp - COLD_CHAIN_TEMP_MAX), abs(temp - COLD_CHAIN_TEMP_MIN))
        contrib = min(0.4 + delta * 0.01, 0.55)
        score += contrib
        reasons.append(f"Temp {temp}°C out of range [{COLD_CHAIN_TEMP_MIN},{COLD_CHAIN_TEMP_MAX}] (+{contrib:.2f})")

    # ── GPS impossible location ───────────────────────────────────────────────
    gps = sensor.get("gps", {})
    lat, lng = gps.get("lat", 20.0), gps.get("lng", 77.0)
    if not (INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX and INDIA_LNG_MIN <= lng <= INDIA_LNG_MAX):
        score += 0.5
        reasons.append(f"GPS ({lat:.4f},{lng:.4f}) outside India (+0.50)")

    # ── GPS jump from previous event ─────────────────────────────────────────
    if prev_event:
        prev_gps  = prev_event.get("sensorData", {}).get("gps", {})
        prev_lat  = prev_gps.get("lat", lat)
        prev_lng  = prev_gps.get("lng", lng)
        dist_km   = _haversine_km(prev_lat, prev_lng, lat, lng)
        if dist_km > MAX_STEP_KM:
            contrib = min(0.3 + dist_km / 10000, 0.5)
            score += contrib
            reasons.append(f"Location jump {dist_km:.0f} km in one step (+{contrib:.2f})")

    # ── Timestamp out of sequence ─────────────────────────────────────────────
    if prev_event:
        try:
            t_curr = datetime.strptime(event["eventTime"], "%Y-%m-%dT%H:%M:%SZ")
            t_prev = datetime.strptime(prev_event["eventTime"], "%Y-%m-%dT%H:%M:%SZ")
            if t_curr <= t_prev:
                score += 0.3
                reasons.append("Timestamp not after previous event (+0.30)")
        except (KeyError, ValueError):
            score += 0.15
            reasons.append("Unparseable timestamp (+0.15)")

    # ── Unknown partner GLN ───────────────────────────────────────────────────
    gln = event.get("bizLocation", "")
    if gln not in KNOWN_GLNS:
        score += 0.4
        reasons.append(f"Unknown GLN '{gln}' (+0.40)")

    # ── Vibration spike ───────────────────────────────────────────────────────
    vib = sensor.get("vibration", 0.02)
    if vib > VIBRATION_MAX:
        contrib = min(0.2 + (vib - VIBRATION_MAX) * 2, 0.35)
        score += contrib
        reasons.append(f"Vibration {vib:.3f}g exceeds {VIBRATION_MAX}g (+{contrib:.2f})")

    final_score = min(round(score, 4), 1.0)
    return final_score, reasons


def gate(score: float) -> str:
    if score < 0.3:
        return "ACCEPT"
    elif score <= 0.6:
        return "CHALLENGE"
    else:
        return "QUARANTINE"


def run_anomaly_gating(events: List[Dict]) -> List[Dict]:
    """
    Process a list of EPCIS events, return enriched dicts with
    risk_score, decision, reasons.
    """
    results = []
    prev_event = None

    for ev in events:
        risk, reasons = score_event(ev, prev_event)
        decision = gate(risk)
        results.append({
            "eventID":    ev["eventID"],
            "eventTime":  ev["eventTime"],
            "city":       ev["_meta"]["city"],
            "risk_score": risk,
            "decision":   decision,
            "reasons":    reasons,
            "is_anomaly": ev["_meta"]["is_anomaly"],
            "anomaly_type": ev["_meta"]["anomaly_type"],
            "raw_event":  ev,
        })
        prev_event = ev

    return results


def compute_metrics(gated: List[Dict]) -> Dict:
    """Precision, recall, F1 on anomaly detection."""
    tp = sum(1 for r in gated if r["is_anomaly"] and r["decision"] != "ACCEPT")
    fp = sum(1 for r in gated if not r["is_anomaly"] and r["decision"] != "ACCEPT")
    fn = sum(1 for r in gated if r["is_anomaly"] and r["decision"] == "ACCEPT")
    tn = sum(1 for r in gated if not r["is_anomaly"] and r["decision"] == "ACCEPT")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "precision": round(precision, 4),
        "recall":    round(recall, 4),
        "f1_score":  round(f1, 4),
        "total":     len(gated),
        "accepted":  sum(1 for r in gated if r["decision"] == "ACCEPT"),
        "challenged":  sum(1 for r in gated if r["decision"] == "CHALLENGE"),
        "quarantined": sum(1 for r in gated if r["decision"] == "QUARANTINE"),
    }


if __name__ == "__main__":
    from events.generator import generate_events
    evts   = generate_events()
    gated  = run_anomaly_gating(evts)
    mets   = compute_metrics(gated)
    print(f"Precision={mets['precision']}  Recall={mets['recall']}  F1={mets['f1_score']}")
    for r in gated[:10]:
        print(f"  {r['eventID']} | {r['risk_score']:.3f} | {r['decision']:12s} | {r['reasons']}")
