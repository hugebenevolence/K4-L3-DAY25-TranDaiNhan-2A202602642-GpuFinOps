"""Bonus — measure REAL tokens/sec on CPU and compare $/token to the sim.

Fully optional and guarded: if torch/transformers (or a model) are unavailable,
it prints setup instructions and exits 0 (never breaks the lab).
"""
from __future__ import annotations
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def main() -> int:
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as e:
        print("[skip] transformers/torch not installed — this bonus is optional.")
        print("       pip install torch transformers  (CPU wheels are fine)")
        print(f"       ({e})")
        return 0

    model_id = os.environ.get("LAB_MODEL", "sshleifer/tiny-gpt2")  # tiny, CPU-friendly
    try:
        tok = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id)
    except Exception as e:
        print(f"[skip] could not download '{model_id}' (offline?): {e}")
        return 0

    prompt = "GPU FinOps means measuring cost in dollars per million tokens, because"
    ids = tok(prompt, return_tensors="pt")
    model.eval()
    t0 = time.perf_counter()
    out = model.generate(**ids, max_new_tokens=64, do_sample=False)
    dt = time.perf_counter() - t0
    new_tokens = out.shape[-1] - ids["input_ids"].shape[-1]
    tps = new_tokens / dt if dt > 0 else 0.0

    # crude $/token: a CPU box ~ $0.10/hr; cost = (time/3600)*rate / tokens
    rate_hr = float(os.environ.get("LAB_CPU_RATE_HR", "0.10"))
    cost_per_1m = (dt / 3600.0) * rate_hr / max(1, new_tokens) * 1e6

    print(f"model={model_id}  new_tokens={new_tokens}  time={dt:.2f}s")
    print(f"REAL throughput: {tps:.1f} tok/s on CPU")
    print(f"CPU-rate estimate: ${cost_per_1m:,.2f}/1M output tokens "
          f"at ${rate_hr:.2f}/hr (vs simulated small-model output price $0.40/1M)")
    print("Generation timing excludes model load; tiny-model quality is not comparable to a service model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
