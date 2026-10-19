# Sikofansi Edukatif

Kode, materi, dan laporan penelitian tentang **sikofansi edukatif**: seberapa sering model bahasa melepas jawaban
benar ketika siswa bersikeras pada miskonsepsi pemrograman Python.

- **Materi:** 30 butir miskonsepsi Python, masing-masing dengan kunci jawaban hasil eksekusi kode.
- **Dialog:** tiga giliran (G1 pertanyaan, G2 tekanan, G3 eskalasi) dalam bahasa Indonesia dan Inggris.
- **Faktor:** pembingkaian (netral/yakin) × tekanan (sederhana, otoritas, sosial-afektif) × bahasa × model × 3 ulangan = 4.320 dialog, ditambah 720 pertanyaan G0 (cek pengetahuan dasar).
- **Model yang diuji:**
  - dua model API lewat SumoPod: `gpt-6-luna` dan `deepseek-v4-flash-0731:netra`;
  - dua model lokal Q4_K_M lewat Ollama: Gemma 2 9B IT dan SahabatAI 9B.
- **Pelabelan:** LLM penilai `glm-5.3-flash` (keluarga berbeda dari semua model yang diuji), lalu divalidasi manusia.

**Status:** pipeline dan uji coba selesai (Tahap 4–4C). **Protokol dibekukan untuk praregistrasi** (tag Git
`protokol-praregistrasi`; prompt penilai v1.1 beku, SHA256 di `tahap3/CHANGELOG.md`). Data utama (Tahap 5) belum
diambil; praregistrasi OSF menyusul.
Log mentah dialog dan label penilai **tidak** ada di repo ini; keduanya akan dirilis lewat OSF.

## Struktur

```text
tahap2/   bank butir dan kunci jawaban (build_bank.py, items.json, items.csv)            terkunci
tahap3/   template dialog, rencana dialog/G0, prompt penilai v1.1, panduan pelabelan     terkunci
          (perubahan yang diizinkan peneliti dicatat di tahap3/CHANGELOG.md; v1.0 di tahap3/arsip/)
tahap4/   pipeline (src/), uji (tests/), persiapan model lokal (model_prep/), laporan (reports/)
catatan_peneliti/   bahan kerja peneliti (bank butir, cek template, kalibrasi penilai)
CLAUDE.md           aturan kerja agen komputasi (simax) yang menjalankan pipeline
```

## Menjalankan ulang

Python 3.11.9, dari folder `tahap4/`:

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows; di Linux/macOS: .venv/bin/pip
cp config.example.yaml config.yaml          # slot model, harga, anggaran
cp .env.example .env                        # kunci API (satu kunci SumoPod per slot)
cp lokal_pribadi.example.env lokal_pribadi.env   # path biner Ollama dan layanan lokal yang perlu dijeda (opsional)
python -m pytest -q tests
```

| Tugas | Perintah |
|---|---|
| G0 (cek pengetahuan) | `python -m src.run_g0 --models gemma2_9b_it sahabatai_9b_it` |
| Dialog | `python -m src.run_dialogs --models <slot..> [--items ..] [--reps ..]` |
| Penilai LLM | `python -m src.run_judge --models <slot..> [--stability]` |
| Nilai G0 otomatis | `python -m src.grade_g0 --models <slot..> --known` |
| Ringkasan | `python -m src.summarize --models <slot..>` |
| Bandingkan dua set label | `python -m src.compare_labels --base tahap4 --new tahap4c` |
| Sampel validasi manusia (Tahap 6, setelah Tahap 5) | `python -m src.sample_validation --phase tahap5` |
| Uji kunci API (1 panggilan per slot, < 0,01 USD) | `python model_prep/cek_kunci_api.py` |
| Estimasi biaya | tambahkan `--estimate-only` (penilai: `--estimate-only --from-plan`) |

Ukuran utama: **sikofansi regresif** pada transisi antargiliran berurutan yang berawal dari Benar. Versi UTAMA:
Benar → Ambigu atau Miskonsepsi. Versi SENSITIVITAS: Benar → Miskonsepsi saja. Metrik sekunder: penarikan koreksi
(Benar → Tidak disebut). Jenis galat penilai yang diketahui: `tahap4/reports/katalog_galat_penilai.md`.

Data utama ditolak tanpa `--phase tahap5 --allow-main`. Persiapan model lokal (unduh bobot, kuantisasi llama.cpp
b11714 ke Q4_K_M, pendaftaran ke Ollama, jendela run) ada di `tahap4/model_prep/`. Versi, commit sumber bobot, dan
SHA256 setiap berkas model tercatat di `tahap4/reports/environment.md`.

## Integritas

- `tahap2/` dan `tahap3/` terkunci. Satu-satunya perubahan (prompt penilai dan panduan pelabelan v1.1) dicatat
  dengan SHA256 sebelum/sesudah di `tahap3/CHANGELOG.md`.
- `.gitattributes` menyimpan berkas data dan berkas terkunci byte-per-byte, sehingga SHA256 yang tercatat tetap
  cocok setelah clone di platform mana pun.
- Laporan per tahap: `tahap4/reports/REPORT_TAHAP4.md`, `REPORT_TAHAP4B.md`, `REPORT_TAHAP4C.md`.

## Lisensi

Repo ini memakai **lisensi ganda**:

| Bagian | Lisensi | Berkas |
|---|---|---|
| **Kode** | MIT ([`LICENSE`](LICENSE)) | `tahap4/src/`, `tahap4/tests/`, dan semua skrip `*.py`, `*.sh`, `*.ps1` di folder mana pun (termasuk `tahap2/build_bank.py`, `tahap3/render_prompts.py`, `tahap4/model_prep/`), serta berkas konfigurasi/templat pendukungnya di `tahap4/` |
| **Data dan dokumen** | CC BY 4.0 ([`LICENSE-DATA`](LICENSE-DATA)) | isi `tahap2/`, `tahap3/`, dan `catatan_peneliti/` selain skrip (bank butir, kunci jawaban, template, rencana dialog, prompt penilai, panduan pelabelan, bahan kalibrasi), laporan di `tahap4/reports/`, `CLAUDE.md`, dan README ini |

Atribusi untuk data dan dokumen (CC BY 4.0): "Sikofansi Edukatif — materi dan laporan penelitian (2026),
https://github.com/victoriavals/sikofansi-edukatif", dengan menyebutkan perubahan bila ada.

Catatan pihak ketiga: butir miskonsepsi diadaptasi dari literatur yang dikutip di `tahap2/build_bank.py`; template
chat dan parameter di `tahap4/model_prep/ollama_gemma2_ref/` disalin dari pustaka model Ollama (`gemma2`); bobot
model tunduk pada lisensi masing-masing (Gemma Terms of Use) dan tidak disertakan.
