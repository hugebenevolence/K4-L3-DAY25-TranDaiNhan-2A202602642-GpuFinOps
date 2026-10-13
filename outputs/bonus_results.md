# Optional bonus lab results

Verified locally on 2026-10-13 (Asia/Bangkok). These are demonstrations, not production prices or hardware benchmarks.

| Bonus | Check | Observed result |
|---|---|---|
| LiteLLM-style tracker | `uv run --python 3.12 --with-requirements requirements.txt -- python bonus/litellm_tracker/demo.py` | `team-chat` stopped before request 11 at its $0.05 cap; spend stayed $0.0460. `team-eval` spent about $0.0003; 15 requests logged. Negative output-token counts are rejected. |
| Local CPU model | `uv run --python 3.12 --with torch --with transformers -- python bonus/local_model/run_local.py` | `sshleifer/tiny-gpt2` produced 64 new tokens at about 335 tok/s on this run. At the assumed $0.10/CPU-hour, generation-only cost was about $0.08/1M output tokens. Model loading, serving overhead and output quality are excluded. |
| Docker observability | `docker compose -f bonus/docker/docker-compose.yml up -d` | Exporter `/metrics` and Prometheus readiness returned HTTP 200; Prometheus scraped 11 `gpu_mfu` and 11 `gpu_wasted_cost_usd_per_hr` series with target `up`; Grafana health was `ok` and loaded **Lab 25 — GPU Cost & Efficiency**. |

The stack is available at `http://localhost:3000` (Grafana), `http://localhost:9090` (Prometheus), and `http://localhost:9101/metrics` (exporter) while Docker Desktop is running. Stop it with `docker compose -f bonus/docker/docker-compose.yml down`.
