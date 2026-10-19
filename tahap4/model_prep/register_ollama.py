"""Daftarkan GGUF lokal ke Ollama lewat REST API (tanpa CLI; CLI di PATH berbeda versi dengan server).

Kedua model memakai TEMPLATE dan parameter yang sama persis: salinan blob resmi Ollama library ``gemma2``
(template sha256:109037be..., params sha256:2490e746... = hanya stop token). Tanpa SYSTEM, tanpa parameter
sampling (temperature/top_p memakai default runtime Ollama).

Pemakaian:
    python -I register_ollama.py <nama_model> <berkas_gguf> <folder_ref_template> [<base_url>]
    (base_url default: instans riset http://127.0.0.1:11435)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import httpx

BASE = sys.argv[4] if len(sys.argv) > 4 else "http://127.0.0.1:11435"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    name, gguf, ref = sys.argv[1], Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
    template = (ref / "template.txt").read_text(encoding="utf-8")
    params = json.loads((ref / "params.json").read_text(encoding="utf-8"))
    digest = sha256_file(gguf)
    print(f"{gguf.name} sha256={digest}", flush=True)
    with httpx.Client(base_url=BASE, timeout=None) as c:
        if c.head(f"/api/blobs/sha256:{digest}").status_code != 200:
            print("unggah blob ke Ollama...", flush=True)
            with open(gguf, "rb") as f:
                r = c.post(f"/api/blobs/sha256:{digest}", content=f)
            r.raise_for_status()
        body = {"model": name, "files": {gguf.name: f"sha256:{digest}"}, "template": template,
                "parameters": params, "stream": False}
        r = c.post("/api/create", json=body)
        print("create:", r.status_code, r.text[:300], flush=True)
        r.raise_for_status()
        show = c.post("/api/show", json={"model": name}).json()
        tags = c.get("/api/tags").json()["models"]
        tag = next(t for t in tags if t["name"] in (name, f"{name}:latest"))
        print(json.dumps({"name": name, "ollama_digest": tag["digest"], "size": tag["size"],
                          "details": show.get("details"), "parameters": show.get("parameters"),
                          "template_sha256": hashlib.sha256(show.get("template", "").encode()).hexdigest(),
                          "modelfile_has_SYSTEM": any(l.startswith("SYSTEM") for l in show.get("modelfile", "").splitlines()),
                          "gguf_sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
