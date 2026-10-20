"""Pengatur run Tahap 5 untuk model lokal (bagian B) dan penilainya (bagian C), dengan kondisi berhenti.

Dua mode, dijalankan sebagai dua proses terpisah:

- ``hasilkan`` (hanya di dalam jendela ``run_window.ps1 -Steps tahap5``): pemeriksaan awal instans riset (versi
  Ollama, digest, dan kuantisasi sama dengan pilot Tahap 4), G0 kedua model, lalu dialog gemma2_9b_it ->
  sahabatai_9b_it dalam potongan kecil (resume antarpotongan). Potongan baru hanya dimulai bila diperkirakan selesai
  sebelum ``--deadline``; bila waktu tidak cukup, berhenti rapi di antara dialog (sisa dilanjutkan di jendela
  berikutnya). Tidak memanggil penilai, agar layanan peneliti bisa dipulihkan segera setelah proses ini keluar.
- ``nilai`` (tanpa menjeda layanan; penilai lewat API): satu thread per model menunggu dialog model itu lengkap
  (1.080 ok), lalu penilai berjalan: utama -> nilai ulang dialog invalid satu kali -> uji stabilitas.
  Berhenti menunggu bila ``--tunggu-sampai`` lewat atau mode ``hasilkan`` mencatat kondisi berhenti.

Kondisi berhenti sama dengan bagian A (``jalankan_tahap5_api.py``). Untuk model lokal, padanan "field model atau
header hulu berubah" adalah nama model, digest, versi server Ollama, atau kuantisasi yang berubah (atau berbeda dari
pilot). Kode keluar ``hasilkan``: 0 = semua selesai, 4 = batas waktu jendela (ada sisa), 2 = kondisi berhenti.

Status dan log: runs/pantau/tahap5_lokal*.json|log dan tahap5_lokal_nilai*.json|log (di-ignore git).

Pemakaian (dari tahap4/):
    python model_prep/jalankan_tahap5_lokal.py hasilkan --deadline 2026-10-21T07:45:00
    python model_prep/jalankan_tahap5_lokal.py nilai --mulai 2026-10-20T22:00:00 --tunggu-sampai 2026-10-21T08:15:00
    python model_prep/jalankan_tahap5_lokal.py periksa [--url http://127.0.0.1:11435]   # hanya baca, tanpa run
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jalankan_tahap5_api import PHASE, T4, Monitor  # noqa: E402
from src.common import iter_records, load_config, model_cfg, run_glob  # noqa: E402

LOCAL = ["gemma2_9b_it", "sahabatai_9b_it"]
G0_PER_MODEL = 180
PILOT_DIALOG_S = {"gemma2_9b_it": 13.9, "sahabatai_9b_it": 10.0}   # latensi bersih rata-rata pilot (REPORT_TAHAP4)
OVERHEAD_S = 45.0       # mulai proses runner + kemungkinan memuat model
MARGIN = 1.3            # cadangan atas latensi rata-rata
G0_MIN_LEFT_S = 600.0   # G0 satu model hanya dimulai bila sisa waktu >= 10 menit


def chunk_size(per_dialog_s: float, seconds_left: float, chunk: int,
               overhead_s: float = OVERHEAD_S, margin: float = MARGIN) -> int:
    """Jumlah dialog potongan berikutnya agar diperkirakan selesai sebelum batas waktu (0 = jangan mulai)."""
    n = int((seconds_left - overhead_s) / (per_dialog_s * margin))
    return max(0, min(chunk, n))


def pilot_reference(cfg: dict, slot: str) -> dict:
    """Digest, versi Ollama, dan kuantisasi yang tercatat di log pilot Tahap 4 (harus tunggal)."""
    keys = ("digest", "ollama_server_version", "quantization_level")
    seen: dict[str, set] = {k: set() for k in keys}
    for kind in ("dialogs", "g0"):
        for _, r in iter_records(cfg["paths"]["runs_dir"] / "tahap4", run_glob(f"{kind}_{slot}")):
            for k in keys:
                if (r.get("model_info") or {}).get(k):
                    seen[k].add(r["model_info"][k])
    if any(len(v) != 1 for v in seen.values()):
        raise SystemExit(f"[{slot}] referensi pilot tidak tunggal: {seen}")
    return {k: next(iter(v)) for k, v in seen.items()}


def get_json(url: str, timeout: float = 10.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def preflight(cfg: dict, url: str | None = None) -> tuple[list[str], dict]:
    """Bandingkan instans Ollama (hanya GET /api/version dan /api/tags) dengan referensi pilot."""
    problems, found = [], {}
    for slot in LOCAL:
        ref = pilot_reference(cfg, slot)
        base = url or model_cfg(cfg, slot)["base_url"]
        try:
            ver = get_json(f"{base}/api/version").get("version")
            tags = get_json(f"{base}/api/tags").get("models", [])
        except Exception as e:  # noqa: BLE001
            problems.append(f"{slot}: instans {base} tidak menjawab ({type(e).__name__}: {e})")
            continue
        mid = model_cfg(cfg, slot)["model_id"]
        hit = [m for m in tags if m.get("name") in (mid, f"{mid}:latest") or m.get("model") in (mid, f"{mid}:latest")]
        cur = {"ollama_server_version": ver,
               "digest": hit[0].get("digest") if hit else None,
               "quantization_level": (hit[0].get("details") or {}).get("quantization_level") if hit else None}
        found[slot] = {"pilot": ref, "sekarang": cur, "base_url": base}
        for k, v in ref.items():
            if cur[k] != v:
                problems.append(f"{slot}: {k} = {cur[k]!r}, pilot = {v!r}")
    return problems, found


class LocalMonitor(Monitor):
    """Monitor bagian A ditambah pemeriksaan identitas model lokal."""

    def __init__(self, cfg: dict, slots: list[str], chunk: int, name: str):
        super().__init__(cfg, slots, chunk, name=name)
        self.ref = {s: pilot_reference(cfg, s) for s in slots}

    def slot_stats(self, slot: str) -> dict:
        s = super().slot_stats(slot)
        recs = [r for r in self.records("dialogs", slot) + self.records("g0", slot) if r.get("status") == "ok"]
        for key, field in (("digest", "digest"), ("ollama_versi", "ollama_server_version"),
                           ("kuantisasi", "quantization_level")):
            s[key] = sorted({(r.get("model_info") or {}).get(field) for r in recs} - {None})
        lat = [r["latency_s_total"] for r in self.records("dialogs", slot) if r["status"] == "ok"]
        s["latensi_dialog_s_60_terakhir"] = st.mean(lat[-60:]) if lat else None
        return s

    def check(self, slot: str) -> list[str]:
        reasons = super().check(slot)
        s = self.status["slots"][slot]
        ref = self.ref[slot]
        for key, field in (("digest", "digest"), ("ollama_versi", "ollama_server_version"),
                           ("kuantisasi", "quantization_level")):
            if len(s[key]) > 1:
                reasons.append(f"{slot}: {key} berubah di tengah run: {s[key]}")
            elif s[key] and s[key][0] != ref[field]:
                reasons.append(f"{slot}: {key} {s[key][0]} berbeda dari pilot {ref[field]}")
        return reasons

    def per_dialog_s(self, slot: str) -> float:
        cur = self.slot_stats(slot)["latensi_dialog_s_60_terakhir"]
        return max(cur or 0.0, 1.0) if cur else PILOT_DIALOG_S[slot] + 2.0


def seconds_left(deadline: datetime) -> float:
    return (deadline - datetime.now()).total_seconds()


def hasilkan(cfg: dict, args: argparse.Namespace) -> int:
    deadline = datetime.fromisoformat(args.deadline)
    mon = LocalMonitor(cfg, LOCAL, args.chunk, name="lokal")
    mon.status["batas_waktu_kerja"] = deadline.isoformat(timespec="seconds")
    mon.log(f"mulai pengatur Tahap 5 lokal: model={LOCAL} potongan={args.chunk} batas kerja={deadline}")
    problems, found = preflight(cfg)
    mon.status["pemeriksaan_awal"] = {"masalah": problems, "hasil": found}
    mon.save()
    if problems:
        mon.halt(["pemeriksaan awal instans riset gagal: " + "; ".join(problems)])
        return 2
    mon.log(f"pemeriksaan awal lolos: {json.dumps({s: v['sekarang'] for s, v in found.items()})}")
    timed_out = False
    try:
        for slot in LOCAL:                                         # 1. G0 kedua model
            if mon.stop_event.is_set() or timed_out:
                break
            if mon.slot_stats(slot)["g0_ok"] >= G0_PER_MODEL:
                continue
            if seconds_left(deadline) < G0_MIN_LEFT_S:
                timed_out = True
                break
            mon.log(f"{slot}: mulai G0")
            rc = mon.run(["src.run_g0", "--phase", PHASE, "--allow-main", "--models", slot])
            mon.log(f"{slot}: G0 selesai rc={rc} ok={mon.slot_stats(slot)['g0_ok']}/{G0_PER_MODEL}")
            reasons = mon.check(slot)
            if reasons:
                mon.halt(reasons)
        for slot in LOCAL:                                         # 2. dialog per model
            stall = 0
            while not mon.stop_event.is_set() and not timed_out:
                before = mon.slot_stats(slot)
                if before["dialog_ok"] >= before["dialog_rencana"]:
                    with mon.lock:
                        mon.status["slots"].setdefault(slot, {})["dialog_selesai"] = datetime.now().isoformat(timespec="seconds")
                    break
                n = chunk_size(mon.per_dialog_s(slot), seconds_left(deadline), args.chunk)
                if n == 0:
                    timed_out = True
                    break
                rc = mon.run(["src.run_dialogs", "--phase", PHASE, "--allow-main", "--models", slot, "--limit", str(n)])
                after = mon.slot_stats(slot)
                mon.log(f"{slot}: dialog {after['dialog_ok']}/{after['dialog_rencana']} (potongan {n}) rc={rc} "
                        f"gagal={len(after['dialog_gagal_tanpa_ok'])} terpotong={after['giliran_terpotong']} "
                        f"rata2={after['latensi_dialog_s_60_terakhir'] or 0:.1f}s")
                reasons = mon.check(slot)
                if reasons:
                    mon.halt(reasons)
                    break
                stall = stall + 1 if after["dialog_ok"] == before["dialog_ok"] else 0
                if stall >= 3:
                    mon.halt([f"{slot}: tidak ada kemajuan dalam 3 potongan berturut-turut"])
    except KeyboardInterrupt:
        mon.halt(["dihentikan manual (KeyboardInterrupt)"])
    for slot in LOCAL:
        mon.check(slot)
    sisa = {s: {"g0": G0_PER_MODEL - mon.status["slots"][s]["g0_ok"],
                "dialog": mon.status["slots"][s]["dialog_rencana"] - mon.status["slots"][s]["dialog_ok"]} for s in LOCAL}
    mon.status["sisa"] = sisa
    if timed_out and not mon.status["berhenti"]:
        mon.status["batas_waktu"] = {"waktu": datetime.now().isoformat(timespec="seconds"), "sisa": sisa}
        mon.log(f"batas waktu jendela: berhenti rapi di antara dialog; sisa {sisa}")
    mon.status["selesai"] = datetime.now().isoformat(timespec="seconds")
    mon.save()
    mon.log("pengatur lokal selesai" + (" (BERHENTI)" if mon.status["berhenti"] else (" (BATAS WAKTU)" if timed_out else "")))
    return 2 if mon.status["berhenti"] else (4 if timed_out else 0)


def nilai(cfg: dict, args: argparse.Namespace) -> int:
    until = datetime.fromisoformat(args.tunggu_sampai)
    if args.mulai:                                   # tidur tanpa membaca log sampai awal jendela
        while datetime.now() < datetime.fromisoformat(args.mulai):
            time.sleep(30)
    mon = LocalMonitor(cfg, LOCAL, 0, name="lokal_nilai")
    gen_status = T4 / "runs" / "pantau" / "tahap5_lokal_status.json"
    mon.log(f"mulai penilai Tahap 5 lokal: model={LOCAL} menunggu dialog lengkap sampai {until}")

    started = datetime.now()

    def generator_halted() -> bool:
        """Pengatur ``hasilkan`` yang dimulai <= 12 jam sebelum proses ini (atau sesudahnya) mencatat berhenti."""
        try:
            st_ = json.loads(gen_status.read_text(encoding="utf-8"))
            return bool(st_.get("berhenti")) and datetime.fromisoformat(st_["mulai"]) >= started - timedelta(hours=12)
        except (OSError, KeyError, ValueError):
            return False

    def follow(slot: str) -> None:
        while not mon.stop_event.is_set():
            s = mon.slot_stats(slot)
            if s["dialog_ok"] >= s["dialog_rencana"]:
                break
            if generator_halted():
                mon.log(f"penilai {slot}: pengatur lokal mencatat kondisi berhenti; penilai tidak dijalankan")
                return
            if datetime.now() > until:
                mon.log(f"penilai {slot}: dialog belum lengkap ({s['dialog_ok']}/{s['dialog_rencana']}) "
                        f"sampai {until}; penilai ditunda ke jendela berikutnya")
                return
            time.sleep(60)
        if not mon.stop_event.is_set():
            mon.judge_slot(slot)

    threads = [threading.Thread(target=follow, args=(s,), daemon=False) for s in LOCAL]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(60)
            for slot in LOCAL:
                reasons = mon.check(slot)
                if reasons:
                    mon.halt(reasons)
                    break
    except KeyboardInterrupt:
        mon.halt(["dihentikan manual (KeyboardInterrupt)"])
    for t in threads:
        t.join()
    for slot in LOCAL:
        mon.check(slot)
    mon.status["selesai"] = datetime.now().isoformat(timespec="seconds")
    mon.save()
    mon.log("penilai lokal selesai" + (" (BERHENTI)" if mon.status["berhenti"] else ""))
    return 2 if mon.status["berhenti"] else 0


def periksa(cfg: dict, args: argparse.Namespace) -> int:
    """Hanya baca: referensi pilot, statistik log Tahap 5, dan (opsional) isi instans Ollama."""
    out = {"pilot": {s: pilot_reference(cfg, s) for s in LOCAL}}
    if args.url:
        problems, found = preflight(cfg, args.url)
        out["instans"] = {"url": args.url, "masalah": problems, "hasil": found}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    h = sub.add_parser("hasilkan")
    h.add_argument("--deadline", required=True, help="waktu lokal ISO; potongan baru harus selesai sebelum ini")
    h.add_argument("--chunk", type=int, default=30)
    n = sub.add_parser("nilai")
    n.add_argument("--tunggu-sampai", required=True, help="waktu lokal ISO; batas menunggu dialog lengkap")
    n.add_argument("--mulai", help="waktu lokal ISO; tidur sampai waktu ini sebelum mulai memantau")
    p = sub.add_parser("periksa")
    p.add_argument("--url", help="GET /api/version dan /api/tags dari instans ini (hanya baca)")
    args = ap.parse_args()
    cfg = load_config()
    sys.exit({"hasilkan": hasilkan, "nilai": nilai, "periksa": periksa}[args.mode](cfg, args))


if __name__ == "__main__":
    main()
