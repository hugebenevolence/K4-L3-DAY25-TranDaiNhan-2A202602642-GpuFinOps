"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    movable_kwh = 0.0
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * min(DAYS, num(j["days"])) * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        if interruptible:
            # Catalog watts are a capacity estimate; measured job power is unavailable.
            movable_kwh += gpu_hours * num(c["watts"]) / 1000.0
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0
    regions = {
        region: {
            "electricity_usd": round(movable_kwh * sustainability.REGION_PRICE_KWH[region], 2),
            "carbon_kg": round(movable_kwh * intensity / 1000.0, 2),
        }
        for region, intensity in sustainability.REGION_CARBON.items()
    }
    baseline_region = "us-east-1"
    cleanest_region = min(regions, key=lambda region: regions[region]["carbon_kg"])
    cheapest_region = min(regions, key=lambda region: regions[region]["electricity_usd"])
    carbon_aware = {
        "movable_kwh": round(movable_kwh, 2), "baseline_region": baseline_region,
        "cleanest_region": cleanest_region, "cheapest_region": cheapest_region,
        "regions": regions,
        "carbon_saved_kg": round(regions[baseline_region]["carbon_kg"] - regions[cleanest_region]["carbon_kg"], 2),
        "electricity_saved_usd": round(regions[baseline_region]["electricity_usd"] - regions[cleanest_region]["electricity_usd"], 2),
    }

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")
        print(f"interruptible work: {movable_kwh:,.1f} kWh at catalog watts")
        print(f"{'region':18}{'$/kWh':>8}{'gCO2/kWh':>11}{'electricity':>14}{'carbon kg':>12}")
        for region, metrics in regions.items():
            print(f"{region:18}{sustainability.REGION_PRICE_KWH[region]:>8.3f}"
                  f"{sustainability.REGION_CARBON[region]:>11}"
                  f"{'$' + format(metrics['electricity_usd'], ',.2f'):>14}"
                  f"{metrics['carbon_kg']:>12,.2f}")
        print(f"moving to {cleanest_region}: {carbon_aware['carbon_saved_kg']:,.1f} kgCO2e and "
              f"${carbon_aware['electricity_saved_usd']:,.2f} electricity saved vs {baseline_region}")

    return {"recommendations": recs, "on_demand_monthly": round(on_demand_monthly),
            "optimized_monthly": round(optimized_monthly), "savings_pct": round(savings_pct, 1),
            "carbon_aware": carbon_aware}


if __name__ == "__main__":
    run()
