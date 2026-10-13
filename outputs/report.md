# NimbusAI — GPU Cost Optimization Report

- **Period:** monthly
- **Baseline spend:** $18,005
- **Optimized spend:** $10,355
- **Projected savings:** $7,650 (**42.5%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,188 |
| Purchasing (spot/reserved) | $5,063 |
| Right-size GPUs (deduplicated) | $799 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cleanest region: europe-north1
- Cheapest electricity region: us-east-wa

_Figures are June-2026 as-of snapshots; re-baseline before acting._

## Unit economics and efficiency

- Inference: **$6.488 → $1.229 per 1M tokens** across 7,533,027 tokens/day (81.1% lower).
- Purchasing: $16,539 → $11,476/month (30.6% lower), using each job's actual scheduled days.
- GPU-Util lies: gpu-h100-4 (util 98.2%, MFU 0.19), gpu-a10g-1 (util 96.9%, MFU 0.27). GPU-Util measures time with active kernels, while MFU measures useful FLOPs against peak. Memory stalls or launch overhead can keep a GPU busy without useful throughput. Benchmark before changing GPU types.
- Idle fleet waste: $20.00/day, or $600/month. The $799/month deduplicated right-size estimate assumes 24h/day at catalog prices.

## Extension 1 — duration- and interruption-aware purchasing

The simple policy projected 40.5% purchasing savings; the revised policy projects **30.6%**. The lower number accounts for full contract billing and GPU-specific spot interruptions. A short job should not be credited with a three-year rate without paying its commitment.
The 36-month chat workload selects 3-year reserved; the 24-month RAG workload selects 1-year reserved; the 12-month search workload remains on-demand at 18h/day. Spot interruption assumptions range from 4% to 12% per GPU-hour. M3 prints the GPU × duty cycle × interruptible recommendation matrix.

## Extension 2 — MBU-aware right-sizing

For inference GPUs with MBU below 60%, candidates must be cheaper per hour and per GB of HBM, preserve 10% VRAM headroom and 20% bandwidth headroom over observed peaks.

| GPU | Current → candidate | Max VRAM / target HBM (GB) | Observed / target peak BW (TB/s) | $/GB-h before → after | Savings ($/month) |
|---|---|---:|---:|---:|---:|
| gpu-a10g-0 | A10G → L4 | 20.3 / 24 | 0.182 / 0.300 | 0.0417 → 0.0333 | 144 |
| gpu-a10g-1 | A10G → L4 | 20.4 / 24 | 0.212 / 0.300 | 0.0417 → 0.0333 | 144 |

These two recommendations project **$288/month**. The A10G util-lie is already in this set; the combined waterfall counts it once. A cheaper GPU-hour alone can fail when model weights do not fit or memory bandwidth cannot sustain decode throughput. Benchmark latency and throughput before migration.

## Extension 3 — cache break-even

The synthetic trace records prefix IDs, first writes and repeat reads. With a $0.50/1M-input-token extra write/storage charge and 90% read discount, caching is enabled only after repeat-read savings exceed that charge:

| Tier | Avg repeat reads / prefix | Break-even reads | Eligible prefixes |
|---|---:|---:|---:|
| small | 3.04 | 3 | 278/471 |
| large | 0.59 | 1 | 132/314 |

Net cache saving is **$0.402/day**, or **$12.06/month**. Small-model input is cheap, so it needs more reuse than large-model input. Prefix IDs and the storage surcharge are illustrative, not provider billing records.

## Extension 4 — reasoning budget

| Traffic | Requests/day | Share of requests | Optimized cost ($/day) | Share of cost | Energy (Wh/day) | Share of energy |
|---|---:|---:|---:|---:|---:|---:|
| Ordinary | 2,199 | 91.6% | 7.85 | 84.8% | 1,887.6 | 6.0% |
| Reasoning | 201 | 8.4% | 1.41 | 15.2% | 29,787.7 | 94.0% |

A 10% request cap is already met. A **5% cap** would reroute 81 reasoning requests/day in a modeled scenario, saving **$0.41/day ($12.30/month)** and **11,932.4 Wh/day**. Gate reasoning on task difficulty or low confidence, then evaluate answer quality before applying the cap. The model assumes ordinary fallback responses have one sixth the output tokens and uses the lab's 80× reasoning energy factor; quality and actual power were not measured.

## Extension 5 — carbon-aware scheduling

For interruptible jobs only, scheduled GPU-hours and catalog watts imply **1,789.0 kWh/month**. All regions below use the same workload energy:

| Region | Electricity ($/kWh) | Grid (gCO2e/kWh) | Electricity ($/month) | Carbon (kg/month) |
|---|---:|---:|---:|---:|
| us-east-1 | 0.120 | 380 | 214.68 | 679.82 |
| us-west-2 | 0.070 | 120 | 125.23 | 214.68 |
| europe-north1 | 0.090 | 30 | 161.01 | 53.67 |
| europe-central2 | 0.180 | 660 | 322.02 | 1,180.74 |
| us-east-wa | 0.055 | 90 | 98.39 | 161.01 |

Moving from us-east-1 to the cleanest region, europe-north1, would avoid **626.15 kgCO2e/month** and reduce modeled electricity by **$53.67/month**. The cheapest electricity is in us-east-wa; it is not the cleanest. Check region capacity, data residency and latency before migrating. GPU rental price differences and migration costs are unknown, so electricity savings are excluded from the GPU spend waterfall.

## Action plan and measurement limits

1. Move eligible training and batch jobs to spot with checkpoints; purchasing has the largest projected savings. Track interruption and recovery time against the model.
2. Route routine inference to the small model, then apply cache and batch where eligible. Measure answer quality, latency and $/1M tokens before rollout.
3. Shut down idle fleet hours, profile the high-util/low-MFU GPUs, and use tagged cost showback (coverage 92%) before chargeback.

Estimates use the lab's seeded June-2026 catalog, one modeled month, and aggregate inference plus workload pools. GPU right-sizing is a price-only upper bound: memory capacity, bandwidth and throughput must be validated. Fleet idle/right-size projections may overlap with purchased workload capacity and require deduplication before a financial commitment. Carbon uses catalog rated watts and illustrative grid factors, not metered energy or real-time intensity.