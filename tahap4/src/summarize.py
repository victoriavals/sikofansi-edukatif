"""Ringkasan angka untuk laporan, dihitung langsung dari log (tanpa mengubah log).

Keluaran: reports/summary_<fase>.json dan potongan Markdown di reports/fragments/: G0, dialog, contoh dialog,
penilai (distribusi label, JSON valid, consistency_flag), stabilitas penilai, penarikan koreksi
(Benar -> Tidak disebut), ringkasan dan contoh uji asap model API, serta reports/pilot_judge_review.csv.

Contoh:
    python -m src.summarize --models gemma2_9b_it sahabatai_9b_it
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

from .common import iter_records, load_config, run_glob

PLAN_DIALOGS_PER_MODEL = 1080


def latest_grades(labels_dir: Path, slot: str) -> list[dict]:
    """Baca CSV nilai G0 terbaru untuk satu slot."""
    files = sorted(labels_dir.glob(f"g0_grades_{slot}_[0-9]*.csv"))
    if not files:
        return []
    with open(files[-1], encoding="utf-8") as f:
        return list(csv.DictReader(f))


def g0_section(slot: str, rows: list[dict]) -> tuple[dict, str]:
    """Akurasi G0 per bahasa, tabel per butir, butir salah >= 2/3, kasus cek manual."""
    by_lang: dict[str, Counter] = defaultdict(Counter)
    per_item: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in rows:
        by_lang[r["lang"]][r["status"]] += 1
        per_item[(r["item_id"], r["lang"])][r["status"]] += 1
    stats = {}
    md = [f"#### {slot}\n", "| Bahasa | n | Benar (otomatis) | Salah | Cek manual | Akurasi batas bawah | Akurasi batas atas |",
          "|---|---|---|---|---|---|---|"]
    for lang in ("id", "en"):
        c = by_lang.get(lang, Counter())
        n = sum(c.values())
        if not n:
            continue
        lo, hi = c["benar"] / n, (c["benar"] + c["cek_manual"]) / n
        stats[lang] = {"n": n, "benar": c["benar"], "salah": c["salah"], "cek_manual": c["cek_manual"],
                       "akurasi_bawah": lo, "akurasi_atas": hi}
        md.append(f"| {lang} | {n} | {c['benar']} | {c['salah']} | {c['cek_manual']} | {lo:.1%} | {hi:.1%} |")
    items = sorted({r["item_id"] for r in rows})
    md += ["", "Benar dari 3 ulangan per butir (angka dalam kurung = cek manual):", "",
           "| Butir | id | en | Butir | id | en | Butir | id | en |", "|---|---|---|---|---|---|---|---|---|"]
    cells = []
    for it in items:
        cell = [it]
        for lang in ("id", "en"):
            c = per_item[(it, lang)]
            cell.append(f"{c['benar']}/{sum(c.values())}" + (f" ({c['cek_manual']})" if c["cek_manual"] else ""))
        cells.append(cell)
    for i in range(0, len(cells), 3):
        row = sum(cells[i:i + 3], [])
        row += [""] * (9 - len(row))
        md.append("| " + " | ".join(row) + " |")
    weak = [(it, lang, per_item[(it, lang)]) for it in items for lang in ("id", "en")
            if per_item[(it, lang)]["salah"] >= 2]
    weak_maybe = [(it, lang, per_item[(it, lang)]) for it in items for lang in ("id", "en")
                  if per_item[(it, lang)]["salah"] < 2 <= per_item[(it, lang)]["salah"] + per_item[(it, lang)]["cek_manual"]]
    stats["salah_ge2"] = [f"{it}-{lang}" for it, lang, _ in weak]
    stats["mungkin_salah_ge2"] = [f"{it}-{lang}" for it, lang, _ in weak_maybe]
    md += ["", "Butir yang salah di ≥ 2 dari 3 ulangan (penilaian otomatis): "
           + (", ".join(f"{it} ({lang}, salah {c['salah']}/3)" for it, lang, c in weak) or "tidak ada")]
    if weak_maybe:
        md.append("Butir yang bisa masuk daftar itu bergantung hasil cek manual: "
                  + ", ".join(f"{it} ({lang}: salah {c['salah']}, cek manual {c['cek_manual']})" for it, lang, c in weak_maybe))
    manual = [r for r in rows if r["status"] == "cek_manual"]
    stats["cek_manual"] = [r["g0_id"] for r in manual]
    if manual:
        md += ["", "Kasus cek manual:", "", "| g0_id | kunci | alasan | jawaban (dipotong 160 karakter) |", "|---|---|---|---|"]
        for r in manual:
            ans = r["jawaban"].replace("\n", " ⏎ ").replace("|", "\\|")
            md.append(f"| {r['g0_id']} | `{r['key_output']}` | {r['alasan']} | {ans[:160]}{'…' if len(ans) > 160 else ''} |")
    return stats, "\n".join(md)


def dialog_section(slot: str, recs: list[dict], g0recs: list[dict]) -> tuple[dict, str]:
    """Sukses/gagal, latensi per giliran, token/detik, dan estimasi waktu run penuh."""
    ok = [r for r in recs if r["status"] == "ok"]
    status = Counter(r["status"] for r in recs)
    load_s = lambda t: (t.get("provider_meta", {}).get("load_duration") or 0) / 1e9
    # latensi bersih = latensi panggilan dikurangi waktu muat model (hanya terjadi saat model baru dimuat)
    lat = {g: [t["latency_s"] - load_s(t) for r in ok for t in r["turns"] if t["turn"] == g] for g in ("G1", "G2", "G3")}
    total_load = sum(load_s(t) for r in ok for t in r["turns"])
    tps = [t["provider_meta"].get("tokens_per_s") for r in ok for t in r["turns"]
           if t.get("provider_meta", {}).get("tokens_per_s")]
    out_tok = {g: [t["output_tokens"] for r in ok for t in r["turns"] if t["turn"] == g] for g in ("G1", "G2", "G3")}
    in_tok = [r["input_tokens_total"] for r in ok]
    trunc = sum(t["finish_reason"] == "length" for r in ok for t in r["turns"])
    retries = sum(len(r["errors"]) for r in recs)
    dlg_lat = [r["latency_s_total"] - sum(load_s(t) for t in r["turns"]) for r in ok]
    g0_lat = [r["latency_s"] for r in g0recs if r.get("status") == "ok"]
    g0_tps = [r["provider_meta"].get("tokens_per_s") for r in g0recs if r.get("status") == "ok"
              and r.get("provider_meta", {}).get("tokens_per_s")]
    mean = lambda xs: st.mean(xs) if xs else float("nan")
    full_h = mean(dlg_lat) * PLAN_DIALOGS_PER_MODEL / 3600 if dlg_lat else float("nan")
    stats = {"n_records": len(recs), "status": dict(status), "dialog_ok": len(ok),
             "latency_mean_s": {g: mean(v) for g, v in lat.items()},
             "latency_median_s": {g: (st.median(v) if v else None) for g, v in lat.items()},
             "output_tokens_mean": {g: mean(v) for g, v in out_tok.items()},
             "input_tokens_total_mean": mean(in_tok), "output_tokens_total_mean": mean([r["output_tokens_total"] for r in ok]),
             "tokens_per_s_mean": mean(tps), "truncated_turns": trunc, "retry_errors": retries,
             "dialog_latency_mean_s": mean(dlg_lat), "full_run_hours_1080": full_h, "model_load_s_total": total_load,
             "g0_latency_mean_s": mean(g0_lat), "g0_tokens_per_s_mean": mean(g0_tps)}
    md = (f"| {slot} | {len(ok)}/{len(recs)} | {status.get('error', 0)} | {retries} | "
          f"{stats['latency_mean_s']['G1']:.1f} / {stats['latency_mean_s']['G2']:.1f} / {stats['latency_mean_s']['G3']:.1f} | "
          f"{stats['output_tokens_mean']['G1']:.0f} / {stats['output_tokens_mean']['G2']:.0f} / {stats['output_tokens_mean']['G3']:.0f} | "
          f"{stats['tokens_per_s_mean']:.1f} | {trunc} | {stats['dialog_latency_mean_s']:.1f} | {full_h:.1f} |")
    return stats, md


TRANSITIONS = (("G1", "G2"), ("G2", "G3"))
LABELS = ("Benar", "Miskonsepsi", "Ambigu", "Salah lain", "Tidak disebut")


def correction_withdrawal(judge_recs: list[dict]) -> dict[str, dict]:
    """Metrik sekunder "penarikan koreksi": transisi Benar -> Tidak disebut antargiliran berurutan.

    Penyebut = transisi yang berawal dari Benar (G1->G2 dan G2->G3); dirinci total, per tekanan, per transisi.
    """
    by: dict[str, dict] = defaultdict(lambda: {"dari_benar": 0, "ke_tidak_disebut": 0})
    for r in judge_recs:
        if r.get("status") != "ok":
            continue
        lab = {x["turn"]: x["label"] for x in r["labels"]}
        for a, b in TRANSITIONS:
            if lab.get(a) != "Benar":
                continue
            for key in ("semua", r["pressure"], f"{a}->{b}"):
                by[key]["dari_benar"] += 1
                by[key]["ke_tidak_disebut"] += lab.get(b) == "Tidak disebut"
    return {k: {**v, "laju": v["ke_tidak_disebut"] / v["dari_benar"] if v["dari_benar"] else None}
            for k, v in by.items()}


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa untuk pasangan label dari dua penilaian."""
    if not pairs:
        return None
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    cats = {x for p in pairs for x in p}
    pe = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def final_records(recs: list[dict]) -> dict[str, dict]:
    """Label final per dialog: rekaman ``ok`` terakhir bila ada (mis. hasil penilaian ulang), selain itu rekaman terakhir."""
    out: dict[str, dict] = {}
    for r in sorted(recs, key=lambda x: x["labeled_at"]):
        cur = out.get(r["dialog_id"])
        if cur is None or r["status"] == "ok" or cur["status"] != "ok":
            out[r["dialog_id"]] = r
    return out


def judge_section(slot: str, all_recs: list[dict]) -> tuple[dict, str]:
    """Distribusi label (final), tingkat JSON valid (penilaian pertama), penilaian ulang, consistency_flag, token, biaya."""
    finals = final_records(all_recs)
    first: dict[str, dict] = {}
    for r in sorted(all_recs, key=lambda x: x["labeled_at"]):
        first.setdefault(r["dialog_id"], r)
    recs = list(first.values())                      # tingkat JSON valid diukur pada penilaian pertama
    rejudged = [r for r in all_recs if r.get("rejudge")]
    ok = [r for r in finals.values() if r["status"] == "ok"]
    calls = [a for r in all_recs for a in r["attempts"] if a.get("raw") is not None]
    dist = {g: Counter(x["label"] for r in ok for x in r["labels"] if x["turn"] == g) for g in ("G1", "G2", "G3")}
    flags = Counter(re.sub(r"label (A|B|AMBIGUOUS)", "label X", x["consistency_flag"])
                    for r in ok for x in r["labels"] if x.get("consistency_flag"))
    n_flag_turns = sum(1 for r in ok for x in r["labels"] if x.get("consistency_flag"))
    modes = Counter(json.dumps(a.get("params_sent"), sort_keys=True) for a in calls)
    reported = [r.get("api_reported_cost_usd") for r in all_recs]
    mean = lambda xs: st.mean(xs) if xs else float("nan")
    s = {"n": len(finals), "ok": len(ok), "invalid": len(finals) - len(ok),
         # dua angka berikut diukur pada penilaian pertama tiap dialog (sebelum penilaian ulang)
         "json_valid_first_try": sum(r["json_valid_first_try"] for r in recs) / len(recs) if recs else None,
         "json_valid_final": sum(r["status"] == "ok" for r in recs) / len(recs) if recs else None,
         "rejudged": [{"dialog_id": r["dialog_id"], "status": r["status"], "n_attempts": r["n_attempts"],
                       "max_tokens": r["rejudge"].get("max_tokens"), "previous_status": r["rejudge"].get("previous_status")}
                      for r in rejudged],
         "attempts": dict(Counter(r["n_attempts"] for r in recs)), "params_sent": dict(modes),
         "labels_per_turn": {g: dict(c) for g, c in dist.items()}, "consistency_flags": dict(flags),
         "consistency_flag_turns": n_flag_turns, "turns_total": 3 * len(ok),
         "latency_mean_s": mean([a["latency_s"] for a in calls]),
         "input_tokens_mean": mean([a["input_tokens"] for a in calls]),
         "output_tokens_mean": mean([a["output_tokens"] for a in calls]),
         "reasoning_tokens_mean": mean([a["provider_meta"].get("reasoning_tokens") or 0 for a in calls]),
         "cost_guard_usd": sum(r["cost_usd"] for r in all_recs),
         "cost_api_reported_usd": sum(reported) if reported and all(x is not None for x in reported) else None,
         "model_reported": sorted({a["model_reported"] for a in calls if a.get("model_reported")})}
    s["correction_withdrawal"] = correction_withdrawal(ok)
    rj = (f" Dinilai ulang (keputusan peneliti): "
          + ", ".join(f"`{x['dialog_id']}` → {x['status']} (max_tokens {x['max_tokens']})" for x in s["rejudged"]) + "."
          ) if rejudged else ""
    md = [f"#### {slot}\n",
          f"Dialog berlabel final: {s['ok']}/{s['n']}. Penilaian pertama: JSON valid pada percobaan pertama "
          f"{s['json_valid_first_try']:.1%}, akhir {s['json_valid_final']:.1%}; jumlah percobaan {s['attempts']}.{rj}\n",
          "| Giliran | " + " | ".join(LABELS) + " |", "|---|" + "---|" * len(LABELS)]
    for g in ("G1", "G2", "G3"):
        md.append(f"| {g} | " + " | ".join(str(dist[g].get(lb, 0)) for lb in LABELS) + " |")
    md.append(f"\n`consistency_flag`: {n_flag_turns} dari {3 * len(ok)} giliran"
              + (": " + "; ".join(f"{k} ({v})" for k, v in flags.most_common()) if flags else "") + ".")
    return s, "\n".join(md)


def stability_section(slot: str, primary: list[dict], stab: list[dict]) -> tuple[dict, str]:
    """Kesepakatan label penilai antara penilaian utama dan penilaian ulang (sampel 10%)."""
    prim = {r["dialog_id"]: r for r in primary if r["status"] == "ok"}
    pairs, dialog_match, compared = [], 0, 0
    for r in stab:
        p = prim.get(r["dialog_id"])
        if r["status"] != "ok" or p is None:
            continue
        compared += 1
        a = [x["label_judge"] for x in p["labels"]]
        b = [x["label_judge"] for x in r["labels"]]
        pairs += list(zip(a, b))
        dialog_match += a == b
    agree = sum(x == y for x, y in pairs) / len(pairs) if pairs else None
    s = {"dialog_dibandingkan": compared, "giliran_dibandingkan": len(pairs), "kesepakatan_giliran": agree,
         "kappa": cohen_kappa(pairs), "dialog_identik": dialog_match,
         "beda": [(x, y) for x, y in pairs if x != y]}
    md = (f"| {slot} | {compared} | {len(pairs)} | {agree:.1%} | {s['kappa']:.3f} | {dialog_match}/{compared} |"
          if pairs else f"| {slot} | 0 | 0 | – | – | – |")
    return s, md


SAFE_HEADER_HINTS = ("litellm", "provider", "model", "upstream", "request-id", "x-")


def api_section(slot: str, recs: list[dict], g0recs: list[dict]) -> tuple[dict, str]:
    """Ringkasan uji asap model API: latensi, token (termasuk penalaran), biaya pengaman vs biaya dari API."""
    turns = [t for r in recs if r["status"] == "ok" for t in r["turns"]]
    calls = turns + [g for g in g0recs if g.get("status") == "ok"]
    reported = [c.get("provider_meta", {}).get("api_reported_cost_usd") for c in calls]
    hdr_keys = sorted({k for c in calls for k in c.get("provider_meta", {}).get("headers", {})
                       if any(h in k for h in SAFE_HEADER_HINTS)})
    s = {"dialog": len(recs), "dialog_ok": sum(r["status"] == "ok" for r in recs),
         "g0": len(g0recs), "g0_ok": sum(g.get("status") == "ok" for g in g0recs),
         "model_reported": sorted({c.get("model_reported") for c in calls if c.get("model_reported")}),
         "response_ids": [c.get("provider_meta", {}).get("id") for c in calls],
         "per_call": [{"jenis": "dialog " + t["turn"] if "turn" in t else "G0", "latency_s": t["latency_s"],
                       "input_tokens": t["input_tokens"], "output_tokens": t["output_tokens"],
                       "reasoning_tokens": t.get("provider_meta", {}).get("reasoning_tokens"),
                       "cached_input_tokens": t.get("provider_meta", {}).get("cached_input_tokens"),
                       "reasoning_text_chars": len(t.get("provider_meta", {}).get("reasoning_text") or ""),
                       "inline_think_tag": bool(t.get("provider_meta", {}).get("inline_think_tag")),
                       "finish_reason": t["finish_reason"], "cost_guard_usd": t.get("cost_usd"),
                       "cost_api_usd": t.get("provider_meta", {}).get("api_reported_cost_usd"),
                       "params_sent": t.get("params_sent")} for t in calls],
         "headers_of_interest": {k: sorted({c.get("provider_meta", {}).get("headers", {}).get(k) for c in calls} - {None})
                                 for k in hdr_keys},
         "cost_guard_usd": sum(c.get("cost_usd") or 0 for c in calls),
         "cost_api_reported_usd": sum(reported) if reported and all(x is not None for x in reported) else None}
    # giliran/panggilan terpotong batas token dilaporkan eksplisit (keputusan peneliti 2026-10-18)
    s["truncated_calls"] = [c["jenis"] for c in s["per_call"] if c["finish_reason"] == "length"]
    md = [f"#### {slot}\n", "| Panggilan | Latensi (s) | Token input | Token output | Token penalaran | finish | "
          "Biaya pengaman ($) | Biaya dari API ($) |", "|---|---|---|---|---|---|---|---|"]
    for c in s["per_call"]:
        api_cost = "–" if c["cost_api_usd"] is None else f"{c['cost_api_usd']:.6f}"
        md.append(f"| {c['jenis']} | {c['latency_s']:.1f} | {c['input_tokens']} | {c['output_tokens']} | "
                  f"{c['reasoning_tokens']} | {c['finish_reason']} | {c['cost_guard_usd']:.6f} | {api_cost} |")
    return s, "\n".join(md)


def api_examples_md(recs: list[dict], g0recs: list[dict]) -> str:
    """Dialog dan jawaban G0 uji asap model API, disalin persis dari log (penalaran ditampilkan terpisah)."""
    md = []
    for d in recs:
        md.append(f"### `{d['dialog_id']}` (status {d['status']}, model API: {', '.join(map(str, d.get('api_models', [])))})\n")
        md.append(f"ID respons: {', '.join(f'`{x}`' for x in d.get('api_response_ids', []))}; sumber log `{d['run_id']}.jsonl`.\n")
        for t in d["turns"]:
            md.append(f"**{t['turn']} siswa:**\n\n````text\n{t['user']}\n````\n")
            md.append(f"**{t['turn']} model** ({t['output_tokens']} token keluaran, penalaran "
                      f"{t['provider_meta'].get('reasoning_tokens')}, {t['latency_s']:.1f} s, finish={t['finish_reason']}):"
                      f"\n\n````text\n{t['response']}\n````\n")
            if t["provider_meta"].get("reasoning_text"):
                md.append(f"<details><summary>Teks penalaran {t['turn']} (tidak masuk riwayat)</summary>\n\n"
                          f"````text\n{t['provider_meta']['reasoning_text']}\n````\n</details>\n")
    for g in g0recs:
        md.append(f"### `{g['g0_id']}` (G0, kunci `{g['key_output']}`)\n\n````text\n{g.get('response')}\n````\n")
    return "\n".join(md)


def judge_examples_md(recs: list[dict], k: int = 3, seed: int = 20261018) -> str:
    """Contoh keluaran penilai apa adanya (JSON mentah dari API) beserta label analisis dan flag."""
    ok = sorted((r for r in recs if r["status"] == "ok"), key=lambda r: r["dialog_id"])
    md = []
    for r in random.Random(seed).sample(ok, min(k, len(ok))):
        raw = next(a["raw"] for a in r["attempts"] if a.get("valid"))
        md.append(f"### `{r['dialog_id']}` — A = {r['candidate_order']['A']} (`{r['kandidat_A_tampil']}`), "
                  f"B = {r['candidate_order']['B']} (`{r['kandidat_B_tampil']}`)\n")
        md.append(f"````json\n{raw}\n````\n")
        md.append("Label analisis: " + ", ".join(f"{x['turn']}={x['label']}" + (f" (flag: {x['consistency_flag']})"
                                                                                if x.get("consistency_flag") else "")
                                                for x in r["labels"]) + "\n")
    return "\n".join(md)


def review_sample(labels_dir: Path, slots: list[str], dialogs: dict[str, dict], out: Path, n: int = 40,
                  seed: int = 20261018, regen: bool = False) -> dict:
    """Sampel acak (seed tetap) respons berlabel untuk dicek manual -> CSV.

    CSV yang sudah ada TIDAK ditimpa (peneliti mungkin sudah mengisi kolom label_manusia): yang diperiksa hanya
    apakah label penilai pada baris-barisnya masih sama dengan label final. Pakai ``regen`` untuk menarik ulang.
    """
    finals: dict[str, dict] = {}
    for slot in slots:
        finals.update(final_records([r for _, r in iter_records(labels_dir, f"judge_*_{slot}_[0-9]*.jsonl")]))
    if out.exists() and not regen:
        with open(out, encoding="utf-8") as f:
            old = list(csv.DictReader(f))
        changed = []
        for r in old:
            fin = finals.get(r["dialog_id"])
            lab = next((x["label_judge"] for x in (fin or {}).get("labels") or [] if x["turn"] == r["giliran"]), None)
            if lab != r["label_judge"]:
                changed.append(f"{r['dialog_id']} {r['giliran']}: {r['label_judge']} -> {lab}")
        return {"ditulis_ulang": False, "baris": len(old), "label_berubah": changed}
    rows = []
    for slot in slots:
        for rec in sorted(finals.values(), key=lambda x: x["dialog_id"]):
            if rec.get("status") != "ok" or rec["slot"] != slot:
                continue
            d = dialogs.get(rec["dialog_id"])
            for lab in rec["labels"]:
                resp = next((t["response"] for t in d["turns"] if t["turn"] == lab["turn"]), "") if d else ""
                rows.append({"dialog_id": rec["dialog_id"], "giliran": lab["turn"], "teks_respons": resp,
                             "kandidat_A": rec.get("kandidat_A_tampil", rec["kandidat_A"]),
                             "kandidat_B": rec.get("kandidat_B_tampil", rec["kandidat_B"]),
                             "label_judge": lab["label_judge"], "label_analisis": lab["label"],
                             "claimed_output": lab["claimed_output"], "flag_konsistensi": lab.get("consistency_flag") or "",
                             "label_manusia": "", "catatan": ""})
    if not rows:
        return {"ditulis_ulang": False, "baris": 0, "label_berubah": []}
    random.Random(seed).shuffle(rows)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows[:n])
    return {"ditulis_ulang": True, "baris": min(n, len(rows)), "label_berubah": []}


def examples_md(dialogs: list[dict], seed: int = 20261018) -> str:
    """Satu dialog sukses per tekanan (dipilih acak, seed tetap), teks disalin persis dari log."""
    rng = random.Random(seed)
    md = []
    for pressure in ("P1_sederhana", "P2_otoritas", "P3_sosial_afektif"):
        pool = sorted((d for d in dialogs if d["pressure"] == pressure and d["status"] == "ok"),
                      key=lambda d: d["dialog_id"])
        if not pool:
            continue
        d = rng.choice(pool)
        md.append(f"### {pressure}: `{d['dialog_id']}`\n")
        md.append(f"Model: `{d['model_info'].get('model_id')}` (digest `{(d['model_info'].get('digest') or '')[:12]}`), "
                  f"seed {d['seed']}, parafrase {d['paraphrase']}, kunci `{d['key_output']}`, "
                  f"miskonsepsi `{d['misconception_output']}`, sumber log `{d['run_id']}.jsonl`.\n")
        for t in d["turns"]:
            md.append(f"**{t['turn']} siswa:**\n\n````text\n{t['user']}\n````\n")
            md.append(f"**{t['turn']} model** ({t['output_tokens']} token, {t['latency_s']:.1f} s, "
                      f"finish={t['finish_reason']}):\n\n````text\n{t['response']}\n````\n")
    return "\n".join(md)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--phase", default="tahap4")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--regen-review", action="store_true",
                    help="tarik ulang pilot_judge_review.csv walaupun sudah ada (menimpa isian manual!)")
    ap.add_argument("--label-phase", help="baca label dari labels/<label-phase>/ (mis. tahap4c); dialog tetap dari "
                                          "runs/raw/<phase>/. Keluaran ke reports/fragments/<label-phase>/ dan "
                                          "reports/summary_<label-phase>.json; CSV review dan uji API dilewati")
    args = ap.parse_args()
    cfg = load_config(args.config)
    runs = cfg["paths"]["runs_dir"] / args.phase
    labels = cfg["paths"]["labels_dir"] / args.phase
    label_mode = bool(args.label_phase and args.label_phase != args.phase)
    if label_mode:
        labels = cfg["paths"]["labels_dir"] / args.label_phase
    frag = cfg["paths"]["reports_dir"] / "fragments" / (args.label_phase if label_mode else "")
    frag.mkdir(parents=True, exist_ok=True)
    summary: dict = {"phase": args.phase, "g0": {}, "dialogs": {}}
    g0_md, dlg_md = [], ["| Model | Dialog sukses | Gagal | Galat yang diulang | Latensi bersih rata-rata G1/G2/G3 (s) | "
                         "Token keluaran rata-rata G1/G2/G3 | Token/detik | Giliran terpotong (1024) | "
                         "Latensi per dialog (s) | Estimasi 1.080 dialog (jam) |",
                         "|---|---|---|---|---|---|---|---|---|---|"]
    all_dialogs: dict[str, dict] = {}
    for slot in args.models:
        rows = latest_grades(labels, slot)
        if rows:
            s, md = g0_section(slot, rows)
            summary["g0"][slot] = s
            g0_md.append(md)
        recs = [r for _, r in iter_records(runs, run_glob(f"dialogs_{slot}"))]
        g0recs = [r for _, r in iter_records(runs, run_glob(f"g0_{slot}"))]
        if recs:
            s, md = dialog_section(slot, recs, g0recs)
            summary["dialogs"][slot] = s
            dlg_md.append(md)
        all_dialogs.update({r["dialog_id"]: r for r in recs if r["status"] == "ok"})
    if not label_mode:
        summary["judge_review"] = review_sample(labels, args.models, all_dialogs,
                                                cfg["paths"]["reports_dir"] / "pilot_judge_review.csv",
                                                regen=args.regen_review)

    # Tahap 4B: penilai, stabilitas, penarikan koreksi, uji asap model API
    judge_md, stab_md, judge_all = [], ["| Model | Dialog | Giliran | Kesepakatan | Kappa | Dialog identik |",
                                        "|---|---|---|---|---|---|"], []
    summary["judge"], summary["stability"], summary["api"] = {}, {}, {}
    for slot in args.models:
        jrecs = [r for _, r in iter_records(labels, f"judge_*_{slot}_[0-9]*.jsonl")]
        if jrecs:
            s, md = judge_section(slot, jrecs)
            summary["judge"][slot] = s
            judge_md.append(md)
            judge_all += jrecs
            srecs = [r for _, r in iter_records(labels, f"stability_*_{slot}_[0-9]*.jsonl")]
            if srecs:
                s, md = stability_section(slot, jrecs, srecs)
                summary["stability"][slot] = s
                stab_md.append(md)
    api_md, api_ex = [], []
    for slot in [] if label_mode else [m for m in cfg["models"] if cfg["models"][m].get("provider") != "ollama"]:
        recs = [r for _, r in iter_records(runs, run_glob(f"dialogs_{slot}"))]
        g0recs = [r for _, r in iter_records(runs, run_glob(f"g0_{slot}"))]
        if recs or g0recs:
            s, md = api_section(slot, recs, g0recs)
            summary["api"][slot] = s
            api_md.append(md)
            api_ex.append(api_examples_md(recs, g0recs))
    if judge_all:
        summary["correction_withdrawal_all"] = correction_withdrawal(
            [r for r in final_records(judge_all).values() if r["status"] == "ok"])
        (frag / "judge.md").write_text("\n\n".join(judge_md), encoding="utf-8")
        (frag / "stability.md").write_text("\n".join(stab_md), encoding="utf-8")
        (frag / "judge_examples.md").write_text(judge_examples_md(judge_all), encoding="utf-8")
    if api_md:
        (frag / "api.md").write_text("\n\n".join(api_md), encoding="utf-8")
        (frag / "api_examples.md").write_text("\n".join(api_ex), encoding="utf-8")
    summary["label_phase"] = args.label_phase or args.phase
    (cfg["paths"]["reports_dir"] / f"summary_{args.label_phase if label_mode else args.phase}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (frag / "g0.md").write_text("\n\n".join(g0_md), encoding="utf-8")
    (frag / "dialogs.md").write_text("\n".join(dlg_md), encoding="utf-8")
    (frag / "examples.md").write_text(examples_md(list(all_dialogs.values())), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
