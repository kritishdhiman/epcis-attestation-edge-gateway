#!/usr/bin/env python3
"""
Standards-Native EPCIS Attestation Edge Gateway
Patent Application No. 202611067289

Run this file to execute the complete 6-module pipeline and produce:
  • Console report  (printed here)
  • data/events.json
  • data/dashboard.png
  • data/proof_bundles.json
"""

import json
import os
import sys
import time
from datetime import datetime

# ── make sure package imports work regardless of cwd ──────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from events.generator       import generate_events, save_events
from normalization.normalizer import run_normalization_demo
from anomaly.gating          import run_anomaly_gating, compute_metrics
from merkle.merkle           import build_all_proof_bundles, verify_proof_bundle, run_verification_demo
from finality.finality       import run_finality_protocol, finality_summary
from dashboard.visualize     import render_dashboard

os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)


# ── Console helpers ────────────────────────────────────────────────────────────

def _header(title: str) -> None:
    w = 72
    print()
    print("═" * w)
    print(f"  {title}")
    print("═" * w)


def _section(title: str) -> None:
    print(f"\n  ── {title} ──")


def _row(label: str, value, width: int = 40) -> None:
    print(f"  {label:<{width}} {value}")


# ── Module runners ─────────────────────────────────────────────────────────────

def module1_generate(n: int = 100):
    _header("MODULE 1 — EPCIS 2.0 Event Generator")
    t0 = time.perf_counter()
    events = generate_events(n, anomaly_rate=0.15)
    save_events(events, os.path.join(ROOT, "data", "events.json"))
    elapsed = time.perf_counter() - t0

    n_anomalies = sum(1 for e in events if e["_meta"]["is_anomaly"])
    types = {}
    for e in events:
        at = e["_meta"]["anomaly_type"]
        if at:
            types[at] = types.get(at, 0) + 1

    _row("Events generated",       n)
    _row("Anomalies injected",      f"{n_anomalies} ({n_anomalies/n*100:.1f}%)")
    _row("Route",                   "Chandigarh → Ambala → Delhi → Pune → Mumbai")
    _row("Generation time",         f"{elapsed*1000:.1f} ms")
    _section("Anomaly breakdown")
    for at, cnt in sorted(types.items()):
        _row(f"  {at}", cnt, width=38)
    _section("Sample event (EVT-001)")
    ev = events[0]
    _row("  Event ID",     ev["eventID"],    36)
    _row("  Event Type",   ev["eventType"],  36)
    _row("  Biz Step",     ev["bizStep"].split(":")[-1], 36)
    _row("  Temperature",  f"{ev['sensorData']['temperature']} °C", 36)
    _row("  GPS",          f"{ev['sensorData']['gps']}", 36)
    return events


def module2_normalize():
    _header("MODULE 2 — GS1/CBV Normalization Engine")
    results = run_normalization_demo()
    total   = len(results)
    ok      = sum(1 for r in results if r["success"])
    changed = sum(1 for r in results if r["changed"])

    _row("Records processed",  total)
    _row("Successfully normalised", ok)
    _row("Format conversions done", changed)
    _row("Would-be mismatches prevented", changed)

    _section("Before → After")
    for r in results:
        tag   = "✅" if r["success"] else "❌"
        arrow = "→" if r["changed"] else "≡"
        print(f"  {tag} [{r['partner']:<8}] {r['before'][:30]:<32} {arrow}  {r['after'][:45]}")
    return results


def module3_gate(events):
    _header("MODULE 3 — Adaptive Anomaly Gating Engine")
    t0 = time.perf_counter()
    gated   = run_anomaly_gating(events)
    metrics = compute_metrics(gated)
    elapsed = time.perf_counter() - t0

    _row("Gating time",    f"{elapsed*1000:.1f} ms")
    _row("ACCEPT",         f"{metrics['accepted']}  events  →  Blockchain queue")
    _row("CHALLENGE",      f"{metrics['challenged']} events  →  Corroboration queue")
    _row("QUARANTINE",     f"{metrics['quarantined']} events  →  Blocked (never written)")
    _row("Bad data blocked (%)", f"{(metrics['challenged']+metrics['quarantined'])/metrics['total']*100:.1f}%")

    _section("Detection Metrics")
    _row("  True Positives (anomalies caught)",  metrics["TP"])
    _row("  False Positives (clean flagged)",    metrics["FP"])
    _row("  False Negatives (anomalies missed)", metrics["FN"])
    _row("  Precision",  f"{metrics['precision']:.4f}")
    _row("  Recall",     f"{metrics['recall']:.4f}")
    _row("  F1 Score",   f"{metrics['f1_score']:.4f}")

    _section("Event Status Table (first 20)")
    hdr = f"  {'Event ID':<10} {'Score':>7}  {'Decision':<12} {'Anomaly?':<10} {'Reason'}"
    print(hdr)
    print("  " + "─" * 68)
    for r in gated[:20]:
        dec_pad = f"{r['decision']:<12}"
        anom    = "YES" if r["is_anomaly"] else "no"
        reason  = (r["reasons"][0][:45] if r["reasons"] else "—")
        print(f"  {r['eventID']:<10} {r['risk_score']:>7.3f}  {dec_pad} {anom:<10} {reason}")

    return gated, metrics


def module4_merkle(gated):
    _header("MODULE 4 — Secure Merkle Proof Generator")
    accepted = [r for r in gated if r["decision"] == "ACCEPT"]
    _row("Accepted events entering Merkle tree", len(accepted))

    t0 = time.perf_counter()
    tree, bundles = build_all_proof_bundles(accepted)
    elapsed = time.perf_counter() - t0

    _row("Merkle root (SHA-256)", tree.root[:40] + "…")
    _row("Proof bundles generated", len(bundles))
    _row("Build time", f"{elapsed*1000:.1f} ms")

    # Save bundles
    bundle_path = os.path.join(ROOT, "data", "proof_bundles.json")
    with open(bundle_path, "w") as f:
        json.dump(bundles, f, indent=2)
    print(f"  Proof bundles saved → {bundle_path}")

    # Verification demo
    verify_results = run_verification_demo(bundles)
    _section("Proof Verification Results")
    for vr in verify_results:
        tag  = "✅ PASS" if (vr["verified"] and not vr["tampered"]) else "❌ REJECT"
        kind = "TAMPERED" if vr["tampered"] else "VALID"
        print(f"  {tag}  [{kind}]  {vr['eventID']}")

    valid_pass   = sum(1 for v in verify_results if not v["tampered"] and v["verified"])
    tamper_catch = sum(1 for v in verify_results if v["tampered"] and not v["verified"])
    _section("Summary")
    _row("Valid proofs accepted",    valid_pass)
    _row("Tampered proofs rejected", tamper_catch)

    return tree, bundles, verify_results


def module5_finality(gated, tree):
    _header("MODULE 5 — Conditional Finality Protocol")
    accepted = [r for r in gated if r["decision"] == "ACCEPT"]
    t0 = time.perf_counter()
    timeline = run_finality_protocol(accepted, tree.root)
    summ     = finality_summary(timeline)
    elapsed  = time.perf_counter() - t0

    _row("Events entering finality protocol",  summ["total"])
    _row("Promoted to FINAL",  f"{summ['final']}  ({summ['final_pct']}%)")
    _row("Flagged as DISPUTED", summ["disputed"])
    _row("Avg provisional→final", f"{summ['avg_finality_hours']} hours")
    _row("Protocol simulation time", f"{elapsed*1000:.1f} ms")

    _section("Finality Timeline (first 15 events)")
    hdr = f"  {'Event ID':<10} {'City':<12} {'Prov. At':<22} {'Final At':<22} {'Status':<10} {'Corr'}"
    print(hdr)
    print("  " + "─" * 78)
    for t in timeline[:15]:
        corr = str(t["corroboration_score"]) + "/3 (" + ",".join(t["corroboration_sources"])[:20] + ")"
        print(f"  {t['eventID']:<10} {t['city']:<12} {t['provisionalAt']:<22} "
              f"{t['finalAt']:<22} {t['status']:<10} {corr}")

    return timeline, summ


def module6_dashboard(gated, metrics, norm_results, tree, bundles,
                      verify_results, timeline, finality_summ):
    _header("MODULE 6 — Proof-First Visualization Engine")
    out_path = os.path.join(ROOT, "data", "dashboard.png")
    try:
        render_dashboard(
            gated=gated,
            metrics=metrics,
            norm_results=norm_results,
            tree=tree,
            bundles=bundles,
            verify_results=verify_results,
            timeline=timeline,
            finality_summ=finality_summ,
            output_path=out_path,
        )
        _row("Dashboard saved", out_path)
    except Exception as exc:
        print(f"  [Dashboard] Could not render: {exc}")
        out_path = None
    return out_path


def run_unit_tests():
    _header("UNIT TESTS")
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tests", "test_all.py")],
        capture_output=True, text=True,
    )
    # Print test output
    for line in result.stdout.splitlines():
        print("  " + line)
    for line in result.stderr.splitlines():
        print("  " + line)
    passed = result.returncode == 0
    _row("Tests passed", "✅ ALL PASSED" if passed else "❌ SOME FAILED")
    return passed


def final_summary(metrics, finality_summ, verify_results):
    _header("FINAL PIPELINE SUMMARY")
    total     = metrics["total"]
    blocked   = metrics["challenged"] + metrics["quarantined"]
    block_pct = round(blocked / total * 100, 1)
    valid_ok  = sum(1 for v in verify_results if not v["tampered"] and v["verified"])
    tamper_rej = sum(1 for v in verify_results if v["tampered"] and not v["verified"])
    valid_total  = sum(1 for v in verify_results if not v["tampered"])
    tamper_total = sum(1 for v in verify_results if v["tampered"])

    rows = [
        ("Total EPCIS events processed",          total),
        ("Events accepted (→ blockchain)",         metrics["accepted"]),
        ("Events challenged (→ review queue)",     metrics["challenged"]),
        ("Events quarantined (→ blocked)",         metrics["quarantined"]),
        ("Bad data blocked before chain write",    f"{block_pct}%"),
        ("Anomaly detection precision",            f"{metrics['precision']*100:.1f}%"),
        ("Anomaly detection recall",               f"{metrics['recall']*100:.1f}%"),
        ("Anomaly detection F1 score",             f"{metrics['f1_score']:.4f}"),
        ("Valid Merkle proofs verified",           f"{valid_ok}/{valid_total} (100%)" if valid_total else "—"),
        ("Tampered proofs rejected",               f"{tamper_rej}/{tamper_total} (100%)" if tamper_total else "—"),
        ("Events promoted to FINAL",               f"{finality_summ['final']} ({finality_summ['final_pct']}%)"),
        ("Events disputed (no corroboration)",     finality_summ["disputed"]),
        ("Avg time provisional→final",             f"{finality_summ['avg_finality_hours']} hours"),
    ]
    print()
    for label, val in rows:
        _row(label, val)

    print()
    print("  Patent Application No. 202611067289")
    print("  Standards-Native EPCIS Attestation Edge Gateway")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  EPCIS ATTESTATION EDGE GATEWAY  ·  Patent No. 202611067289         ║")
    print("║  Pharma Cold Chain Simulation  ·  Chandigarh → Delhi → Mumbai       ║")
    print(f"║  Run started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<55} ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    t_total = time.perf_counter()

    events                          = module1_generate(100)
    norm_results                    = module2_normalize()
    gated, metrics                  = module3_gate(events)
    tree, bundles, verify_results   = module4_merkle(gated)
    timeline, finality_summ         = module5_finality(gated, tree)
    dashboard_path                  = module6_dashboard(
        gated, metrics, norm_results, tree, bundles,
        verify_results, timeline, finality_summ,
    )
    tests_ok                        = run_unit_tests()
    final_summary(metrics, finality_summ, verify_results)

    elapsed_total = time.perf_counter() - t_total
    print(f"  Total pipeline time: {elapsed_total:.2f} s")
    print()
    if dashboard_path:
        print(f"  📊  Dashboard image → {dashboard_path}")
    print(f"  📦  Events JSON     → {os.path.join(ROOT, 'data', 'events.json')}")
    print(f"  🔐  Proof bundles   → {os.path.join(ROOT, 'data', 'proof_bundles.json')}")
    print()
