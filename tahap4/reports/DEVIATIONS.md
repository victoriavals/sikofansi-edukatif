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
