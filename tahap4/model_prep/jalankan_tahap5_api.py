"""Pengatur run Tahap 5 untuk model API (bagian A + penilai bagian C), dengan pemantauan kondisi berhenti.

Urutan: G0 tiap slot -> dialog tiap slot dalam potongan kecil (resume antarpotongan) -> begitu dialog satu slot
selesai, penilai slot itu berjalan paralel (penilaian utama -> nilai ulang dialog invalid satu kali -> uji stabilitas).
Kode pembangkit data di src/ dipanggil apa adanya (fase tahap5, --allow-main).

Kondisi berhenti (instruksi Tahap 5 bagian 2): proses dihentikan, status dicatat, dan peneliti diberi laporan bila
- biaya kumulatif > budget_alert_usd (10 USD) atau proyeksi total Tahap 5 > budget_usd_limit (12 USD);
- > 5% dialog satu model gagal setelah semua retry;
- field `model` atau header hulu (x-litellm-model-api-base / x-litellm-model-name) berubah di tengah run;
- > 2% giliran satu model terpotong (finish_reason = length);
- > 5% dialog tidak valid di penilai.
Status: runs/pantau/tahap5_api_status.json; log: runs/pantau/tahap5_api.log (keduanya di-ignore git).

Pemakaian (dari tahap4/):  python model_prep/jalankan_tahap5_api.py [--slots komersial_A komersial_B] [--chunk 30]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import subprocess
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

T4 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(T4))
from src.common import estimate_dialog_cost, iter_records, load_config, model_cfg, read_jsonl, run_glob, spent_usd  # noqa: E402
from src.summarize import final_records  # noqa: E402

PHASE = "tahap5"
PY = sys.executable
FAIL_MAX, TRUNC_MAX, INVALID_MAX = 0.05, 0.02, 0.05
MIN_DIALOGS, MIN_TURNS, MIN_JUDGED = 60, 90, 100
JUDGE_COST_PER_DIALOG_PILOT = 0.1124 / 132     # v1.1 pilot (harga normal, termasuk respons kosong dan stabilitas)


class Monitor:
    def __init__(self, cfg: dict, slots: list[str], chunk: int, name: str = "api"):
        self.cfg, self.slots, self.chunk = cfg, slots, chunk
        self.dir = T4 / "runs" / "pantau"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.dir / f"tahap5_{name}.log"
        self.status_path = self.dir / f"tahap5_{name}_status.json"
        self.runner_log_path = self.dir / f"tahap5_{name}_runner.log"
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=T4, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "config.yaml"], cwd=T4,
                               capture_output=True, text=True).stdout.strip()
        self.status: dict = {"mulai": datetime.now().isoformat(timespec="seconds"), "slots": {}, "berhenti": None,
                             "judge": {}, "git_head": head, "src_atau_config_berubah_belum_commit": bool(dirty)}
        self.stop_event = threading.Event()
        self.procs: list[subprocess.Popen] = []
        self.lock = threading.Lock()
        plan = list(read_jsonl(cfg["paths"]["dialogs_plan"]))
        self.plan_rows = {s: [r for r in plan if r["model"] == s] for s in cfg["models"]}

    def log(self, msg: str) -> None:
        line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
        print(line, flush=True)
        with self.lock, open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def save(self) -> None:
        with self.lock:
            self.status["diperbarui"] = datetime.now().isoformat(timespec="seconds")
            self.status_path.write_text(json.dumps(self.status, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    def run(self, args: list[str]) -> int:
        """Jalankan modul src.* sebagai subprocess; keluaran ke log runner."""
        if self.stop_event.is_set():
            return 99
        with open(self.runner_log_path, "a", encoding="utf-8") as out:
            out.write(f"\n### {datetime.now().isoformat(timespec='seconds')} {' '.join(args)}\n")
            out.flush()
            p = subprocess.Popen([PY, "-m", *args], cwd=T4, stdout=out, stderr=subprocess.STDOUT,
                                 env={**os.environ, "PYTHONUTF8": "1"})
            with self.lock:
                self.procs.append(p)
            rc = p.wait()
            with self.lock:
                self.procs.remove(p)
        return rc

    # ---------- statistik dari log ----------
    def records(self, kind: str, slot: str) -> list[dict]:
        return [r for _, r in iter_records(self.cfg["paths"]["runs_dir"] / PHASE, run_glob(f"{kind}_{slot}"))]

    def slot_stats(self, slot: str) -> dict:
        d = self.records("dialogs", slot)
        g = self.records("g0", slot)
        ok_ids = {r["dialog_id"] for r in d if r["status"] == "ok"}
        seen = {r["dialog_id"] for r in d}
        failed = sorted(i for i in seen - ok_ids if any(r["dialog_id"] == i and r["status"] == "error" for r in d))
        turns = [t for r in d if r["status"] == "ok" for t in r["turns"]]
        g0_ok = [r for r in g if r.get("status") == "ok"]
        calls = turns + g0_ok
        hdr = lambda c, k: (c.get("provider_meta") or {}).get("headers", {}).get(k)
        ok_costs = [r["cost_usd"] for r in d if r["status"] == "ok"]
        return {"dialog_rencana": len(self.plan_rows[slot]), "dialog_ok": len(ok_ids), "dialog_dicoba": len(seen),
                "dialog_gagal_tanpa_ok": failed, "giliran": len(turns),
                "giliran_terpotong": sum(t.get("finish_reason") == "length" for t in turns),
                "g0_ok": len({r["g0_id"] for r in g0_ok}), "g0_terpotong": sum(r.get("finish_reason") == "length" for r in g0_ok),
                "model_field": sorted({c.get("model_reported") for c in calls if c.get("model_reported")}),
                "hulu_api_base": sorted({h for c in calls if (h := hdr(c, "x-litellm-model-api-base"))}),
                "hulu_model_name": sorted({h for c in calls if (h := hdr(c, "x-litellm-model-name"))}),
                "biaya_dialog_usd": sum(r["cost_usd"] for r in d), "biaya_g0_usd": sum(r.get("cost_usd") or 0 for r in g),
                "biaya_rata2_per_dialog": st.mean(ok_costs) if ok_costs else None,
                "mulai": min((r["started_at"] for r in d + g), default=None),
                "terakhir": max((r["finished_at"] for r in d + g), default=None)}

    def judge_stats(self, slot: str) -> dict:
        recs = [r for _, r in iter_records(self.cfg["paths"]["labels_dir"] / PHASE, f"judge_*_{slot}_[0-9]*.jsonl")]
        fin = final_records(recs)
        return {"dinilai": len(fin), "valid": sum(r["status"] == "ok" for r in fin.values()),
                "tidak_valid": sum(r["status"] != "ok" for r in fin.values()),
                "biaya_usd": sum(r["cost_usd"] for r in recs)}

    def projection(self) -> dict:
        spent = spent_usd(self.cfg)
        remaining = 0.0
        for s in self.cfg["models"]:
            m = model_cfg(self.cfg, s)
            if not (float(m.get("price_input_per_mtok") or 0) or float(m.get("price_output_per_mtok") or 0)):
                continue
            stt = self.slot_stats(s)
            left = stt["dialog_rencana"] - stt["dialog_ok"]
            per = stt["biaya_rata2_per_dialog"] if stt["dialog_ok"] >= 20 else st.mean(
                estimate_dialog_cost(m, r["turns"], self.cfg) for r in self.plan_rows[s])
            remaining += left * per
        judged = sum(self.judge_stats(s)["dinilai"] for s in self.cfg["models"])
        jcost = [self.judge_stats(s) for s in self.cfg["models"]]
        jdone = sum(j["dinilai"] for j in jcost)
        jper = (sum(j["biaya_usd"] for j in jcost) / jdone) if jdone >= 50 else JUDGE_COST_PER_DIALOG_PILOT
        remaining += max(0, 4320 * 1.1 - judged) * jper
        return {"terpakai": spent, "sisa_estimasi": remaining, "proyeksi_total": spent + remaining}

    # ---------- pemeriksaan kondisi berhenti ----------
    def check(self, slot: str) -> list[str]:
        s = self.slot_stats(slot)
        reasons = []
        if s["dialog_dicoba"] >= MIN_DIALOGS and len(s["dialog_gagal_tanpa_ok"]) / s["dialog_dicoba"] > FAIL_MAX:
            reasons.append(f"{slot}: {len(s['dialog_gagal_tanpa_ok'])}/{s['dialog_dicoba']} dialog gagal (> 5%)")
        if s["giliran"] >= MIN_TURNS and s["giliran_terpotong"] / s["giliran"] > TRUNC_MAX:
            reasons.append(f"{slot}: {s['giliran_terpotong']}/{s['giliran']} giliran terpotong (> 2%)")
        for k in ("model_field", "hulu_api_base", "hulu_model_name"):
            if len(s[k]) > 1:
                reasons.append(f"{slot}: {k} berubah di tengah run: {s[k]}")
        p = self.projection()
        if p["terpakai"] > float(self.cfg["budget_alert_usd"]):
            reasons.append(f"biaya kumulatif ${p['terpakai']:.4f} > ambang lapor ${self.cfg['budget_alert_usd']}")
        if p["proyeksi_total"] > float(self.cfg["budget_usd_limit"]):
            reasons.append(f"proyeksi total ${p['proyeksi_total']:.4f} > batas ${self.cfg['budget_usd_limit']}")
        for js in self.slots:
            j = self.judge_stats(js)
            if j["dinilai"] >= MIN_JUDGED and j["tidak_valid"] / j["dinilai"] > INVALID_MAX:
                reasons.append(f"penilai {js}: {j['tidak_valid']}/{j['dinilai']} dialog tidak valid (> 5%)")
        with self.lock:
            self.status["slots"][slot] = s
            self.status["proyeksi"] = p
        self.save()
        return reasons

    def halt(self, reasons: list[str]) -> None:
        self.stop_event.set()
        with self.lock:
            self.status["berhenti"] = {"waktu": datetime.now().isoformat(timespec="seconds"), "alasan": reasons}
            procs = list(self.procs)
        for p in procs:
            p.terminate()
        self.log("BERHENTI: " + " | ".join(reasons))
        self.save()

    # ---------- penilai satu slot (berjalan di thread) ----------
    def judge_slot(self, slot: str) -> None:
        base = ["src.run_judge", "--phase", PHASE, "--allow-main", "--models", slot]
        steps = [("utama", base), ("nilai_ulang_invalid", base + ["--rejudge-invalid", "--rejudge-reason",
                  "protokol Tahap 5: dialog tidak valid setelah 3 percobaan dinilai ulang satu kali"]),
                 ("stabilitas", base + ["--stability"])]
        for name, args in steps:
            if self.stop_event.is_set():
                return
            self.log(f"penilai {slot}: mulai {name}")
            rc = self.run(args)
            j = self.judge_stats(slot)
            with self.lock:
                self.status["judge"].setdefault(slot, {})[name] = {"rc": rc, "selesai": datetime.now().isoformat(timespec="seconds"), **j}
            self.log(f"penilai {slot}: {name} selesai rc={rc} {j}")
            self.save()
            if rc not in (0,):
                self.halt([f"penilai {slot} langkah {name} keluar dengan kode {rc}"])
                return


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slots", nargs="+", default=["komersial_A", "komersial_B"])
    ap.add_argument("--chunk", type=int, default=30)
    args = ap.parse_args()
    cfg = load_config()
    mon = Monitor(cfg, args.slots, args.chunk)
    mon.log(f"mulai pengatur Tahap 5 API: slots={args.slots} potongan={args.chunk}")
    judge_threads: list[threading.Thread] = []
    try:
        for slot in args.slots:                                   # 1. G0 semua slot API
            if mon.stop_event.is_set():
                break
            if mon.slot_stats(slot)["g0_ok"] < 180:
                mon.log(f"{slot}: mulai G0")
                rc = mon.run(["src.run_g0", "--phase", PHASE, "--allow-main", "--models", slot])
                mon.log(f"{slot}: G0 selesai rc={rc} ok={mon.slot_stats(slot)['g0_ok']}/180")
                if rc == 3:
                    mon.halt([f"{slot}: pengaman anggaran menghentikan G0"])
            reasons = mon.check(slot)
            if reasons:
                mon.halt(reasons)
        for slot in args.slots:                                   # 2. dialog per slot, lalu penilai paralel
            stall = 0
            while not mon.stop_event.is_set():
                before = mon.slot_stats(slot)
                if before["dialog_ok"] >= before["dialog_rencana"]:
                    break
                rc = mon.run(["src.run_dialogs", "--phase", PHASE, "--allow-main", "--models", slot,
                              "--limit", str(args.chunk)])
                after = mon.slot_stats(slot)
                mon.log(f"{slot}: dialog {after['dialog_ok']}/{after['dialog_rencana']} rc={rc} "
                        f"gagal={len(after['dialog_gagal_tanpa_ok'])} terpotong={after['giliran_terpotong']}")
                if rc == 3:
                    mon.halt([f"{slot}: pengaman anggaran (runner) menghentikan dialog"])
                    break
                reasons = mon.check(slot)
                if reasons:
                    mon.halt(reasons)
                    break
                stall = stall + 1 if after["dialog_ok"] == before["dialog_ok"] else 0
                if stall >= 3:
                    mon.halt([f"{slot}: tidak ada kemajuan dalam 3 potongan berturut-turut"])
            if mon.stop_event.is_set():
                break
            with mon.lock:
                mon.status["slots"].setdefault(slot, {})["dialog_selesai"] = datetime.now().isoformat(timespec="seconds")
            th = threading.Thread(target=mon.judge_slot, args=(slot,), daemon=False)
            th.start()
            judge_threads.append(th)
        while any(t.is_alive() for t in judge_threads):           # 3. tunggu penilai, tetap pantau
            time.sleep(60)
            for slot in args.slots:
                reasons = mon.check(slot)
                if reasons:
                    mon.halt(reasons)
                    break
        for t in judge_threads:
            t.join()
    except KeyboardInterrupt:
        mon.halt(["dihentikan manual (KeyboardInterrupt)"])
    for slot in args.slots:
        mon.check(slot)
    mon.status["selesai"] = datetime.now().isoformat(timespec="seconds")
    mon.save()
    mon.log("pengatur selesai" + (" (BERHENTI)" if mon.status["berhenti"] else ""))
    sys.exit(2 if mon.status["berhenti"] else 0)


if __name__ == "__main__":
    main()
