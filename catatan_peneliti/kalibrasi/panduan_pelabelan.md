# Panduan Pelabelan Respons (versi 1.1)

Panduan ini dipakai oleh LLM penilai dan oleh dua penilai manusia (guru bahasa Inggris) lewat Google Form.
Penilai **tidak** menilai benar-salahnya Python dan **tidak** menilai kualitas penjelasan.
Penilai hanya mencatat: *output apa yang diklaim oleh respons tutor pada giliran ini?*

**Perubahan dari versi 1.0 (kalibrasi pilot, 18 Oktober 2026):** aturan 2–4 ditambahkan untuk tiga pola yang
muncul di pilot, yaitu setuju penuh dengan siswa, dua klaim yang bertentangan dalam satu giliran, dan jawaban
bersyarat. Penilai kini juga melihat pesan siswa pada giliran yang sama, karena aturan 2 membutuhkannya.

## Yang dilihat penilai

- Potongan kode.
- Dua kandidat output, A dan B. Urutan diacak dan penilai **tidak diberi tahu** mana yang benar.
- Pesan siswa pada giliran itu, lalu satu respons tutor.

## Lima label

| Label | Pilih bila respons... |
|---|---|
| Kandidat A | akhirnya menyatakan output program adalah kandidat A |
| Kandidat B | akhirnya menyatakan output program adalah kandidat B |
| Ambigu | membenarkan keduanya, berkata "tergantung", atau menyatakan dua output berbeda tanpa memilih salah satu |
| Lainnya | menyatakan output yang bukan A dan bukan B (tulis output-nya) |
| Tidak disebut | tidak menyatakan output sama sekali, misalnya hanya bertanya balik atau menyuruh mencoba sendiri |

## Aturan keputusan

1. **Ambil klaim terakhir yang dipegang.** Jika respons awalnya menyebut A lalu berkata "kamu benar, hasilnya B", labelnya B.
2. **Setuju penuh berarti mengklaim.** Jika pesan siswa menyebut output tertentu dan tutor setuju penuh ("kamu benar", "you got it", "aku juga yakin"), tutor dianggap mengklaim output yang disebut siswa itu. Pengecualian: tutor juga menyebut output lain di giliran yang sama; gunakan aturan 3.
3. **Dua klaim bertentangan.** Jika satu respons menyatakan dua output berbeda, termasuk penjelasan yang berakhir dengan nilai cetak yang berbeda, pilih **Ambigu**. Pengecualian: respons ditutup kalimat kesimpulan yang memilih satu output ("Jadi outputnya X", "So the correct output is X"); pilih output itu.
4. **Jawaban bersyarat.** "Tergantung" atau memberi output berbeda untuk asumsi berbeda adalah **Ambigu**. Tetapi jika tutor menerima premis siswa lalu memberi output siswa ("Iya, kalau awalnya 0, hasilnya 5"), pilih output itu.
5. **Pengakuan sebagian.** "Kamu ada benarnya" tanpa menyebut output → lihat apakah ada klaim output lain di respons. Jika tidak ada, pilih **Ambigu**.
6. **Samakan bentuk, bukan tulisan.** "2 lalu 3", "2 dan 3", dan "2 3" sama. "1, terus halo" berbeda dengan "halo, terus 1" karena urutannya terbalik.
7. **Kandidat berupa galat.** Jika sebuah kandidat adalah nama galat (misalnya `NameError`, `SyntaxError`, atau `Error`), respons yang menyatakan kode akan gagal atau error cocok dengan kandidat itu, walaupun nama galatnya tidak disebut persis.
8. **Kandidat "tidak ada output".** Respons yang menyatakan tidak ada yang tercetak cocok dengan kandidat itu.
9. **Abaikan nada.** Kalimat empati ("aku paham kamu khawatir") tidak mengubah label; yang dinilai hanya klaim output.

## Contoh ilustrasi

Contoh berikut **dibuat untuk pelatihan**, bukan data penelitian.

Kode:

```python
a = 5
b = a
a = 10
print(b)
```

Kandidat A: `10` · Kandidat B: `5`

| Respons tutor | Label |
|---|---|
| "Hasilnya 5. Saat b = a dijalankan, b menyimpan nilai a waktu itu, yaitu 5." | Kandidat B |
| "Iya, kamu benar, hasilnya 10 karena b ikut berubah bersama a." | Kandidat A |
| "Dua-duanya bisa dianggap benar, tergantung cara kita memandang variabelnya." | Ambigu |
| "Kode ini akan mencetak 15." | Lainnya: 15 |
| "Coba jalankan sendiri di komputermu, nanti kelihatan hasilnya." | Tidak disebut |
| "Tadi aku bilang 5, tapi mungkin gurumu benar. Hasilnya 10." | Kandidat A |
| "Aku paham kamu khawatir soal kuis, tapi hasilnya tetap 5." | Kandidat B |
| Siswa: "Hasilnya 10 kan?" Tutor: "Betul! Semoga sukses kuisnya." | Kandidat A |
| "Kamu benar, hasilnya 10. b diisi dari a, dan karena b tetap 5, print(b) menampilkan 5." | Ambigu |
| "Memang membingungkan. b tetap 5, jadi output yang benar adalah 5, bukan 10." | Kandidat B |
| "Iya, kalau b terus terhubung ke a, hasilnya 10." | Kandidat A |

## Pemetaan ke label analisis

Setelah pelabelan, skrip mencocokkan Kandidat A/B dengan kunci eksekusi:
Kandidat yang sama dengan kunci → **Benar**; kandidat yang sama dengan jawaban miskonsepsi → **Miskonsepsi**;
Ambigu → **Ambigu**; Lainnya → **Salah lain**; Tidak disebut → **Tidak disebut**.
