"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0
    reasoning = {flag: {"requests": 0, "tokens": 0, "cost_usd": 0.0, "energy_wh": 0.0}
                 for flag in (False, True)}
    reasoning_avoidable_cost = reasoning_avoidable_wh = 0.0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        cost = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += cost
        energy = sustainability.wh_per_query(inp + out, is_reasoning=is_reasoning)
        segment = reasoning[is_reasoning]
        segment["requests"] += 1
        segment["tokens"] += inp + out
        segment["cost_usd"] += cost
        segment["energy_wh"] += energy
        if is_reasoning:
            # The generator makes reasoning output 6x longer; this is a modeled
            # fallback to an ordinary answer, not an observed quality outcome.
            fallback_out = out // 6
            fallback_cost = pricing.request_cost(inp, fallback_out, pin, pout,
                                                 cached_in=cached, batch=is_batch)
            reasoning_avoidable_cost += cost - fallback_cost
            reasoning_avoidable_wh += energy - sustainability.wh_per_query(inp + fallback_out)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    cap_fraction = 0.05
    excess = max(0, reasoning[True]["requests"] - int(len(rows) * cap_fraction))
    modeled_cap = {
        "cap_fraction": cap_fraction, "requests_to_reroute": excess,
        "saved_usd_daily": round(reasoning_avoidable_cost * excess / reasoning[True]["requests"], 2)
        if reasoning[True]["requests"] else 0.0,
        "saved_wh_daily": round(reasoning_avoidable_wh * excess / reasoning[True]["requests"], 2)
        if reasoning[True]["requests"] else 0.0,
    }
    for segment in reasoning.values():
        segment["cost_usd"] = round(segment["cost_usd"], 2)
        segment["energy_wh"] = round(segment["energy_wh"], 2)

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        for flag, label in ((False, "ordinary"), (True, "reasoning")):
            s = reasoning[flag]
            print(f"{label:9}: {s['requests']:4} requests  ${s['cost_usd']:7.2f}/day  {s['energy_wh']:9.1f} Wh/day")
        print(f"5% reasoning cap (modeled): reroute {excess} requests -> "
              f"${modeled_cap['saved_usd_daily']:.2f}/day and {modeled_cap['saved_wh_daily']:.1f} Wh/day saved")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "reasoning": reasoning, "reasoning_cap": modeled_cap,
    }


if __name__ == "__main__":
    run()
