#!/usr/bin/env bash
# Konversi bobot HF (bf16) -> GGUF BF16 -> Q4_K_M statis (tanpa imatrix) dengan llama.cpp b11714
# untuk KEDUA model, dengan perintah dan versi alat yang identik.
#
# Pemakaian (dari folder tahap4/):  bash model_prep/quantize.sh [slot ...]
set -euo pipefail
T4="$(cd "$(dirname "$0")/.." && pwd)"
LC="$T4/tools/llama.cpp-b11714"
BIN="$T4/tools/llama-b11714-bin-win-cpu-x64"
PY="$T4/.venv-convert/Scripts/python.exe"
OUT="$T4/models/gguf"
mkdir -p "$OUT"
SLOTS=("${@:-sahabatai_9b_it gemma2_9b_it}")

for slot in ${SLOTS[@]}; do
  echo "== [$slot] konversi HF -> GGUF BF16 ($(date -Is))"
  # dijalankan dari folder tahap4 (bukan folder bobot) agar tidak ada modul dari data unduhan yang ikut ter-import
  (cd "$T4" && "$PY" "$LC/convert_hf_to_gguf.py" "$T4/models/hf/$slot" --outtype bf16 \
      --outfile "$OUT/$slot-BF16.gguf")
  echo "== [$slot] kuantisasi BF16 -> Q4_K_M ($(date -Is))"
  "$BIN/llama-quantize.exe" "$OUT/$slot-BF16.gguf" "$OUT/$slot-Q4_K_M.gguf" Q4_K_M
  echo "== [$slot] SHA256"
  sha256sum "$OUT/$slot-BF16.gguf" "$OUT/$slot-Q4_K_M.gguf" | tee -a "$OUT/SHA256SUMS.txt"
done
echo "SELESAI ($(date -Is))"
