#!/usr/bin/env bash
# Instans Ollama khusus penelitian di 127.0.0.1:11435, terpisah dari server Ollama lain di mesin ini (11434).
# Biner Ollama (0.40.5) dibaca dari OLLAMA_BIN di tahap4/lokal_pribadi.env (di-ignore git); setelan dikendalikan penelitian:
#   1 slot (tanpa batching paralel), KV cache f16, maks 1 model termuat, model disimpan di tahap4/models/ollama.
# Flash attention dibiarkan pada default Ollama; status aktualnya dicatat dari log llama-server.
#
# Pemakaian (dari tahap4/):  bash model_prep/research_ollama.sh          # normal
#                            DEBUG=1 bash model_prep/research_ollama.sh  # log debug (prompt ter-render)
set -euo pipefail
T4="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$T4/runs/ollama_logs"
mkdir -p "$LOGDIR" "$T4/models/ollama"
export OLLAMA_HOST=127.0.0.1:11435
export OLLAMA_MODELS="$(cygpath -w "$T4/models/ollama")"
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_KEEP_ALIVE=30m
export OLLAMA_KV_CACHE_TYPE="${KV:-f16}"   # f16 = keputusan peneliti; KV=q8_0 hanya untuk pengukuran opsi
export OLLAMA_CONTEXT_LENGTH=4096
unset OLLAMA_FLASH_ATTENTION OLLAMA_DEBUG
SUFFIX=""
if [ "${DEBUG:-0}" = "1" ]; then export OLLAMA_DEBUG=1; SUFFIX="_debug"; fi
LOG="$LOGDIR/serve_$(date +%Y%m%d-%H%M%S)_kv${OLLAMA_KV_CACHE_TYPE}${SUFFIX}.log"
echo "log: $LOG"
env | grep '^OLLAMA_' | sort > "$LOG.env"
OLLAMA_BIN="$(sed -n 's/^OLLAMA_BIN=//p' "$T4/lokal_pribadi.env" 2>/dev/null | tail -1)"
[ -n "$OLLAMA_BIN" ] || { echo "OLLAMA_BIN belum diisi di $T4/lokal_pribadi.env (lihat lokal_pribadi.example.env)" >&2; exit 1; }
exec "$OLLAMA_BIN" serve >> "$LOG" 2>&1
