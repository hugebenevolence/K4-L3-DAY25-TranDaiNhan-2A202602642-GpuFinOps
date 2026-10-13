"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly") -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    pct_text = f"{pct:.1f}".rstrip("0").rstrip(".")
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"- **Period:** {period}",
        f"- **Baseline spend:** ${baseline_usd:,.0f}",
        f"- **Optimized spend:** ${optimized_usd:,.0f}",
        f"- **Projected savings:** ${savings:,.0f} (**{pct_text}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cleanest region: {sustainability.get('cleanest_region', sustainability.get('best_region', 'n/a'))}",
            f"- Cheapest electricity region: {sustainability.get('cheapest_region', 'n/a')}",
        ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str, baseline_usd: float) -> str:
    """Write a savings waterfall PNG. Returns the path. No-op if matplotlib absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers)
    remaining = baseline_usd
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(0, baseline_usd, color="#475569")
    ax.text(0, baseline_usd + baseline_usd * 0.01, f"${baseline_usd:,.0f}", ha="center")
    for i, name in enumerate(names, start=1):
        saving = levers[name]
        remaining -= saving
        ax.bar(i, saving, bottom=remaining, color="#2e548a")
        ax.text(i, remaining + saving / 2, f"-${saving:,.0f}", ha="center", va="center", color="white")
    ax.bar(len(names) + 1, remaining, color="#1b7a53")
    ax.text(len(names) + 1, remaining + baseline_usd * 0.01, f"${remaining:,.0f}", ha="center")
    ax.set_xticks(range(len(names) + 2), ["Baseline", *names, "Optimized"], rotation=18, ha="right")
    ax.set_ylabel("Spend (USD / month)")
    ax.set_title("Monthly GPU spend: baseline to optimized")
    ax.set_ylim(0, baseline_usd * 1.08)
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
