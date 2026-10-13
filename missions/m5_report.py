"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import num, catalog_by_type, ROOT
from finops import pricing, report, sustainability
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing, m4_allocation

DAYS = 30
# one tier down for over-provisioned ("util-lie") GPUs
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    r4 = m4_allocation.run(verbose=False)
    cat = catalog_by_type()

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    mbu_ids = {r["gpu_id"] for r in r1["rightsize"]}
    rightsize_savings = r1["rightsize_savings_monthly"]
    for lie in r1["lies"]:
        if lie["gpu_id"] in mbu_ids:
            continue  # one GPU cannot earn two independent right-size savings
        cur = lie["gpu_type"]
        tgt = RIGHTSIZE_MAP.get(cur, cur)
        delta = num(cat[cur]["on_demand_hr"]) - num(cat[tgt]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size GPUs (deduplicated)": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- sustainability snapshot ---
    median_tokens = 800
    wh = sustainability.wh_per_query(median_tokens)
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "cleanest_region": r3["carbon_aware"]["cleanest_region"],
        "cheapest_region": r3["carbon_aware"]["cheapest_region"],
    }

    md = report.build_report(baseline, optimized, levers, sustainability=sust)
    reasoning = r2["reasoning"]
    ordinary, deep = reasoning[False], reasoning[True]
    all_energy = ordinary["energy_wh"] + deep["energy_wh"]
    cap = r2["reasoning_cap"]
    carbon = r3["carbon_aware"]
    lie_ids = ", ".join(f"{gpu['gpu_id']} (util {gpu['gpu_util_pct']:.1f}%, MFU {gpu['mfu']:.2f})"
                        for gpu in r1["lies"])
    region_lines = [
        "| Region | Electricity ($/kWh) | Grid (gCO2e/kWh) | Electricity ($/month) | Carbon (kg/month) |",
        "|---|---:|---:|---:|---:|",
    ]
    for region, values in carbon["regions"].items():
        region_lines.append(
            f"| {region} | {sustainability.REGION_PRICE_KWH[region]:.3f} | "
            f"{sustainability.REGION_CARBON[region]} | {values['electricity_usd']:,.2f} | "
            f"{values['carbon_kg']:,.2f} |"
        )
    mbu_lines = [
        "| GPU | Current → candidate | Max VRAM / target HBM (GB) | Observed / target peak BW (TB/s) | $/GB-h before → after | Savings ($/month) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in r1["rightsize"]:
        mbu_lines.append(
            f"| {item['gpu_id']} | {item['current']} → {item['target']} | "
            f"{item['max_vram_gb']:.1f} / {item['target_hbm_gb']:.0f} | "
            f"{item['observed_bw_tbs']:.3f} / {item['target_peak_bw_tbs']:.3f} | "
            f"{item['current_usd_per_gb']:.4f} → {item['target_usd_per_gb']:.4f} | "
            f"{item['monthly_savings']:.0f} |"
        )
    cache_lines = [
        "| Tier | Avg repeat reads / prefix | Break-even reads | Eligible prefixes |",
        "|---|---:|---:|---:|",
    ]
    for tier, stats in r2["cache"]["tiers"].items():
        cache_lines.append(
            f"| {tier} | {stats['avg_reads']:.2f} | {stats['break_even_reads']} | "
            f"{stats['eligible_prefixes']}/{stats['prefixes']} |"
        )
    md += "\n" + "\n".join([
        "", "## Unit economics and efficiency", "",
        f"- Inference: **${r2['baseline_per_m']:.3f} → ${r2['optimized_per_m']:.3f} per 1M tokens** "
        f"across {r2['total_tokens']:,} tokens/day ({r2['savings_pct']:.1f}% lower).",
        f"- Purchasing: ${r3['on_demand_monthly']:,.0f} → ${r3['optimized_monthly']:,.0f}/month "
        f"({r3['savings_pct']:.1f}% lower), using each job's actual scheduled days.",
        f"- GPU-Util lies: {lie_ids}. GPU-Util measures time with active kernels, while MFU "
        "measures useful FLOPs against peak. Memory stalls or launch overhead can keep a GPU busy "
        "without useful throughput. Benchmark before changing GPU types.",
        f"- Idle fleet waste: ${r1['idle_waste_daily']:,.2f}/day, or ${idle_savings:,.0f}/month. "
        f"The ${rightsize_savings:,.0f}/month deduplicated right-size estimate assumes 24h/day at catalog prices.",
        "", "## Extension 1 — duration- and interruption-aware purchasing", "",
        f"The simple policy projected {r3['legacy_savings_pct']:.1f}% purchasing savings; "
        f"the revised policy projects **{r3['savings_pct']:.1f}%**. The lower number accounts "
        "for full contract billing and GPU-specific spot interruptions. A short job should not "
        "be credited with a three-year rate without paying its commitment.",
        f"The 36-month chat workload selects 3-year reserved; the 24-month RAG workload "
        f"selects 1-year reserved; the 12-month search workload remains on-demand at 18h/day. "
        f"Spot interruption assumptions range from {min(pricing.SPOT_INTERRUPT_RATE.values()):.0%} "
        f"to {max(pricing.SPOT_INTERRUPT_RATE.values()):.0%} per GPU-hour. "
        "M3 prints the GPU × duty cycle × interruptible recommendation matrix.",
        "", "## Extension 2 — MBU-aware right-sizing", "",
        "For inference GPUs with MBU below 60%, candidates must be cheaper per hour and per GB "
        "of HBM, preserve 10% VRAM headroom and 20% bandwidth headroom over observed peaks.",
        "", *mbu_lines, "",
        f"These two recommendations project **${r1['rightsize_savings_monthly']:,.0f}/month**. "
        "The A10G util-lie is already in this set; the combined waterfall counts it once. "
        "A cheaper GPU-hour alone can fail when model weights do not fit or memory bandwidth "
        "cannot sustain decode throughput. Benchmark latency and throughput before migration.",
        "", "## Extension 3 — cache break-even", "",
        f"The synthetic trace records prefix IDs, first writes and repeat reads. With a "
        f"${r2['cache']['write_surcharge_per_m']:.2f}/1M-input-token extra write/storage "
        "charge and 90% read discount, caching is enabled only after repeat-read savings "
        "exceed that charge:",
        "", *cache_lines, "",
        f"Net cache saving is **${r2['cache']['net_savings_daily']:.3f}/day**, or "
        f"**${r2['cache']['net_savings_daily'] * DAYS:.2f}/month**. "
        "Small-model input is cheap, so it needs more reuse than large-model input. "
        "Prefix IDs and the storage surcharge are illustrative, not provider billing records.",
        "", "## Extension 4 — reasoning budget", "",
        "| Traffic | Requests/day | Share of requests | Optimized cost ($/day) | Share of cost | Energy (Wh/day) | Share of energy |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| Ordinary | {ordinary['requests']:,} | {ordinary['requests'] / (ordinary['requests'] + deep['requests']):.1%} | "
        f"{ordinary['cost_usd']:.2f} | {ordinary['cost_usd'] / (ordinary['cost_usd'] + deep['cost_usd']):.1%} | "
        f"{ordinary['energy_wh']:,.1f} | {ordinary['energy_wh'] / all_energy:.1%} |",
        f"| Reasoning | {deep['requests']:,} | {deep['requests'] / (ordinary['requests'] + deep['requests']):.1%} | "
        f"{deep['cost_usd']:.2f} | {deep['cost_usd'] / (ordinary['cost_usd'] + deep['cost_usd']):.1%} | "
        f"{deep['energy_wh']:,.1f} | {deep['energy_wh'] / all_energy:.1%} |",
        "",
        f"A 10% request cap is already met. A **5% cap** would reroute {cap['requests_to_reroute']} "
        f"reasoning requests/day in a modeled scenario, saving **${cap['saved_usd_daily']:.2f}/day "
        f"(${cap['saved_usd_daily'] * DAYS:.2f}/month)** and **{cap['saved_wh_daily']:,.1f} Wh/day**. "
        "Gate reasoning on task difficulty or low confidence, then evaluate answer quality before applying the cap. "
        "The model assumes ordinary fallback responses have one sixth the output tokens and uses the "
        "lab's 80× reasoning energy factor; quality and actual power were not measured.",
        "", "## Extension 5 — carbon-aware scheduling", "",
        f"For interruptible jobs only, scheduled GPU-hours and catalog watts imply "
        f"**{carbon['movable_kwh']:,.1f} kWh/month**. All regions below use the same workload energy:",
        "", *region_lines, "",
        f"Moving from {carbon['baseline_region']} to the cleanest region, {carbon['cleanest_region']}, "
        f"would avoid **{carbon['carbon_saved_kg']:,.2f} kgCO2e/month** and reduce modeled "
        f"electricity by **${carbon['electricity_saved_usd']:,.2f}/month**. "
        f"The cheapest electricity is in {carbon['cheapest_region']}; it is not the cleanest. "
        "Check region capacity, data residency and latency before migrating. GPU rental price differences "
        "and migration costs are unknown, so electricity savings are excluded from the GPU spend waterfall.",
        "", "## Action plan and measurement limits", "",
        "1. Move eligible training and batch jobs to spot with checkpoints; purchasing has the largest "
        "projected savings. Track interruption and recovery time against the model.",
        "2. Route routine inference to the small model, then apply cache and batch where eligible. "
        "Measure answer quality, latency and $/1M tokens before rollout.",
        "3. Shut down idle fleet hours, profile the high-util/low-MFU GPUs, and use tagged cost "
        f"showback (coverage {r4['tag_coverage']:.0%}) before chargeback.",
        "", "Estimates use the lab's seeded June-2026 catalog, one modeled month, and aggregate "
        "inference plus workload pools. GPU right-sizing is a price-only upper bound: memory capacity, "
        "bandwidth and throughput must be validated. Fleet idle/right-size projections may overlap "
        "with purchased workload capacity and require deduplication before a financial commitment. "
        "Carbon uses catalog rated watts and illustrative grid factors, not metered energy or real-time intensity.",
    ])
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    png = report.savings_waterfall(levers, os.path.join(ROOT, "outputs", "savings.png"), baseline)

    if verbose:
        if hasattr(_sys.stdout, "reconfigure"):
            _sys.stdout.reconfigure(encoding="utf-8")
        print("== M5 Optimization Report ==")
        print(md)
        print(f"\nWritten: outputs/report.md" + (f" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
            "levers": levers, "total_savings_pct": round(total_pct, 1)}


if __name__ == "__main__":
    run()
