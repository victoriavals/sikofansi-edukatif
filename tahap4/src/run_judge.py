"""Runner LLM penilai: label setiap dialog sukses memakai tahap3/judge_prompt.md dan judge_schema.json.

- Prompt sistem = blok "System prompt" + bagian "Illustrative examples" dari judge_prompt.md, apa adanya
  (keputusan peneliti 2026-10-18). Template pengguna = blok "User prompt template".
- Kandidat "(tidak ada output)" ditampilkan ke penilai sebagai "(tidak ada output) [no output]"; data terkunci tidak diubah.
- Urutan kandidat A/B diacak per dialog: sha256(f"{seed}:{dialog_id}") genap -> A = kunci; dicatat di keluaran.
- Penilai dipanggil dengan temperature 0 dan keluaran terstruktur (json_schema). Bila API menolak temperature atau
  json_schema, adapter memakai default penyedia / mode JSON dan mencatatnya. Keluaran divalidasi terhadap skema
  (plus cek giliran G1, G2, G3 berurutan); tidak valid -> diulang, maksimal ``max_json_attempts`` kali.
- Label A/B dipetakan ke Benar/Miskonsepsi; AMBIGUOUS -> Ambigu; OTHER -> Salah lain; NONE -> Tidak disebut.
- Keluaran: labels/<fase>/judge_<penilai>_<slot>_<waktu>.jsonl (append-only, resume per dialog_id).
- ``--stability``: nilai ulang 10% dialog berlabel (sampel acak, seed tetap) ke stability_<penilai>_<slot>_<waktu>.jsonl.
- Resume melewati semua dialog yang sudah punya rekaman (ok maupun invalid). Dialog invalid hanya dinilai ulang lewat
  ``--rejudge-invalid`` (atas keputusan peneliti); rekamannya diberi field ``rejudge`` berisi alasan dan run sebelumnya.
- ``--estimate-only --from-plan``: estimasi biaya penilai untuk semua dialog rencana fase itu (tanpa panggilan model).

Contoh:
    python -m src.run_judge --models gemma2_9b_it sahabatai_9b_it
    python -m src.run_judge --models gemma2_9b_it sahabatai_9b_it --stability
    python -m src.run_judge --phase tahap5 --models gemma2_9b_it komersial_A --estimate-only --from-plan
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics as st
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .adapters import BaseAdapter, make_adapter
from .common import (AppendOnlyLog, completed_ids, cost_usd, iter_records, kode_block, load_config, model_cfg,
                     now_iso, read_jsonl, run_glob, runtime_info, stamp, write_meta)
from .runlib import BudgetTracker, call_with_retry, compact_model, errors_cost, turn_cost

LABEL_MAP = {"AMBIGUOUS": "Ambigu", "OTHER": "Salah lain", "NONE": "Tidak disebut"}
FENCE_JSON_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.S)
EXAMPLES_HEADING = "## Illustrative examples (training only, not study data)"
CANDIDATE_DISPLAY = {"(tidak ada output)": "(tidak ada output) [no output]"}


def parse_judge_prompt(md_path: Path) -> tuple[str, str, str]:
    """Ambil (blok prompt sistem, template pengguna, bagian contoh ilustrasi) dari judge_prompt.md, apa adanya."""
    md = md_path.read_text(encoding="utf-8")
    sys_m = re.search(r"## System prompt\s*```text\n(.*?)\n```", md, re.S)
    usr_m = re.search(r"## User prompt template\s*```text\n(.*?)\n```", md, re.S)
    ex_i = md.find(EXAMPLES_HEADING)
    if not (sys_m and usr_m) or ex_i < 0:
        raise SystemExit(f"Tidak menemukan blok prompt/contoh di {md_path}")
    return sys_m.group(1), usr_m.group(1), md[ex_i:].strip()


def build_system_prompt(system_block: str, examples: str) -> str:
    """Prompt sistem penilai: blok sistem lalu bagian contoh ilustrasi (keputusan peneliti 2026-10-18)."""
    return f"{system_block}\n\n{examples}"


def candidate_order(dialog_id: str, seed: int) -> dict[str, str]:
    """Urutan kandidat reprodusibel per dialog: {'A': 'key'|'misconception', 'B': ...}."""
    h = int(hashlib.sha256(f"{seed}:{dialog_id}".encode("utf-8")).hexdigest(), 16)
    return {"A": "key", "B": "misconception"} if h % 2 == 0 else {"A": "misconception", "B": "key"}


def display_candidate(text: str) -> str:
    """Teks kandidat seperti yang ditampilkan ke penilai."""
    return CANDIDATE_DISPLAY.get(text, text)


def candidates(rec: dict, order: dict[str, str], display: bool = False) -> tuple[str, str]:
    """Teks kandidat (A, B) untuk satu dialog sesuai urutan acak; ``display`` = bentuk yang ditampilkan."""
    cand = {"key": rec["key_output"], "misconception": rec["misconception_output"]}
    a, b = cand[order["A"]], cand[order["B"]]
    return (display_candidate(a), display_candidate(b)) if display else (a, b)


def build_user_prompt(template: str, rec: dict, code: str, order: dict[str, str]) -> str:
    """Isi template penilai dengan kode, kandidat (bentuk tampilan), dan tiga pasang giliran dari log dialog."""
    cand_a, cand_b = candidates(rec, order, display=True)
    values: dict[str, str] = {"kode_block": kode_block(code), "kandidat_A": cand_a, "kandidat_B": cand_b}
    for i, t in enumerate(rec["turns"], 1):
        values[f"turn_{i}"] = t["user"]
        values[f"response_{i}"] = t["response"]
    return template.format(**values)


def parse_and_validate(text: str, validator: Draft202012Validator) -> tuple[dict | None, list[str]]:
    """Parse JSON keluaran penilai dan validasi. Kembalikan (objek atau None, daftar masalah)."""
    s = text.strip()
    m = FENCE_JSON_RE.match(s)
    if m:
        s = m.group(1)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as e:
        return None, [f"JSONDecodeError: {e}"]
    problems = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in validator.iter_errors(obj)]
    if not problems and [t["turn"] for t in obj["turns"]] != ["G1", "G2", "G3"]:
        problems.append("giliran harus G1, G2, G3 berurutan")
    return (obj if not problems else None), problems


def map_label(label: str, order: dict[str, str]) -> str:
    """Petakan label penilai ke label analisis sesuai CLAUDE.md."""
    if label in ("A", "B"):
        return "Benar" if order[label] == "key" else "Miskonsepsi"
    return LABEL_MAP[label]


def _norm(s: str) -> str:
    return " ".join(s.split())


def consistency_flag(turn: dict, cand_a: str, cand_b: str) -> str | None:
    """Tandai label A/B yang bertentangan dengan claimed_output penilai sendiri (label TIDAK diubah).

    Pembanding string setelah normalisasi spasi, terhadap bentuk mentah maupun bentuk tampilan kandidat.
    Parafrase ("2 lalu 3") wajar tidak cocok, jadi flag ini hanya petunjuk untuk validasi manusia.
    """
    claimed = _norm(turn.get("claimed_output") or "")
    forms_a = {_norm(cand_a), _norm(display_candidate(cand_a))}
    forms_b = {_norm(cand_b), _norm(display_candidate(cand_b))}
    label = turn["label"]
    if label == "A" and claimed in forms_b and not forms_a & forms_b:
        return "label A tetapi claimed_output sama dengan kandidat B"
    if label == "B" and claimed in forms_a and not forms_a & forms_b:
        return "label B tetapi claimed_output sama dengan kandidat A"
    if label in ("A", "B", "AMBIGUOUS") and claimed and claimed not in forms_a | forms_b:
        return f"label {label} tetapi claimed_output bukan A/B secara harfiah"
    return None


def stability_sample(ids: list[str], frac: float, seed: int, slot: str) -> list[str]:
    """Sampel acak reprodusibel ``ceil(frac * n)`` dialog_id untuk uji stabilitas satu slot."""
    ids = sorted(ids)
    k = min(len(ids), math.ceil(frac * len(ids)))
    return sorted(random.Random(f"{seed}:{slot}").sample(ids, k))


class JudgeContext:
    """Semua bahan tetap satu run penilai (prompt, skema, kode butir, parameter)."""

    def __init__(self, cfg: dict, jm: dict):
        jcfg = cfg["judge"]
        md_path = cfg["paths"]["judge_prompt"]
        block, self.user_template, examples = parse_judge_prompt(md_path)
        self.system_prompt = build_system_prompt(block, examples)
        self.system_sha256 = hashlib.sha256(self.system_prompt.encode("utf-8")).hexdigest()
        # versi prompt (judul "(vX.Y)") dan SHA256 berkas judge_prompt.md dicatat di setiap rekaman label
        md_bytes = md_path.read_bytes()
        ver = re.search(r"\(v([\d.]+)\)", md_bytes.decode("utf-8").splitlines()[0])
        self.prompt_version = ver.group(1) if ver else None
        self.prompt_file_sha256 = hashlib.sha256(md_bytes).hexdigest()
        self.schema = json.loads(cfg["paths"]["judge_schema"].read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(self.schema)
        items = json.loads(cfg["paths"]["items"].read_text(encoding="utf-8"))["items"]
        self.codes = {it["id"]: it["kode"] for it in items}
        self.order_seed = int(jcfg["candidate_order_seed"])
        self.max_json = int(jcfg["max_json_attempts"])
        self.params: dict[str, Any] = {"temperature": jcfg.get("temperature", 0),
                                       "max_tokens": int(jcfg["max_tokens"]), "json_schema": self.schema}
        self.jm = jm
        self.cfg = cfg


def label_one(ctx: JudgeContext, adapter: BaseAdapter, rec: dict, path: Path, run_id: str, desc: dict,
              dev_judge: bool) -> dict:
    """Labeli satu dialog (maks. ``max_json_attempts`` percobaan JSON) dan kembalikan rekaman log-nya."""
    order = candidate_order(rec["dialog_id"], ctx.order_seed)
    user_prompt = build_user_prompt(ctx.user_template, rec, ctx.codes[rec["item_id"]], order)
    messages = [{"role": "system", "content": ctx.system_prompt}, {"role": "user", "content": user_prompt}]
    attempts, parsed, cost = [], None, 0.0
    for a in range(1, ctx.max_json + 1):
        res, errs = call_with_retry(adapter, messages, ctx.params, ctx.cfg["retry"])
        cost += errors_cost(ctx.jm, errs)  # respons kosong yang tetap ditagih
        if res is None:
            attempts.append({"attempt": a, "call_errors": errs, "raw": None, "valid": False})
            continue
        cost += turn_cost(ctx.jm, res)
        obj, problems = parse_and_validate(res.text, ctx.validator)
        d = res.to_dict()
        d.pop("text")
        attempts.append({"attempt": a, "call_errors": errs, "raw": res.text, "valid": obj is not None,
                         "problems": problems, **d})
        if obj is not None:
            parsed = obj
            break
    labels = None
    cand_a, cand_b = candidates(rec, order)
    if parsed:
        labels = [{"turn": t["turn"], "label_judge": t["label"], "label": map_label(t["label"], order),
                   "claimed_output": t["claimed_output"], "rationale": t["rationale"],
                   "consistency_flag": consistency_flag(t, cand_a, cand_b)}
                  for t in parsed["turns"]]
    reported = [x.get("provider_meta", {}).get("api_reported_cost_usd") for x in attempts if x.get("raw") is not None]
    return {"run_id": run_id, "dialog_id": rec["dialog_id"], "status": "ok" if parsed else "invalid",
            **{k: rec[k] for k in ("item_id", "framing", "pressure", "lang", "rep", "slot",
                                   "key_output", "misconception_output")},
            "source_log": path.name, "source_run_id": rec["run_id"],
            "judge_info": compact_model(desc), "dev_judge": dev_judge,
            "candidate_order": order, "candidate_order_seed": ctx.order_seed,
            "kandidat_A": cand_a, "kandidat_B": cand_b,
            "kandidat_A_tampil": display_candidate(cand_a), "kandidat_B_tampil": display_candidate(cand_b),
            "judge_prompt_version": ctx.prompt_version, "judge_prompt_file_sha256": ctx.prompt_file_sha256,
            "system_prompt_sha256": ctx.system_sha256, "user_prompt": user_prompt, "n_attempts": len(attempts),
            "json_valid_first_try": bool(attempts and attempts[0]["valid"]),
            "judge_params_sent": attempts[-1].get("params_sent") if attempts else None,
            "attempts": attempts, "judge_output": parsed, "labels": labels, "labeled_at": now_iso(),
            "api_reported_cost_usd": sum(reported) if reported and all(r is not None for r in reported) else None,
            "cost_usd": cost}


def load_dialogs(src_dir: Path, prefix: str) -> dict[str, tuple[Path, dict]]:
    """Dialog sukses (pertama per dialog_id) dari log mentah satu slot."""
    dialogs: dict[str, tuple[Path, dict]] = {}
    for path, rec in iter_records(src_dir, run_glob(prefix)):
        if rec.get("status") == "ok" and rec["dialog_id"] not in dialogs:
            dialogs[rec["dialog_id"]] = (path, rec)
    return dialogs


def estimate_from_plan(cfg: dict, ctx: JudgeContext, slots: list[str], phase: str, ref_phase: str = "tahap4") -> None:
    """Estimasi biaya penilai untuk semua dialog rencana ``phase`` dari ukuran nyata run penilai ``ref_phase``.

    Token input per dialog = (panjang prompt sistem + prompt pengguna dengan respons sepanjang rata-rata respons
    slot itu di log ``ref_phase``) / (karakter per token yang teramati pada penilai). Token keluaran dan jumlah
    panggilan per dialog = rata-rata nyata dari log penilai ``ref_phase``, TERMASUK panggilan berrespons kosong
    yang tetap ditagih (penalaran menghabiskan max_tokens). Ditambah fraksi uji stabilitas.
    """
    jlabels = [r for _, r in iter_records(cfg["paths"]["labels_dir"] / ref_phase, "judge_*.jsonl")]
    calls = [a for r in jlabels for a in r["attempts"] if a.get("raw") is not None]
    if not calls:
        raise SystemExit(f"Belum ada log penilai di labels/{ref_phase}; jalankan penilai pilot dulu.")
    cpt = st.mean(len(ctx.system_prompt) + len(r["user_prompt"]) for r in jlabels) / st.mean(a["input_tokens"] for a in calls)
    # respons kosong yang ditagih: token dari field billed_* (log baru) atau dari teks galat (log lama)
    empty_out = []
    for r in jlabels:
        for a in r["attempts"]:
            for e in a.get("call_errors", []):
                if e.get("billed_output_tokens") is not None:
                    empty_out.append(e["billed_output_tokens"])
                elif (m := re.search(r"Respons kosong .*output_tokens=(\d+)", e.get("error", ""))):
                    empty_out.append(int(m.group(1)))
    out_per_call = (sum(a["output_tokens"] for a in calls) + sum(empty_out)) / (len(calls) + len(empty_out))
    calls_per_dialog = (len(calls) + len(empty_out)) / len(jlabels)
    print(f"[penilai] panggilan sukses={len(calls)}, respons kosong ditagih={len(empty_out)} "
          f"({len(empty_out) / (len(calls) + len(empty_out)):.0%} dari semua panggilan)")
    frac = float(cfg["judge"].get("stability_frac", 0))
    plan = list(read_jsonl(cfg["paths"]["dialogs_plan"]))
    print(f"[penilai] acuan {ref_phase}: {len(jlabels)} dialog, {cpt:.2f} karakter/token, {out_per_call:.0f} token "
          f"keluaran/panggilan, {calls_per_dialog:.3f} panggilan/dialog, stabilitas +{frac:.0%}")
    total = tot_in = tot_out = 0.0
    for slot in slots:
        rows = [r for r in plan if r["model"] == slot]
        resp = [t["response"] for _, d in iter_records(cfg["paths"]["runs_dir"] / "tahap4", run_glob(f"dialogs_{slot}"))
                if d.get("status") == "ok" for t in d["turns"]]
        if not resp:
            print(f"[penilai] {slot}: tidak ada respons acuan di {ref_phase}; dilewati")
            continue
        mean_resp = st.mean(len(x) for x in resp)
        n_calls = len(rows) * (1 + frac) * calls_per_dialog
        in_tok = sum(len(ctx.system_prompt) + len(build_user_prompt(
            ctx.user_template, {**r, "turns": [{"user": u, "response": "x" * int(mean_resp)} for u in r["turns"]]},
            ctx.codes[r["item_id"]], candidate_order(r["dialog_id"], ctx.order_seed))) for r in rows) / cpt
        in_tok *= (1 + frac) * calls_per_dialog
        out_tok = n_calls * out_per_call
        c = cost_usd(ctx.jm, int(in_tok), int(out_tok))
        total += c
        tot_in += in_tok
        tot_out += out_tok
        print(f"[penilai] {slot}: dialog={len(rows)} (respons rata-rata {mean_resp:.0f} karakter, n acuan={len(resp)}) "
              f"panggilan~{n_calls:.0f} token input~{in_tok/1e6:.3f}M keluaran~{out_tok/1e6:.3f}M biaya~${c:.4f}")
    print(f"[penilai] TOTAL fase {phase}: token input~{tot_in/1e6:.3f}M keluaran~{tot_out/1e6:.3f}M biaya~${total:.4f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--phase", default="tahap4")
    ap.add_argument("--models", nargs="+", required=True, help="slot model yang dialognya dilabeli")
    ap.add_argument("--source-dev-model", help="labeli log uji asap runs/dev/ dengan model dev ini")
    ap.add_argument("--dev-judge", help="uji asap: pakai model dev_models sebagai penilai; keluaran ke labels/dev/")
    ap.add_argument("--stability", action="store_true", help="nilai ulang sampel 10%% dialog berlabel (uji stabilitas)")
    ap.add_argument("--rejudge-invalid", action="store_true",
                    help="nilai ulang dialog yang semua penilaiannya invalid (hanya atas keputusan peneliti)")
    ap.add_argument("--rejudge-reason", default="keputusan peneliti 2026-10-18 (Tahap 4B butir 1): max_tokens 4096",
                    help="alasan yang dicatat di log untuk --rejudge-invalid")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--estimate-only", action="store_true")
    ap.add_argument("--from-plan", action="store_true", help="dengan --estimate-only: estimasi dari rencana fase")
    ap.add_argument("--ref-phase", default="tahap4",
                    help="dengan --from-plan: folder label acuan ukuran nyata (mis. tahap4c untuk prompt v1.1)")
    ap.add_argument("--label-phase", help="folder label (labels/<label-phase>/), mis. tahap4c untuk kalibrasi; "
                                          "dialog tetap dibaca dari runs/raw/<phase>/. Default = --phase")
    ap.add_argument("--stage-limit-usd", type=float,
                    help="batas biaya tahap ini (biaya tercatat di folder label tahap + run ini); berhenti bila lewat")
    args = ap.parse_args()

    cfg = load_config(args.config)
    jm = model_cfg(cfg, args.dev_judge) if args.dev_judge else model_cfg(cfg, "judge")
    ctx = JudgeContext(cfg, jm)
    if args.estimate_only and args.from_plan:
        estimate_from_plan(cfg, ctx, args.models, args.phase, ref_phase=args.ref_phase)
        return
    if args.phase == "tahap5":
        raise SystemExit("Penilai fase tahap5 hanya setelah data utama ada (izin peneliti).")
    judge_name = args.dev_judge or f"judge-{jm['model_id']}".replace("/", "_").replace(":", "_")
    src_dir = (cfg["paths"]["dev_dir"] if args.source_dev_model else cfg["paths"]["runs_dir"]) / args.phase
    out_dir = cfg["paths"]["labels_dir"] / ("dev" if (args.dev_judge or args.source_dev_model)
                                            else (args.label_phase or args.phase))
    budget = BudgetTracker(cfg, stage_dir=out_dir if args.stage_limit_usd is not None else None,
                           stage_limit=args.stage_limit_usd)
    print(f"[penilai] prompt v{ctx.prompt_version} (sha256 berkas {ctx.prompt_file_sha256[:12]}...), "
          f"max_tokens {ctx.params['max_tokens']}, label -> {out_dir}"
          + (f", batas tahap ${args.stage_limit_usd:.2f} (terpakai ${budget.stage_spent:.4f})"
             if args.stage_limit_usd is not None else ""))

    for slot in args.models:
        tested_family = (cfg["models"].get(slot) or {}).get("family")
        if not args.dev_judge and tested_family and tested_family == jm.get("family"):
            raise SystemExit(f"Penilai ({jm.get('family')}) sekeluarga dengan model yang diuji ({slot}); ganti penilai.")
        prefix = f"dialogs_{slot}__{args.source_dev_model}" if args.source_dev_model else f"dialogs_{slot}"
        dialogs = load_dialogs(src_dir, prefix)
        primary_prefix = f"judge_{judge_name}_{slot}"
        existing: dict[str, list[dict]] = {}
        for _, r in iter_records(out_dir, run_glob(primary_prefix)):
            existing.setdefault(r["dialog_id"], []).append(r)
        ok_ids = {d for d, rs in existing.items() if any(x["status"] == "ok" for x in rs)}
        invalid_ids = set(existing) - ok_ids
        if args.stability:
            sample = stability_sample(list(ok_ids), float(cfg["judge"]["stability_frac"]),
                                      int(cfg["judge"]["stability_seed"]), slot)
            out_prefix = f"stability_{judge_name}_{slot}"
            done = completed_ids(out_dir, run_glob(out_prefix), "dialog_id")
            todo = [dialogs[d] for d in sample if d not in done and d in dialogs]
            print(f"[{slot}] stabilitas: berlabel={len(ok_ids)} sampel={len(sample)} {sample}")
        elif args.rejudge_invalid:
            # hanya atas keputusan peneliti: dialog yang semua penilaiannya invalid dinilai ulang, ditandai di log
            out_prefix = primary_prefix
            done = ok_ids
            todo = [dialogs[d] for d in sorted(invalid_ids) if d in dialogs]
            print(f"[{slot}] nilai ulang dialog invalid: {sorted(invalid_ids)}")
        else:
            # resume: lewati SEMUA dialog yang sudah punya rekaman (ok maupun invalid); invalid hanya dinilai
            # ulang lewat --rejudge-invalid agar batas "maks. 3 percobaan" tidak dilampaui diam-diam
            out_prefix = primary_prefix
            done = set(existing)
            todo = [v for k, v in sorted(dialogs.items(), key=lambda kv: kv[1][1].get("order", 0)) if k not in done]
        if args.limit is not None:
            todo = todo[: args.limit]
        cpt = cfg["cost_estimate"]["chars_per_token"]
        est_in = sum(len(ctx.system_prompt) + len(build_user_prompt(
            ctx.user_template, r, ctx.codes[r["item_id"]], candidate_order(r["dialog_id"], ctx.order_seed)))
            for _, r in todo) / cpt
        est = cost_usd(jm, int(est_in), int(cfg["judge"]["max_tokens"]) * len(todo))  # keluaran: batas atas
        ok, why = budget.check(jm, est)
        print(f"[{slot}] dialog sukses={len(dialogs)} sudah selesai={len(done)} akan dilabeli={len(todo)} "
              f"| estimasi biaya (batas atas)=${est:.4f} terpakai=${budget.spent:.4f} batas=${budget.limit:.2f}")
        if not ok:
            print(f"[{slot}] DITOLAK: {why}")
            continue
        if args.estimate_only or not todo:
            continue

        adapter = make_adapter(jm, cfg)
        desc = adapter.describe()
        run_id = f"{out_prefix}_{stamp()}"
        write_meta(out_dir / f"{run_id}.meta.json",
                   {"run_id": run_id, "kind": "judge_stability" if args.stability else "judge", "phase": args.phase,
                    "slot": slot, "judge": desc, "dev_judge": bool(args.dev_judge), "source_dir": str(src_dir),
                    "params_requested": {**ctx.params, "json_schema": "judge_schema.json"},
                    "candidate_order_seed": ctx.order_seed, "max_json_attempts": ctx.max_json,
                    "candidate_display": CANDIDATE_DISPLAY,
                    "judge_prompt_version": ctx.prompt_version, "judge_prompt_file_sha256": ctx.prompt_file_sha256,
                    "label_phase": args.label_phase or args.phase, "stage_limit_usd": args.stage_limit_usd,
                    "system_prompt": ctx.system_prompt, "system_prompt_sha256": ctx.system_sha256,
                    "started_at": now_iso(), **runtime_info()})
        log = AppendOnlyLog(out_dir / f"{run_id}.jsonl")
        n_ok = n_bad = 0
        stopped_budget = False
        try:
            for i, (path, rec) in enumerate(todo, 1):
                ok, why = budget.check(jm, est / max(len(todo), 1))
                if not ok:
                    print(f"[{slot}] BERHENTI: {why}")
                    stopped_budget = True
                    break
                out = label_one(ctx, adapter, rec, path, run_id, desc, bool(args.dev_judge))
                if args.stability:
                    out["stability"] = True
                if args.rejudge_invalid:
                    prev = existing.get(rec["dialog_id"], [])
                    out["rejudge"] = {"dinilai_ulang": True, "alasan": args.rejudge_reason,
                                      "previous_run_ids": [p["run_id"] for p in prev],
                                      "previous_status": [p["status"] for p in prev],
                                      "max_tokens": ctx.params["max_tokens"]}
                log.write(out)
                budget.add(out["cost_usd"])
                n_ok += out["status"] == "ok"
                n_bad += out["status"] != "ok"
                print(f"[{slot}] {i}/{len(todo)} {rec['dialog_id']} {out['status']} percobaan={out['n_attempts']} "
                      f"{[l['label'] for l in out['labels']] if out['labels'] else ''}", flush=True)
        except KeyboardInterrupt:
            log.close()
            print(f"Dihentikan; ok={n_ok} invalid={n_bad}. Jalankan ulang perintah yang sama untuk melanjutkan.")
            sys.exit(130)
        log.close()
        end = {"run_id": run_id, "finished_at": now_iso(), "ok": n_ok, "invalid": n_bad,
               "temperature_dropped": getattr(adapter, "temperature_dropped", None),
               "json_mode": getattr(adapter, "json_mode", None),
               "fallback_events": getattr(adapter, "fallback_events", None)}
        write_meta(out_dir / f"{run_id}.end.json", end)
        print(f"[{slot}] selesai {run_id}: ok={n_ok} invalid={n_bad} temperature_dropped={end['temperature_dropped']} "
              f"json_mode={end['json_mode']} biaya_kumulatif=${budget.spent:.4f} -> {log.path}")
        if stopped_budget:
            print("Run dihentikan oleh pengaman anggaran; laporkan ke peneliti sebelum melanjutkan.")
            sys.exit(3)


if __name__ == "__main__":
    main()
