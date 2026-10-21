"""Paket rilis data Tahap 5 untuk diunggah ke OSF (BUKAN untuk GitHub): zip + manifest SHA256 per berkas + SHA256 zip.

Isi: log mentah runs/raw/tahap5/ (dialog dan G0, beserta .meta.json), log ringkas dan status pengatur
runs/pantau/tahap5_*, label penilai labels/tahap5/ (judge_*, stability_*, .meta/.end), nilai G0 dan g0_known.csv,
salinan config, environment.md, DEVIATIONS.md, dan berkas protokol beku (judge_prompt.md, panduan_pelabelan.md,
judge_schema.json, CHANGELOG.md). Materi validasi manusia (labels/tahap5/validasi_manusia/)
TIDAK dimasukkan sampai Tahap 6 selesai, agar penilai manusia tetap buta terhadap label penilai LLM.

Pemakaian (dari tahap4/):  python model_prep/paket_rilis.py   -> ../release/tahap5/
"""
from __future__ import annotations

import csv
import hashlib
import sys
import zipfile
from datetime import datetime
from pathlib import Path

T4 = Path(__file__).resolve().parent.parent
ROOT = T4.parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def collect() -> list[Path]:
    files: list[Path] = []
    files += sorted((T4 / "runs" / "raw" / "tahap5").glob("*"))
    files += sorted(p for p in (T4 / "labels" / "tahap5").rglob("*") if p.is_file() and "validasi_manusia" not in p.parts)
    # log ringkas dan status pengatur run (linimasa dan pemeriksaan kondisi berhenti)
    files += [T4 / "runs" / "pantau" / f"tahap5_{n}{ext}" for n in ("api", "lokal", "lokal_nilai")
              for ext in (".log", "_status.json")]
    files += [T4 / "config.yaml", T4 / "reports" / "environment.md", T4 / "reports" / "DEVIATIONS.md",
              ROOT / "tahap3" / "judge_prompt.md", ROOT / "tahap3" / "panduan_pelabelan.md",
              ROOT / "tahap3" / "judge_schema.json", ROOT / "tahap3" / "CHANGELOG.md"]
    return [f for f in files if f.is_file()]


def main() -> None:
    files = collect()
    if not files:
        raise SystemExit("Tidak ada berkas Tahap 5 untuk dipaketkan.")
    out = ROOT / "release" / "tahap5"
    out.mkdir(parents=True, exist_ok=True)
    tag = datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest = out / f"MANIFEST_{tag}.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "bytes", "sha256"])
        for p in files:
            w.writerow([p.relative_to(ROOT).as_posix(), p.stat().st_size, sha256(p)])
    zpath = out / f"sikofansi_tahap5_{tag}.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, p.relative_to(ROOT).as_posix())
        z.write(manifest, f"release/tahap5/{manifest.name}")
    with open(out / "SHA256SUMS.txt", "a", encoding="utf-8") as f:
        f.write(f"{sha256(zpath)}  {zpath.name}\n{sha256(manifest)}  {manifest.name}\n")
    print(f"{len(files)} berkas -> {zpath} ({zpath.stat().st_size / 1e6:.1f} MB)")
    print(f"SHA256 zip: {sha256(zpath)}")


if __name__ == "__main__":
    sys.exit(main())
