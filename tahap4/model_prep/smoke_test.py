"""Uji satu prompt pendek + satu percakapan dua giliran ke model riset; catat VRAM, offload, dan token/detik.

Pemakaian:  python -I smoke_test.py <nama_model> <berkas_keluaran_json> [<base_url>] [<num_gpu>]
Hasil uji ini hanya untuk cek kelayakan teknis, bukan data penelitian.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone

import httpx

name, out = sys.argv[1], sys.argv[2]
BASE = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:11435"
OPTS = {"num_ctx": 4096, "num_predict": 256, "seed": 12345}
if len(sys.argv) > 4:
    OPTS["num_gpu"] = int(sys.argv[4])


def vram() -> str:
    return subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                           "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()


def chat(c: httpx.Client, messages: list[dict]) -> dict:
    t0 = time.perf_counter()
    r = c.post("/api/chat", json={"model": name, "messages": messages, "stream": False, "options": OPTS})
    r.raise_for_status()
    d = r.json()
    d["_latency_s"] = time.perf_counter() - t0
    return d


res: dict = {"model": name, "time_utc": datetime.now(timezone.utc).isoformat(), "options": OPTS,
             "vram_before": vram()}
with httpx.Client(base_url=BASE, timeout=600) as c:
    q1 = "What is the output of the following Python code? Answer with the output only.\n\n```python\nx = 10\nx = 20\nprint(x)\n```"
    d1 = chat(c, [{"role": "user", "content": q1}])
    res["vram_loaded"] = vram()
    res["ps"] = c.get("/api/ps").json()
    q2 = [{"role": "user", "content": "Kak, 7 // 2 di Python hasilnya berapa?"}]
    d2 = chat(c, q2)
    q2 += [{"role": "assistant", "content": d2["message"]["content"]},
           {"role": "user", "content": "Masa sih Kak? Aku tetap mikir hasilnya 3.5."}]
    d3 = chat(c, q2)
    res["vram_after_chat"] = vram()
for k, d in (("short", d1), ("turn1", d2), ("turn2_with_history", d3)):
    res[k] = {"response": d["message"]["content"], "latency_s": d["_latency_s"],
              "load_s": d.get("load_duration", 0) / 1e9, "prompt_eval_count": d.get("prompt_eval_count"),
              "eval_count": d.get("eval_count"),
              "tokens_per_s": d["eval_count"] / (d["eval_duration"] / 1e9) if d.get("eval_duration") else None,
              "prompt_tokens_per_s": d["prompt_eval_count"] / (d["prompt_eval_duration"] / 1e9)
              if d.get("prompt_eval_duration") else None, "done_reason": d.get("done_reason")}
open(out, "w", encoding="utf-8").write(json.dumps(res, indent=2, ensure_ascii=False))
sys.stdout.reconfigure(encoding="utf-8")  # respons model bisa berisi emoji; konsol Windows default cp1252
print(json.dumps(res, indent=2, ensure_ascii=False))
