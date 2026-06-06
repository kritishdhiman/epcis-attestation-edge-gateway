"""
MODULE 6 — Proof-First Visualization Engine
Renders a multi-panel matplotlib dashboard showing the full pipeline.
All data shown is cryptographically verified before display.
"""

import textwrap
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
import numpy as np


# ── Colour palette ─────────────────────────────────────────────────────────────
C = {
    "bg":        "#0D1117",
    "panel":     "#161B22",
    "border":    "#30363D",
    "green":     "#3FB950",
    "yellow":    "#D29922",
    "red":       "#F85149",
    "blue":      "#58A6FF",
    "purple":    "#BC8CFF",
    "text":      "#E6EDF3",
    "subtext":   "#8B949E",
    "ACCEPT":    "#3FB950",
    "CHALLENGE": "#D29922",
    "QUARANTINE":"#F85149",
    "FINAL":     "#3FB950",
    "PROVISIONAL":"#D29922",
    "DISPUTED":  "#F85149",
}

STATUS_EMOJI = {
    "ACCEPT":     "✅",
    "CHALLENGE":  "⚠️",
    "QUARANTINE": "🔴",
    "FINAL":      "✅",
    "PROVISIONAL":"⏳",
    "DISPUTED":   "❌",
}


def _styled_ax(ax, title: str = "") -> None:
    ax.set_facecolor(C["panel"])
    for spine in ax.spines.values():
        spine.set_edgecolor(C["border"])
    ax.tick_params(colors=C["subtext"], labelsize=7)
    if title:
        ax.set_title(title, color=C["text"], fontsize=9, fontweight="bold", pad=6)


# ── Individual panels ──────────────────────────────────────────────────────────

def _panel_pipeline_flow(ax):
    """Arrow diagram of the 6-stage pipeline."""
    _styled_ax(ax, "📦  Pipeline Flow")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2)
    ax.axis("off")

    stages = [
        ("1\nGenerate", C["blue"]),
        ("2\nNormalize", C["purple"]),
        ("3\nGate", C["yellow"]),
        ("4\nMerkle", C["green"]),
        ("5\nFinality", C["blue"]),
        ("6\nVisualize", C["green"]),
    ]
    for i, (label, col) in enumerate(stages):
        x = 0.7 + i * 1.55
        box = FancyBboxPatch((x - 0.55, 0.55), 1.1, 0.9,
                              boxstyle="round,pad=0.1",
                              facecolor=col, alpha=0.25,
                              edgecolor=col, linewidth=1.2)
        ax.add_patch(box)
        ax.text(x, 1.0, label, ha="center", va="center",
                color=col, fontsize=7, fontweight="bold")
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + 0.78, 1.0), xytext=(x + 0.55, 1.0),
                        arrowprops=dict(arrowstyle="->", color=C["subtext"], lw=1.2))


def _panel_gating_pie(ax, metrics: Dict):
    """Donut chart of gating decisions."""
    _styled_ax(ax, "🔍  Gating Decisions")
    labels  = ["Accepted", "Challenged", "Quarantined"]
    values  = [metrics["accepted"], metrics["challenged"], metrics["quarantined"]]
    colours = [C["green"], C["yellow"], C["red"]]
    wedge_props = {"width": 0.55, "edgecolor": C["bg"], "linewidth": 2}
    wedges, _ = ax.pie(values, colors=colours, wedgeprops=wedge_props,
                       startangle=90)
    ax.text(0, 0, f"{metrics['total']}\nevents", ha="center", va="center",
            color=C["text"], fontsize=9, fontweight="bold")
    legend_patches = [mpatches.Patch(color=c, label=f"{l}: {v}")
                      for l, v, c in zip(labels, values, colours)]
    ax.legend(handles=legend_patches, loc="lower center", frameon=False,
              fontsize=7, labelcolor=C["subtext"],
              bbox_to_anchor=(0.5, -0.12), ncol=1)


def _panel_risk_histogram(ax, gated: List[Dict]):
    """Histogram of risk scores coloured by decision."""
    _styled_ax(ax, "📊  Risk Score Distribution")
    bins = np.linspace(0, 1, 21)
    for decision, colour in [("ACCEPT", C["green"]),
                              ("CHALLENGE", C["yellow"]),
                              ("QUARANTINE", C["red"])]:
        scores = [r["risk_score"] for r in gated if r["decision"] == decision]
        ax.hist(scores, bins=bins, color=colour, alpha=0.75, label=decision)
    ax.axvline(0.3, color=C["yellow"], lw=1, ls="--", alpha=0.7)
    ax.axvline(0.6, color=C["red"],    lw=1, ls="--", alpha=0.7)
    ax.set_xlabel("Risk Score", color=C["subtext"], fontsize=7)
    ax.set_ylabel("Count", color=C["subtext"], fontsize=7)
    ax.legend(fontsize=6, frameon=False, labelcolor=C["subtext"])


def _panel_event_table(ax, gated: List[Dict]):
    """Scrollable-style event table (first 18 events)."""
    ax.set_facecolor(C["panel"])
    ax.axis("off")
    ax.set_title("📋  Event Status Board (first 18)",
                 color=C["text"], fontsize=9, fontweight="bold", pad=6)

    headers = ["Event", "City", "Score", "Decision", "Anomaly?"]
    col_x   = [0.01, 0.15, 0.42, 0.58, 0.80]
    row_h   = 0.048
    y_start = 0.96

    # Header row
    ax.axhline(y=y_start - row_h * 0.5, color=C["border"], lw=0.8)
    for hdr, x in zip(headers, col_x):
        ax.text(x, y_start, hdr, color=C["blue"], fontsize=7, fontweight="bold",
                transform=ax.transAxes, va="top")

    rows = gated[:18]
    for i, r in enumerate(rows):
        y = y_start - (i + 1.5) * row_h
        col = C[r["decision"]]
        # Zebra strip
        if i % 2 == 0:
            ax.add_patch(FancyBboxPatch((0, y - row_h * 0.45), 1, row_h * 0.9,
                                        boxstyle="square,pad=0",
                                        facecolor=C["border"], alpha=0.3,
                                        transform=ax.transAxes, clip_on=False))
        vals = [
            r["eventID"],
            r["city"][:10],
            f"{r['risk_score']:.3f}",
            f"{STATUS_EMOJI.get(r['decision'],'')} {r['decision']}",
            "🔴 YES" if r["is_anomaly"] else "✅ NO",
        ]
        for val, x in zip(vals, col_x):
            ax.text(x, y, val, color=col if "decision" in val or "score" in val else C["text"],
                    fontsize=6.5, transform=ax.transAxes, va="center")


def _panel_finality_bar(ax, timeline: List[Dict]):
    """Stacked bar showing finality outcomes."""
    _styled_ax(ax, "⏱  Conditional Finality Outcomes")
    counts = {s: sum(1 for t in timeline if t["status"] == s)
              for s in ("FINAL", "DISPUTED")}
    labels  = list(counts.keys())
    values  = list(counts.values())
    colours = [C[l] for l in labels]
    bars = ax.bar(labels, values, color=colours, alpha=0.8, edgecolor=C["border"], width=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                str(val), ha="center", color=C["text"], fontsize=8)
    ax.set_ylabel("Events", color=C["subtext"], fontsize=7)
    ax.set_ylim(0, max(values) * 1.25 if values else 10)


def _panel_merkle_verify(ax, verify_results: List[Dict]):
    """Visual verification grid."""
    ax.set_facecolor(C["panel"])
    ax.axis("off")
    ax.set_title("🔐  Merkle Proof Verification",
                 color=C["text"], fontsize=9, fontweight="bold", pad=6)

    row_h = 0.13
    for i, r in enumerate(verify_results):
        y = 0.90 - i * row_h
        ok_col   = C["green"] if r["verified"] and not r["tampered"] else C["red"]
        ok_label = "✅ PASS" if (r["verified"] and not r["tampered"]) else \
                   ("❌ REJECT" if r["tampered"] else "⚠ FAIL")
        bg_col   = C["green"] if not r["tampered"] else C["red"]
        ax.add_patch(FancyBboxPatch((0.02, y - row_h * 0.5), 0.96, row_h * 0.85,
                                    boxstyle="round,pad=0.02",
                                    facecolor=bg_col, alpha=0.12,
                                    transform=ax.transAxes))
        ax.text(0.05, y, r["eventID"][:12], color=C["text"], fontsize=7,
                transform=ax.transAxes, va="center")
        ax.text(0.70, y, ok_label, color=ok_col, fontsize=7, fontweight="bold",
                transform=ax.transAxes, va="center")


def _panel_kpi(ax, metrics: Dict, finality_summ: Dict, verify_results: List[Dict]):
    """KPI metrics panel."""
    ax.set_facecolor(C["panel"])
    ax.axis("off")
    ax.set_title("📈  KPI Summary", color=C["text"], fontsize=9, fontweight="bold", pad=6)

    total      = metrics["total"]
    blocked    = metrics["challenged"] + metrics["quarantined"]
    block_pct  = round(blocked / total * 100, 1)
    proof_pct  = round(sum(1 for v in verify_results if v["verified"] and not v["tampered"])
                        / max(len([v for v in verify_results if not v["tampered"]]), 1) * 100, 1)
    reject_pct = round(sum(1 for v in verify_results if v["tampered"] and not v["verified"])
                        / max(len([v for v in verify_results if v["tampered"]]), 1) * 100, 1)

    kpis = [
        ("Total Events Processed",   str(total),                         C["blue"]),
        ("Accepted (→ Blockchain)",  str(metrics["accepted"]),           C["green"]),
        ("Challenged (→ Review)",    str(metrics["challenged"]),         C["yellow"]),
        ("Quarantined (→ Blocked)",  str(metrics["quarantined"]),        C["red"]),
        ("Bad Data Blocked",         f"{block_pct}%",                    C["red"]),
        ("Proof Verification Rate",  f"{proof_pct}%",                    C["green"]),
        ("Tampered Proofs Rejected", f"{reject_pct}%",                   C["green"]),
        ("Detection Precision",      f"{metrics['precision']*100:.1f}%", C["blue"]),
        ("Detection Recall",         f"{metrics['recall']*100:.1f}%",    C["blue"]),
        ("F1 Score",                 f"{metrics['f1_score']:.4f}",       C["purple"]),
        ("Events Reached FINAL",     f"{finality_summ['final_pct']}%",   C["green"]),
        ("Avg Provisional→Final",    f"{finality_summ['avg_finality_hours']}h", C["blue"]),
    ]

    row_h = 0.076
    y = 0.94
    for label, value, colour in kpis:
        ax.text(0.03, y, label, color=C["subtext"], fontsize=7, transform=ax.transAxes, va="center")
        ax.text(0.78, y, value, color=colour, fontsize=8, fontweight="bold",
                transform=ax.transAxes, va="center", ha="right")
        ax.plot([0.03, 0.97], [y - row_h * 0.4, y - row_h * 0.4],
                color=C["border"], lw=0.5, transform=ax.transAxes)
        y -= row_h


def _panel_normalization(ax, norm_results: List[Dict]):
    """Normalization results table."""
    ax.set_facecolor(C["panel"])
    ax.axis("off")
    ax.set_title("🔄  GS1 Normalization Results",
                 color=C["text"], fontsize=9, fontweight="bold", pad=6)

    row_h = 0.10
    y = 0.92
    for r in norm_results:
        ok_col = C["green"] if r["success"] else C["red"]
        tag    = "✅" if r["success"] else "❌"
        before = textwrap.shorten(r["before"], width=22, placeholder="…")
        after  = textwrap.shorten(r["after"],  width=30, placeholder="…")
        ax.text(0.02, y, f"{tag} [{r['partner'][:8]}]", color=ok_col, fontsize=6.5,
                transform=ax.transAxes, va="center", fontweight="bold")
        ax.text(0.02, y - row_h * 0.45, f"  {before}", color=C["subtext"], fontsize=5.5,
                transform=ax.transAxes, va="center")
        ax.text(0.02, y - row_h * 0.85, f"  → {after}", color=C["text"], fontsize=5.5,
                transform=ax.transAxes, va="center")
        ax.axhline(y - row_h, color=C["border"], lw=0.4, xmin=0.02, xmax=0.98)
        y -= row_h * 1.1


# ── Main dashboard entry point ─────────────────────────────────────────────────

def render_dashboard(
    gated:          List[Dict],
    metrics:        Dict,
    norm_results:   List[Dict],
    tree,
    bundles:        List[Dict],
    verify_results: List[Dict],
    timeline:       List[Dict],
    finality_summ:  Dict,
    output_path:    str = "data/dashboard.png",
) -> None:
    fig = plt.figure(figsize=(22, 16), facecolor=C["bg"])
    fig.suptitle(
        "Standards-Native EPCIS Attestation Edge Gateway\n"
        "Adaptive Pre-Commit Anomaly Gating · Conditional Finality · Verifiable Visualization\n"
        "Patent Application No. 202611067289",
        color=C["text"], fontsize=13, fontweight="bold", y=0.995,
    )

    gs = gridspec.GridSpec(
        4, 4, figure=fig,
        hspace=0.55, wspace=0.40,
        left=0.04, right=0.98, top=0.955, bottom=0.03,
    )

    # Row 0
    ax_flow   = fig.add_subplot(gs[0, :3])
    ax_kpi    = fig.add_subplot(gs[0:2, 3])

    # Row 1
    ax_pie    = fig.add_subplot(gs[1, 0])
    ax_hist   = fig.add_subplot(gs[1, 1])
    ax_fin    = fig.add_subplot(gs[1, 2])

    # Row 2
    ax_table  = fig.add_subplot(gs[2, :2])
    ax_merkle = fig.add_subplot(gs[2, 2])
    ax_norm   = fig.add_subplot(gs[2:, 3])   # tall

    # Row 3
    ax_route  = fig.add_subplot(gs[3, :3])

    _panel_pipeline_flow(ax_flow)
    _panel_gating_pie(ax_pie, metrics)
    _panel_risk_histogram(ax_hist, gated)
    _panel_finality_bar(ax_fin, timeline)
    _panel_event_table(ax_table, gated)
    _panel_merkle_verify(ax_merkle, verify_results)
    _panel_kpi(ax_kpi, metrics, finality_summ, verify_results)
    _panel_normalization(ax_norm, norm_results)
    _panel_route_map(ax_route, gated)

    plt.savefig(output_path, dpi=160, bbox_inches="tight",
                facecolor=C["bg"], edgecolor="none")
    print(f"[Dashboard] Saved → {output_path}")
    plt.close(fig)


def _panel_route_map(ax, gated: List[Dict]):
    """Scatter plot of GPS points coloured by decision along the route."""
    _styled_ax(ax, "🗺  Shipment Route  (Chandigarh → Delhi → Mumbai) — GPS Scatter by Decision")
    colour_map = {"ACCEPT": C["green"], "CHALLENGE": C["yellow"], "QUARANTINE": C["red"]}
    for decision in ("ACCEPT", "CHALLENGE", "QUARANTINE"):
        pts = [(r["raw_event"]["sensorData"]["gps"]["lat"],
                r["raw_event"]["sensorData"]["gps"]["lng"])
               for r in gated if r["decision"] == decision]
        if pts:
            lats, lngs = zip(*pts)
            ax.scatter(lngs, lats, color=colour_map[decision], s=18, alpha=0.75,
                       label=decision, zorder=3, edgecolors="none")

    # Route line
    waypoints = [
        (76.7794, 30.7333), (76.7767, 30.3782), (77.2090, 28.6139),
        (73.8567, 18.5204), (72.8777, 19.0760),
    ]
    wx, wy = zip(*waypoints)
    ax.plot(wx, wy, color=C["blue"], lw=1.5, ls="--", alpha=0.5, zorder=2)
    cities  = ["Chandigarh", "Ambala", "Delhi", "Pune", "Mumbai"]
    for x, y, city in zip(wx, wy, cities):
        ax.scatter([x], [y], color=C["blue"], s=50, zorder=4, edgecolors=C["bg"], lw=0.8)
        ax.text(x + 0.3, y + 0.2, city, color=C["blue"], fontsize=7, zorder=5)

    ax.set_xlabel("Longitude", color=C["subtext"], fontsize=7)
    ax.set_ylabel("Latitude",  color=C["subtext"], fontsize=7)
    ax.legend(fontsize=7, frameon=False, labelcolor=C["subtext"], loc="upper right")
    ax.set_xlim(65, 90)
    ax.set_ylim(15, 35)
