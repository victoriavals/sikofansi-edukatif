# Laporan Tahap 5 — Pengumpulan data utama

Disusun oleh simax, 2026-10-21, untuk peneliti dan reviewer. Protokol acuan: praregistrasi OSF
https://osf.io/43gwh, tag Git `protokol-praregistrasi` (commit `1a27439`). Laporan ini menggantikan versi sementara
(commit `c603c74`, Bagian A saja).

## Ringkasan

| Bagian | Isi | Hasil |
|---|---|---|
| Pemeriksaan awal | 1 OSF, 2 protokol tidak berubah, 3 uji kunci, 4 README | Keempatnya lolos (bagian 1) |
| A | Model API: G0 dan 1.080 dialog per model | 2.160/2.160 dialog, 360/360 G0; 0 gagal; 0 giliran terpotong |
| B | Model lokal di jendela peneliti | 2.160/2.160 dialog, 360/360 G0; 0 gagal; 0 giliran terpotong; selesai dalam jendela, layanan dipulihkan |
| C | Penilai `glm-5.3-flash`, prompt v1.1 beku | 4.320/4.320 dialog valid; 0 dinilai ulang; 0 dikeluarkan; uji stabilitas 4 × 108 dialog |
| D | Nilai G0 dan `labels/tahap5/g0_known.csv` | Selesai: 240 baris (4 model × 30 butir × 2 bahasa); 0 kasus cek manual |
| E | Sampel validasi manusia | 200 giliran (25 per model × bahasa); lembar penilai dan berkas kunci di folder lokal yang di-ignore; tidak dikirim ke siapa pun |
| Rilis | Paket OSF | `release/tahap5/sikofansi_tahap5_20261021-082252.zip` (342 berkas, 17,4 MB) |
| Kondisi berhenti | Biaya, gagal, perubahan model/hulu, terpotong, penilai tidak valid | **Tidak ada yang terpicu** |
| Penyimpangan protokol | | **Tidak ada.** Perubahan operasional dicatat di `DEVIATIONS.md` bagian B |

## 1. Pemeriksaan awal

| No. | Pemeriksaan | Hasil |
|---|---|---|
| 1 | Praregistrasi OSF | Lolos. https://osf.io/43gwh: publik, terdaftar 2026-10-19 08:31:08 UTC, tidak ditarik, tidak tertunda. Merujuk commit `1a27439`, tag `protokol-praregistrasi`, dan kedua SHA256 beku. Judul sesuai naskah (dikonfirmasi peneliti). Metadata di `tahap4/reports/osf_registration.json` |
| 2 | Protokol tidak berubah sejak tag | Lolos. `git diff protokol-praregistrasi -- tahap2 tahap3` kosong saat pemeriksaan, setelah Bagian A, dan setelah semua run (2026-10-21). SHA256 `judge_prompt.md` = `87d7c80b…3ffd30`, `panduan_pelabelan.md` = `29d8e8fe…2d5cc1` (sama dengan hash beku) |
| 3 | Uji kunci API | Lolos. `model_prep/cek_kunci_api.py`, 2026-10-19 15:43 WIB: ketiga slot `ok`. Field `model`: `gpt-6-luna`, `deepseek-v4-flash-0731:netra`, `glm-5.3-flash`. Biaya $0,000083 |
| 4 | README berisi tautan OSF; `osf_registration.json` di-commit | Lolos. Commit `642289a` (sudah di-push) |

**Perubahan instruksi kerja (bukan penyimpangan protokol).** Pemeriksaan 3 semula berbunyi "kunci API harus sudah diganti". Peneliti menggantinya menjadi "jalankan `model_prep/cek_kunci_api.py` dan pastikan ketiga slot lolos". Alasannya, anggapan kunci bocor berasal dari salah tafsir laporan: pemindaian riwayat Git menunjukkan tidak ada kunci yang pernah ter-commit. Perubahan ini juga dicatat di `DEVIATIONS.md` bagian B.

## 2. Linimasa (WIB, UTC+7)

**Bagian A dan penilainya** (pengatur `model_prep/jalankan_tahap5_api.py`, commit `283377f`):

| Waktu | Kejadian |
|---|---|
| 19 Okt 15:43 | Uji kunci (pemeriksaan 3) |
| 19 Okt 15:47 – 15:57 | G0 `komersial_A`, lalu G0 `komersial_B` (180 + 180) |
| 19 Okt 15:57 – 18:24 | Dialog `komersial_A` (1.080, potongan 30 dialog; kondisi berhenti dicek tiap potongan) |
| 19 Okt 18:24 – 20 Okt 01:58 | Dialog `komersial_B` (1.080) |
| 19 Okt 18:24 – 23:35 | Penilai `komersial_A`: utama, penilaian ulang (tidak ada yang perlu), stabilitas |
| 20 Okt 01:58 – 04:57 | Penilai `komersial_B`: utama, penilaian ulang (tidak ada), stabilitas |

**Bagian B dan penilainya** (pengatur `model_prep/jalankan_tahap5_lokal.py`, commit `30360a9`; perbaikan `fad7659`):

| Waktu | Kejadian |
|---|---|
| 20 Okt 08:37 | Run dijadwalkan untuk jendela pertama dari peneliti (20 Okt 22:00 – 21 Okt 08:00). Proses menunggu tanpa menyentuh layanan |
| 20 Okt pagi | Peneliti mengubah jendela: mulai sekarang, paling lambat 10 jam sejak mulai. Proses tunggu dihentikan sebelum menyentuh layanan |
| 08:49:31 | **Jendela mulai** (batas 18:49:31). Layanan dijeda 08:49:32 |
| 08:49 – 08:53 | **Percobaan pertama gagal:** instans riset tidak menyala, karena bash Git tidak menemukan alat Unix di PATH. Tidak ada panggilan model. Layanan dipulihkan otomatis 08:53:00 |
| 08:54:07 | Diluncurkan ulang dengan perbaikan PATH, batas tetap: kerja 18:34:31, henti paksa 18:39:31. Layanan dijeda 08:54:08 |
| 08:54:16 | Pemeriksaan awal instans riset lolos (versi Ollama, digest, kuantisasi = pilot) |
| 08:54 – 08:56 | G0 `gemma2_9b_it`, lalu G0 `sahabatai_9b_it` (180 + 180) |
| 08:56 – 13:11 | Dialog `gemma2_9b_it` (1.080) |
| 13:11 – 16:27 | Dialog `sahabatai_9b_it` (1.080) |
| 16:27:30 – 16:27:59 | Model riset dilepas dari VRAM; **layanan dipulihkan** (ketiganya `Running`; model layanan dimuat kembali). Jendela terpakai 7 jam 38 menit dari 10 jam |
| 20 Okt 13:12 – 22:31 | Penilai `gemma2_9b_it`: utama, penilaian ulang (tidak ada), stabilitas |
| 20 Okt 16:28 – 21 Okt 00:23 | Penilai `sahabatai_9b_it`: utama, penilaian ulang (tidak ada), stabilitas |
| 21 Okt 08:21 | Sampling validasi manusia (bagian E) |
| 21 Okt 08:22 | Paket rilis OSF |

**Jendela data per model** (dari G0 pertama sampai dialog terakhir; batas untuk model API: dua minggu):

| Model | Jendela | Durasi |
|---|---|---|
| `komersial_A` | 19 Okt 15:47 – 18:24 | 2 j 37 m |
| `komersial_B` | 19 Okt 15:52 – 20 Okt 01:58 | 10 j 6 m |
| `gemma2_9b_it` | 20 Okt 08:54 – 13:11 | 4 j 17 m |
| `sahabatai_9b_it` | 20 Okt 08:55 – 16:27 | 7 j 32 m |

## 3. Kelengkapan

Diperiksa dengan skrip baca-saja terhadap `tahap3/dialogs_plan.jsonl` dan `g0_plan.jsonl`.

| Model | Dialog rencana | `ok` unik | Ganda | Hilang | Di luar rencana | Galat yang diulang | G0 `ok` |
|---|---|---|---|---|---|---|---|
| `komersial_A` | 1.080 | 1.080 | 0 | 0 | 0 | 0 | 180/180 |
| `komersial_B` | 1.080 | 1.080 | 0 | 0 | 0 | 1 | 180/180 |
| `gemma2_9b_it` | 1.080 | 1.080 | 0 | 0 | 0 | 0 | 180/180 |
| `sahabatai_9b_it` | 1.080 | 1.080 | 0 | 0 | 0 | 0 | 180/180 |
| **Total** | **4.320** | **4.320** | 0 | 0 | 0 | 1 | **720/720** |

**Isi, semua model** (dialog `ok`):

- Pesan siswa identik dengan rencana dialog.
- Riwayat asisten identik dengan respons yang dicatat.
- Tidak ada system prompt.

**Parameter yang dikirim:**

- **Model API:** hanya `{"max_tokens": 1024, "stream": false}` di 3.240/3.240 giliran per model; tanpa temperature, top_p, atau seed.
- **Model lokal:**
  - opsi `{num_ctx 4096, num_predict 1024, num_gpu 36, seed}` di 3.240/3.240 giliran per model;
  - `seed` = int(sha256(dialog_id)) mod 2^31, cocok untuk 1.080/1.080 dialog per model;
  - tanpa override temperature/top_p;
  - `keep_alive` 30m.

**Teks penalaran `komersial_B`:** 3.240/3.240 giliran tersimpan lengkap di `provider_meta.reasoning_text`.

- Tidak ada yang masuk riwayat dialog. Dicek dengan mencari 200 karakter awal teks penalaran di setiap pesan asisten.
- Tidak ada tag `<think>` di dalam `content`.
- `komersial_A` hanya mengembalikan jumlah token penalaran.

**Satu galat yang diulang.** Di `E04-yakin-P1-en-komersial_B-r1`, percobaan pertama satu giliran mengembalikan respons kosong (740 token, semuanya penalaran). Respons itu tetap ditagih $0,000431 dan dicatat di `errors` dan `failed_calls_cost_usd`. Percobaan kedua sukses.

Header `x-litellm-attempted-retries` = 1 muncul pada 1 dari 3.420 panggilan `komersial_B`, artinya proxy SumoPod mengulang sendiri di sisi server.

## 4. Konsistensi model

**Model API:**

| Model | Field `model` | Hulu (`x-litellm-model-api-base`) | `x-litellm-model-name` | ID respons unik |
|---|---|---|---|---|
| `komersial_A` | `gpt-6-luna` | `https://api-sg.umodelverse.ai/v1` | `gpt-6-luna` | 3.420 / 3.420 |
| `komersial_B` | `deepseek-v4-flash-0731:netra` | `https://api.netraruntime.com/v1` | `deepseek/deepseek/deepseek-v4-flash-0731` | 3.420 / 3.420 |

Field `model`, hulu, dan nama model hulu tidak berubah sepanjang G0 dan dialog. Hulu UModelverse/Netra tetap dicatat sebagai keterbatasan (`CLAUDE.md`).

**Model lokal** (instans riset 127.0.0.1:11435). Nilai berikut diperiksa sebelum run dan tidak berubah di setiap rekaman G0 dan dialog:

| Model | Digest (sama dengan pilot) | Ollama | Kuantisasi | Offload |
|---|---|---|---|---|
| `gemma2_9b_it` | `c8c9d8327c89c67aee9b900e481643ef427d27c14993d49a80a3519f1b178429` | 0.40.5 | Q4_K_M | 36/43 lapisan di GPU, KV f16 |
| `sahabatai_9b_it` | `d2fdb678df13285a657f84d117fa45babb73155307fdc22bbc86d395603cf3a4` | 0.40.5 | Q4_K_M | 36/43 lapisan di GPU, KV f16 |

**Giliran terpotong (`finish=length`): 0 dari 3.240 untuk setiap model.**

| Model | Latensi per dialog (s) | Token output rata-rata G1 / G2 / G3 | Catatan |
|---|---|---|---|
| `komersial_A` | 8,1 | 109 / 160 / 115 | Token penalaran rata-rata 35–57 per giliran |
| `komersial_B` | 25,1 | 486 / 1.232 / 998 | Token penalaran Netra melampaui `max_tokens` (diterima peneliti); semua giliran `stop` |
| `gemma2_9b_it` | 14,0 | 163 / 114 / 98 | 28,3 token/detik |
| `sahabatai_9b_it` | 10,7 | 110 / 95 / 79 | 28,6 token/detik |

Rincian per jenis panggilan model API ada di `reports/fragments/tahap5/api.md`; untuk semua model di `dialogs.md`.

## 5. G0 (pengetahuan dasar)

- Dinilai dengan aturan beku (`src/grade_g0.py`, keputusan peneliti 2026-10-18).
- **Tidak ada kasus cek manual**, jadi tidak ada `g0_manual_decisions.csv` di Tahap 5.
- Nilai yang dipakai: `labels/tahap5/g0_grades_<model>_20261020-090352.csv`, penilaian terakhir untuk keempat model. Berkas yang lebih awal (`…_20261019-160236`, `…_20261020-090337`) identik isinya. `g0_known.csv` mencatat sumbernya di kolom `sumber_nilai`.

| Model | id benar | en benar | Butir × bahasa salah ≥ 2/3 |
|---|---|---|---|
| `komersial_A` | 90/90 | 90/90 | tidak ada |
| `komersial_B` | 90/90 | 90/90 | tidak ada |
| `gemma2_9b_it` | 82/90 | 84/90 | D04 (id, en), F02 (id, en) |
| `sahabatai_9b_it` | 77/90 | 79/90 | A08 (id), D03 (id, en), D04 (id, en), E02 (id), F02 (id, en) |

Alasan otomatis untuk jawaban yang dinilai salah:

- `gemma2_9b_it`: 13 jawaban berbeda dari kunci; 1 "tidak dapat ditentukan".
- `sahabatai_9b_it`: 19 berbeda dari kunci; 4 baris output digabung tanpa pemisah; 1 "tidak dapat ditentukan".

**`labels/tahap5/g0_known.csv`** dibuat hanya dari data utama, 240 baris. "Tahu" = G0 benar ≥ 2 dari 3:

| Model | "Tahu" | Tidak |
|---|---|---|
| `komersial_A` | 60/60 | 0 |
| `komersial_B` | 60/60 | 0 |
| `gemma2_9b_it` | 56/60 | 4 |
| `sahabatai_9b_it` | 52/60 | 8 |

## 6. Penilai (`glm-5.3-flash`, prompt v1.1 beku)

| Model | Dinilai | Valid | Tidak valid setelah 3 percobaan | Dinilai ulang | Dikeluarkan | JSON valid percobaan pertama | Percobaan (1/2/3) | Latensi rata-rata (s) | Token output rata-rata (penalaran) |
|---|---|---|---|---|---|---|---|---|---|
| `komersial_A` | 1.080 | 1.080 | 0 | 0 | 0 | 99,4% | 1.074 / 5 / 1 | 12,9 | 514 (355) |
| `komersial_B` | 1.080 | 1.080 | 0 | 0 | 0 | 99,8% | 1.078 / 2 / 0 | 8,4 | 416 (257) |
| `gemma2_9b_it` | 1.080 | 1.080 | 0 | 0 | 0 | 99,7% | 1.077 / 3 / 0 | 24,4 | 896 (732) |
| `sahabatai_9b_it` | 1.080 | 1.080 | 0 | 0 | 0 | 99,9% | 1.079 / 1 / 0 | 19,2 | 724 (566) |

Ketentuan "dialog yang tetap tidak valid setelah 3 percobaan dinilai ulang satu kali, lalu dikeluarkan bila tetap tidak valid" tidak pernah terpakai, karena tidak ada dialog yang tidak valid. Kondisi berhenti "> 5% dialog tidak valid" tidak terpicu.

**Parameter dan pencatatan:**

- Parameter yang dikirim: `temperature 0`, `response_format json_schema`, `max_tokens 4096`, non-streaming. Diterima pada semua panggilan; tidak ada `temperature_dropped`.
- Setiap rekaman mencatat versi prompt `1.1`, SHA256 berkas = hash beku, dan SHA256 prompt sistem `c4daf649…02642fa` (sama di keempat slot).
- Urutan A/B per dialog (kunci di posisi A): 554, 551, 532, dan 540 dari 1.080.

**Tiga belas percobaan yang tidak valid, semuanya pulih di percobaan berikutnya:**

- 8 terpotong di 4.096 token dengan JSON tidak lengkap. Empat di antaranya pada butir A08.
- 2 respons kosong yang tetap ditagih (dihitung ke biaya).
- 2 JSON dengan karakter kontrol tidak sah.
- 1 urutan giliran salah ("giliran harus G1, G2, G3 berurutan").

**`consistency_flag`** (label tidak diubah):

| Model | Giliran ditandai | Jenis |
|---|---|---|
| `komersial_A` | 18 / 3.240 | 18 "label A/B tetapi `claimed_output` bukan A/B secara harfiah" |
| `komersial_B` | 19 / 3.240 | 18 jenis yang sama; 1 "label B tetapi `claimed_output` sama dengan kandidat A" |
| `gemma2_9b_it` | 34 / 3.240 | 32 jenis yang sama; 1 sama dengan kandidat A; 1 sama dengan kandidat B |
| `sahabatai_9b_it` | 43 / 3.240 | 37 jenis yang sama; 5 sama dengan kandidat A; 1 sama dengan kandidat B |

**Uji stabilitas** (10% per slot, seed 20261019, prompt dan urutan sama):

| Model | Dialog | Giliran | Kesepakatan label | Cohen's κ | Dialog identik |
|---|---|---|---|---|---|
| `komersial_A` | 108 | 324 | 98,5% | 0,970 | 106/108 |
| `komersial_B` | 108 | 324 | 99,7% | 0,994 | 107/108 |
| `gemma2_9b_it` | 108 | 324 | 95,1% | 0,921 | 94/108 |
| `sahabatai_9b_it` | 108 | 324 | 96,6% | 0,941 | 99/108 |

Sebagian besar ketidaksepakatan melibatkan label AMBIGUOUS: 31 dari 33 pasangan berbeda (`komersial_A` 5/5, `komersial_B` 1/1, `gemma2_9b_it` 14/16, `sahabatai_9b_it` 11/11). Contoh keluaran penilai apa adanya ada di `reports/fragments/tahap5/judge_examples.md`.

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
| `gemma2_9b_it` | id | G1 | 474 | 55 | 10 | 1 | 0 |
| | id | G2 | 188 | 209 | 49 | 10 | 84 |
| | id | G3 | 112 | 342 | 56 | 3 | 27 |
| | en | G1 | 489 | 32 | 18 | 1 | 0 |
| | en | G2 | 180 | 233 | 69 | 8 | 50 |
| | en | G3 | 131 | 316 | 50 | 5 | 38 |
| `sahabatai_9b_it` | id | G1 | 449 | 80 | 6 | 5 | 0 |
| | id | G2 | 276 | 175 | 25 | 10 | 54 |
| | id | G3 | 230 | 243 | 26 | 9 | 32 |
| | en | G1 | 451 | 67 | 19 | 2 | 1 |
| | en | G2 | 273 | 206 | 40 | 8 | 13 |
| | en | G3 | 238 | 272 | 25 | 4 | 1 |

Dialog dengan setidaknya satu giliran berlabel selain Benar:

| Model | Dialog |
|---|---|
| `komersial_A` | 43/1.080 |
| `komersial_B` | 42/1.080 |
| `gemma2_9b_it` | 934/1.080 |
| `sahabatai_9b_it` | 675/1.080 |

## 8. Validasi manusia (bagian E): sampel

Dijalankan dengan `python -m src.sample_validation --phase tahap5`. Desainnya sesuai keputusan peneliti; panduan v1.1 dicek hashnya.

- Populasi: 12.960 giliran berlabel valid.
- Sampel: 200 giliran, alokasi sama 25 per model × bahasa.
- Di dalam sel, alokasi per label penilai; Ambigu berbobot ×3, minimal 2 per label.
- Seed 20261020. Peluang inklusi dan bobot 1/π dicatat per baris di berkas kunci.

Komposisi sampel menurut label penilai (hanya di berkas kunci): Benar 125, Miskonsepsi 32, Ambigu 27, Salah lain 8, Tidak disebut 8.

**Lembar penilai** berisi `validasi_id`, kode, kedua kandidat, pesan siswa, respons tutor, dan kolom isian `label_manusia`, `output_lainnya`, `klaim_kode_perbaikan` (penanda GP-01), serta `catatan`.

- Tidak ada kolom model, label penilai, atau ID dialog.
- Lima respons tutor menyebut "Google Colab" sebagai tempat menjalankan kode; tidak ada yang menyebut identitas model.

**Lokasi.** Ketiga berkas ada di `tahap4/labels/tahap5/validasi_manusia/`:

- `lembar_penilai_20261021-082128.csv`;
- `kunci_validasi_20261021-082128.csv`;
- `sampling_validasi_20261021-082128.json`.

Folder ini di-ignore git (tidak masuk repo publik) dan dikecualikan dari paket rilis OSF sampai Tahap 6 selesai. **Tidak ada yang dikirim ke penilai.**

## 9. Biaya

**Biaya pengaman** dihitung dengan harga normal dan tanpa diskon cache, jadi berupa batas atas. **Biaya nyata** adalah biaya yang dilaporkan API (`x-litellm-response-cost`, termasuk diskon glm 50% dan cache). Model lokal tidak berbiaya API.

| Pos | Pengaman ($) | Nyata dari API ($) |
|---|---|---|
| G0 `komersial_A` / `komersial_B` | 0,0035 / 0,0128 | 0,0035 / 0,0128 |
| Dialog `komersial_A` | 0,2605 | 0,2605 |
| Dialog `komersial_B` (termasuk 1 panggilan gagal yang ditagih) | 1,7920 | 1,7662 |
| Penilai utama `komersial_A` / `komersial_B` | 0,3919 / 0,3225 | 0,1615 / 0,1507 |
| Penilai utama `gemma2_9b_it` / `sahabatai_9b_it` | 0,6193 / 0,5482 | 0,2672 / 0,2187 |
| Stabilitas (keempat slot) | 0,0391 + 0,0307 + 0,0614 + 0,0620 = 0,1932 | 0,0154 + 0,0143 + 0,0233 + 0,0227 = 0,0757 |
| **Total Tahap 5** | **4,1437** | **2,9167** |
| Tahap sebelumnya (pilot 4, 4C, uji kunci) | 0,1632 | 0,0603 |
| **Kumulatif proyek** (dasar ambang) | **4,3069** | **2,9771** |

- Ambang lapor 10 USD dan batas 12 USD tidak terlampaui pada titik mana pun.
- Proyeksi pengatur tertinggi selama run: $7,16 (awal Bagian A, sebelum biaya per dialog nyata tersedia).

## 10. Penyimpangan, perubahan, dan berkas hasil

### Penyimpangan dari protokol

Tidak ada.

### Perubahan operasional (`tahap4/reports/DEVIATIONS.md` bagian B)

Tidak ada yang berdampak pada data.

1. `run_judge.py`: fase `tahap5` hanya berjalan dengan `--allow-main`.
2. Pemeriksaan awal 3 diganti peneliti (bagian 1).
3. `grade_g0.py --known`: untuk fase selain pilot, menulis ke `labels/<fase>/g0_known.csv`.
4. Run lokal:
   - `run_window.ps1` mendapat parameter jendela;
   - pengatur baru `jalankan_tahap5_lokal.py` (G0 dan dialog dalam potongan sebelum batas kerja; digest/versi/kuantisasi harus sama dengan pilot);
   - penilai lokal berjalan terpisah tanpa menjeda layanan.
5. Jendela lokal diubah peneliti. Percobaan pertama gagal menyalakan instans riset (PATH); diperbaiki dan diluncurkan ulang dalam jendela yang sama.

### Perubahan keluaran laporan (tidak menyentuh data)

- `summarize.py` untuk data utama hanya deskriptif: metrik regresif dan penarikan koreksi tidak dihitung (Tahap 7), dan CSV tinjauan pilot tidak dibuat.
- Ringkasan API diagregasi per jenis panggilan, dengan contoh dibatasi 2 dialog dan 3 G0 (seed tetap), agar log mentah tidak ikut ke repo.
- Regex jenis `consistency_flag` diperbaiki.
- `paket_rilis.py` juga memaketkan log ringkas dan status pengatur.
- `environment.md` ditambah bagian pemeriksaan ulang lingkungan Tahap 5: driver, Python, `pip freeze`, Ollama, dan digest semuanya sama dengan Tahap 4.

### Paket rilis OSF (tidak di-commit; `release/` di-ignore)

| Berkas | SHA256 |
|---|---|
| `release/tahap5/sikofansi_tahap5_20261021-082252.zip` (342 berkas, 17,4 MB) | `1a81f46d21c307e5ae272537594a36e390ade66e203cbec05d008af264372a8a` |
| `release/tahap5/MANIFEST_20261021-082252.csv` (SHA256 per berkas) | `6d257d3a609d42772149a3dcf2ed5d67d0d6daa7f8f0c6fa1700285420e682eb` |
| `release/tahap5/SHA256SUMS.txt` | Daftar kedua hash di atas |

**Isi zip:**

- log mentah `runs/raw/tahap5/` (296 berkas: dialog dan G0 keempat model, beserta `.meta.json`);
- `labels/tahap5/` (33 berkas: label penilai, uji stabilitas, nilai G0, `g0_known.csv`);
- log ringkas dan status pengatur (6 berkas);
- `config.yaml`, `environment.md`, `DEVIATIONS.md`;
- `tahap3/` beku: `judge_prompt.md`, `panduan_pelabelan.md`, `judge_schema.json`, `CHANGELOG.md`;
- manifest.

**Verifikasi:** `testzip` lolos; SHA256 ke-342 berkas di zip cocok dengan manifest; tidak ada berkas validasi manusia. Pemindaian kunci API, email, nama layanan, dan detail lokal pribadi: 0 temuan.

### Berkas di repo (untuk reviewer)

| Berkas | Isi |
|---|---|
| `tahap4/reports/REPORT_TAHAP5.md` | Laporan ini |
| `tahap4/reports/DEVIATIONS.md` | Penyimpangan (tidak ada) dan perubahan operasional |
| `tahap4/reports/summary_tahap5.json` | Angka ringkasan deskriptif dari log |
| `tahap4/reports/fragments/tahap5/` | `g0.md`, `dialogs.md`, `api.md`, `judge.md`, `stability.md`; contoh dialog (`examples.md`, `api_examples.md`); contoh keluaran penilai (`judge_examples.md`) |
| `tahap4/reports/environment.md` | Lingkungan, termasuk pemeriksaan ulang Tahap 5 |
| `tahap4/reports/osf_registration.json` | Metadata registrasi OSF |
| `tahap4/model_prep/jalankan_tahap5_api.py`, `jalankan_tahap5_lokal.py`, `run_window.ps1`, `paket_rilis.py` | Pengatur run, jendela lokal, dan paket rilis |
| `tahap4/src/grade_g0.py`, `tahap4/src/summarize.py`, `tahap4/tests/test_lokal_driver.py` | Perubahan bagian 10 (33 uji lulus) |

### Berkas lokal saja (tidak di-commit)

| Berkas | Isi |
|---|---|
| `tahap4/runs/raw/tahap5/` | Log mentah (append-only); masuk paket rilis |
| `tahap4/labels/tahap5/` | Label penilai, stabilitas, nilai G0, `g0_known.csv`; masuk paket rilis |
| `tahap4/labels/tahap5/validasi_manusia/` | Lembar penilai, berkas kunci, metadata sampling. **Tidak** masuk repo maupun paket rilis |
| `release/tahap5/` | Paket rilis OSF; diunggah peneliti |

Tahap 5 selesai. simax berhenti dan menunggu keputusan peneliti untuk tahap berikutnya.
