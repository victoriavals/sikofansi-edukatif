"""Utilitas bersama: konfigurasi, path, log JSONL append-only, seed, resume, dan anggaran biaya."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml
from dotenv import load_dotenv

TAHAP4 = Path(__file__).resolve().parent.parent
PHASES = {"tahap4", "tahap5"}  # tahap4 = uji coba/pilot; tahap5 = data utama (butuh izin peneliti)


def now_iso() -> str:
    """Timestamp UTC ISO-8601 dengan milidetik."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def stamp() -> str:
    """Penanda waktu untuk nama berkas run (waktu lokal, aman untuk nama berkas)."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Baca config.yaml, ubah path relatif menjadi absolut, dan muat .env ke variabel lingkungan."""
    cfg_path = Path(path) if path else TAHAP4 / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["_config_path"] = str(cfg_path.resolve())
    cfg["paths"] = {k: (TAHAP4 / v).resolve() for k, v in cfg["paths"].items()}
    load_dotenv(TAHAP4 / ".env", override=False)  # nilai kunci tidak pernah dicetak atau dicatat
    return cfg


def model_cfg(cfg: dict, name: str) -> dict[str, Any]:
    """Ambil konfigurasi slot model (models/dev_models/judge) dan pastikan tidak ada TODO."""
    if name == "judge":
        m = dict(cfg["judge"])
    elif name in cfg.get("models", {}):
        m = dict(cfg["models"][name])
    elif name in cfg.get("dev_models", {}):
        m = dict(cfg["dev_models"][name])
        m["_dev"] = True
    else:
        raise SystemExit(f"Slot model tidak dikenal di config: {name}")
    todo = [k for k, v in m.items() if v == "TODO"]
    if todo:
        raise SystemExit(f"Slot '{name}' belum lengkap (TODO: {', '.join(todo)}). Isi config.yaml dulu.")
    m["_slot"] = name
    return m


def seed_for(identifier: str) -> int:
    """Seed reprodusibel per dialog/pertanyaan: int(sha256(id)) mod 2^31."""
    return int(hashlib.sha256(identifier.encode("utf-8")).hexdigest(), 16) % (2**31)


def kode_block(code: str) -> str:
    """Blok kode Python dengan format yang sama seperti tahap3/render_prompts.py."""
    return f"```python\n{code}\n```"


def read_jsonl(path: Path) -> Iterator[dict]:
    """Baca JSONL baris demi baris; baris rusak (mis. terpotong saat dihentikan) dilewati dengan peringatan."""
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                print(f"[peringatan] baris {n} di {path.name} bukan JSON valid; dilewati", file=sys.stderr)


def run_glob(prefix: str) -> str:
    """Pola glob tepat untuk berkas log satu awalan: <prefix>_YYYYmmdd-HHMMSS.jsonl.

    Mencegah awalan pendek ikut mencocokkan awalan yang lebih panjang (mis. model dev lain)."""
    return f"{prefix}_{'[0-9]' * 8}-{'[0-9]' * 6}.jsonl"


def iter_records(folder: Path, pattern: str) -> Iterator[tuple[Path, dict]]:
    """Iterasi semua rekaman dari berkas JSONL yang cocok pola, urut nama berkas."""
    if not folder.exists():
        return
    for p in sorted(folder.glob(pattern)):
        for rec in read_jsonl(p):
            yield p, rec


def completed_ids(folder: Path, pattern: str, id_key: str) -> set[str]:
    """ID yang sudah sukses (status == 'ok') di semua log yang cocok pola; dipakai untuk resume."""
    return {rec[id_key] for _, rec in iter_records(folder, pattern) if rec.get("status") == "ok"}


class AppendOnlyLog:
    """Penulis JSONL append-only: satu berkas baru per run, flush + fsync setiap baris."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise SystemExit(f"Berkas log sudah ada, tidak akan ditimpa: {path}")
        self._f = open(path, "a", encoding="utf-8", newline="\n")

    def write(self, record: dict) -> None:
        self._f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._f.flush()
        os.fsync(self._f.fileno())

    def close(self) -> None:
        self._f.close()


def write_meta(path: Path, meta: dict) -> None:
    """Tulis berkas metadata run (sekali, di samping log JSONL); tidak pernah menimpa."""
    if path.exists():
        raise SystemExit(f"Berkas metadata sudah ada: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def runtime_info() -> dict[str, str]:
    """Info runtime ringkas untuk metadata run."""
    return {"python": platform.python_version(), "platform": platform.platform(), "argv": " ".join(sys.argv)}


def cost_usd(m: dict, input_tokens: int | None, output_tokens: int | None) -> float:
    """Biaya satu panggilan dari harga per 1 juta token di config."""
    pin = float(m.get("price_input_per_mtok") or 0)
    pout = float(m.get("price_output_per_mtok") or 0)
    return ((input_tokens or 0) * pin + (output_tokens or 0) * pout) / 1e6


def spent_usd(cfg: dict) -> float:
    """Total biaya API yang sudah tercatat di semua log (runs/ dan labels/, termasuk dev)."""
    total = 0.0
    for folder in (cfg["paths"]["runs_dir"], cfg["paths"]["dev_dir"], cfg["paths"]["labels_dir"]):
        if folder.exists():
            for p in folder.rglob("*.jsonl"):
                for rec in read_jsonl(p):
                    total += float(rec.get("cost_usd") or 0)
    return total


def estimate_dialog_cost(m: dict, turns: Iterable[str], cfg: dict) -> float:
    """Estimasi kasar biaya satu dialog multi-giliran (riwayat ikut dikirim tiap giliran)."""
    cpt = cfg["cost_estimate"]["chars_per_token"]
    # override per slot dari uji asap: token keluaran yang DITAGIH per giliran (termasuk penalaran) dan token yang
    # MASUK RIWAYAT per giliran (hanya jawaban terlihat; penalaran tidak dikirim ulang). Default: nilai config.
    out_tok = m.get("est_output_tokens_per_turn") or cfg["cost_estimate"]["output_tokens_per_turn"]
    hist_tok = m.get("est_history_tokens_per_turn") or out_tok
    history, total_in, total_out = 0.0, 0.0, 0.0
    for t in turns:
        history += len(t) / cpt
        total_in += history
        total_out += out_tok
        history += hist_tok
    return cost_usd(m, int(total_in), int(total_out))


def check_phase(phase: str, allow_main: bool, estimate_only: bool = False) -> None:
    """Tolak fase data utama tanpa izin eksplisit (CLAUDE.md aturan 8). Estimasi saja tidak memanggil model."""
    if phase not in PHASES:
        raise SystemExit(f"Fase tidak dikenal: {phase} (pilihan: {sorted(PHASES)})")
    if phase == "tahap5" and not allow_main and not estimate_only:
        raise SystemExit("Fase tahap5 (data utama) butuh izin peneliti; jalankan dengan --allow-main setelah izin diberikan.")
