"""Checks for the optional policies; the original graded tests are unchanged."""
from bonus.litellm_tracker.tracker import BudgetExceeded, CostTracker
from finops import pricing
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing, m4_allocation
from missions._common import catalog_by_type


def test_cache_break_even_and_plan():
    assert pricing.cache_break_even_reads(0.50, 0.20) == 3
    assert pricing.cache_break_even_reads(0.50, 3.00) == 1
    assert not pricing.cache_is_worth_it(2, 0.50, input_price_per_m=0.20)
    assert pricing.cache_is_worth_it(3, 0.50, input_price_per_m=0.20)
    rows = ([{"cache_prefix_id": "reuse", "route_tier": "small", "cached_input_tokens": "0"}]
            + [{"cache_prefix_id": "reuse", "route_tier": "small", "cached_input_tokens": "100"}] * 3
            + [{"cache_prefix_id": "once", "route_tier": "small", "cached_input_tokens": "0"}])
    plan = m2_inference_levers.cache_plan(rows)
    assert plan["decisions"] == {"reuse": True, "once": False}


def test_commitment_horizon_and_spot_risk():
    h100 = catalog_by_type()["H100"]
    assert pricing.recommend_tier(24, False, gpu_type="H100", expected_months=36,
                                  prices=h100) == "reserved_3yr"
    assert pricing.recommend_tier(24, False, gpu_type="H100", expected_months=24,
                                  prices=h100) == "reserved_1yr"
    assert pricing.recommend_tier(4, False, gpu_type="H100", expected_months=2,
                                  prices=h100) == "on_demand"
    assert pricing.recommend_tier(24, False, gpu_type="H100", expected_months=36,
                                  days_per_month=1, prices=h100) == "on_demand"
    assert pricing.recommend_tier(20, True, gpu_type="H100", expected_months=1,
                                  prices=h100) == "spot"


def test_rightsize_preserves_observed_memory_and_bandwidth():
    result = m1_efficiency_audit.run(False)
    catalog = catalog_by_type()
    assert result["rightsize"]
    for rec in result["rightsize"]:
        target = catalog[rec["target"]]
        assert float(target["hbm_gb"]) >= rec["max_vram_gb"] * 1.10
        assert float(target["peak_bw_tbs"]) >= rec["observed_bw_tbs"] * 1.20
        assert rec["target_usd_per_gb"] < rec["current_usd_per_gb"]


def test_cost_allocation_matches_cache_policy():
    inference = m2_inference_levers.run(False)
    allocation = m4_allocation.run(False)
    assert abs(sum(allocation["by_team"].values()) - inference["optimized_daily"]) < 0.03
    purchasing = m3_purchasing.run(False)
    assert purchasing["legacy_savings_pct"] > purchasing["savings_pct"]
    assert {r["contract"] for r in purchasing["recommendations"]} >= {
        "reserved_1yr", "reserved_3yr"}


def test_mock_tracker_cannot_bypass_budget_with_negative_output():
    tracker = CostTracker({"key": 0.0})
    try:
        tracker.complete("key", "large", "hello", max_output_tokens=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative output tokens must be rejected")
    try:
        tracker.complete("key", "large", "hello", max_output_tokens=1)
    except BudgetExceeded:
        pass
    else:
        raise AssertionError("zero-dollar budget must block paid requests")
    assert tracker.report().get("key", 0) == 0
