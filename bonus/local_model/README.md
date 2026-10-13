# Bonus — real local model ($/token from real tok/s)

Run a tiny model on CPU, measure **real tokens/sec**, and compare the resulting
`$/1M-token` to the simulation. Optional — needs `torch` + `transformers`.

```bash
pip install torch transformers
cd bonus/local_model
python run_local.py                 # uses a tiny CPU model
LAB_MODEL=Qwen/Qwen2.5-0.5B python run_local.py   # try a bigger one
```

From the repository root, `uv run --python 3.12 --with torch --with transformers -- python bonus/local_model/run_local.py`
also installs the optional packages in an isolated environment. The printed
`$/1M output tokens` uses the `LAB_CPU_RATE_HR` assumption and times generation
only; it is not a quality- or service-equivalent price comparison.

If deps or the model download are unavailable, the script prints instructions and
exits cleanly (it never breaks the lab).
