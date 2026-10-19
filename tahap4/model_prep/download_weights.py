"""Unduh bobot asli (safetensors bf16) kedua model lokal dan verifikasi SHA256-nya.

Sumber:
- sahabatai_9b_it: GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct (tidak bergerbang)
- gemma2_9b_it   : unsloth/gemma-2-9b-it, mirror tanpa gerbang yang safetensors, tokenizer.json,
                   tokenizer.model, dan special_tokens_map.json-nya identik (hash LFS/blob) dengan
                   google/gemma-2-9b-it. Identitas ini diperiksa ulang di sini sebelum dan sesudah unduh.

Pemakaian:
    python -I download_weights.py <folder_tujuan> [<berkas_manifest_json>]
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

MODELS = {
    "sahabatai_9b_it": "GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct",
    "gemma2_9b_it": "unsloth/gemma-2-9b-it",
}
OFFICIAL_GEMMA = "google/gemma-2-9b-it"
PATTERNS = ["*.safetensors", "model.safetensors.index.json", "config.json", "generation_config.json",
            "tokenizer.json", "tokenizer.model", "tokenizer_config.json", "special_tokens_map.json"]
MUST_MATCH_OFFICIAL = ["model-00001-of-00004.safetensors", "model-00002-of-00004.safetensors",
                       "model-00003-of-00004.safetensors", "model-00004-of-00004.safetensors",
                       "model.safetensors.index.json", "tokenizer.json", "tokenizer.model",
                       "special_tokens_map.json"]


def remote_hashes(api: HfApi, repo: str) -> tuple[str, dict[str, dict]]:
    """Kembalikan (commit sha, {file: {sha256|blob_id, size}}) dari metadata Hub."""
    info = api.model_info(repo, files_metadata=True)
    out = {}
    for s in info.siblings:
        out[s.rfilename] = {"lfs_sha256": s.lfs.sha256 if s.lfs else None, "blob_id": s.blob_id, "size": s.size}
    return info.sha, out


def sha256_file(path: Path) -> str:
    """SHA256 berkas lokal, dibaca per blok 16 MB."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    dest = Path(sys.argv[1]).resolve()
    manifest_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else dest / "download_manifest.json"
    api = HfApi()
    off_sha, off = remote_hashes(api, OFFICIAL_GEMMA)
    manifest: dict = {"created_utc": datetime.now(timezone.utc).isoformat(), "official_gemma_commit": off_sha, "models": {}}
    for slot, repo in MODELS.items():
        commit, remote = remote_hashes(api, repo)
        if slot == "gemma2_9b_it":
            for f in MUST_MATCH_OFFICIAL:
                a, b = remote[f], off[f]
                same = (a["lfs_sha256"] or a["blob_id"]) == (b["lfs_sha256"] or b["blob_id"])
                if not same:
                    raise SystemExit(f"Mirror {repo} tidak identik dengan {OFFICIAL_GEMMA} pada {f}; berhenti.")
            print(f"[{slot}] mirror identik dengan {OFFICIAL_GEMMA} untuk {len(MUST_MATCH_OFFICIAL)} berkas inti", flush=True)
        local = dest / slot
        local.mkdir(parents=True, exist_ok=True)
        print(f"[{slot}] unduh {repo}@{commit} -> {local}", flush=True)
        snapshot_download(repo, revision=commit, local_dir=local, allow_patterns=PATTERNS)
        files = {}
        for p in sorted(local.glob("*")):
            if not p.is_file():
                continue
            r = remote.get(p.name)
            digest = sha256_file(p)
            ok = None
            if r and r["lfs_sha256"]:
                ok = digest == r["lfs_sha256"]
                if not ok:
                    raise SystemExit(f"SHA256 tidak cocok: {p}")
            files[p.name] = {"sha256": digest, "size": p.stat().st_size, "lfs_verified": ok}
            print(f"   {p.name}: {digest[:16]}... lfs_ok={ok}", flush=True)
        manifest["models"][slot] = {"repo": repo, "commit": commit, "files": files}
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("SELESAI", flush=True)


if __name__ == "__main__":
    main()
