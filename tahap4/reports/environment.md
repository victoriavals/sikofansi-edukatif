# Lingkungan komputasi (Tahap 4)

> **Versi repo:** nama layanan Windows, path lokal, dan akun pribadi peneliti dipindahkan ke `tahap4/lokal_pribadi.env` (catatan lokal, tidak di-commit). Isi hasil tidak diubah.

Dicatat oleh simax, 2026-10-18. Semua nilai diambil langsung dari perintah/log yang disebut; tidak ada yang diperkirakan.

## Perangkat keras dan sistem

| Komponen | Nilai | Sumber |
|---|---|---|
| GPU | NVIDIA GeForce RTX 4060 Ti, **8 GB** (8188 MiB), compute 8.9, VBIOS 95.06.2b.00.94, batas daya 160 W | `nvidia-smi` |
| Driver NVIDIA | 610.88 (KMD; paket Windows 32.0.16.1088) | `nvidia-smi`, WMI |
| CUDA | UMD 13.3 (driver); Ollama memakai pustaka bawaan `lib/ollama/cuda_v13` | `nvidia-smi`, log Ollama |
| CPU | Intel Core i5-13400F, 10 inti / 16 thread | WMI |
| RAM | 31,8 GB | WMI |
| OS | Windows 11 Pro 10.0.26200 | WMI |
| VRAM dasar tanpa model | ±714 MiB (desktop + proses lain milik pengguna) | `nvidia-smi` setelah layanan Ollama dijeda |

## Python

- Python **3.11.9** (`C:\Program Files\Python311\python.exe`).
- `tahap4/.venv` — pipeline (runner, adapter, penilai). `pip freeze` lengkap di bawah dan di `reports/pip_freeze.txt`.
- `tahap4/.venv-convert` — khusus konversi llama.cpp (torch 2.11.0+cpu, transformers 4.57.6, numpy 2.2.6, sentencepiece 0.2.2,
  gguf 0.19.0, protobuf 4.25.9; sesuai `requirements-convert_hf_to_gguf.txt` b11714). Lengkap di `reports/pip_freeze_convert.txt`.

## Ollama

| Hal | Nilai |
|---|---|
| Biner server | `OLLAMA_BIN` (path di `tahap4/lokal_pribadi.env`), **0.40.5** (runner llama.cpp / `llama-server`) |
| Instans yang dipakai penelitian | **instans riset khusus** `127.0.0.1:11435` (`model_prep/research_ollama.sh`), terpisah dari server Ollama produksi milik peneliti |
| Setelan instans riset | `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_KV_CACHE_TYPE=f16`, `OLLAMA_CONTEXT_LENGTH=4096`, `OLLAMA_KEEP_ALIVE=30m`, `OLLAMA_MODELS=tahap4\models\ollama`; flash attention tidak diset (default `auto` → **aktif** menurut log) |
| Opsi per panggilan | `num_ctx=4096`, `num_predict=1024`, `seed=int(sha256(id)) mod 2^31`, `num_gpu=36` (keputusan peneliti: KV f16, offload parsial dikunci) |
| Penempatan layer | **36/43 layer di GPU** (35 blok + output), 7 blok di CPU; KV f16 1.344 MiB (sebagian di CPU) | 
| Sampling efektif | Tidak di-override. `ollama show --parameters` hanya berisi `stop "<start_of_turn>"`, `stop "<end_of_turn>"`; nilai efektif dari log `llama-server`: **temp 0,8; top_k 40; top_p 0,9; min_p 0; typical_p 1; repeat_penalty 1,0; repeat_last_n 64; presence/frequency penalty 0** |
| CLI di PATH | `ollama.exe` di profil pengguna Windows lain (path di `tahap4/lokal_pribadi.env`) 0.34.0 (berbeda versi dengan server; **tidak dipakai** — pendaftaran model lewat REST API) |
| Layanan peneliti (tidak dipakai untuk data) | server Ollama produksi 127.0.0.1:11434 (KV q8_0, flash attention 1, 4 slot, keep_alive -1) beserta gateway dan tunnel-nya (nama di `tahap4/lokal_pribadi.env`); dijeda selama run lokal dengan izin peneliti, log di `runs/ollama_logs/services.log` |

## Model lokal

Kedua model dikuantisasi sendiri dengan alat dan perintah identik:
llama.cpp **b11714** (commit `c0fd78626405c6d9b934efef0ec7291fcc20e3d6`; biner `llama-b11714-bin-win-cpu-x64.zip`
SHA256 `f78eded047061a3f86372db426797400a2f1bb0ec37868d5927dd820eb3386c0`, cocok dengan digest rilis GitHub),
`convert_hf_to_gguf.py --outtype bf16` lalu `llama-quantize ... Q4_K_M` (**statis, tanpa imatrix**). Skrip: `model_prep/quantize.sh`.

| Slot | Sumber bobot (commit) | GGUF Q4_K_M SHA256 | Ukuran | Digest Ollama |
|---|---|---|---|---|
| `gemma2_9b_it` | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` — safetensors, index, tokenizer.json, tokenizer.model, special_tokens_map.json **identik (hash LFS/blob) dengan `google/gemma-2-9b-it` @ `11c9b309abf73637e4b6f9a3fa1e92e615547819`** | `cde4c7a7b7d6ae78e3dbb0381a079ef10bf377698c91071f61ff386a677f590a` | 5.761.057.696 B | `c8c9d8327c89c67aee9b900e481643ef427d27c14993d49a80a3519f1b178429` |
| `sahabatai_9b_it` | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` (bobot identik dengan `Sahabat-AI/...` @ `ecd7c80b`) | `3da313008840e75e45bf5aca53c0752e9c2072c2b8536774d1ce50d26e7e3131` | 5.761.057.632 B | `d2fdb678df13285a657f84d117fa45babb73155307fdc22bbc86d395603cf3a4` |

Berkas antara BF16: `gemma2_9b_it-BF16.gguf` SHA256 `35f14ef13732cf1c50cbd363b816c51377bf455ff6bda73baecf87d4886ca24b`,
`sahabatai_9b_it-BF16.gguf` SHA256 `c875d834cb0a5116860225e5c27dac83d43e0d5f7a4346716f2a34c64296e8a7`.
Ukuran kuantisasi keduanya 5.488,40 MiB (4,98 BPW). Metadata GGUF memuat `attn_logit_softcapping=50`,
`final_logit_softcapping=30`, `sliding_window=4096`.

SHA256 safetensors yang diunduh (semua cocok dengan hash LFS di Hugging Face; daftar lengkap di `models/hf/download_manifest.json`):

| Berkas | gemma2_9b_it | sahabatai_9b_it |
|---|---|---|
| model-00001-of-00004 | `a0d4eb4fcbddfe01b0dc7a58386a3980826ededaf0ecd67d1ef38995b89615ba` | `f049e12b64490cd381d6266c22fd518947aec2d0b07288968c7e2448d86639af` |
| model-00002-of-00004 | `712a589c333f49f7b6f3870838a9e0ab4b3c0260abd5130e8c54316e6c99640b` | `bb64a550c196dd94523d7bdb821e920a76f1821e3668fa351e5d782034e6022f` |
| model-00003-of-00004 | `5a9f84eb9846840802200c6502ccaaebf0a146ee89dcb8822fab795c392dd667` | `7cd7b4b84de41f02d4cdfad19c4e6dfb0c0b3c3a30d4838d362f32c5e8bcae35` |
| model-00004-of-00004 | `3349b4960bbc0bf7e47a624e5c520881adb06e2da4bda6ed14b51c7f647fe26c` | `1fb28a1ee59339014752cf330932a474d794d2201ec0a14b19b5046b8c3c997a` |
| tokenizer.model | `61a7b147390c64585d6c3543dd6fc636906c9af3865a5548f27f31aee1d4c8e2` | `61a7b147390c64585d6c3543dd6fc636906c9af3865a5548f27f31aee1d4c8e2` |

**Chat template (identik untuk kedua model):** salinan blob resmi Ollama library `gemma2`
(template `sha256:109037bec39c0becc8221222ae23557559bc594290945a2c4221ab4f303b8871`,
params `sha256:2490e7468436707d5156d7959cf3c6341cc46ee323084cfa3fcf30fe76e397dc` = hanya stop token), tanpa SYSTEM.
Diverifikasi: jumlah token prompt yang diproses Ollama sama persis dengan render chat template resmi HF
(`apply_chat_template`, termasuk `<bos>`) — 47 token untuk satu giliran dan 88 token untuk percakapan dua giliran.

**Kecepatan (uji asap, KV f16, num_gpu 36):** generasi ±28 token/detik, VRAM terpakai ±6,7 GB saat model termuat
(`reports/smoke/`).

## pip freeze — `.venv` (pipeline)

```text
annotated-types==0.8.0
anthropic==1.15.0
anyio==4.15.1
attrs==26.1.0
certifi==2026.7.22
cffi==2.1.1
charset-normalizer==3.5.2
click==8.5.0
colorama==0.4.6
cryptography==50.0.2
distro==1.9.0
docstring_parser==0.18.0
filelock==4.2.1
fsspec==2026.9.0
google-auth==2.62.0
google-genai==2.31.0
h11==0.16.0
hf-xet==1.7.0
httpcore==1.0.9
httpcore2==2.13.1
httpx==0.28.1
httpx2==2.13.1
huggingface_hub==2.2.0
idna==3.20
iniconfig==2.3.1
jiter==0.17.0
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
openai==3.35.1
opentelemetry-api==1.45.1
packaging==26.3
pluggy==1.7.0
pyasn1==0.6.4
pyasn1_modules==0.4.2
pycparser==3.11
pydantic==2.14.1
pydantic_core==2.50.1
Pygments==2.21.0
pytest==9.1.1
python-dotenv==1.2.4
PyYAML==6.0.3
referencing==0.37.0
requests==2.34.2
rpds-py==2026.9.1
sniffio==1.3.1
tenacity==9.1.4
tqdm==4.70.1
truststore==0.10.5
typing-inspection==0.4.4
typing_extensions==4.16.0
urllib3==2.8.0
websockets==16.1.1
```

## pip freeze — `.venv-convert` (konversi llama.cpp)

```text
certifi==2026.7.22
charset-normalizer==3.5.2
colorama==0.4.6
filelock==4.2.2
fsspec==2026.9.0
gguf==0.19.0
huggingface_hub==0.36.2
idna==3.20
Jinja2==3.1.6
MarkupSafe==3.0.4
mpmath==1.3.0
networkx==3.6.1
numpy==2.2.6
packaging==26.3
protobuf==4.25.9
PyYAML==6.0.3
regex==2026.9.29
requests==2.34.2
safetensors==0.8.0
sentencepiece==0.2.2
sympy==1.14.0
tokenizers==0.22.2
torch==2.11.0+cpu
tqdm==4.70.1
transformers==4.57.6
typing_extensions==4.16.0
urllib3==2.8.0
```

## Bobot HF asli (dihapus 2026-10-18 atas keputusan peneliti; GGUF disimpan)

Repo resmi pembanding: `google/gemma-2-9b-it` @ `11c9b309abf73637e4b6f9a3fa1e92e615547819`. Manifest lengkap: `reports/hf_download_manifest.json` (disalin sebelum penghapusan `models/hf/`).

| Slot | Repo @ commit | Berkas | SHA256 | Ukuran (B) | Cocok hash LFS |
|---|---|---|---|---|---|
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | config.json | `6cb3b3cc40bb6d21321fd9ad80500fca7a2e5242e1236e13c34905dc8c119bcb` | 954 | – |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | generation_config.json | `579a77ece54c9fbeb2d13505532c9ad6afcfe5ab24b0ff795d7e357b364c70cc` | 190 | – |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | model-00001-of-00004.safetensors | `f049e12b64490cd381d6266c22fd518947aec2d0b07288968c7e2448d86639af` | 4903351912 | ya |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | model-00002-of-00004.safetensors | `bb64a550c196dd94523d7bdb821e920a76f1821e3668fa351e5d782034e6022f` | 4947570872 | ya |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | model-00003-of-00004.safetensors | `7cd7b4b84de41f02d4cdfad19c4e6dfb0c0b3c3a30d4838d362f32c5e8bcae35` | 4962221464 | ya |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | model-00004-of-00004.safetensors | `1fb28a1ee59339014752cf330932a474d794d2201ec0a14b19b5046b8c3c997a` | 3670322200 | ya |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | model.safetensors.index.json | `c38b39b80b2d7aa422464a9b816af4c30d2177e471b89e5325df1336a23ad284` | 39072 | – |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | special_tokens_map.json | `baec30ea10906f16adb8c18af7a34023002c1746542612b8b41c9f09e1351351` | 636 | – |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | tokenizer.json | `5f7eee611703c5ce5d1eee32d9cdcfe465647b8aff0c1dfb3bed7ad7dbb05060` | 34362873 | ya |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | tokenizer.model | `61a7b147390c64585d6c3543dd6fc636906c9af3865a5548f27f31aee1d4c8e2` | 4241003 | ya |
| sahabatai_9b_it | `GoToCompany/gemma2-9b-cpt-sahabatai-v1-instruct` @ `ca19cec82a7d2bdba20020e1bebf296417cfc3ee` | tokenizer_config.json | `7f9252d2b25b9f6ea71cf1d813597e01aa272237c4848d2cb100e70a17c81b30` | 47019 | – |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | config.json | `7b881c1a317cc0ff34d36efdbd3668c10a2e7e6d5acae600a07f62bdd74d2cf8` | 927 | – |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | generation_config.json | `4ebdb5448f194666939265b988d4e8f6437d970dcb271e6f3133ccb70df22798` | 190 | – |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | model-00001-of-00004.safetensors | `a0d4eb4fcbddfe01b0dc7a58386a3980826ededaf0ecd67d1ef38995b89615ba` | 4903351912 | ya |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | model-00002-of-00004.safetensors | `712a589c333f49f7b6f3870838a9e0ab4b3c0260abd5130e8c54316e6c99640b` | 4947570872 | ya |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | model-00003-of-00004.safetensors | `5a9f84eb9846840802200c6502ccaaebf0a146ee89dcb8822fab795c392dd667` | 4962221464 | ya |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | model-00004-of-00004.safetensors | `3349b4960bbc0bf7e47a624e5c520881adb06e2da4bda6ed14b51c7f647fe26c` | 3670322200 | ya |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | model.safetensors.index.json | `c38b39b80b2d7aa422464a9b816af4c30d2177e471b89e5325df1336a23ad284` | 39072 | – |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | special_tokens_map.json | `baec30ea10906f16adb8c18af7a34023002c1746542612b8b41c9f09e1351351` | 636 | – |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | tokenizer.json | `3f289bc05132635a8bc7aca7aa21255efd5e18f3710f43e3cdb96bcd41be4922` | 17525357 | ya |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | tokenizer.model | `61a7b147390c64585d6c3543dd6fc636906c9af3865a5548f27f31aee1d4c8e2` | 4241003 | ya |
| gemma2_9b_it | `unsloth/gemma-2-9b-it` @ `fc7d4737cda11c3a19af2b722319e846670b4d89` | tokenizer_config.json | `e5ac0f1cfb5f450763d368edacbb2448a3c02c8d8f7f98d963a820751fb0ddc3` | 47022 | – |

## Tahap 5 (data utama, 2026-10-19 s.d. 2026-10-21): pemeriksaan ulang lingkungan

Diperiksa 2026-10-21 setelah semua run Tahap 5; tidak ada perubahan dibanding Tahap 4:

| Komponen | Tahap 5 | Sumber |
|---|---|---|
| Driver NVIDIA / CUDA UMD | 610.88 / 13.3 (sama) | `nvidia-smi` |
| Python | 3.11.9 (sama) | `.venv` |
| `pip freeze` `.venv` | identik dengan `reports/pip_freeze.txt` | `pip freeze` dibandingkan dengan `diff` |
| Server Ollama instans riset | 0.40.5 (sama); dicek pengatur sebelum run dan di setiap rekaman | `/api/version`, `model_info` di log |
| Digest `gemma2_9b_it` | `c8c9d8327c89c67aee9b900e481643ef427d27c14993d49a80a3519f1b178429` (sama dengan pilot; 1.080 dialog + 180 G0) | `/api/tags`, `model_info` di log |
| Digest `sahabatai_9b_it` | `d2fdb678df13285a657f84d117fa45babb73155307fdc22bbc86d395603cf3a4` (sama dengan pilot; 1.080 dialog + 180 G0) | `/api/tags`, `model_info` di log |
| Kuantisasi / offload | Q4_K_M; 36/43 lapisan di GPU, KV cache f16 | log `serve_20261020-085413_kvf16.log` |
