# DEVIATIONS — Penyimpangan dari protokol praregistrasi (Tahap 5 dan seterusnya)

Protokol acuan: OSF https://osf.io/43gwh, repo tag `protokol-praregistrasi`
(commit `1a274394b13d4e5289d7dd9589a20660bacb8068`). Setiap penyimpangan dicatat dengan tanggal, apa yang menyimpang,
alasan, dan dampaknya. Berkas ini dilaporkan di artikel.

## A. Penyimpangan dari protokol

Belum ada.

## B. Perubahan kode atau prosedur operasional (bukan perubahan protokol; dicatat untuk transparansi)

| Tanggal | Apa | Alasan | Dampak pada data |
|---|---|---|---|
| 2026-10-19 | `tahap4/src/run_judge.py`: pengaman fase `tahap5` diubah dari "selalu menolak" menjadi "hanya dengan `--allow-main`" (5 baris; sama seperti runner dialog dan G0). | Pengaman versi bertag mencegah penilaian data utama sama sekali, padahal penilaian Tahap 5 adalah bagian protokol. | Tidak ada. Butir, template, prompt penilai (beku, hash dicek), seed, dan parameter model tidak berubah. |
| 2026-10-19 | Pemeriksaan awal 3 (instruksi kerja Tahap 5) diganti peneliti dari "kunci API harus diganti" menjadi "uji kunci dengan `model_prep/cek_kunci_api.py`, ketiga slot lolos". | Anggapan kunci bocor berasal dari salah tafsir laporan; pemindaian menunjukkan tidak ada kunci yang pernah ter-commit. | Tidak ada. Ini perubahan instruksi kerja, bukan protokol praregistrasi (keputusan peneliti). |
| 2026-10-19 | `tahap4/src/grade_g0.py --known`: untuk fase selain `tahap4`, `g0_known.csv` ditulis ke `labels/<fase>/` (Tahap 5: `labels/tahap5/g0_known.csv`, hanya dari data utama); fase pilot tetap ke `labels/g0_known.csv`. | Instruksi Tahap 5 meminta `labels/tahap5/g0_known.csv` dari data utama saja; versi lama selalu menimpa berkas pilot. | Tidak ada. Hanya lokasi berkas keluaran; aturan penilaian G0 dan definisi "tahu" (≥ 2 dari 3) tidak berubah. |
| 2026-10-20 | Run lokal Tahap 5: `model_prep/run_window.ps1` mendapat parameter jendela (`-StartAt`, `-WorkDeadline`, `-EndAt`) dan langkah `tahap5`; pengatur baru `model_prep/jalankan_tahap5_lokal.py` (G0 lalu dialog dalam potongan; potongan hanya dimulai bila diperkirakan selesai sebelum batas kerja; pemeriksaan awal dan kondisi berhenti termasuk digest, versi Ollama, dan kuantisasi harus sama dengan pilot). Penilai model lokal berjalan sebagai proses terpisah tanpa menjeda layanan. | Jendela run lokal dari peneliti: Selasa 20 Okt 2026 22.00 – Rabu 21 Okt 08.00 WIB; bila belum selesai, berhenti rapi dan layanan dipulihkan sebelum 08.00. | Tidak ada. Runner `src/` dipanggil apa adanya (`--phase tahap5 --allow-main`); parameter model, seed, dan urutan dialog tidak berubah. |
