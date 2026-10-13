"""Pricing & purchasing economics — measure in $/1M-token, not $/GPU-hr.

Figures are June-2026 as-of snapshots from the deck's RESEARCH dossier; treat
live prices as fast-moving (re-baseline before each cohort).
"""
from __future__ import annotations
import math


SPOT_INTERRUPT_RATE = {"H100": 0.05, "H200": 0.04, "A100": 0.07,
                       "A10G": 0.12, "L4": 0.10, "B200": 0.04, "MI300X": 0.08}


def request_cost(
    input_tok: int,
    output_tok: int,
    price_in_per_m: float,
    price_out_per_m: float,
    cached_in: int = 0,
    cache_discount: float = 0.10,   # Anthropic cached-read ~0.1x (=-90%)
    batch: bool = False,
    batch_discount: float = 0.50,   # Batch API ~ -50%
) -> float:
    """USD cost of a single request. Cached input billed at cache_discount x price."""
    cached_in = min(max(0, cached_in), input_tok)
    uncached_in = input_tok - cached_in
    cost = (
        (uncached_in / 1e6) * price_in_per_m
        + (cached_in / 1e6) * price_in_per_m * cache_discount
        + (output_tok / 1e6) * price_out_per_m
    )
    if batch:
        cost *= batch_discount
    return cost


def dollars_per_million(total_cost_usd: float, total_tokens: int) -> float:
    """Aggregate unit economics: $ per 1,000,000 tokens served."""
    if total_tokens <= 0:
        return 0.0
    return total_cost_usd / (total_tokens / 1e6)


def discount_stack(
    batch: bool = False,
    cache_hit_frac: float = 0.0,
    batch_discount: float = 0.50,
    cache_discount: float = 0.10,
) -> float:
    """Effective fraction of the naive bill after stacking discounts (input-heavy view).

    Discounts MULTIPLY: cache applies to the cached share of input, batch to the
    whole bill. batch + 100% cache-hit -> 0.5 * 0.1 = 0.05 (~95% off).
    """
    cache_mult = cache_hit_frac * cache_discount + (1.0 - cache_hit_frac)
    batch_mult = batch_discount if batch else 1.0
    return cache_mult * batch_mult


def break_even_utilization(discount_frac: float) -> float:
    """Utilization at which a commitment pays off ~= 1 - discount.

    A 45% reserved discount needs ~55% utilization (~13.2h/day) to beat on-demand.
    """
    return max(0.0, min(1.0, 1.0 - discount_frac))


def cache_break_even_reads(write_surcharge_per_m: float, input_price_per_m: float,
                           read_discount: float = 0.10) -> int | float:
    """Minimum repeat reads that repay one cache-write surcharge per 1M input tokens."""
    if (not all(math.isfinite(x) for x in (write_surcharge_per_m, input_price_per_m, read_discount))
            or write_surcharge_per_m < 0 or input_price_per_m <= 0
            or not 0 <= read_discount <= 1):
        raise ValueError("invalid cache price or discount")
    saving_per_read = input_price_per_m * (1.0 - read_discount)
    if saving_per_read <= 0:
        return math.inf
    return math.floor(write_surcharge_per_m / saving_per_read) + 1


def cache_is_worth_it(avg_cache_reads: float, write_cost_per_m: float,
                      read_discount: float = 0.10, input_price_per_m: float = 1.0) -> bool:
    """Compare repeat-read savings with the extra cache-write/storage cost."""
    cache_break_even_reads(write_cost_per_m, input_price_per_m, read_discount)
    if not math.isfinite(avg_cache_reads) or avg_cache_reads < 0:
        raise ValueError("avg_cache_reads must be finite and nonnegative")
    return (avg_cache_reads * input_price_per_m * (1.0 - read_discount)
            > write_cost_per_m)


def recommend_tier(hours_per_day: float, interruptible: bool, reserved_discount: float = 0.45,
                   *, gpu_type: str | None = None, expected_months: int | None = None,
                   days_per_month: float = 30, prices: dict | None = None) -> str:
    """Pick a purchasing tier from a workload's duty cycle + interruptibility.

    With a catalog and planning horizon, compare full spot/rework and committed
    contract costs. Old three-argument calls retain the lab's simple policy.
    """
    if prices is not None and expected_months is not None:
        months = max(1, int(expected_months))
        active_hours = max(0.0, hours_per_day) * min(30, max(0.0, days_per_month)) * months
        candidates = {"on_demand": active_hours * float(prices["on_demand_hr"])}
        if interruptible:
            candidates["spot"] = spot_checkpoint_cost(
                active_hours, float(prices["spot_hr"]), float(prices["on_demand_hr"]),
                interrupt_rate=SPOT_INTERRUPT_RATE.get(gpu_type, 0.05),
            )["spot_cost"]
        candidates["reserved_1yr"] = (math.ceil(months / 12) * 12 * 30 * 24
                                       * float(prices["reserved_1yr_hr"]))
        candidates["reserved_3yr"] = (math.ceil(months / 36) * 36 * 30 * 24
                                       * float(prices["reserved_3yr_hr"]))
        return min(candidates, key=candidates.get)
    duty = max(0.0, hours_per_day) / 24.0
    be = break_even_utilization(reserved_discount)
    if interruptible and hours_per_day < 24:
        return "spot"
    if duty >= be:
        return "reserved"
    return "on_demand"


def spot_checkpoint_cost(
    job_hours: float,
    spot_hr: float,
    on_demand_hr: float,
    interrupt_rate: float = 0.05,      # per-hour chance (H100 spot ~<5%)
    ckpt_overhead_frac: float = 0.03,  # steady cost of writing checkpoints
    rework_hours_per_interrupt: float = 0.5,
) -> dict:
    """Effective cost of running a checkpointable job on spot vs on-demand.

    Interruptions waste the compute since the last checkpoint (rework); checkpointing
    adds a small steady overhead. Spot still wins for interruptible jobs.
    """
    expected_interrupts = job_hours * interrupt_rate
    rework_hours = expected_interrupts * rework_hours_per_interrupt
    effective_hours = job_hours * (1.0 + ckpt_overhead_frac) + rework_hours
    spot_cost = effective_hours * spot_hr
    on_demand_cost = job_hours * on_demand_hr
    savings_pct = (1.0 - spot_cost / on_demand_cost) * 100.0 if on_demand_cost > 0 else 0.0
    return {
        "spot_effective_hours": round(effective_hours, 2),
        "spot_cost": round(spot_cost, 2),
        "on_demand_cost": round(on_demand_cost, 2),
        "savings_pct": round(savings_pct, 1),
    }
