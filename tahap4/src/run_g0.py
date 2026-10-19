"""Runner G0 (cek pengetahuan dasar) dari tahap3/g0_plan.jsonl: satu panggilan per baris, sesi bersih.

Log terpisah dari dialog: runs/raw/<fase>/g0_<slot>_<waktu>.jsonl. Resume berdasarkan g0_id yang sudah sukses.

Contoh:
    python -m src.run_g0 --models gemma2_9b_it sahabatai_9b_it
    python -m src.run_g0 --models gemma2_9b_it --items A01 --limit 1 --dev-model gemma3_4b_dev
"""
from __future__ import annotations

import argparse
import sys

from .adapters import make_adapter
from .common import (AppendOnlyLog, check_phase, completed_ids, estimate_dialog_cost, load_config, model_cfg,
                     now_iso, read_jsonl, run_glob, runtime_info, seed_for, stamp, write_meta)
from .runlib import (BudgetTracker, add_filter_args, call_with_retry, compact_model, gen_params, log_prefix,
                     errors_cost, out_dir_for, select_rows, turn_cost)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_filter_args(ap)
    args = ap.parse_args()

    cfg = load_config(args.config)
    check_phase(args.phase, args.allow_main, args.estimate_only)
    plan = list(read_jsonl(cfg["paths"]["g0_plan"]))
    out_dir = out_dir_for(cfg, args.phase, args.dev_model)
    budget = BudgetTracker(cfg)

    for slot in args.models:
        rows = select_rows(plan, slot, args)
        if not rows:
            print(f"[{slot}] tidak ada baris G0 yang cocok filter")
            continue
        m = model_cfg(cfg, args.dev_model or slot)
        prefix = log_prefix("g0", slot, args.dev_model)
        done = completed_ids(out_dir, run_glob(prefix), "g0_id")
        todo = [r for r in rows if r["g0_id"] not in done]
        if args.limit is not None:
            todo = todo[: args.limit]
        # G0 menjawab jauh lebih pendek daripada giliran dialog: pakai est_g0_output_tokens per slot bila ada
        g0_m = {**m, "est_output_tokens_per_turn": m.get("est_g0_output_tokens") or m.get("est_output_tokens_per_turn")}
        est = sum(estimate_dialog_cost(g0_m, [r["prompt"]], cfg) for r in todo)
        ok, why = budget.check(m, est)
        print(f"[{slot}] G0 cocok filter={len(rows)} sudah sukses={sum(r['g0_id'] in done for r in rows)} "
              f"akan dijalankan={len(todo)} | estimasi biaya=${est:.4f} terpakai=${budget.spent:.4f}")
        if not ok:
            print(f"[{slot}] DITOLAK: {why}")
            continue
        if args.estimate_only or not todo:
            continue

        adapter = make_adapter(m, cfg)
        desc = adapter.describe()
        info = compact_model(desc)
        run_id = f"{prefix}_{stamp()}"
        write_meta(out_dir / f"{run_id}.meta.json",
                   {"run_id": run_id, "kind": "g0", "phase": args.phase, "slot": slot, "dev_model": args.dev_model,
                    "model": desc, "config_slot": {k: v for k, v in m.items() if not k.startswith("_")},
                    "generation": cfg["ollama"] if m["provider"] == "ollama" else {"max_tokens": cfg["max_tokens"]},
                    "retry": cfg["retry"], "n_planned": len(todo), "started_at": now_iso(), **runtime_info()})
        log = AppendOnlyLog(out_dir / f"{run_id}.jsonl")
        n_ok = n_err = 0
        stopped_budget = False
        try:
            for i, row in enumerate(todo, 1):
                ok, why = budget.check(m, estimate_dialog_cost(g0_m, [row["prompt"]], cfg))
                if not ok:
                    print(f"[{slot}] BERHENTI: {why}")
                    stopped_budget = True
                    break
                seed = seed_for(row["g0_id"])
                params, seed_sent = gen_params(m, cfg, seed)
                messages = [{"role": "user", "content": row["prompt"]}]
                started = now_iso()
                res, errs = call_with_retry(adapter, messages, params, cfg["retry"])
                rec = {"run_id": run_id, **{k: row[k] for k in ("g0_id", "item_id", "lang", "model", "rep",
                                                               "key_output")},
                       "status": "ok" if res else "error", "slot": slot, "model_info": info,
                       "dev_substitute": {"plan_slot": slot, "actual_model": args.dev_model} if args.dev_model else None,
                       "seed": seed, "seed_sent": seed_sent, "params_requested": params, "system_prompt": None,
                       "messages": messages + ([{"role": "assistant", "content": res.text}] if res else []),
                       "response": res.text if res else None, "errors": errs, "attempts": len(errs) + (1 if res else 0),
                       "started_at": started, "finished_at": now_iso(), "cost_usd": (turn_cost(m, res) if res else 0.0) + errors_cost(m, errs)}
                if res:
                    d = res.to_dict()
                    d.pop("text")
                    rec.update(d)
                    rec["response_id"] = res.provider_meta.get("id")
                    rec["reasoning_tokens"] = res.provider_meta.get("reasoning_tokens")
                    rec["api_reported_cost_usd"] = res.provider_meta.get("api_reported_cost_usd")
                if res is not None:
                    rec["truncated"] = res.finish_reason == "length"
                log.write(rec)
                budget.add(rec["cost_usd"])
                n_ok += res is not None
                n_err += res is None
                print(f"[{slot}] {i}/{len(todo)} {row['g0_id']} {rec['status']} "
                      f"{(res.latency_s if res else 0):.1f}s biaya_kumulatif=${budget.spent:.4f}", flush=True)
                if rec.get("truncated"):
                    print(f"[{slot}] PERHATIAN: {row['g0_id']} terpotong (finish=length)", flush=True)
        except KeyboardInterrupt:
            log.close()
            print(f"Dihentikan; ok={n_ok} error={n_err}. Jalankan ulang perintah yang sama untuk melanjutkan.")
            sys.exit(130)
        log.close()
        print(f"[{slot}] selesai run {run_id}: ok={n_ok} error={n_err} -> {log.path}")
        if stopped_budget:
            print("Run dihentikan oleh pengaman anggaran; laporkan ke peneliti sebelum melanjutkan.")
            sys.exit(3)


if __name__ == "__main__":
    main()
