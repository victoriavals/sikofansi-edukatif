"""Bandingkan dua set label penilai (mis. prompt v1.0 vs v1.1) dan bandingkan dengan label kalibrasi.

Label dibandingkan dalam ruang label penilai (A/B/AMBIGUOUS/OTHER/NONE). Urutan kandidat per dialog sama di kedua
set (seed tetap), jadi kecocokan huruf = kecocokan label analisis; label analisis ikut dilaporkan.
Hanya membaca log; keluaran: CSV perubahan, ringkasan JSON, dan potongan Markdown.

Contoh:
    python -m src.compare_labels --base tahap4 --new tahap4c \
        --calibration ../catatan_peneliti/kalibrasi/pilot_judge_review_kalibrasi.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from .common import iter_records, load_config
from .summarize import cohen_kappa, final_records

TURNS = ("G1", "G2", "G3")


def load_finals(labels_dir: Path, slots: list[str]) -> dict[str, dict]:
    """Label final per dialog (rekaman ok terakhir) dari berkas judge_* satu folder label."""
    out: dict[str, dict] = {}
    for slot in slots:
        out.update(final_records([r for _, r in iter_records(labels_dir, f"judge_*_{slot}_[0-9]*.jsonl")]))
    return out


def turn_map(rec: dict | None) -> dict[str, dict]:
    return {x["turn"]: x for x in (rec or {}).get("labels") or []}


def compare_sets(base: dict[str, dict], new: dict[str, dict]) -> dict:
    """Kesepakatan per giliran antara dua set label final, plus daftar semua giliran yang berubah."""
    pairs: list[tuple[str, str]] = []
    per_turn: dict[str, list[tuple[str, str]]] = {t: [] for t in TURNS}
    per_slot: dict[str, list[tuple[str, str]]] = {}
    transitions: Counter = Counter()
    changed, missing = [], []
    for did in sorted(set(base) | set(new)):
        b, n = base.get(did), new.get(did)
        if not (b and n and b["status"] == "ok" and n["status"] == "ok"):
            missing.append({"dialog_id": did, "base": b["status"] if b else None, "new": n["status"] if n else None})
            continue
        bt, nt = turn_map(b), turn_map(n)
        for t in TURNS:
            pair = (bt[t]["label_judge"], nt[t]["label_judge"])
            pairs.append(pair)
            per_turn[t].append(pair)
            per_slot.setdefault(b["slot"], []).append(pair)
            transitions[(bt[t]["label"], nt[t]["label"])] += 1
            if pair[0] != pair[1]:
                changed.append({"dialog_id": did, "slot": b["slot"], "giliran": t, "tekanan": b["pressure"],
                                "kandidat_A": n.get("kandidat_A_tampil", n["kandidat_A"]),
                                "kandidat_B": n.get("kandidat_B_tampil", n["kandidat_B"]),
                                "label_v10": bt[t]["label_judge"], "label_v11": nt[t]["label_judge"],
                                "analisis_v10": bt[t]["label"], "analisis_v11": nt[t]["label"],
                                "claimed_v10": bt[t]["claimed_output"], "claimed_v11": nt[t]["claimed_output"],
                                "alasan_v10": bt[t]["rationale"], "alasan_v11": nt[t]["rationale"]})
    agree = lambda ps: (sum(a == b for a, b in ps) / len(ps)) if ps else None
    return {"giliran": len(pairs), "sepakat": sum(a == b for a, b in pairs), "kesepakatan": agree(pairs),
            "kappa": cohen_kappa(pairs),
            "per_giliran": {t: {"n": len(p), "kesepakatan": agree(p), "kappa": cohen_kappa(p)} for t, p in per_turn.items()},
            "per_model": {s: {"n": len(p), "kesepakatan": agree(p), "kappa": cohen_kappa(p)} for s, p in per_slot.items()},
            "transisi_analisis": {f"{a} -> {b}": c for (a, b), c in sorted(transitions.items()) if a != b},
            "berubah": changed, "tidak_dibandingkan": missing}


def compare_calibration(csv_path: Path, base: dict[str, dict], new: dict[str, dict]) -> dict:
    """Kesepakatan label penilai (v1.0 dan v1.1) dengan kolom label_kalibrasi di CSV kalibrasi."""
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out_rows, p_base, p_new = [], [], []
    for r in rows:
        nb = turn_map(new.get(r["dialog_id"])).get(r["giliran"])
        bb = turn_map(base.get(r["dialog_id"])).get(r["giliran"])
        v11 = nb["label_judge"] if nb else None
        v10 = bb["label_judge"] if bb else None
        out_rows.append({"dialog_id": r["dialog_id"], "giliran": r["giliran"], "label_kalibrasi": r["label_kalibrasi"],
                         "label_v10_csv": r["label_judge"], "label_v10_log": v10, "label_v11": v11,
                         "sesuai_v10_csv": r["sesuai"], "v11_sesuai": "ya" if v11 == r["label_kalibrasi"] else "tidak",
                         "catatan_kalibrasi": r["catatan_kalibrasi"],
                         "alasan_v11": nb["rationale"] if nb else None, "claimed_v11": nb["claimed_output"] if nb else None})
        p_new.append((r["label_kalibrasi"], v11 or "–"))
        p_base.append((r["label_kalibrasi"], r["label_judge"]))
    agree = lambda ps: sum(a == b for a, b in ps) / len(ps) if ps else None
    return {"baris": len(rows), "v11_sepakat": sum(a == b for a, b in p_new), "v11_kesepakatan": agree(p_new),
            "v11_kappa": cohen_kappa(p_new), "v10_sepakat": sum(a == b for a, b in p_base),
            "v10_kesepakatan": agree(p_base), "v10_kappa": cohen_kappa(p_base),
            "v10_csv_sama_dengan_log": all(x["label_v10_csv"] == x["label_v10_log"] for x in out_rows),
            "sebelumnya_tidak_sesuai": [x for x in out_rows if x["sesuai_v10_csv"] != "ya"],
            "v11_tidak_sesuai": [x for x in out_rows if x["v11_sesuai"] != "ya"], "rows": out_rows}


def _md_changes(cmp: dict) -> str:
    md = ["| Dialog | Giliran | Tekanan | A / B | v1.0 | v1.1 | Alasan v1.1 |", "|---|---|---|---|---|---|---|"]
    for c in cmp["berubah"]:
        md.append(f"| `{c['dialog_id']}` | {c['giliran']} | {c['tekanan'].split('_')[0]} | `{c['kandidat_A']}` / "
                  f"`{c['kandidat_B']}` | {c['label_v10']} ({c['analisis_v10']}) | {c['label_v11']} ({c['analisis_v11']}) | "
                  f"{(c['alasan_v11'] or '').replace('|', '/')} |")
    return "\n".join(md)


def _md_calibration(cal: dict) -> str:
    md = ["| Dialog | Giliran | Kalibrasi | v1.0 | v1.1 | v1.1 sesuai | Catatan kalibrasi / alasan v1.1 |",
          "|---|---|---|---|---|---|---|"]
    show = {(x["dialog_id"], x["giliran"]) for x in cal["sebelumnya_tidak_sesuai"] + cal["v11_tidak_sesuai"]}
    for x in cal["rows"]:
        if (x["dialog_id"], x["giliran"]) in show:
            note = (x["catatan_kalibrasi"] or "") + (f" — v1.1: {x['alasan_v11']}" if x["alasan_v11"] else "")
            md.append(f"| `{x['dialog_id']}` | {x['giliran']} | {x['label_kalibrasi']} | {x['label_v10_csv']} | "
                      f"{x['label_v11']} | {x['v11_sesuai']} | {note.replace('|', '/')} |")
    return "\n".join(md)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--base", default="tahap4", help="folder label pembanding (v1.0)")
    ap.add_argument("--new", default="tahap4c", help="folder label baru (v1.1)")
    ap.add_argument("--models", nargs="+", default=["gemma2_9b_it", "sahabatai_9b_it"])
    ap.add_argument("--calibration", help="CSV kalibrasi berkolom label_kalibrasi")
    args = ap.parse_args()
    cfg = load_config(args.config)
    ldir = cfg["paths"]["labels_dir"]
    base, new = load_finals(ldir / args.base, args.models), load_finals(ldir / args.new, args.models)
    cmp = compare_sets(base, new)
    out_dir = ldir / args.new
    with open(out_dir / f"perubahan_label_{args.base}_vs_{args.new}.csv", "w", newline="", encoding="utf-8") as f:
        fields = list(cmp["berubah"][0].keys()) if cmp["berubah"] else ["dialog_id"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(cmp["berubah"])
    result = {"base": args.base, "new": args.new, "banding": cmp}
    frag = cfg["paths"]["reports_dir"] / "fragments" / args.new
    frag.mkdir(parents=True, exist_ok=True)
    (frag / "perubahan.md").write_text(_md_changes(cmp), encoding="utf-8")
    if args.calibration:
        cal = compare_calibration(Path(args.calibration), base, new)
        result["kalibrasi"] = cal
        (frag / "kalibrasi.md").write_text(_md_calibration(cal), encoding="utf-8")
    (cfg["paths"]["reports_dir"] / f"compare_{args.base}_vs_{args.new}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in cmp.items() if k not in ("berubah",)}, indent=1, ensure_ascii=False)[:3000])
    print("giliran berubah:", len(cmp["berubah"]))
    if args.calibration:
        print({k: v for k, v in result["kalibrasi"].items() if k not in ("rows", "sebelumnya_tidak_sesuai", "v11_tidak_sesuai")})


if __name__ == "__main__":
    main()
