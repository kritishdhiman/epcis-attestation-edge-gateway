"""
MODULE 1 — EPCIS Event Generator
Simulates realistic supply chain events in EPCIS 2.0 JSON format
for a pharma cold chain: Chandigarh → Delhi → Mumbai
Injects 15% anomalous events for testing the gating engine.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any


# ── Route definition ──────────────────────────────────────────────────────────
ROUTE = [
    {
        "city": "Chandigarh",
        "lat": 30.7333, "lng": 76.7794,
        "gln": "urn:epc:id:sgln:0614141.00729.0",
        "company": "PharmaSource Ltd",
    },
    {
        "city": "Ambala",
        "lat": 30.3782, "lng": 76.7767,
        "gln": "urn:epc:id:sgln:0614142.00100.0",
        "company": "ColdHub Ambala",
    },
    {
        "city": "Delhi",
        "lat": 28.6139, "lng": 77.2090,
        "gln": "urn:epc:id:sgln:0614143.00500.0",
        "company": "MediTrans Delhi",
    },
    {
        "city": "Pune",
        "lat": 18.5204, "lng": 73.8567,
        "gln": "urn:epc:id:sgln:0614144.00800.0",
        "company": "PharmaHub Pune",
    },
    {
        "city": "Mumbai",
        "lat": 19.0760, "lng": 72.8777,
        "gln": "urn:epc:id:sgln:0614145.01200.0",
        "company": "CityPharma Mumbai",
    },
]

BIZ_STEPS = [
    "urn:epcglobal:cbv:bizstep:shipping",
    "urn:epcglobal:cbv:bizstep:receiving",
    "urn:epcglobal:cbv:bizstep:storing",
    "urn:epcglobal:cbv:bizstep:transporting",
    "urn:epcglobal:cbv:bizstep:loading",
]

ANOMALY_TYPES = [
    "temperature_spike",
    "location_jump",
    "timestamp_tamper",
    "fake_partner",
]


def _make_epc() -> str:
    company = "0614141"
    item = "107346"
    serial = str(random.randint(1000, 9999))
    return f"urn:epc:id:sgtin:{company}.{item}.{serial}"


def _normal_event(
    event_id: str,
    seq: int,
    base_time: datetime,
    location: Dict,
) -> Dict[str, Any]:
    """Build a clean, in-spec EPCIS 2.0 event."""
    event_time = base_time + timedelta(minutes=seq * 15)
    # Small GPS jitter around the waypoint
    lat = location["lat"] + random.uniform(-0.05, 0.05)
    lng = location["lng"] + random.uniform(-0.05, 0.05)
    return {
        "eventID": event_id,
        "eventType": "ObjectEvent",
        "eventTime": event_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eventTimeZoneOffset": "+05:30",
        "epcList": [_make_epc()],
        "action": random.choice(["OBSERVE", "ADD", "DELETE"]),
        "bizStep": random.choice(BIZ_STEPS),
        "bizLocation": location["gln"],
        "readPoint": location["gln"],
        "sensorData": {
            "temperature": round(random.uniform(2.0, 8.0), 2),   # cold-chain OK
            "humidity": round(random.uniform(40.0, 60.0), 2),
            "gps": {"lat": round(lat, 6), "lng": round(lng, 6)},
            "doorOpen": random.choice([False, False, False, True]),
            "vibration": round(random.uniform(0.01, 0.05), 3),
        },
        "_meta": {
            "is_anomaly": False,
            "anomaly_type": None,
            "city": location["city"],
        },
    }


def _inject_anomaly(event: Dict, anomaly_type: str, seq: int, base_time: datetime) -> Dict:
    """Mutate a clean event to simulate a specific anomaly."""
    event = json.loads(json.dumps(event))        # deep-copy
    event["_meta"]["is_anomaly"] = True
    event["_meta"]["anomaly_type"] = anomaly_type

    if anomaly_type == "temperature_spike":
        event["sensorData"]["temperature"] = round(random.uniform(25.0, 35.0), 2)

    elif anomaly_type == "location_jump":
        # Teleport to a completely impossible location (e.g., overseas)
        event["sensorData"]["gps"] = {"lat": 51.5074, "lng": -0.1278}   # London

    elif anomaly_type == "timestamp_tamper":
        # Roll back the timestamp to before the base time
        fake_time = base_time - timedelta(hours=random.randint(2, 48))
        event["eventTime"] = fake_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    elif anomaly_type == "fake_partner":
        event["bizLocation"] = "urn:epc:id:sgln:UNKNOWN.99999.0"
        event["readPoint"]   = "urn:epc:id:sgln:UNKNOWN.99999.0"

    return event


def generate_events(n: int = 100, anomaly_rate: float = 0.15) -> List[Dict]:
    """
    Generate `n` EPCIS 2.0 events along the cold-chain route.
    `anomaly_rate` fraction will be injected anomalies.
    """
    random.seed(42)
    base_time = datetime(2026, 6, 4, 6, 0, 0)
    events: List[Dict] = []
    n_anomalies = int(n * anomaly_rate)
    anomaly_indices = set(random.sample(range(n), n_anomalies))

    # Distribute events across route waypoints
    waypoint_size = n // len(ROUTE)

    for i in range(n):
        event_id = f"EVT-{i+1:03d}"
        waypoint  = ROUTE[min(i // waypoint_size, len(ROUTE) - 1)]
        ev = _normal_event(event_id, i, base_time, waypoint)

        if i in anomaly_indices:
            atype = random.choice(ANOMALY_TYPES)
            ev = _inject_anomaly(ev, atype, i, base_time)

        events.append(ev)

    return events


def save_events(events: List[Dict], path: str = "data/events.json") -> None:
    with open(path, "w") as f:
        json.dump(events, f, indent=2)
    print(f"[Generator] Saved {len(events)} events → {path}")


if __name__ == "__main__":
    evts = generate_events()
    save_events(evts, "../data/events.json")
