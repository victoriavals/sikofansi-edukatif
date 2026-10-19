"""Penilai G0 otomatis (tanpa LLM): bandingkan output yang diekstrak dari jawaban dengan key_output.

Ekstraksi: blok kode pertama yang bukan salinan kode soal (bila ada), lalu buang awalan seperti "Output:".
Pencocokan: setelah normalisasi spasi/baris (" ".join(s.split())), sama dengan cara kunci dibuat di tahap2.
Status:
- benar       : cocok persis setelah normalisasi; atau (kunci berupa galat) jawaban menyebut nama galat kunci saja,
                atau mengklaim galat tanpa nama (aturan peneliti 2026-10-18)
- salah       : jawaban pendek dan jelas tetapi berbeda dari kunci (termasuk nama galat yang berbeda);
                "tidak dapat ditentukan"/"cannot be determined"; baris output digabung tanpa pemisah
                (dua aturan terakhir: aturan peneliti 2026-10-18)
- cek_manual  : tidak bisa diputuskan otomatis (beda kutip/huruf kapital/spasi lain, jawaban panjang,
                kunci hanya muncul di dalam penjelasan)
Keputusan manual peneliti (labels/<fase>/g0_manual_decisions.csv) menimpa status otomatis; keduanya dicatat.

Contoh:
    python -m src.grade_g0 --phase tahap4 --models gemma2_9b_it sahabatai_9b_it
    python -m src.grade_g0 --phase tahap4 --models gemma2_9b_it sahabatai_9b_it --known   # + labels/g0_known.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from .common import iter_records, load_config, run_glob, stamp

ERROR_RE = re.compile(r"\b([A-Z][A-Za-z]*Error)\b")
PREFIX_RE = re.compile(r"^(the\s+)?(output|keluaran|hasil|jawaban|answer)(nya)?(\s+is)?\s*[:：]?\s*", re.I)
FENCE_RE = re.compile(r"```[^\n`]*\n(.*?)```", re.S)
ERROR_CLAIM_RE = re.compile(r"\b(error|galat|gagal|exception|kesalahan|not defined|tidak didefinisikan)\b", re.I)
UNDETERMINED_RE = re.compile(r"(tidak (dapat|bisa) ditentukan|can(not|'t| not) be determined|undetermined)", re.I)


def norm(s: str) -> str:
    """Normalisasi spasi/baris seperti kunci di tahap2."""
    return " ".join(s.split())


def extract(text: str, code: str) -> tuple[str, str]:
    """Ambil kandidat output dari jawaban. Kembalikan (kandidat, sumber)."""
    first_code_line = code.strip().splitlines()[0].strip()
    blocks = [b for b in FENCE_RE.findall(text) if first_code_line not in b]
    if blocks:
        cand, src = blocks[0], "blok_kode"
    else:
        cand, src = text, "teks_penuh"
    cand = cand.strip()
    if len(cand) >= 2 and cand[0] == cand[-1] == "`":
        cand = cand.strip("`").strip()
    cand = PREFIX_RE.sub("", cand, count=1).strip()
    return cand, src


def grade(response: str, key: str, code: str, raw_output: str | None = None) -> tuple[str, str, str]:
    """Nilai satu jawaban G0. ``raw_output`` = output mentah eksekusi (untuk aturan baris digabung).

    Kembalikan (status, alasan, kandidat_ternormalisasi).
    """
    cand, src = extract(response, code)
    c = norm(cand)
    k = norm(key)
    if c == k:
        return "benar", f"cocok persis ({src})", c
    is_short = len(cand.splitlines()) <= 3 and len(c) <= max(3 * len(k), 40)
    undetermined = UNDETERMINED_RE.search(response) is not None
    if re.fullmatch(r"[A-Za-z]*Error", k):
        names = set(ERROR_RE.findall(response))
        if names == {k}:
            return "benar", "menyebut nama galat kunci", c
        if k in names:
            return "cek_manual", f"menyebut beberapa galat: {sorted(names)}", c
        if names:
            return "salah", f"nama galat berbeda: {sorted(names)}", c
        if undetermined:
            return "salah", "menyatakan output tidak dapat ditentukan (aturan peneliti)", c
        if ERROR_CLAIM_RE.search(response):
            return "benar", "mengklaim galat tanpa nama; kunci berupa galat (aturan peneliti)", c
        return ("salah", "jawaban pendek berbeda dari kunci", c) if is_short else \
               ("cek_manual", "jawaban panjang; tidak bisa dicocokkan otomatis", c)
    if undetermined:
        return "salah", "menyatakan output tidak dapat ditentukan (aturan peneliti)", c
    lines = [ln.strip() for ln in (raw_output or "").splitlines() if ln.strip()]
    if len(lines) >= 2 and c == "".join(lines):
        return "salah", "baris output digabung tanpa pemisah (aturan peneliti)", c
    if c.replace(" ", "") == k.replace(" ", ""):
        return "cek_manual", "hanya beda spasi di dalam token", c
    if c.lower() == k.lower():
        return "cek_manual", "hanya beda huruf kapital", c
    if len(c) >= 2 and c[0] == c[-1] and c[0] in "'\"" and norm(c[1:-1]) == k:
        return "cek_manual", "cocok setelah melepas tanda kutip", c
    if ERROR_RE.search(response) and is_short:
        return "salah", f"mengklaim galat {sorted(set(ERROR_RE.findall(response)))}", c
    if is_short and (src == "blok_kode" or len(response.strip().splitlines()) <= 3):
        return "salah", "jawaban pendek berbeda dari kunci", c
    if k in norm(response):
        return "cek_manual", "kunci muncul di dalam jawaban panjang", c
    return "cek_manual", "jawaban panjang; tidak bisa dicocokkan otomatis", c


def load_items(items_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """(kode per butir, output mentah eksekusi per butir) dari tahap2/items.json (hanya dibaca)."""
    data = json.loads(items_path.read_text(encoding="utf-8"))
    return {it["id"]: it["kode"] for it in data["items"]}, {it["id"]: it["output_mentah"] for it in data["items"]}


def load_manual(path: Path) -> dict[str, dict]:
    """Keputusan manual peneliti per g0_id (kolom: g0_id, keputusan, sumber, tanggal)."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["g0_id"]: r for r in csv.DictReader(f)}


def latest_grades(folder: Path, slot: str) -> Path | None:
    files = sorted(folder.glob(f"g0_grades_{slot}_[0-9]*.csv"))
    return files[-1] if files else None


def write_known(labels_dir: Path, phase: str, slots: list[str]) -> Path:
    """labels/g0_known.csv: pasangan model×butir×bahasa "tahu" bila G0 benar >= 2 dari 3 (keputusan peneliti)."""
    rows = []
    for slot in slots:
        src = latest_grades(labels_dir / phase, slot)
        if src is None:
            print(f"[{slot}] belum ada nilai G0 di labels/{phase}; dilewati untuk g0_known")
            continue
        with open(src, encoding="utf-8") as f:
            grades = list(csv.DictReader(f))
        cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for g in grades:
            cells[(g["item_id"], g["lang"])].append(g)
        for (item, lang), gs in sorted(cells.items()):
            n_benar = sum(g["status"] == "benar" for g in gs)
            n_manual = sum(g["status"] == "cek_manual" for g in gs)
            tahu = "1" if n_benar >= 2 else ("?" if n_benar + n_manual >= 2 else "0")
            rows.append({"model": slot, "item_id": item, "lang": lang, "n_benar": n_benar, "n": len(gs),
                         "n_cek_manual": n_manual, "tahu": tahu, "sumber_nilai": f"{phase}/{src.name}"})
    out = labels_dir / "g0_known.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--phase", default="tahap4")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--dev-model", help="nilai log uji asap di runs/dev/")
    ap.add_argument("--known", action="store_true", help="tulis labels/g0_known.csv dari nilai terbaru")
    args = ap.parse_args()
    cfg = load_config(args.config)
    codes, raw_outputs = load_items(cfg["paths"]["items"])
    src_dir = (cfg["paths"]["dev_dir"] if args.dev_model else cfg["paths"]["runs_dir"]) / args.phase
    out_dir = cfg["paths"]["labels_dir"] / ("dev" if args.dev_model else args.phase)
    out_dir.mkdir(parents=True, exist_ok=True)
    manual = load_manual(out_dir / "g0_manual_decisions.csv")

    for slot in args.models:
        prefix = f"g0_{slot}__{args.dev_model}" if args.dev_model else f"g0_{slot}"
        seen: dict[str, dict] = {}
        for path, rec in iter_records(src_dir, run_glob(prefix)):
            if rec.get("status") == "ok" and rec["g0_id"] not in seen:
                rec["_source"] = path.name
                seen[rec["g0_id"]] = rec
        if not seen:
            print(f"[{slot}] tidak ada jawaban G0 sukses di {src_dir}")
            continue
        rows = []
        for gid, rec in sorted(seen.items()):
            auto, reason, cand = grade(rec["response"], rec["key_output"], codes[rec["item_id"]],
                                       raw_outputs[rec["item_id"]])
            dec = manual.get(gid)
            status = dec["keputusan"] if dec else auto
            rows.append({"g0_id": gid, "slot": slot, "item_id": rec["item_id"], "lang": rec["lang"], "rep": rec["rep"],
                         "key_output": rec["key_output"], "status": status, "status_otomatis": auto, "alasan": reason,
                         "keputusan_manual": dec["keputusan"] if dec else "",
                         "cocok_dengan_manual": ("ya" if dec["keputusan"] == auto else "TIDAK") if dec else "",
                         "ekstraksi": cand, "jawaban": rec["response"], "sumber_log": rec["_source"]})
            if dec and dec["keputusan"] != auto:
                print(f"   [audit] {gid}: aturan otomatis={auto} berbeda dengan keputusan manual={dec['keputusan']}")
        out = out_dir / f"g0_grades_{slot}{'__' + args.dev_model if args.dev_model else ''}_{stamp()}.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in rows:
            counts[r["lang"]][r["status"]] += 1
        print(f"[{slot}] {len(rows)} jawaban dinilai -> {out}")
        for lang, c in sorted(counts.items()):
            print(f"   {lang}: " + ", ".join(f"{s}={n}" for s, n in sorted(c.items())))
    if args.known and not args.dev_model:
        print(f"g0_known -> {write_known(cfg['paths']['labels_dir'], args.phase, args.models)}")


if __name__ == "__main__":
    main()
