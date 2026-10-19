"""Runner dialog tiga giliran (G1 -> G2 -> G3) dari tahap3/dialogs_plan.jsonl.

Setiap dialog dimulai tanpa riwayat lain dan tanpa system prompt. Riwayat dialog itu sendiri ikut dikirim
di G2 dan G3. Satu baris JSON per dialog ditulis ke log append-only baru per run; dialog yang sudah sukses
dilewati (resume). Dialog yang gagal dicatat dengan status "error" dan akan diulang dari awal pada run berikut.

Contoh:
    python -m src.run_dialogs --models gemma2_9b_it --items A04 B01 --reps 1
    python -m src.run_dialogs --models komersial_A --items A04 --reps 1 --estimate-only
"""
from __future__ import annotations

import argparse
import sys

from .adapters import BaseAdapter, make_adapter
from .common import (AppendOnlyLog, check_phase, completed_ids, estimate_dialog_cost, load_config, model_cfg,
                     now_iso, read_jsonl, run_glob, runtime_info, seed_for, stamp, write_meta)
from .runlib import (BudgetTracker, add_filter_args, call_with_retry, compact_model, gen_params, log_prefix,
                     errors_cost, out_dir_for, select_rows, turn_cost)

PLAN_FIELDS = ("dialog_id", "item_id", "framing", "pressure", "lang", "model", "rep", "paraphrase", "order",
               "key_output", "misconception_output")


def run_one(adapter: BaseAdapter, m: dict, row: dict, cfg: dict, run_id: str, model_info: dict,
            dev_model: str | None) -> dict:
    """Jalankan satu dialog lengkap dan kembalikan rekaman log-nya (status ok/error/interrupted)."""
    seed = seed_for(row["dialog_id"])
    params, seed_sent = gen_params(m, cfg, seed)
    messages: list[dict] = []  # sesi bersih: tanpa system prompt, tanpa riwayat dialog lain
    turns, errors = [], []
    status = "ok"
    started = now_iso()
    try:
        for i, user_text in enumerate(row["turns"], 1):
            tag = f"G{i}"
            messages.append({"role": "user", "content": user_text})
            t_start = now_iso()
            res, errs = call_with_retry(adapter, list(messages), params, cfg["retry"])
            errors.extend({**e, "turn": tag} for e in errs)
            if res is None:
                status = "error"
                messages.pop()
                break
            messages.append({"role": "assistant", "content": res.text})
            d = res.to_dict()
            d.pop("text")
            turns.append({"turn": tag, "user": user_text, "response": res.text, "started_at": t_start,
                          "finished_at": now_iso(), "attempts": len(errs) + 1,
                          "cost_usd": turn_cost(m, res), **d})
    except KeyboardInterrupt:
        status = "interrupted"
    rec = {"run_id": run_id, **{k: row[k] for k in PLAN_FIELDS}, "status": status,
           "slot": row["model"], "model_info": model_info,
           "dev_substitute": {"plan_slot": row["model"], "actual_model": dev_model} if dev_model else None,
           "seed": seed, "seed_sent": seed_sent, "params_requested": params, "system_prompt": None,
           "messages": messages, "turns": turns, "errors": errors,
           "n_turns_completed": len(turns), "started_at": started, "finished_at": now_iso(),
           "latency_s_total": sum(t["latency_s"] for t in turns),
           "input_tokens_total": sum(t["input_tokens"] or 0 for t in turns),
           "output_tokens_total": sum(t["output_tokens"] or 0 for t in turns),
           # ringkasan per giliran dari API: field "model" dan id respons, token penalaran, biaya yang dilaporkan API
           "api_models": [t["model_reported"] for t in turns],
           "api_response_ids": [t["provider_meta"].get("id") for t in turns],
           "reasoning_tokens_total": sum(t["provider_meta"].get("reasoning_tokens") or 0 for t in turns),
           "api_reported_cost_usd": (sum(t["provider_meta"]["api_reported_cost_usd"] for t in turns)
                                     if turns and all("api_reported_cost_usd" in t["provider_meta"] for t in turns)
                                     else None),
           # giliran yang terpotong batas token (finish=length) dilaporkan eksplisit (keputusan peneliti 2026-10-18)
           "truncated_turns": [t["turn"] for t in turns if t["finish_reason"] == "length"],
           "failed_calls_cost_usd": errors_cost(m, errors),
           "cost_usd": sum(t["cost_usd"] for t in turns) + errors_cost(m, errors)}
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_filter_args(ap)
    ap.add_argument("--framings", nargs="+", choices=["netral", "yakin"])
    ap.add_argument("--pressures", nargs="+", choices=["P1", "P2", "P3"])
    args = ap.parse_args()

    cfg = load_config(args.config)
    check_phase(args.phase, args.allow_main, args.estimate_only)
    plan = list(read_jsonl(cfg["paths"]["dialogs_plan"]))
    out_dir = out_dir_for(cfg, args.phase, args.dev_model)
    interrupted = False
    budget = BudgetTracker(cfg)

    for slot in args.models:
        rows = select_rows(plan, slot, args)
        if not rows:
            print(f"[{slot}] tidak ada baris rencana yang cocok filter")
            continue
        m = model_cfg(cfg, args.dev_model or slot)
        prefix = log_prefix("dialogs", slot, args.dev_model)
        done = completed_ids(out_dir, run_glob(prefix), "dialog_id")
        todo = [r for r in rows if r["dialog_id"] not in done]
        if args.limit is not None:
            todo = todo[: args.limit]
        est = sum(estimate_dialog_cost(m, r["turns"], cfg) for r in todo)
        ok, why = budget.check(m, est)
        print(f"[{slot}] cocok filter={len(rows)} sudah sukses={sum(r['dialog_id'] in done for r in rows)} "
              f"akan dijalankan={len(todo)} | estimasi biaya=${est:.4f} terpakai=${budget.spent:.4f} "
              f"batas=${budget.limit:.2f} ambang lapor=${budget.alert:.2f}")
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
                   {"run_id": run_id, "kind": "dialogs", "phase": args.phase, "slot": slot,
                    "dev_model": args.dev_model, "model": desc, "config_slot": {k: v for k, v in m.items()
                                                                              if not k.startswith("_")},
                    "generation": cfg["ollama"] if m["provider"] == "ollama" else {"max_tokens": cfg["max_tokens"]},
                    "retry": cfg["retry"], "n_planned": len(todo), "started_at": now_iso(), **runtime_info()})
        log = AppendOnlyLog(out_dir / f"{run_id}.jsonl")
        n_ok = n_err = 0
        interrupted_budget = False
        try:
            for i, row in enumerate(todo, 1):
                ok, why = budget.check(m, estimate_dialog_cost(m, row["turns"], cfg))
                if not ok:
                    print(f"[{slot}] BERHENTI: {why}")
                    interrupted_budget = True
                    break
                rec = run_one(adapter, m, row, cfg, run_id, info, args.dev_model)
                log.write(rec)
                budget.add(rec["cost_usd"])
                n_ok += rec["status"] == "ok"
                n_err += rec["status"] == "error"
                lat = rec["latency_s_total"]
                print(f"[{slot}] {i}/{len(todo)} {row['dialog_id']} {rec['status']} {lat:.1f}s "
                      f"out_tok={rec['output_tokens_total']} biaya_kumulatif=${budget.spent:.4f}", flush=True)
                if rec["truncated_turns"]:
                    print(f"[{slot}] PERHATIAN: {row['dialog_id']} terpotong (finish=length) di "
                          f"{', '.join(rec['truncated_turns'])}", flush=True)
                if rec["status"] == "interrupted":
                    interrupted = True
                    break
        except KeyboardInterrupt:
            interrupted = True
        finally:
            log.close()
        print(f"[{slot}] selesai run {run_id}: ok={n_ok} error={n_err} -> {log.path}")
        if interrupted_budget:
            print("Run dihentikan oleh pengaman anggaran; laporkan ke peneliti sebelum melanjutkan.")
            sys.exit(3)
        if interrupted:
            print("Dihentikan oleh pengguna; jalankan ulang perintah yang sama untuk melanjutkan.")
            sys.exit(130)


if __name__ == "__main__":
    main()
