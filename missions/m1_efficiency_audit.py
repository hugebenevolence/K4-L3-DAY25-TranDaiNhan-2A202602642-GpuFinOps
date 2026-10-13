"""M1 — Efficiency Audit: MFU/MBU, the GPU-Util lie, and idle waste (deck §5).

Run: python missions/m1_efficiency_audit.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from collections import defaultdict
from missions._common import load_csv, num, catalog_by_type
from finops import metrics


def run(verbose: bool = True) -> dict:
    tel = load_csv("gpu_telemetry.csv")
    cat = catalog_by_type()

    # per-row MFU/MBU, then aggregate per GPU
    agg = defaultdict(lambda: {"util": [], "mfu": [], "mbu": [], "bw": [],
                               "type": None, "workload": None, "max_vram": 0.0, "idle_hours": 0})
    for r in tel:
        gtype = r["gpu_type"]
        peak_fp16 = num(cat[gtype]["peak_tflops_fp16"])
        peak_bw = num(cat[gtype]["peak_bw_tbs"])
        mfu = metrics.compute_mfu(num(r["achieved_tflops"]), peak_fp16)
        mbu = metrics.compute_mbu(num(r["achieved_bw_tbs"]), peak_bw)
        a = agg[r["gpu_id"]]
        a["type"] = gtype
        a["workload"] = r["workload"]
        a["util"].append(num(r["gpu_util_pct"]))
        a["mfu"].append(mfu)
        a["mbu"].append(mbu)
        a["bw"].append(num(r["achieved_bw_tbs"]))
        a["max_vram"] = max(a["max_vram"], num(r["mem_used_gb"]))
        if num(r["gpu_util_pct"]) < 10:  # effectively idle this interval (1h)
            a["idle_hours"] += 1

    summary = []
    for gid, a in agg.items():
        summary.append({
            "gpu_id": gid, "gpu_type": a["type"],
            "gpu_util_pct": round(sum(a["util"]) / len(a["util"]), 1),
            "mfu": round(sum(a["mfu"]) / len(a["mfu"]), 3),
            "mbu": round(sum(a["mbu"]) / len(a["mbu"]), 3),
            "observed_bw_tbs": round(max(a["bw"]), 3),
            "max_vram_gb": round(a["max_vram"], 1),
            "workload": a["workload"],
            "idle_hours": a["idle_hours"],
        })

    lies = metrics.flag_util_lies(summary)
    idle_waste = 0.0
    for s in summary:
        on_demand = num(cat[s["gpu_type"]]["on_demand_hr"])
        idle_waste += metrics.idle_waste_usd(s["idle_hours"], on_demand)

    vram_unit_cost = {gpu: round(num(c["on_demand_hr"]) / num(c["hbm_gb"]), 4)
                      for gpu, c in cat.items()}
    rightsize = []
    for s in summary:
        # Inference decode is the memory-bound cohort in this synthetic data.
        if s["workload"] != "infer" or s["mbu"] >= 0.60:
            continue
        current = cat[s["gpu_type"]]
        candidates = [
            (gpu, c) for gpu, c in cat.items()
            if num(c["on_demand_hr"]) < num(current["on_demand_hr"])
            and vram_unit_cost[gpu] < vram_unit_cost[s["gpu_type"]]
            and num(c["hbm_gb"]) >= s["max_vram_gb"] * 1.10
            and num(c["peak_bw_tbs"]) >= s["observed_bw_tbs"] * 1.20
        ]
        if not candidates:
            continue
        target, target_cat = min(candidates, key=lambda item: num(item[1]["on_demand_hr"]))
        saving = (num(current["on_demand_hr"]) - num(target_cat["on_demand_hr"])) * 24 * 30
        rightsize.append({
            "gpu_id": s["gpu_id"], "current": s["gpu_type"], "target": target,
            "mbu": s["mbu"], "observed_bw_tbs": s["observed_bw_tbs"],
            "target_peak_bw_tbs": num(target_cat["peak_bw_tbs"]),
            "max_vram_gb": s["max_vram_gb"], "target_hbm_gb": num(target_cat["hbm_gb"]),
            "current_usd_per_gb": vram_unit_cost[s["gpu_type"]],
            "target_usd_per_gb": vram_unit_cost[target],
            "monthly_savings": round(saving, 2),
        })
    rightsize_savings = round(sum(r["monthly_savings"] for r in rightsize), 2)

    if verbose:
        print("== M1 Efficiency Audit ==")
        print(f"{'GPU':14}{'type':7}{'util%':>7}{'MFU':>7}{'MBU':>7}{'idle_h':>8}")
        for s in sorted(summary, key=lambda x: x["mfu"]):
            print(f"{s['gpu_id']:14}{s['gpu_type']:7}{s['gpu_util_pct']:>7}{s['mfu']:>7}{s['mbu']:>7}{s['idle_hours']:>8}")
        print(f"\nGPU-Util LIES (util>=90% but MFU<30%): {[l['gpu_id'] for l in lies]}")
        print(f"Idle waste (1 day): ${idle_waste:,.2f}  ->  ${idle_waste*30:,.0f}/month")
        print("MBU-aware inference right-sizing (10% VRAM, 20% bandwidth headroom):")
        for r in rightsize:
            print(f"  {r['gpu_id']}: {r['current']} -> {r['target']}  MBU={r['mbu']:.2f}  "
                  f"BW {r['observed_bw_tbs']:.3f}/{r['target_peak_bw_tbs']:.3f} TB/s  "
                  f"VRAM {r['max_vram_gb']:.1f}/{r['target_hbm_gb']:.0f} GB  "
                  f"$/GB {r['current_usd_per_gb']:.4f}->{r['target_usd_per_gb']:.4f}  "
                  f"save ${r['monthly_savings']:.0f}/month")
        print(f"MBU right-size total: ${rightsize_savings:,.0f}/month (before benchmarking)")

    return {"summary": summary, "lies": lies, "idle_waste_daily": round(idle_waste, 2),
            "vram_unit_cost": vram_unit_cost, "rightsize": rightsize,
            "rightsize_savings_monthly": rightsize_savings}


if __name__ == "__main__":
    run()
