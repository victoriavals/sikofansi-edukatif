"""Uji asap kunci API: 1 panggilan kecil per slot API (komersial_A, komersial_B, judge) untuk memastikan kunci di
tahap4/.env berfungsi, misalnya setelah kunci diganti. Bukan data penelitian: log ke runs/dev/cek_kunci/.

Biaya per panggilan dihitung dengan harga normal di config; skrip menolak berjalan bila estimasi batas atas total
melebihi --max-usd (default 0,01 USD). Kunci tidak pernah dicetak; yang dicetak hanya status, field model, ID respons,
token, dan biaya.

Pemakaian (dari tahap4/):  python -m model_prep.cek_kunci_api   atau   python model_prep/cek_kunci_api.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.adapters import AdapterError, make_adapter  # noqa: E402
from src.common import AppendOnlyLog, cost_usd, load_config, model_cfg, now_iso, stamp  # noqa: E402

PROMPT = "Balas hanya dengan satu kata: OK"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--slots", nargs="+", default=["komersial_A", "komersial_B", "judge"])
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--max-usd", type=float, default=0.01)
    args = ap.parse_args()
    cfg = load_config(args.config)
    slots = {s: model_cfg(cfg, s) for s in args.slots}
    est = sum(cost_usd(m, 50, args.max_tokens) for m in slots.values())
    print(f"estimasi batas atas: ${est:.5f} (batas ${args.max_usd:.2f})")
    if est > args.max_usd:
        raise SystemExit("estimasi melebihi batas; tidak dijalankan")
    log = AppendOnlyLog(cfg["paths"]["dev_dir"] / "cek_kunci" / f"cek_kunci_{stamp()}.jsonl")
    total, ok_all = 0.0, True
    for slot, m in slots.items():
        rec = {"slot": slot, "model_id": m["model_id"], "api_key_env": m.get("api_key_env"), "time": now_iso(),
               "prompt": PROMPT}
        try:
            res = make_adapter(m, cfg).chat([{"role": "user", "content": PROMPT}], {"max_tokens": args.max_tokens})
            c = cost_usd(m, res.input_tokens, res.output_tokens)
            rec.update(status="ok", response=res.text, model_reported=res.model_reported,
                       response_id=res.provider_meta.get("id"), input_tokens=res.input_tokens,
                       output_tokens=res.output_tokens, reasoning_tokens=res.provider_meta.get("reasoning_tokens"),
                       finish_reason=res.finish_reason, latency_s=res.latency_s, cost_usd=c,
                       api_reported_cost_usd=res.provider_meta.get("api_reported_cost_usd"),
                       upstream=res.provider_meta.get("headers", {}).get("x-litellm-model-api-base"))
            total += c
            print(f"[{slot}] OK  model={res.model_reported} id={res.provider_meta.get('id')} "
                  f"token={res.input_tokens}/{res.output_tokens} biaya=${c:.6f} jawaban={res.text.strip()[:30]!r}")
        except AdapterError as e:  # 401/403 = kunci tidak valid
            ok_all = False
            rec.update(status="error", error=str(e)[:500], http_status=e.status, cost_usd=0.0)
            print(f"[{slot}] GAGAL status={e.status}: {str(e)[:200]}")
        log.write(rec)
    log.close()
    print(f"total biaya (harga normal): ${total:.6f} | log: {log.path}")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
