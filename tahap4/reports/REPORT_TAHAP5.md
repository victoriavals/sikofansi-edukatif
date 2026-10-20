# Laporan Tahap 5 — Pengumpulan data utama (SEMENTARA: Bagian A selesai)

Disusun oleh simax, 2026-10-20, untuk peneliti dan reviewer. Protokol acuan: praregistrasi OSF
https://osf.io/43gwh, tag Git `protokol-praregistrasi` (commit `1a27439`).

**Status laporan: sementara.**

- **Bagian A (model API) dan penilaiannya:** selesai.
- **Bagian B (model lokal):** belum dijalankan. Jendela run lokal di instruksi masih berupa placeholder ("[isi tanggal dan jam … atau "menyusul"]"). Sesuai instruksi "Jangan menjeda layanan di luar jendela yang disebut di sini", layanan Ollama produksi peneliti tidak dijeda dan tidak ada run lokal.
- **Bergantung pada Bagian B:** penilaian model lokal (C), `g0_known.csv` keempat model (D), sampling validasi manusia (E), dan paket rilis OSF. Semuanya menunggu.

Bagian 3–8 di bawah memuat angka dari log apa adanya.

## Ringkasan

| Bagian | Isi | Status |
|---|---|---|
| Pemeriksaan awal | 1 OSF, 2 protokol tidak berubah, 3 uji kunci, 4 README | Keempatnya lolos (bagian 1) |
| A | G0 dan 1.080 dialog per model API | **Selesai.** 2.160/2.160 dialog dan 360/360 G0 sukses; 0 gagal; 0 giliran terpotong |
| B | G0 dan dialog model lokal di jendela peneliti | **Menunggu jendela** (belum ditentukan) |
| C | Penilai untuk tiap model setelah model itu selesai | Model API **selesai**: 2.160/2.160 dialog valid, 0 dinilai ulang, 0 dikeluarkan; uji stabilitas 2 × 108 dialog. Model lokal menunggu B |
| D | Nilai G0 dan `labels/tahap5/g0_known.csv` | Nilai G0 model API selesai (360/360 benar). `g0_known.csv` dibuat setelah G0 lokal |
| E | Lembar validasi manusia dan berkas kunci | Menunggu semua dialog dinilai |
| Kondisi berhenti | Biaya, gagal, perubahan model/hulu, terpotong, penilai tidak valid | **Tidak ada yang terpicu** (bagian 4 dan 8) |

## 1. Pemeriksaan awal

| No. | Pemeriksaan | Hasil |
|---|---|---|
| 1 | Praregistrasi OSF | Lolos. https://osf.io/43gwh: publik, terdaftar 2026-10-19 08:31:08 UTC, tidak ditarik, tidak tertunda. Merujuk commit `1a27439`, tag `protokol-praregistrasi`, dan kedua SHA256 beku. Judul sesuai naskah (dikonfirmasi peneliti). Metadata disimpan di `tahap4/reports/osf_registration.json` |
| 2 | Protokol tidak berubah sejak tag | Lolos. `git diff protokol-praregistrasi -- tahap2 tahap3` kosong saat pemeriksaan dan diulang setelah Bagian A (2026-10-20): tetap kosong. SHA256 `judge_prompt.md` = `87d7c80b…3ffd30`, `panduan_pelabelan.md` = `29d8e8fe…2d5cc1` (sama dengan hash beku) |
| 3 | Uji kunci API | Lolos. `model_prep/cek_kunci_api.py`, 2026-10-19 15:43 WIB: ketiga slot `ok`. Field `model`: `gpt-6-luna`, `deepseek-v4-flash-0731:netra`, `glm-5.3-flash`. Biaya $0,000083 |
| 4 | README berisi tautan OSF; `osf_registration.json` di-commit | Lolos. Commit `642289a` (sudah di-push) |

**Perubahan instruksi kerja (bukan penyimpangan protokol).** Pemeriksaan 3 semula berbunyi "kunci API harus sudah diganti". Peneliti menggantinya menjadi "jalankan `model_prep/cek_kunci_api.py` dan pastikan ketiga slot lolos". Alasannya, anggapan kunci bocor berasal dari salah tafsir laporan: pemindaian riwayat Git menunjukkan tidak ada kunci yang pernah ter-commit. Perubahan ini juga dicatat di `DEVIATIONS.md` bagian B.

## 2. Linimasa (WIB, UTC+7)

| Waktu | Kejadian |
|---|---|
| 19 Okt 15:43 | Uji kunci (pemeriksaan 3) |
| 19 Okt 15:47:04 | Pengatur `model_prep/jalankan_tahap5_api.py --slots komersial_A komersial_B --chunk 30` mulai. Commit `283377f`, tanpa perubahan kode/config yang belum di-commit |
| 15:47 – 15:52 | G0 `komersial_A` (180) |
| 15:52 – 15:57 | G0 `komersial_B` (180) |
| 15:57 – 18:24 | Dialog `komersial_A` (1.080, potongan 30 dialog; kondisi berhenti dicek tiap potongan) |
| 18:24 – 20 Okt 01:58 | Dialog `komersial_B` (1.080) |
| 18:24 – 23:09 | Penilai `komersial_A` (utama), berjalan paralel dengan dialog `komersial_B` |
| 23:09 | Penilaian ulang dialog tidak valid `komersial_A`: tidak ada dialog yang perlu dinilai ulang |
| 23:09 – 23:35 | Uji stabilitas `komersial_A` (108 dialog) |
| 20 Okt 01:58 – 04:42 | Penilai `komersial_B` (utama); penilaian ulang: tidak ada |
| 04:42 – 04:57 | Uji stabilitas `komersial_B` (108 dialog) |
| 04:58:08 | Pengatur selesai, tanpa kondisi berhenti |

**Jendela data per model API.** Ketentuannya paling lama dua minggu. Dari G0 pertama sampai dialog terakhir:

- `komersial_A`: 2 jam 37 menit (19 Okt 15:47 – 18:24 WIB).
- `komersial_B`: 10 jam 6 menit (19 Okt 15:52 – 20 Okt 01:58 WIB).

## 3. Kelengkapan

Diperiksa dengan skrip baca-saja terhadap `tahap3/dialogs_plan.jsonl` dan `g0_plan.jsonl`.

| Model | Dialog rencana | Rekaman | `ok` unik | Ganda | Hilang | Di luar rencana | Galat yang diulang | G0 `ok` |
|---|---|---|---|---|---|---|---|---|
| `komersial_A` | 1.080 | 1.080 | 1.080 | 0 | 0 | 0 | 0 | 180/180 |
| `komersial_B` | 1.080 | 1.080 | 1.080 | 0 | 0 | 0 | 1 | 180/180 |

**Hasil pemeriksaan isi** (semua dialog `ok`):

- Pesan siswa identik dengan rencana dialog.
- Riwayat asisten identik dengan respons yang dicatat.
- Tidak ada system prompt.
- Parameter yang dikirim hanya `{"max_tokens": 1024, "stream": false}` di 3.240/3.240 giliran per model. Tidak ada temperature, top_p, atau seed.

**Teks penalaran:**

- `komersial_B`: 3.240/3.240 giliran punya teks penalaran terpisah, tersimpan lengkap di `provider_meta.reasoning_text`.
- Tidak ada satu pun yang masuk riwayat dialog. Dicek dengan mencari 200 karakter awal teks penalaran di setiap pesan asisten.
- Tidak ada tag `<think>` di dalam `content`.
- `komersial_A` tidak mengembalikan teks penalaran, hanya jumlah token penalaran.

**Satu galat yang diulang.** Di `E04-yakin-P1-en-komersial_B-r1`, percobaan pertama satu giliran mengembalikan respons kosong (`finish_reason=stop`, 740 token keluaran, semuanya penalaran). Respons itu tetap ditagih $0,000431, dicatat di `errors` dan `failed_calls_cost_usd`, lalu diulang otomatis. Percobaan kedua sukses.

**Percobaan ulang di proxy.** Header `x-litellm-attempted-retries` = 1 muncul pada 1 dari 3.420 panggilan `komersial_B`. Artinya proxy SumoPod mengulang sendiri satu kali di sisi server. Nilainya 0 pada semua panggilan `komersial_A`.

## 4. Konsistensi model

| Model | Field `model` (semua panggilan) | Hulu (`x-litellm-model-api-base`) | `x-litellm-model-name` | ID respons |
|---|---|---|---|---|
| `komersial_A` | `gpt-6-luna` | `https://api-sg.umodelverse.ai/v1` | `gpt-6-luna` | 3.420 unik / 3.420 |
| `komersial_B` | `deepseek-v4-flash-0731:netra` | `https://api.netraruntime.com/v1` | `deepseek/deepseek/deepseek-v4-flash-0731` | 3.420 unik / 3.420 |

- Field `model`, hulu, dan nama model hulu tidak berubah sepanjang G0 dan dialog.
- `x-litellm-model-id` `komersial_B` tunggal (`707d05ba-…`).
- Di hulu Netra, header CDN menunjukkan beberapa node tepi (BunnyCDN ID1/SG1). Ini node jaringan di depan hulu yang sama, bukan perubahan model.
- Hulu UModelverse/Netra tetap dicatat sebagai keterbatasan, sesuai `CLAUDE.md`.

**Token dan latensi per jenis panggilan** (dari `reports/fragments/tahap5/api.md`):

| Model | Panggilan | n | Latensi rata-rata / median (s) | Token output rata-rata | Token penalaran rata-rata (maks.) | finish |
|---|---|---|---|---|---|---|
| `komersial_A` | G0 | 180 | 1,7 / 1,5 | 30 | 19 (128) | stop = 180 |
| | G1 | 1.080 | 2,5 / 2,3 | 109 | 35 (127) | stop = 1.080 |
| | G2 | 1.080 | 3,0 / 2,8 | 160 | 57 (326) | stop = 1.080 |
| | G3 | 1.080 | 2,5 / 2,3 | 115 | 40 (190) | stop = 1.080 |
| `komersial_B` | G0 | 180 | 1,7 / 1,2 | 121 | 118 (1.016) | stop = 180 |
| | G1 | 1.080 | 4,4 / 3,8 | 486 | 256 (1.226) | stop = 1.080 |
| | G2 | 1.080 | 11,1 / 10,5 | 1.232 | 737 (2.676) | stop = 1.080 |
| | G3 | 1.080 | 9,6 / 9,0 | 998 | 539 (1.599) | stop = 1.080 |

**Giliran terpotong (`finish=length`): 0 dari 3.240 per model.** Token output `komersial_B` di atas 1.024 berasal dari token penalaran Netra yang melampaui `max_tokens`. Ini diterima apa adanya (keputusan peneliti 2026-10-18), dan semua giliran tetap berakhir dengan `stop`.

## 5. G0 (pengetahuan dasar)

- Dinilai dengan aturan beku (`src/grade_g0.py`, keputusan peneliti 2026-10-18).
- Nilai disimpan di `labels/tahap5/g0_grades_komersial_{A,B}_20261019-160236.csv`.

| Model | id benar | en benar | Cek manual | Butir salah ≥ 2/3 |
|---|---|---|---|---|
| `komersial_A` | 90/90 | 90/90 | 0 | tidak ada |
| `komersial_B` | 90/90 | 90/90 | 0 | tidak ada |

Akibatnya, untuk kedua model API, ke-60 pasangan butir × bahasa berstatus "tahu" (≥ 2 dari 3).

`labels/tahap5/g0_known.csv` dibuat sekali setelah G0 model lokal dinilai: keempat model, hanya G0 Tahap 5. Untuk itu `grade_g0 --known` kini menulis ke `labels/<fase>/` untuk fase selain pilot (lihat bagian 9).

## 6. Penilai (`glm-5.3-flash`, prompt v1.1 beku)

| Model | Dialog dinilai | Valid | Tidak valid setelah 3 percobaan | Dinilai ulang | Dikeluarkan | JSON valid percobaan pertama | Percobaan (1/2/3) |
|---|---|---|---|---|---|---|---|
| `komersial_A` | 1.080 | 1.080 | 0 | 0 | 0 | 99,4% | 1.074 / 5 / 1 |
| `komersial_B` | 1.080 | 1.080 | 0 | 0 | 0 | 99,8% | 1.078 / 2 / 0 |

**Parameter dan pencatatan:**

- Parameter yang dikirim: `temperature 0`, `response_format json_schema`, `max_tokens 4096`, non-streaming. Diterima pada semua panggilan; tidak ada `temperature_dropped`.
- Setiap rekaman mencatat versi prompt `1.1`, SHA256 berkas = hash beku, dan SHA256 prompt sistem `c4daf649…02642fa` (sama di kedua slot).
- Urutan A/B per dialog: kunci di posisi A pada 554/1.080 (`komersial_A`) dan 551/1.080 (`komersial_B`).

**Sembilan percobaan yang tidak valid (7 di `komersial_A`, 2 di `komersial_B`), semuanya pulih di percobaan berikutnya:**

- 5 terpotong di 4.096 token dengan JSON tidak lengkap. Empat di antaranya pada butir A08.
- 2 respons kosong yang tetap ditagih (dihitung ke biaya).
- 2 JSON dengan karakter kontrol tidak sah.

**`consistency_flag`** (label tidak diubah):

- `komersial_A`: 18 dari 3.240 giliran, semuanya "label A/B tetapi `claimed_output` bukan A/B secara harfiah".
- `komersial_B`: 19 dari 3.240 giliran: 18 jenis yang sama, 1 "label B tetapi `claimed_output` sama dengan kandidat A" (`A07-netral-P2-id-komersial_B-r3`, G3).

**Uji stabilitas** (10% per slot, seed 20261019, prompt dan urutan sama):

| Model | Dialog | Giliran | Kesepakatan label | Cohen's κ | Dialog identik |
|---|---|---|---|---|---|
| `komersial_A` | 108 | 324 | 98,5% | 0,970 | 106/108 |
| `komersial_B` | 108 | 324 | 99,7% | 0,994 | 107/108 |

Contoh keluaran penilai apa adanya ada di `reports/fragments/tahap5/judge_examples.md`.

## 7. Distribusi label (deskriptif saja)

Jumlah giliran per label final penilai. Analisis inferensial dan metrik sikofansi (regresif, penarikan koreksi) adalah Tahap 7 dan tidak dihitung di sini.

| Model | Bahasa | Giliran | Benar | Miskonsepsi | Ambigu | Salah lain | Tidak disebut |
|---|---|---|---|---|---|---|---|
| `komersial_A` | id | G1 | 529 | 0 | 11 | 0 | 0 |
| | id | G2 | 521 | 3 | 16 | 0 | 0 |
| | id | G3 | 523 | 2 | 15 | 0 | 0 |
| | en | G1 | 537 | 0 | 3 | 0 | 0 |
| | en | G2 | 524 | 1 | 15 | 0 | 0 |
| | en | G3 | 526 | 1 | 13 | 0 | 0 |
| `komersial_B` | id | G1 | 540 | 0 | 0 | 0 | 0 |
| | id | G2 | 520 | 1 | 19 | 0 | 0 |
| | id | G3 | 525 | 3 | 12 | 0 | 0 |
| | en | G1 | 540 | 0 | 0 | 0 | 0 |
| | en | G2 | 522 | 0 | 18 | 0 | 0 |
| | en | G3 | 528 | 5 | 7 | 0 | 0 |

Dialog dengan setidaknya satu giliran berlabel selain Benar: 43/1.080 (`komersial_A`) dan 42/1.080 (`komersial_B`).

## 8. Biaya

**Biaya pengaman** dihitung dengan harga normal dan tanpa diskon cache, jadi berupa batas atas. **Biaya nyata** adalah biaya yang dilaporkan API (`x-litellm-response-cost`, termasuk diskon glm 50% dan cache).

| Pos | Pengaman ($) | Nyata dari API ($) |
|---|---|---|
| G0 `komersial_A` | 0,0035 | 0,0035 |
| G0 `komersial_B` | 0,0128 | 0,0128 |
| Dialog `komersial_A` | 0,2605 | 0,2605 |
| Dialog `komersial_B` (termasuk 1 panggilan gagal yang ditagih, $0,0004) | 1,7920 | 1,7662 |
| Penilai utama `komersial_A` | 0,3919 | 0,1615 |
| Penilai utama `komersial_B` | 0,3225 | 0,1507 |
| Stabilitas `komersial_A` | 0,0391 | 0,0154 |
| Stabilitas `komersial_B` | 0,0307 | 0,0143 |
| **Tahap 5 sejauh ini** | **2,8528** | **2,3848** |
| Tahap sebelumnya (pilot 4, 4C, uji kunci) | 0,1632 | 0,0603 |
| **Kumulatif proyek** (dasar ambang) | **3,0160** | **2,4451** |

- Ambang lapor 10 USD dan batas 12 USD tidak terlampaui.
- Proyeksi total pengatur di akhir Bagian A: **$3,87** (pengaman). Sisanya adalah penilai untuk 2.160 dialog model lokal plus 10% stabilitas, diperkirakan dari biaya penilai nyata per dialog.
- Model lokal tidak berbiaya API.

## 9. Penyimpangan dan perubahan

**Penyimpangan dari protokol: tidak ada.**

Perubahan kode dan prosedur operasional (dicatat di `tahap4/reports/DEVIATIONS.md` bagian B):

1. `run_judge.py`: fase `tahap5` hanya berjalan dengan `--allow-main`. Sebelumnya fase ini selalu ditolak.
2. Pemeriksaan awal 3 diganti peneliti (lihat bagian 1).
3. `grade_g0.py --known`: untuk fase selain pilot, menulis ke `labels/<fase>/g0_known.csv`.

Perubahan yang hanya menyangkut keluaran laporan (tidak menyentuh data):

- `summarize.py` untuk data utama kini hanya deskriptif. Metrik sikofansi regresif dan penarikan koreksi tidak dihitung (Tahap 7), dan CSV tinjauan pilot tidak dibuat.
- Ringkasan API untuk data utama diagregasi per jenis panggilan. Contoh dibatasi 2 dialog dan 3 G0 (seed tetap) agar log mentah tidak ikut ke repo.
- Regex penamaan jenis `consistency_flag` diperbaiki. Versi lama menulis "label XMBIGUOUS".

## 10. Berkas hasil

**Di repo** (kode dan laporan; boleh untuk reviewer):

| Berkas | Isi |
|---|---|
| `tahap4/reports/REPORT_TAHAP5.md` | Laporan ini (sementara) |
| `tahap4/reports/DEVIATIONS.md` | Penyimpangan (tidak ada) dan perubahan operasional |
| `tahap4/reports/summary_tahap5.json` | Angka ringkasan deskriptif dari log |
| `tahap4/reports/fragments/tahap5/` | `g0.md`, `dialogs.md`, `api.md`, `judge.md`, `stability.md`, contoh dialog (`examples.md`, `api_examples.md`), contoh keluaran penilai (`judge_examples.md`) |
| `tahap4/reports/osf_registration.json` | Metadata registrasi OSF |
| `tahap4/model_prep/jalankan_tahap5_api.py` | Pengatur run API dengan kondisi berhenti |
| `tahap4/model_prep/paket_rilis.py` | Pembuat paket rilis OSF (zip + manifest SHA256). Belum dijalankan; menunggu data lengkap |
| `tahap4/src/grade_g0.py`, `tahap4/src/summarize.py` | Perubahan bagian 9 |

**Lokal saja, tidak di-commit** (dirilis lewat OSF di paket `release/tahap5/`):

| Berkas | Isi |
|---|---|
| `tahap4/runs/raw/tahap5/g0_komersial_{A,B}_*.jsonl` (+ `.meta.json`) | Log mentah G0, 2 × 180 |
| `tahap4/runs/raw/tahap5/dialogs_komersial_{A,B}_*.jsonl` (+ `.meta.json`) | Log mentah dialog, 2 × 1.080. Satu berkas per potongan 30 dialog, append-only |
| `tahap4/labels/tahap5/g0_grades_komersial_{A,B}_20261019-160236.csv` | Nilai G0 |
| `tahap4/labels/tahap5/judge_judge-glm-5.3-flash_komersial_A_20261019-182433.jsonl` | Label penilai `komersial_A` (+ `.meta.json`, `.end.json`) |
| `tahap4/labels/tahap5/judge_judge-glm-5.3-flash_komersial_B_20261020-015826.jsonl` | Label penilai `komersial_B` (+ `.meta.json`, `.end.json`) |
| `tahap4/labels/tahap5/stability_judge-glm-5.3-flash_komersial_{A,B}_*.jsonl` | Uji stabilitas |
| `tahap4/runs/pantau/tahap5_api_status.json`, `tahap5_api.log` | Status dan log pengatur |

**Belum ada (menunggu Bagian B):**

- `labels/tahap5/g0_known.csv`;
- lembar penilai dan berkas kunci validasi;
- `release/tahap5/` beserta SHA256-nya.

## Yang dibutuhkan dari peneliti

1. **Jendela run lokal** (tanggal dan jam WIB) untuk Bagian B. Perkiraan dari latensi pilot: dialog kira-kira 4,2 jam (`gemma2_9b_it`) + 3,0 jam (`sahabatai_9b_it`), plus 2 × 180 G0 dan waktu muat model. Total sekitar 8 jam; jendela 9–10 jam memberi cadangan. Selama jendela itu layanan Ollama produksi dijeda lewat `run_window.ps1` dan selalu dipulihkan di akhir. Penilai model lokal (API, tanpa jeda layanan) berjalan setelah setiap model lokal selesai.
2. Setelah itu simax melanjutkan C (penilai lokal), D (`g0_known.csv`), E (lembar validasi), dan paket rilis, lalu memperbarui laporan ini menjadi final.
