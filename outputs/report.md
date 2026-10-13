# NimbusAI — GPU Cost Optimization Report

- **Period:** monthly
- **Baseline spend:** $18,005
- **Optimized spend:** $8,848
- **Projected savings:** $9,157 (**51%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $6,690 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cleanest region: europe-north1
- Cheapest electricity region: us-east-wa

_Figures are June-2026 as-of snapshots; re-baseline before acting._

## Unit economics and efficiency

- Inference: **$6.488 → $1.126 per 1M tokens** across 7,533,027 tokens/day (82.6% lower).
- Purchasing: $16,539 → $9,849/month (40.5% lower), using each job's actual scheduled days.
- GPU-Util lies: gpu-h100-4 (util 98.2%, MFU 0.19), gpu-a10g-1 (util 96.9%, MFU 0.27). GPU-Util measures time with active kernels, while MFU measures useful FLOPs against peak. Memory stalls or launch overhead can keep a GPU busy without useful throughput. Benchmark before changing GPU types.
- Idle fleet waste: $20.00/day, or $600/month. The $655/month right-size estimate assumes 24h/day at catalog prices.

## Extension 1 — reasoning budget

| Traffic | Requests/day | Share of requests | Optimized cost ($/day) | Share of cost | Energy (Wh/day) | Share of energy |
|---|---:|---:|---:|---:|---:|---:|
| Ordinary | 2,199 | 91.6% | 7.09 | 83.5% | 1,887.6 | 6.0% |
| Reasoning | 201 | 8.4% | 1.40 | 16.5% | 29,787.7 | 94.0% |

A 10% request cap is already met. A **5% cap** would reroute 81 reasoning requests/day in a modeled scenario, saving **$0.41/day ($12.30/month)** and **11,932.4 Wh/day**. Gate reasoning on task difficulty or low confidence, then evaluate answer quality before applying the cap. The model assumes ordinary fallback responses have one sixth the output tokens and uses the lab's 80× reasoning energy factor; quality and actual power were not measured.

## Extension 2 — carbon-aware scheduling

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