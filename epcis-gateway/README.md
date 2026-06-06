# Standards-Native EPCIS Attestation Edge Gateway
### with Adaptive Pre-Commit Anomaly Gating, Conditional Finality, and Verifiable 3D/Digital-Twin Visualization

**Patent Application No. 202611067289**  
*Pharma Cold Chain Simulation — Chandigarh → Delhi → Mumbai*

---

## Abstract

Existing blockchain-based supply chain systems suffer from a fundamental "garbage-in, garbage-out" problem: once malformed or fraudulent event data is written to an immutable ledger, it cannot be corrected. This system introduces a standards-native edge gateway that intercepts, validates, and cryptographically attests EPCIS 2.0 events *before* they are committed to any distributed ledger. Six novel modules work in pipeline to ensure that only cryptographically verified, corroborated events ever reach the blockchain.

---

## What is EPCIS 2.0?

**EPCIS** (Electronic Product Code Information Services) is a GS1 standard that enables trading partners to share supply chain visibility data. Version 2.0 adds JSON-LD support, sensor data extensions, and richer business context vocabularies (CBV). It answers four core questions about any physical object:

| Question | EPCIS Field |
|----------|-------------|
| **What** was observed? | `epcList` (SGTIN URN) |
| **When** did it happen? | `eventTime` |
| **Where** did it occur? | `bizLocation` (GLN URN) |
| **Why** (business context)? | `bizStep` (CBV URI) |

Without a standards-native gateway, each trading partner can write any data they claim to be EPCIS — there is no enforcement of format, sensor plausibility, or sequence integrity.

---

## The "Garbage-In, Garbage-Out" Problem

```
Trading Partner A                    Blockchain
  ┌──────────────┐                  ┌────────────────────────────┐
  │ Temp: 32°C   │ ─── writes ───►  │ EVT-042: TEMP=32°C  [FINAL]│
  │ (cold chain  │                  │ (immutable, cannot remove) │
  │  violation)  │                  └────────────────────────────┘
  └──────────────┘
         ▲
         │ Nobody checked this before writing!
```

This gateway solves the problem by inserting a validation layer *before* the blockchain write:

```
Event → [Normalize] → [Gate/Score] → [Merkle Proof] → [Conditional Commit] → Blockchain
                            │
                    QUARANTINE (never written)
                    CHALLENGE  (held for review)
                    ACCEPT     (proceed to chain)
```

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                 EPCIS ATTESTATION EDGE GATEWAY                      │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ MODULE 1 │   │ MODULE 2 │   │ MODULE 3 │   │ MODULE 4 │        │
│  │ Generate │──►│Normalize │──►│  Gate &  │──►│  Merkle  │        │
│  │  Events  │   │  GS1/CBV │   │  Score   │   │  Proof   │        │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘        │
│                                      │               │             │
│                                   QUARANTINE    ┌──────────┐       │
│                                   CHALLENGE     │ MODULE 5 │       │
│                                                 │Conditional│      │
│                                                 │ Finality  │      │
│                                                 └──────────┘       │
│                                                      │             │
│                                               ┌──────────┐         │
│                                               │ MODULE 6 │         │
│                                               │Dashboard │         │
│                                               └──────────┘         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6 Novel Features

### 1. Edge Anomaly Gating Engine (`anomaly/gating.py`)

Scores each EPCIS event 0.0–1.0 based on multiple risk factors evaluated at the edge, before any network write:

| Risk Factor | Score Contribution | Rationale |
|-------------|-------------------|-----------|
| Temperature out of cold-chain range | +0.40–0.55 | Pharma efficacy breach |
| GPS outside India bounding box | +0.50 | Physical impossibility |
| GPS jump > 600 km between events | +0.30–0.50 | Teleportation detection |
| Timestamp not sequential | +0.30 | Replay/tamper attack |
| Unknown partner GLN | +0.40 | Unauthorised partner |
| Vibration spike | +0.20–0.35 | Rough handling |

**Gating decisions:**
- Score `< 0.3` → **ACCEPT** — passes to Merkle + blockchain queue
- Score `0.3–0.6` → **CHALLENGE** — held in corroboration queue
- Score `> 0.6` → **QUARANTINE** — permanently blocked

### 2. GS1/CBV Normalization Module (`normalization/normalizer.py`)

Three trading partners use incompatible identifier formats:

```
Partner A (internal):  PROD-1234
                           ↓  normalize
                       urn:epc:id:sgtin:0614141.107346.2017

Partner B (EAN-13):    5901234123457
                           ↓  normalize
                       urn:epc:id:sgtin:0614143.12345.3001

Partner C (GS1 URN):   urn:epc:id:sgtin:0614145.107346.2017
                           ↓  validate
                       urn:epc:id:sgtin:0614145.107346.2017  (unchanged)
```

Without normalisation, cross-partner queries fail silently — events for the same physical item appear to be different objects.

### 3. Conditional Finality Protocol (`finality/finality.py`)

Two-stage blockchain commitment prevents premature finalisation:

```
Stage 1 — PROVISIONAL:
  Event accepted by gateway
  └─► Merkle root written to ledger
  └─► Status: PROVISIONAL

Stage 2 — Corroboration sources:
  a) Partner co-attestation received     → +1
  b) Sensor data matches reported values → +1
  c) SLA milestone confirmed             → +1

  Score ≥ 2  → promoted to FINAL
  Score < 2 after timeout → DISPUTED
```

### 4. Secure Merkle Proof Generator (`merkle/merkle.py`)

Each accepted event receives a cryptographic proof bundle:

```json
{
  "eventID": "EVT-001",
  "eventHash": "sha256(canonical_event_json)",
  "merkleRoot": "root_of_all_accepted_events",
  "proofPath": [
    {"hash": "sibling_hash", "direction": "right"},
    ...
  ],
  "signature": "hmac_sha256(eventHash + merkleRoot, gateway_key)",
  "timestamp": "2026-06-04T10:30:00Z"
}
```

Verification is deterministic: walk the proof path, recompute the root, compare signatures. Any tamper to the event data produces a different hash and fails verification.

### 5. Proof-First Visualization Engine (`dashboard/visualize.py`)

The dashboard **only displays events that have a verified cryptographic proof**. There is no "trust me" data — every metric shown is backed by a Merkle proof bundle. Panels include:

- Pipeline flow diagram
- Gating decision donut chart
- Risk score histogram with threshold markers
- Per-event status table (first 18 events)
- Conditional finality bar chart
- Merkle proof verification grid
- KPI summary panel
- GPS route scatter (coloured by decision)
- GS1 normalization results

### 6. Integrated Corroboration Sensor Suite

Simulated sensor corroboration sources:
- **Partner attestation** — co-signing by the receiving partner (simulated 70% rate)
- **Sensor cross-check** — IoT sensor data matches the event payload (75% rate)
- **SLA milestone** — delivery confirmation from logistics system (50% rate)

---

## Project Structure

```
epcis-attestation-edge-gateway/
├── main.py                   ← Single-command pipeline runner
├── README.md
├── events/
│   └── generator.py          ← EPCIS 2.0 event generator + anomaly injector
├── normalization/
│   └── normalizer.py         ← GS1/CBV multi-format normalizer
├── anomaly/
│   └── gating.py             ← Risk scoring + gating logic
├── merkle/
│   └── merkle.py             ← SHA-256 Merkle tree + proof generator/verifier
├── finality/
│   └── finality.py           ← Conditional finality protocol (simulated ledger)
├── dashboard/
│   └── visualize.py          ← Matplotlib proof-first dashboard
├── tests/
│   └── test_all.py           ← 25 unit tests (all modules)
└── data/                     ← Generated at runtime
    ├── events.json
    ├── proof_bundles.json
    └── dashboard.png
```

---

## Results

| Metric | Value |
|--------|-------|
| Total events processed | 100 |
| Events accepted (→ blockchain) | 80 |
| Events challenged (→ review) | 16 |
| Events quarantined (→ blocked) | 4 |
| **Bad data blocked before chain write** | **20.0%** |
| Anomaly detection precision | 75.0% |
| Anomaly detection recall | **100.0%** |
| F1 Score | 0.857 |
| Valid Merkle proofs accepted | 5/5 (100%) |
| Tampered proofs rejected | 3/3 (100%) |
| Events promoted to FINAL | ~81% |
| Avg provisional → final time | ~12 hours |

*Zero false negatives — every injected anomaly was caught.*

---

## Comparison vs Prior Art

| Feature | Traditional EPCIS | Blockchain-Only | **This System** |
|---------|------------------|-----------------|-----------------|
| Pre-commit validation | ✗ | ✗ | ✅ Edge gating |
| Risk scoring | ✗ | ✗ | ✅ 0.0–1.0 per event |
| Bad data blocked before write | ✗ | ✗ | ✅ 20%+ blocked |
| Merkle proofs per event | ✗ | Partial | ✅ Every event |
| Conditional finality | ✗ | ✗ | ✅ Corroboration-gated |
| Multi-partner normalisation | Manual | Manual | ✅ Automated |
| Sensor corroboration | ✗ | ✗ | ✅ 3 sources |
| Proof-first dashboard | ✗ | ✗ | ✅ Verified-only UI |
| GS1 EPCIS 2.0 native | Partial | ✗ | ✅ Full compliance |
| Real-time anomaly detection | ✗ | ✗ | ✅ Edge scoring |
| Cold-chain monitoring | ✗ | ✗ | ✅ Temp + GPS + vibe |
| Tamper detection | ✗ | Hash-only | ✅ Proof + signature |
| Disputed state handling | ✗ | ✗ | ✅ Auto-flag |
| Recall risk reduction | ✗ | ✗ | ✅ Anomalies pre-blocked |
| Timestamp integrity | ✗ | ✗ | ✅ Sequence validation |
| Unknown partner detection | ✗ | ✗ | ✅ GLN whitelist |

---

## Installation & Running

```bash
# Install dependencies
pip install matplotlib pandas

# Run the complete pipeline (generates all outputs in one shot)
python main.py

# Run unit tests independently
python tests/test_all.py
```

**Outputs produced by one run:**
- Console: full module-by-module report with all metrics
- `data/events.json` — 100 simulated EPCIS 2.0 events
- `data/proof_bundles.json` — Merkle proof for every accepted event
- `data/dashboard.png` — 9-panel proof-first visualization

---

## Future Scope

1. **Real hardware gateway** — Deploy on ARM edge device (Raspberry Pi / Jetson) at warehouse dock doors
2. **Hyperledger Fabric integration** — Replace the local dict ledger with actual Fabric channel commits
3. **Pharma cold chain deployment** — Full GDP (Good Distribution Practice) compliance mode with audit trail export
4. **ECDSA signatures** — Replace HMAC with proper asymmetric key pairs per gateway node
5. **3D Digital Twin** — Integrate GPS timeline with Three.js shipment visualisation
6. **ML anomaly model** — Replace rule-based scoring with a trained LSTM on historical route patterns
7. **W3C Verifiable Credentials** — Wrap proof bundles as VCs for interoperability with identity ecosystems

---

## Patent Information

**Patent Application No.:** 202611067289  
**Title:** Standards-Native EPCIS Attestation Edge Gateway with Adaptive Pre-Commit Anomaly Gating, Conditional Finality, and Verifiable 3D/Digital-Twin Visualization  
**Jurisdiction:** India (Controller General of Patents, Designs & Trade Marks)

---

*This simulation uses only Python standard library + matplotlib + pandas. No external blockchain node, no cloud services, no API keys required.*
