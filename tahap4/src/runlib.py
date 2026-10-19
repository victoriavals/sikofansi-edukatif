"""Logika bersama runner: retry + backoff, parameter generasi, filter rencana, folder keluaran, anggaran."""
from __future__ import annotations

import argparse
import random
import time
from pathlib import Path
from typing import Any

from .adapters import AdapterError, BaseAdapter, ChatResult
from .common import PHASES, cost_usd, now_iso, read_jsonl, spent_usd


def call_with_retry(adapter: BaseAdapter, messages: list[dict], params: dict[str, Any],
                    retry: dict[str, Any]) -> tuple[ChatResult | None, list[dict]]:
    """Panggil model dengan exponential backoff. Kembalikan (hasil atau None, daftar galat per percobaan).

    Respons kosong dianggap galat yang layak diulang. Galat non-retryable (mis. 400/401) langsung berhenti.
    Tidak pernah ada respons pengganti: bila semua percobaan gagal, hasilnya None dan galat dicatat.
    """
    errors: list[dict] = []
    max_attempts = int(retry["max_attempts"])
    for attempt in range(1, max_attempts + 1):
        try:
            res = adapter.chat(messages, params)
            if not res.text.strip():
                # respons kosong tetap DITAGIH penyedia (mis. penalaran menghabiskan max_tokens): catat tokennya
                errors.append({"attempt": attempt, "time": now_iso(), "status": None, "retryable": True,
                               "error": f"Respons kosong (finish_reason={res.finish_reason}, "
                                        f"output_tokens={res.output_tokens})",
                               "billed_input_tokens": res.input_tokens, "billed_output_tokens": res.output_tokens,
                               "reasoning_tokens": res.provider_meta.get("reasoning_tokens"),
                               "api_reported_cost_usd": res.provider_meta.get("api_reported_cost_usd"),
                               "model_reported": res.model_reported, "response_id": res.provider_meta.get("id")})
                if attempt < max_attempts:
                    _backoff(retry, attempt)
                continue
            return res, errors
        except AdapterError as e:
            errors.append({"attempt": attempt, "time": now_iso(), "error": str(e)[:1000],
                           "status": e.status, "retryable": e.retryable})
            if not e.retryable:
                break
        except Exception as e:  # galat tak terduga dari SDK tetap dicatat dan diulang
            errors.append({"attempt": attempt, "time": now_iso(), "error": f"{type(e).__name__}: {e}"[:1000],
                           "status": None, "retryable": True})
        if attempt < max_attempts:
            _backoff(retry, attempt)
    return None, errors


def _backoff(retry: dict[str, Any], attempt: int) -> None:
    """Jeda exponential backoff dengan jitter sebelum percobaan berikutnya."""
    delay = min(float(retry["max_delay_s"]), float(retry["base_delay_s"]) * 2 ** (attempt - 1))
    time.sleep(delay * (0.75 + 0.5 * random.random()))


def errors_cost(m: dict, errors: list[dict]) -> float:
    """Biaya panggilan gagal yang tetap ditagih (respons kosong), dari token yang dilaporkan API."""
    return sum(cost_usd(m, e.get("billed_input_tokens"), e.get("billed_output_tokens")) for e in errors)


def gen_params(m: dict, cfg: dict, seed: int) -> tuple[dict[str, Any], bool]:
    """Parameter generasi untuk model yang diuji, sesuai CLAUDE.md. Kembalikan (params, seed_dikirim).

    - Ollama: num_ctx, num_predict (=max_tokens), seed, dan num_gpu bila diset (penempatan layer, bukan
      parameter sampling); temperature/top_p tidak di-override.
    - API komersial: hanya max_tokens; tanpa parameter sampling. Seed hanya bila ``send_seed: true``.
    """
    if m["provider"] == "ollama":
        opts = cfg["ollama"]["options"]
        params: dict[str, Any] = {"num_ctx": int(opts["num_ctx"]),
                                  "max_tokens": int(opts.get("num_predict", cfg["max_tokens"])), "seed": seed}
        if opts.get("num_gpu") is not None and not m.get("_dev"):
            params["num_gpu"] = int(opts["num_gpu"])
        return params, True
    params: dict[str, Any] = {"max_tokens": int(cfg["max_tokens"])}
    if m.get("send_seed"):
        params["seed"] = seed
    return params, bool(m.get("send_seed"))


def compact_model(desc: dict) -> dict[str, Any]:
    """Ringkasan metadata model untuk setiap baris log (metadata lengkap ada di berkas .meta.json)."""
    keep = {k: desc.get(k) for k in ("provider", "model_id", "family", "base_url", "digest", "ollama_server_version")}
    details = desc.get("details") or {}
    if details:
        keep["quantization_level"] = details.get("quantization_level")
        keep["parameter_size"] = details.get("parameter_size")
    return {k: v for k, v in keep.items() if v is not None}


def add_filter_args(ap: argparse.ArgumentParser) -> None:
    """Argumen CLI yang sama untuk runner dialog dan G0."""
    ap.add_argument("--config", help="path config.yaml (default: tahap4/config.yaml)")
    ap.add_argument("--phase", default="tahap4", choices=sorted(PHASES),
                    help="tahap4 = uji coba (default); tahap5 = data utama, butuh --allow-main")
    ap.add_argument("--allow-main", action="store_true", help="izinkan fase tahap5 (hanya setelah izin peneliti)")
    ap.add_argument("--models", nargs="+", required=True, help="slot model di rencana, mis. gemma2_9b_it")
    ap.add_argument("--items", nargs="+", help="filter item_id, mis. A04 B01")
    ap.add_argument("--reps", nargs="+", type=int, help="filter ulangan, mis. 1 2")
    ap.add_argument("--langs", nargs="+", choices=["id", "en"])
    ap.add_argument("--limit", type=int, help="maksimum baris yang dijalankan per slot (untuk uji kecil)")
    ap.add_argument("--dev-model", help="uji asap: jalankan baris slot ini dengan model dev_models; log ke runs/dev/")
    ap.add_argument("--estimate-only", action="store_true", help="hanya tampilkan jumlah dan estimasi biaya")


def select_rows(plan: list[dict], slot: str, args: argparse.Namespace) -> list[dict]:
    """Filter baris rencana untuk satu slot sesuai argumen, urut kolom ``order`` (atau urutan berkas)."""
    rows = [r for r in plan if r["model"] == slot]
    if args.items:
        rows = [r for r in rows if r["item_id"] in set(args.items)]
    if args.reps:
        rows = [r for r in rows if r["rep"] in set(args.reps)]
    if args.langs:
        rows = [r for r in rows if r["lang"] in set(args.langs)]
    if getattr(args, "framings", None):
        rows = [r for r in rows if r["framing"] in set(args.framings)]
    if getattr(args, "pressures", None):
        rows = [r for r in rows if r["pressure"].split("_")[0] in set(args.pressures)]
    return sorted(rows, key=lambda r: r.get("order", 0))


def out_dir_for(cfg: dict, phase: str, dev_model: str | None) -> Path:
    """Folder log: runs/raw/<fase>/ untuk data, runs/dev/<fase>/ untuk uji asap dengan model dev."""
    return (cfg["paths"]["dev_dir"] if dev_model else cfg["paths"]["runs_dir"]) / phase


def log_prefix(kind: str, slot: str, dev_model: str | None) -> str:
    """Awalan nama berkas log; dev diberi nama model pengganti agar resume tidak tercampur."""
    return f"{kind}_{slot}__{dev_model}" if dev_model else f"{kind}_{slot}"


def is_paid(m: dict) -> bool:
    return float(m.get("price_input_per_mtok") or 0) > 0 or float(m.get("price_output_per_mtok") or 0) > 0


class BudgetTracker:
    """Pengaman anggaran kumulatif (harga normal, batas atas).

    Biaya yang sudah tercatat di semua log dibaca SEKALI saat dibuat, lalu ditambah per dialog/panggilan run ini
    (tidak membaca ulang ribuan baris log di setiap dialog). Dua ambang dari config:
    - ``budget_usd_limit``: tolak bila terpakai + estimasi langkah berikutnya melebihi batas;
    - ``budget_alert_usd``: berhenti dan laporkan ke peneliti begitu biaya kumulatif melewati ambang ini.
    Proses lain yang berjalan bersamaan tidak terlihat; jalankan run API berbayar satu per satu.
    """

    def __init__(self, cfg: dict, stage_dir: Path | None = None, stage_limit: float | None = None):
        self.limit = float(cfg["budget_usd_limit"])
        self.alert = float(cfg.get("budget_alert_usd") or self.limit)
        self.spent = spent_usd(cfg)
        # batas khusus satu tahap (mis. kalibrasi 4C < 1 USD): biaya yang tercatat di folder tahap itu + run ini
        self.stage_limit = stage_limit
        self.stage_spent = 0.0
        if stage_dir is not None and stage_dir.exists():
            self.stage_spent = sum(float(r.get("cost_usd") or 0) for p in stage_dir.rglob("*.jsonl")
                                   for r in read_jsonl(p))

    def add(self, cost: float) -> None:
        self.spent += float(cost or 0)
        self.stage_spent += float(cost or 0)

    def check(self, m: dict, estimate: float) -> tuple[bool, str]:
        """(boleh_jalan, alasan_berhenti) untuk langkah berikutnya dengan estimasi biaya ``estimate``."""
        if not is_paid(m):
            return True, ""
        if self.stage_limit is not None and self.stage_spent + estimate > self.stage_limit:
            return False, (f"biaya tahap ${self.stage_spent:.4f} + estimasi ${estimate:.4f} melewati batas tahap "
                           f"${self.stage_limit:.2f}: BERHENTI dan laporkan ke peneliti")
        if self.spent >= self.alert:
            return False, (f"biaya kumulatif ${self.spent:.4f} melewati ambang ${self.alert:.2f} "
                           f"(budget_alert_usd): BERHENTI dan laporkan ke peneliti")
        if self.spent + estimate > self.limit:
            return False, (f"terpakai ${self.spent:.4f} + estimasi ${estimate:.4f} melebihi "
                           f"budget_usd_limit ${self.limit:.2f}: minta izin peneliti")
        return True, ""


def turn_cost(m: dict, res: ChatResult) -> float:
    return cost_usd(m, res.input_tokens, res.output_tokens)
