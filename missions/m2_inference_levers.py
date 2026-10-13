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
CACHE_WRITE_SURCHARGE_PER_M = 0.50  # illustrative storage/write charge above ordinary input billing


def cache_plan(rows: list[dict]) -> dict:
    """Enable caching only for prefixes whose observed repeat reads repay the write."""
    prefixes = {}
    for r in rows:
        prefix = r["cache_prefix_id"]
        if prefix not in prefixes:
            prefixes[prefix] = {"tier": r["route_tier"], "reads": 0}
        elif int(num(r["cached_input_tokens"])) > 0:
            prefixes[prefix]["reads"] += 1
    decisions = {}
    tiers = {}
    for tier, (input_price, _) in MODEL_PRICES.items():
        groups = {key: value for key, value in prefixes.items() if value["tier"] == tier}
        eligible = {key: pricing.cache_is_worth_it(value["reads"], CACHE_WRITE_SURCHARGE_PER_M,
                                                    input_price_per_m=input_price)
                    for key, value in groups.items()}
        decisions.update(eligible)
        tiers[tier] = {
            "prefixes": len(groups), "eligible_prefixes": sum(eligible.values()),
            "avg_reads": round(sum(g["reads"] for g in groups.values()) / len(groups), 2) if groups else 0.0,
            "break_even_reads": pricing.cache_break_even_reads(CACHE_WRITE_SURCHARGE_PER_M, input_price),
            "input_price_per_m": input_price,
        }
    return {"decisions": decisions, "tiers": tiers}


def optimized_request_cost(r: dict, plan: dict, seen_prefixes: set) -> float:
    """Price an ordered CSV row, including the first cache write when worthwhile."""
    inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
    pin, pout = MODEL_PRICES[r["route_tier"]]
    prefix = r["cache_prefix_id"]
    use_cache = plan["decisions"][prefix]
    cached = int(num(r["cached_input_tokens"])) if use_cache else 0
    batch = bool(int(num(r["is_batch"])))
    cost = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=batch)
    if prefix not in seen_prefixes:
        seen_prefixes.add(prefix)
        if use_cache:
            cost += int(num(r["cacheable_input_tokens"])) / 1e6 * CACHE_WRITE_SURCHARGE_PER_M
    return cost


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    plan = cache_plan(rows)
    seen_prefixes = set()
    base_cost = opt_cost = no_cache_cost = 0.0
    total_tokens = 0
    reasoning = {flag: {"requests": 0, "tokens": 0, "cost_usd": 0.0, "energy_wh": 0.0}
                 for flag in (False, True)}
    reasoning_avoidable_cost = reasoning_avoidable_wh = 0.0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        no_cache_cost += pricing.request_cost(inp, out, pin, pout, batch=is_batch)
        cost = optimized_request_cost(r, plan, seen_prefixes)
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
            reasoning_avoidable_cost += (out - fallback_out) / 1e6 * pout * (0.5 if is_batch else 1.0)
            reasoning_avoidable_wh += energy - sustainability.wh_per_query(inp + fallback_out)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    cache_net_savings = no_cache_cost - opt_cost
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
        print(f"cache net savings: ${cache_net_savings:.3f}/day after ${CACHE_WRITE_SURCHARGE_PER_M:.2f}/1M write surcharge")
        for tier, stats in plan["tiers"].items():
            print(f"  {tier}: {stats['avg_reads']:.2f} repeat reads/prefix vs "
                  f"{stats['break_even_reads']} needed; {stats['eligible_prefixes']}/{stats['prefixes']} enabled")
        for flag, label in ((False, "ordinary"), (True, "reasoning")):
            s = reasoning[flag]
            print(f"{label:9}: {s['requests']:4} requests  ${s['cost_usd']:7.2f}/day  {s['energy_wh']:9.1f} Wh/day")
        print(f"5% reasoning cap (modeled): reroute {excess} requests -> "
              f"${modeled_cap['saved_usd_daily']:.2f}/day and {modeled_cap['saved_wh_daily']:.1f} Wh/day saved")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "cache": {"net_savings_daily": round(cache_net_savings, 3),
                  "write_surcharge_per_m": CACHE_WRITE_SURCHARGE_PER_M,
                  "tiers": plan["tiers"]},
        "reasoning": reasoning, "reasoning_cap": modeled_cap,
    }


if __name__ == "__main__":
    run()
