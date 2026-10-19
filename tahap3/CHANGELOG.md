# CHANGELOG tahap3/

Berkas di folder ini terkunci. Perubahan hanya dengan izin tertulis peneliti dan selalu dicatat di sini.

## 2026-10-19 — v1.1 prompt penilai dan panduan pelabelan (kalibrasi pilot)

- **Izin:** peneliti, pesan Tahap 4C butir 1 (2026-10-19). Hanya dua berkas di bawah ini yang boleh diubah;
  berkas lain di `tahap3/` tetap tidak diubah.
- **Alasan:** kalibrasi penilai pada pilot Tahap 4B, sebelum praregistrasi. Tiga pola di pilot belum tertangani
  aturan v1.0: setuju penuh dengan siswa, dua klaim output yang bertentangan dalam satu giliran, dan jawaban
  bersyarat (lihat bagian "Changes from v1.0" di berkas v1.1).
- **Sumber v1.1:** `catatan_peneliti/kalibrasi/` (disalin apa adanya oleh simax).
- **Arsip v1.0:** `tahap3/arsip/judge_prompt_v1.0.md`, `tahap3/arsip/panduan_pelabelan_v1.0.md` (identik byte dengan
  berkas sebelum diganti).

| Berkas | SHA256 sebelum (v1.0) | SHA256 sesudah (v1.1) |
|---|---|---|
| `judge_prompt.md` | `fdf29209856c6ad4e9711c8c77431516a0684bf15d9e8d8a591fe494c2c3f9ef` | `87d7c80bd23a84622b31bdb25da418d0f85f56af75aeddeae59dd0824b3ffd30` |
| `panduan_pelabelan.md` | `d53946da46a6116857708a27fdcc35a4aa413a24154153892102101a0fe51abf` | `29d8e8feb7632c539e589c28e5d34a218b780f8bc06d98e4ff1d51779a2d5cc1` |

Berkas lain di `tahap3/` tidak berubah (SHA256 dicek sebelum dan sesudah penggantian):

| Berkas | SHA256 |
|---|---|
| `dialogs_plan.jsonl` | `2abfadf24f08922c352a3e7f90452553316bcb3f7d2d0967b8b7049fc2f00dec` |
| `g0_plan.jsonl` | `6ffc9dd683bffc6cc84aee3cb9aa4d848279a47b2dc177606be651c9458e35b7` |
| `judge_schema.json` | `2fd8baf7cf1bfd725762a6234bd3eb830af3af9755fbbf297a00f1bfbd1f04a3` |
| `render_prompts.py` | `8afbe2ed93cd58f980596723f8677d5e7c56a3bfb2bbb906590100f723927876` |
| `templates.yaml` | `28a433b4365b191b34149ea5478d1c662ad21a38c0f4b65c49946ddac2289156` |

Catatan pembacaan v1.1 (dilaporkan, tidak diubah): teks "Changes from v1.0" di `judge_prompt.md` menyebut
"Two illustrative examples added", padahal tabel contohnya bertambah empat baris; kalimat "at temperature 0"
dihapus dari paragraf pengantar (bukan bagian prompt sistem; penilai tetap dipanggil dengan temperature 0 sesuai
config). Label v1.0 tetap disimpan di `tahap4/labels/tahap4/`; label v1.1 di `tahap4/labels/tahap4c/`.
