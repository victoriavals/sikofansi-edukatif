"""Sampling validasi manusia (Tahap 6): respons tutor dari data utama Tahap 5 untuk dinilai manusia.

Desain (keputusan peneliti atas Tahap 4C, 2026-10-19):
- 200 respons (satuan = satu giliran tutor), dari data utama Tahap 5, BUKAN pilot.
- Distratifikasi per model × bahasa (alokasi sama per sel) dan per label penilai di dalam sel. Alokasi per label
  sebanding jumlahnya, dengan label Ambigu (AMBIGUOUS) disampling berlebih (bobot ``--ambiguous-factor``) dan
  minimal ``--min-per-label`` per label yang ada. Peluang inklusi dan bobot (1/π) dicatat per baris.
- Lembar penilai menampilkan: kode, dua kandidat (urutan sama dengan penilai LLM), pesan siswa pada giliran itu,
  dan respons tutor, plus kolom isian: label manusia, output lain, penanda galat "klaim_kode_perbaikan", catatan.
  Identitas model dan label penilai LLM TIDAK ada di lembar penilai, hanya di berkas kunci.
- Panduan: tahap3/panduan_pelabelan.md v1.1 (beku; SHA256 dicek terhadap config judge.frozen_sha256).

Jalankan SETELAH Tahap 5 selesai dilabeli:
    python -m src.sample_validation --phase tahap5
Data pilot hanya untuk uji skrip: --allow-pilot --out-dir <folder di luar labels/>.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from .common import iter_records, kode_block, load_config, now_iso, run_glob, stamp
from .run_judge import display_candidate
from .summarize import final_records

DEFAULT_SLOTS = ["komersial_A", "komersial_B", "gemma2_9b_it", "sahabatai_9b_it"]
FORM_LABELS = "Kandidat A | Kandidat B | Ambigu | Lainnya | Tidak disebut"


def allocate(counts: dict[str, int], n: int, ambiguous_factor: float, min_per_label: int) -> dict[str, int]:
    """Alokasi ``n`` sampel ke label dalam satu sel: lantai min(min_per_label, N), sisa sebanding N × bobot
    (Ambigu × ambiguous_factor), dibatasi N; pembulatan sisa terbesar. Deterministik."""
    labels = sorted(l for l, c in counts.items() if c > 0)
    n = min(n, sum(counts[l] for l in labels))
    alloc = {l: min(min_per_label, counts[l]) for l in labels}
    while sum(alloc.values()) > n:                      # lantai melebihi kuota: kurangi dari label terbesar
        big = max((l for l in labels if alloc[l] > 0), key=lambda l: (alloc[l], l))
        alloc[big] -= 1
    weight = {l: counts[l] * (ambiguous_factor if l == "Ambigu" else 1.0) for l in labels}
    while sum(alloc.values()) < n:
        open_ = [l for l in labels if alloc[l] < counts[l]]
        rem = n - sum(alloc.values())
        tot_w = sum(weight[l] for l in open_)
        share = {l: rem * weight[l] / tot_w for l in open_}
        add = {l: min(int(share[l]), counts[l] - alloc[l]) for l in open_}
        if sum(add.values()) == 0:                       # sisa < 1 per label: beri ke pecahan terbesar
            best = max(open_, key=lambda l: (share[l] - int(share[l]), weight[l], l))
            add = {best: 1}
        for l, a in add.items():
            alloc[l] += a
    return alloc


def build_population(cfg: dict, label_dir: Path, runs_dir: Path, slots: list[str]) -> list[dict]:
    """Satuan populasi = satu giliran tutor dengan label final penilai yang valid."""
    items = {it["id"]: it for it in json.loads(cfg["paths"]["items"].read_text(encoding="utf-8"))["items"]}
    units = []
    for slot in slots:
        finals = final_records([r for _, r in iter_records(label_dir, f"judge_*_{slot}_[0-9]*.jsonl")])
        dialogs = {r["dialog_id"]: r for _, r in iter_records(runs_dir, run_glob(f"dialogs_{slot}"))
                   if r.get("status") == "ok"}
        for did, lab in sorted(finals.items()):
            if lab["status"] != "ok" or did not in dialogs:
                continue
            turns = {t["turn"]: t for t in dialogs[did]["turns"]}
            for x in lab["labels"]:
                t = turns[x["turn"]]
                units.append({
                    "dialog_id": did, "giliran": x["turn"], "model": slot, "lang": lab["lang"],
                    "framing": lab["framing"], "pressure": lab["pressure"], "item_id": lab["item_id"],
                    "label_analisis": x["label"], "label_judge": x["label_judge"],
                    "claimed_output_judge": x["claimed_output"], "alasan_judge": x["rationale"],
                    "consistency_flag": x.get("consistency_flag") or "",
                    "kandidat_A": display_candidate(lab["kandidat_A"]), "kandidat_B": display_candidate(lab["kandidat_B"]),
                    "A_adalah": lab["candidate_order"]["A"], "B_adalah": lab["candidate_order"]["B"],
                    "key_output": lab["key_output"], "misconception_output": lab["misconception_output"],
                    "kode": kode_block(items[lab["item_id"]]["kode"]), "pesan_siswa": t["user"],
                    "respons_tutor": t["response"], "judge_prompt_version": lab.get("judge_prompt_version"),
                    "judge_log": lab["run_id"], "dialog_log": dialogs[did]["run_id"]})
    return units


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--phase", default="tahap5", help="fase dialog (runs/raw/<phase>/); default tahap5")
    ap.add_argument("--label-phase", help="fase label (labels/<label-phase>/); default = --phase")
    ap.add_argument("--models", nargs="+", default=DEFAULT_SLOTS)
    ap.add_argument("--total", type=int, default=200)
    ap.add_argument("--ambiguous-factor", type=float, default=3.0, help="bobot sampling berlebih label Ambigu")
    ap.add_argument("--min-per-label", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20261020)
    ap.add_argument("--out-dir", help="default: labels/<label-phase>/validasi_manusia/")
    ap.add_argument("--allow-pilot", action="store_true", help="izinkan data selain tahap5 (HANYA uji skrip)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    label_phase = args.label_phase or args.phase
    if args.phase != "tahap5" and not args.allow_pilot:
        raise SystemExit("Validasi manusia harus dari data utama Tahap 5 (--phase tahap5). Data pilot hanya untuk "
                         "uji skrip dengan --allow-pilot dan --out-dir di luar labels/.")
    guide = (cfg["paths"]["judge_prompt"].parent / "panduan_pelabelan.md")
    guide_sha = hashlib.sha256(guide.read_bytes()).hexdigest()
    frozen = (cfg["judge"].get("frozen_sha256") or {}).get("panduan_pelabelan.md")
    if frozen and guide_sha != frozen:
        raise SystemExit(f"panduan_pelabelan.md berbeda dari versi beku ({frozen[:12]}...); hentikan.")

    units = build_population(cfg, cfg["paths"]["labels_dir"] / label_phase, cfg["paths"]["runs_dir"] / args.phase,
                             args.models)
    if not units:
        raise SystemExit(f"Tidak ada giliran berlabel di labels/{label_phase} untuk {args.models}.")
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for u in units:
        cells[(u["model"], u["lang"])].append(u)
    keys = sorted(cells)
    base, extra = divmod(args.total, len(keys))
    sample, alloc_rows = [], []
    for i, key in enumerate(keys):
        quota = base + (1 if i < extra else 0)
        by_label: dict[str, list[dict]] = defaultdict(list)
        for u in cells[key]:
            by_label[u["label_analisis"]].append(u)
        alloc = allocate({l: len(v) for l, v in by_label.items()}, quota, args.ambiguous_factor, args.min_per_label)
        for label, k in sorted(alloc.items()):
            pool = sorted(by_label[label], key=lambda u: (u["dialog_id"], u["giliran"]))
            rng = random.Random(f"{args.seed}:{key[0]}:{key[1]}:{label}")
            chosen = rng.sample(pool, k)
            pi = k / len(pool)
            for u in chosen:
                sample.append({**u, "strata": f"{key[0]}|{key[1]}|{label}", "N_strata": len(pool), "n_strata": k,
                               "peluang_inklusi": round(pi, 6), "bobot": round(1 / pi, 6)})
            alloc_rows.append({"model": key[0], "lang": key[1], "label": label, "N": len(pool), "n": k})
    random.Random(args.seed).shuffle(sample)              # urutan butir form acak (seed tetap)
    for i, s in enumerate(sample, 1):
        s["validasi_id"] = f"V{i:03d}"

    out = Path(args.out_dir) if args.out_dir else cfg["paths"]["labels_dir"] / label_phase / "validasi_manusia"
    out.mkdir(parents=True, exist_ok=True)
    tag = stamp()
    form_cols = ["validasi_id", "kode", "kandidat_A", "kandidat_B", "pesan_siswa", "respons_tutor",
                 "label_manusia", "output_lainnya", "klaim_kode_perbaikan", "catatan"]
    with open(out / f"lembar_penilai_{tag}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=form_cols)
        w.writeheader()
        for s in sample:
            w.writerow({**{c: s.get(c, "") for c in form_cols[:6]}, "label_manusia": "", "output_lainnya": "",
                        "klaim_kode_perbaikan": "", "catatan": ""})
    key_cols = ["validasi_id", "dialog_id", "giliran", "model", "lang", "framing", "pressure", "item_id", "strata",
                "N_strata", "n_strata", "peluang_inklusi", "bobot", "label_judge", "label_analisis",
                "claimed_output_judge", "alasan_judge", "consistency_flag", "A_adalah", "B_adalah", "key_output",
                "misconception_output", "judge_prompt_version", "judge_log", "dialog_log"]
    with open(out / f"kunci_validasi_{tag}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=key_cols)
        w.writeheader()
        w.writerows({c: s.get(c, "") for c in key_cols} for s in sorted(sample, key=lambda s: s["validasi_id"]))
    meta = {"dibuat": now_iso(), "phase": args.phase, "label_phase": label_phase, "models": args.models,
            "total": len(sample), "ambiguous_factor": args.ambiguous_factor, "min_per_label": args.min_per_label,
            "seed": args.seed, "populasi_giliran": len(units), "panduan": "tahap3/panduan_pelabelan.md",
            "panduan_sha256": guide_sha, "pilihan_label_form": FORM_LABELS,
            "kolom_klaim_kode_perbaikan": ("ya/tidak: respons tutor menyatakan output dari KODE PERBAIKAN yang ia "
                                           "sarankan (bukan kode asli); untuk menghitung jenis galat penilai GP-01"),
            "alokasi": alloc_rows, "label_sampel": dict(Counter(s["label_analisis"] for s in sample)),
            "uji_pilot": args.phase != "tahap5"}
    (out / f"sampling_validasi_{tag}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"populasi {len(units)} giliran; sampel {len(sample)} -> {out}")
    print("label sampel:", meta["label_sampel"])
    for r in alloc_rows:
        print(f"  {r['model']:16s} {r['lang']} {r['label']:13s} N={r['N']:4d} n={r['n']}")


if __name__ == "__main__":
    main()
