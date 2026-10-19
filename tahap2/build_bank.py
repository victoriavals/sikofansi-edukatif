"""
Bank miskonsepsi pemrograman (Tahap 2).

Skrip ini:
1. Mendefinisikan 36 kandidat butir (30 terpilih + 6 cadangan).
2. Menjalankan setiap potongan kode Python di proses terpisah.
3. Menyimpan output eksekusi sebagai kunci jawaban, lalu mencocokkannya
   dengan prediksi peneliti dan memastikan kunci != jawaban miskonsepsi.
4. Menulis items.csv, items.json, dan item_bank.xlsx.

Jalankan ulang di PC Anda (Python 3.11 atau 3.12) untuk memverifikasi kunci:
    python build_bank.py
"""
import csv
import json
import platform
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

SRC = {
    "SW18": ("Swidan, Hermans, & Smit (2018), ICER '18; kode M dari katalog Sorva (2012)",
             "https://doi.org/10.1145/3230977.3230995"),
    "HE18": ("Hermans, Swidan, Aivaloglou, & Smit (2018), WiPSCE '18",
             "https://research.ou.nl/en/publications/thinking-out-of-the-box-comparing-metaphors-for-variables-in-prog/"),
    "CO25": ("Colla, Mens, & Lienard (2025), Programming 2025 Companion, OASIcs; nama miskonsepsi ProgMiscon",
             "https://doi.org/10.4230/OASIcs.Programming.2025.21"),
    "CH21": ("Chiodini dkk. (2021), ITiCSE '21; inventori ProgMiscon",
             "https://doi.org/10.1145/3430665.3456343"),
    "QL18": ("Qian & Lehman (2018), EURASIA J. Math. Sci. Tech. Ed.",
             "https://doi.org/10.29333/ejmste/94227"),
    "FL91": ("Fleury (1991), ACM SIGCSE Bulletin 23(1); dirujuk Chiodini dkk. (2021)",
             "https://doi.org/10.1145/3430665.3456343"),
    "TBD":  ("Sumber literatur belum diverifikasi", ""),
}

# Setiap butir: id, topik, nama miskonsepsi, sumber, kode, prediksi kunci (kanonik),
# jawaban miskonsepsi (kanonik), frasa siswa, alasan siswa (ID/EN), pernyataan miskonsepsi (ID/EN), status
ITEMS = [
    # ---------- A. Variabel dan penugasan ----------
    dict(id="A01", topik="Variabel dan penugasan", nama="M9: variabel menyimpan beberapa nilai sekaligus", src="SW18",
         kode="x = 10\nx = 20\nprint(x)", prediksi="20", mis="10 20", frasa_id="10 sama 20", frasa_en="10 and 20",
         alasan_id="x diisi 10 dulu terus 20, jadi dua-duanya kesimpan",
         alasan_en="x got 10 first and then 20, so it keeps both",
         stmt_id="Sebuah variabel dapat menyimpan beberapa nilai sekaligus.",
         stmt_en="A variable can hold several values at the same time."),
    dict(id="A02", topik="Variabel dan penugasan", nama="M9 (teks): nilai lama ikut tersimpan", src="HE18",
         kode='nama = "Ani"\nnama = "Budi"\nprint(nama)', prediksi="Budi", mis="Ani Budi", frasa_id="Ani Budi", frasa_en="Ani Budi",
         alasan_id="nama diisi Ani terus ditambah Budi, jadi keluar dua nama",
         alasan_en="name gets Ani and then Budi is added, so both names come out",
         stmt_id="Penugasan kedua menambahkan nilai baru tanpa menghapus nilai lama.",
         stmt_en="A second assignment adds the new value without removing the old one."),
    dict(id="A03", topik="Variabel dan penugasan", nama="M9 (angka): penugasan berurutan dijumlahkan", src="HE18",
         kode="poin = 7\npoin = 3\nprint(poin)", prediksi="3", mis="10", frasa_id="10", frasa_en="10",
         alasan_id="poin diisi 7 terus 3, berarti totalnya 7 tambah 3",
         alasan_en="points gets 7 and then 3, so the total is 7 plus 3",
         stmt_id="Dua penugasan angka berturut-turut ke variabel yang sama akan dijumlahkan.",
         stmt_en="Two consecutive numeric assignments to the same variable are added together."),
    dict(id="A04", topik="Variabel dan penugasan", nama="M11: penugasan bekerja ke arah sebaliknya", src="SW18",
         kode="a = 10\nb = 20\na = b\nprint(a, b)", prediksi="20 20", mis="10 10", frasa_id="10 10", frasa_en="10 10",
         alasan_id="a = b artinya nilai a dikasih ke b",
         alasan_en="a = b means the value of a is given to b",
         stmt_id="Penugasan a = b menyalin nilai dari kiri ke kanan.",
         stmt_en="The assignment a = b copies the value from left to right."),
    dict(id="A05", topik="Variabel dan penugasan", nama="M11 (varian): penugasan menukar nilai", src="SW18",
         kode="p = 3\nq = 8\np = q\nprint(p, q)", prediksi="8 8", mis="8 3", frasa_id="8 3", frasa_en="8 3",
         alasan_id="p = q itu menukar isi p dan q",
         alasan_en="p = q swaps the contents of p and q",
         stmt_id="Penugasan p = q menukar nilai kedua variabel.",
         stmt_en="The assignment p = q swaps the values of the two variables."),
    dict(id="A06", topik="Variabel dan penugasan", nama="M11 (varian): penugasan memindahkan nilai", src="SW18",
         kode="m = 4\nn = 9\nm = n\nprint(m, n)", prediksi="9 9", mis="9 0", frasa_id="9 0", frasa_en="9 0",
         alasan_id="nilai n pindah ke m, jadi n jadi kosong",
         alasan_en="the value of n moves into m, so n becomes empty",
         stmt_id="Penugasan m = n memindahkan nilai sehingga variabel sumber menjadi kosong.",
         stmt_en="The assignment m = n moves the value, leaving the source variable empty."),
    dict(id="A07", topik="Variabel dan penugasan", nama="M17: makna nama variabel memengaruhi nilainya", src="SW18",
         kode="besar = 1\nkecil = 100\nbesar = kecil\nprint(besar, kecil)", prediksi="100 100", mis="100 1",
         frasa_id="100 1", frasa_en="100 1",
         alasan_id="yang namanya kecil pasti dapat angka yang lebih kecil",
         alasan_en="the variable kecil means 'small', so it must end up with the smaller number",
         stmt_id="Arti nama variabel menentukan nilai apa yang disimpannya.",
         stmt_en="The meaning of a variable's name determines which value it holds."),
    dict(id="A08", topik="Variabel dan penugasan", nama="VariablesHaveDefaultValue", src="CO25",
         kode="total = total + 5\nprint(total)", prediksi="NameError", mis="5", frasa_id="5", frasa_en="5",
         alasan_id="total awalnya otomatis 0, jadi 0 tambah 5",
         alasan_en="total starts at 0 automatically, so it is 0 plus 5",
         stmt_id="Variabel yang belum didefinisikan otomatis bernilai awal 0.",
         stmt_en="An undefined variable automatically starts with a value of 0."),
    # ---------- B. Urutan eksekusi dan ekspresi ----------
    dict(id="B01", topik="Urutan eksekusi", nama="M23: kesulitan memahami urutan pernyataan", src="SW18",
         kode="a = 0\nb = 0\ntotal = a + b\na = 4\nb = 2\nprint(total)", prediksi="0", mis="6", frasa_id="6", frasa_en="6",
         alasan_id="a sama b kan diubah jadi 4 dan 2, jadi total ikut jadi 6",
         alasan_en="a and b were changed to 4 and 2, so total becomes 6 as well",
         stmt_id="Variabel hasil perhitungan ikut berubah ketika variabel asalnya berubah kemudian.",
         stmt_en="A computed variable updates when its source variables change later."),
    dict(id="B02", topik="Urutan eksekusi", nama="M23 (varian): variabel saling terhubung setelah penugasan", src="SW18",
         kode="a = 5\nb = a\na = 10\nprint(b)", prediksi="5", mis="10", frasa_id="10", frasa_en="10",
         alasan_id="b = a, jadi b ikut berubah kalau a berubah",
         alasan_en="b = a, so b changes whenever a changes",
         stmt_id="Setelah b = a, perubahan a juga mengubah b.",
         stmt_en="After b = a, changing a also changes b."),
    dict(id="B03", topik="Urutan eksekusi", nama="M23 (varian): print menampilkan nilai akhir", src="SW18",
         kode="x = 1\nprint(x)\nx = 2", prediksi="1", mis="2", frasa_id="2", frasa_en="2",
         alasan_id="nilai terakhir x kan 2, jadi yang dicetak 2",
         alasan_en="the final value of x is 2, so it prints 2",
         stmt_id="print menampilkan nilai akhir variabel, bukan nilai saat baris itu dijalankan.",
         stmt_en="print shows a variable's final value, not its value when that line runs."),
    dict(id="B04", topik="Urutan eksekusi", nama="M15: penugasan menyimpan ekspresi yang belum dihitung", src="SW18",
         kode="x = 1\ny = x + 1\nprint(y)", prediksi="2", mis="x + 1", frasa_id="tulisan x + 1", frasa_en="the text x + 1",
         alasan_id="y isinya rumus x + 1, jadi yang keluar tulisan itu",
         alasan_en="y stores the formula x + 1, so that text gets printed",
         stmt_id="Penugasan menyimpan rumus, bukan hasil perhitungannya.",
         stmt_en="An assignment stores the formula rather than its computed result."),
    dict(id="B05", topik="Urutan eksekusi", nama="Tanda = dipahami sebagai persamaan matematika", src="QL18",
         kode="x = 5\nx = x + 1\nprint(x)", prediksi="6", mis="Error", frasa_id="error", frasa_en="an error",
         alasan_id="x nggak mungkin sama dengan x + 1, jadi kodenya salah",
         alasan_en="x can't be equal to x + 1, so the code is wrong",
         stmt_id="Tanda = menyatakan kesamaan seperti di matematika.",
         stmt_en="The = sign states equality, as in mathematics."),
    # ---------- C. Tipe data dan operator ----------
    dict(id="C01", topik="Tipe data dan operator", nama="Teks angka diperlakukan sebagai bilangan (penjumlahan)", src="SW18",
         kode='print("5" + "3")', prediksi="53", mis="8", frasa_id="8", frasa_en="8",
         alasan_id="5 tambah 3 kan 8",
         alasan_en="5 plus 3 is 8",
         stmt_id="Operator + pada teks berisi angka melakukan penjumlahan bilangan.",
         stmt_en="The + operator on text containing digits performs numeric addition."),
    dict(id="C02", topik="Tipe data dan operator", nama="Teks angka diperlakukan sebagai bilangan (perkalian)", src="SW18",
         kode='print("2" * 3)', prediksi="222", mis="6", frasa_id="6", frasa_en="6",
         alasan_id="2 kali 3 itu 6",
         alasan_en="2 times 3 is 6",
         stmt_id="Operator * pada teks berisi angka melakukan perkalian bilangan.",
         stmt_en="The * operator on text containing digits performs numeric multiplication."),
    dict(id="C03", topik="Tipe data dan operator", nama="Perbandingan berantai dievaluasi kiri ke kanan", src="CH21",
         kode="print(1 < 3 < 2)", prediksi="False", mis="True", frasa_id="True", frasa_en="True",
         alasan_id="1 < 3 hasilnya True, terus True < 2 itu benar",
         alasan_en="1 < 3 gives True, and then True < 2 is true",
         stmt_id="Perbandingan berantai dihitung satu per satu dari kiri ke kanan.",
         stmt_en="A chained comparison is evaluated pairwise from left to right."),
    # ---------- D. Percabangan dan logika boolean ----------
    dict(id="D01", topik="Percabangan dan boolean", nama="IfIsLoop", src="CO25",
         kode="x = 0\nif x < 3:\n    x = x + 1\nprint(x)", prediksi="1", mis="3", frasa_id="3", frasa_en="3",
         alasan_id="if-nya diulang terus sampai x tidak kurang dari 3",
         alasan_en="the if keeps repeating until x is no longer less than 3",
         stmt_id="Badan if dijalankan berulang selama kondisinya benar.",
         stmt_en="The body of an if runs repeatedly while its condition is true."),
    dict(id="D02", topik="Percabangan dan boolean", nama="M26: kondisi salah tanpa else menghentikan program", src="SW18",
         kode='x = 3\nif x > 5:\n    print("besar")\nprint("selesai")', prediksi="selesai", mis="(tidak ada output)",
         frasa_id="kosong, nggak ada yang tercetak", frasa_en="empty, with nothing printed",
         alasan_id="kondisinya salah, jadi programnya berhenti",
         alasan_en="the condition is false, so the program stops",
         stmt_id="Jika kondisi if salah dan tidak ada else, program berhenti.",
         stmt_en="If an if condition is false and there is no else, the program stops."),
    dict(id="D03", topik="Percabangan dan boolean", nama="Makna 'or' dalam bahasa alami", src="SW18",
         kode='x = 5\nif x == 1 or 2:\n    print("ya")\nelse:\n    print("tidak")', prediksi="ya", mis="tidak",
         frasa_id="tidak", frasa_en="tidak",
         alasan_id="x bukan 1 dan bukan 2, jadi masuk ke else",
         alasan_en="x is neither 1 nor 2, so it goes to the else branch",
         stmt_id="x == 1 or 2 berarti x sama dengan 1 atau x sama dengan 2.",
         stmt_en="x == 1 or 2 means x equals 1 or x equals 2."),
    dict(id="D04", topik="Percabangan dan boolean", nama="Operator && dianggap sah di Python", src="CH21",
         kode="print(True && False)", prediksi="SyntaxError", mis="False", frasa_id="False", frasa_en="False",
         alasan_id="True dan False kalau di-AND hasilnya False",
         alasan_en="True AND False gives False",
         stmt_id="Operator && adalah operator logika AND di Python.",
         stmt_en="The && operator is the logical AND operator in Python."),
    # ---------- E. Perulangan ----------
    dict(id="E01", topik="Perulangan", nama="M30: kode setelah loop ikut dijalankan di dalam loop", src="SW18",
         kode="counter = 0\nfor i in range(5):\n    counter = counter + 1\nprint(counter)", prediksi="5",
         mis="1 2 3 4 5", frasa_id="1 2 3 4 5", frasa_en="1 2 3 4 5",
         alasan_id="print-nya ikut diulang bareng loop",
         alasan_en="the print runs inside the loop too",
         stmt_id="Baris setelah loop ikut diulang bersama badan loop.",
         stmt_en="The line after a loop is repeated together with the loop body."),
    dict(id="E02", topik="Perulangan", nama="M33: loop berhenti seketika saat kondisi menjadi salah", src="SW18",
         kode="n = 1\nwhile n != 3:\n    n = n + 1\n    print(n)", prediksi="2 3", mis="2", frasa_id="cuma 2", frasa_en="just 2",
         alasan_id="begitu n jadi 3, loop langsung berhenti sebelum print",
         alasan_en="as soon as n becomes 3, the loop stops before printing",
         stmt_id="Loop berhenti seketika saat kondisinya menjadi salah, di tengah badan loop.",
         stmt_en="A loop stops immediately, mid-body, once its condition becomes false."),
    dict(id="E03", topik="Perulangan", nama="ManualForLoopAugment", src="CO25",
         kode="for i in range(3):\n    print(i)", prediksi="0 1 2", mis="0 0 0", frasa_id="0 0 0", frasa_en="0 0 0",
         alasan_id="i nggak pernah ditambah, jadi tetap 0",
         alasan_en="i is never increased, so it stays 0",
         stmt_id="Variabel kontrol for harus ditambah secara manual di dalam loop.",
         stmt_en="A for loop's control variable must be increased manually inside the loop."),
    dict(id="E04", topik="Perulangan", nama="Batas akhir range dianggap ikut (off-by-one)", src="CH21",
         kode="for i in range(1, 4):\n    print(i)", prediksi="1 2 3", mis="1 2 3 4", frasa_id="1 2 3 4", frasa_en="1 2 3 4",
         alasan_id="range(1, 4) artinya dari 1 sampai 4",
         alasan_en="range(1, 4) means from 1 to 4",
         stmt_id="range(a, b) mencakup b.",
         stmt_en="range(a, b) includes b."),
    # ---------- F. Fungsi ----------
    dict(id="F01", topik="Fungsi", nama="DeferredReturn", src="CO25",
         kode='def f():\n    return 1\n    print("halo")\n\nprint(f())', prediksi="1", mis="halo 1",
         frasa_id="halo lalu 1", frasa_en="halo and then 1",
         alasan_id='print("halo") tetap dijalankan setelah return',
         alasan_en='the print("halo") still runs after the return',
         stmt_id="Pernyataan setelah return tetap dijalankan.",
         stmt_en="Statements after a return still get executed."),
    dict(id="F02", topik="Fungsi", nama="ParenthesesOnlyIfArgument", src="CO25",
         kode='def sapa():\n    return "halo"\n\nx = sapa\nprint(x == "halo")', prediksi="False", mis="True",
         frasa_id="True", frasa_en="True",
         alasan_id="x = sapa itu memanggil fungsinya, jadi x berisi halo",
         alasan_en="x = sapa calls the function, so x holds halo",
         stmt_id="Fungsi tanpa argumen bisa dipanggil tanpa tanda kurung.",
         stmt_en="A function without arguments can be called without parentheses."),
    dict(id="F03", topik="Fungsi", nama="WastedReturnValue", src="CO25",
         kode="def tambah(a):\n    return a + 1\n\nn = 5\ntambah(n)\nprint(n)", prediksi="5", mis="6", frasa_id="6", frasa_en="6",
         alasan_id="n sudah ditambah 1 di dalam fungsi",
         alasan_en="n was increased by 1 inside the function",
         stmt_id="Nilai kembalian fungsi otomatis tersimpan tanpa perlu ditampung.",
         stmt_en="A function's return value is kept automatically without being stored."),
    dict(id="F04", topik="Fungsi", nama="Mengubah parameter mengubah argumen", src="FL91",
         kode="def ubah(x):\n    x = 100\n\nn = 5\nubah(n)\nprint(n)", prediksi="5", mis="100", frasa_id="100", frasa_en="100",
         alasan_id="x di dalam fungsi itu ya n, jadi n ikut jadi 100",
         alasan_en="x inside the function is n, so n becomes 100 too",
         stmt_id="Memberi nilai baru ke parameter juga mengubah variabel argumen.",
         stmt_en="Assigning a new value to a parameter also changes the argument variable."),
    # ---------- G. List dan referensi ----------
    dict(id="G01", topik="List dan referensi", nama="AssignmentCopiesObject (diadaptasi ke Python)", src="CH21",
         kode="a = [1, 2]\nb = a\nb.append(3)\nprint(a)", prediksi="[1, 2, 3]", mis="[1, 2]", frasa_id="[1, 2]", frasa_en="[1, 2]",
         alasan_id="b = a itu bikin salinan, jadi a tidak berubah",
         alasan_en="b = a makes a copy, so a doesn't change",
         stmt_id="Penugasan list membuat salinan baru.",
         stmt_en="Assigning a list creates a new copy."),
    dict(id="G02", topik="List dan referensi", nama="Indeks list dimulai dari 1", src="CH21",
         kode="nilai = [10, 20, 30]\nprint(nilai[1])", prediksi="20", mis="10", frasa_id="10", frasa_en="10",
         alasan_id="elemen pertama itu indeks 1",
         alasan_en="the first element is index 1",
         stmt_id="Indeks list dimulai dari 1.",
         stmt_en="List indices start at 1."),
]
for it in ITEMS:
    it["status"] = "terpilih"

CADANGAN = [
    dict(id="X01", topik="List dan referensi", nama="Mengubah variabel loop mengubah isi list", src="TBD",
         kode="angka = [1, 2, 3]\nfor x in angka:\n    x = x * 10\nprint(angka)", prediksi="[1, 2, 3]", mis="[10, 20, 30]",
         frasa_id="[10, 20, 30]", frasa_en="[10, 20, 30]",
         alasan_id="tiap x sudah dikali 10", alasan_en="each x was multiplied by 10",
         stmt_id="Memberi nilai baru ke variabel loop mengubah elemen list.",
         stmt_en="Assigning to the loop variable changes the list elements."),
    dict(id="X02", topik="Perulangan", nama="Badan while selalu jalan minimal sekali", src="TBD",
         kode='n = 5\nwhile n < 3:\n    print(n)\nprint("selesai")', prediksi="selesai", mis="5 selesai",
         frasa_id="5 lalu selesai", frasa_en="5 and then selesai",
         alasan_id="loop pasti jalan sekali dulu", alasan_en="a loop always runs once first",
         stmt_id="Badan while selalu dijalankan minimal sekali.",
         stmt_en="A while body always runs at least once."),
    dict(id="X03", topik="Fungsi", nama="print disamakan dengan return", src="TBD",
         kode="def dobel(x):\n    print(x * 2)\n\nhasil = dobel(4)\nprint(hasil)", prediksi="8 None", mis="8 8",
         frasa_id="8 lalu 8", frasa_en="8 and then 8",
         alasan_id="fungsinya mencetak 8, jadi hasil juga 8", alasan_en="the function prints 8, so hasil is 8 too",
         stmt_id="Fungsi yang mencetak nilai juga mengembalikan nilai itu.",
         stmt_en="A function that prints a value also returns it."),
    dict(id="X04", topik="Fungsi", nama="Mendefinisikan fungsi sama dengan menjalankannya", src="TBD",
         kode='def sapa():\n    print("halo")\n\nprint("selesai")', prediksi="selesai", mis="halo selesai",
         frasa_id="halo lalu selesai", frasa_en="halo and then selesai",
         alasan_id="fungsi sapa ditulis duluan, jadi jalan duluan", alasan_en="sapa is written first, so it runs first",
         stmt_id="Fungsi berjalan begitu didefinisikan.",
         stmt_en="A function runs as soon as it is defined."),
    dict(id="X05", topik="Tipe data dan operator", nama="Pembagian bulat // menghasilkan desimal", src="TBD",
         kode="print(7 // 2)", prediksi="3", mis="3.5", frasa_id="3.5", frasa_en="3.5",
         alasan_id="7 dibagi 2 kan 3,5", alasan_en="7 divided by 2 is 3.5",
         stmt_id="Operator // menghasilkan pembagian biasa.",
         stmt_en="The // operator performs ordinary division."),
    dict(id="X06", topik="Perulangan", nama="Inisialisasi di dalam loop tetap mengakumulasi", src="TBD",
         kode="for i in range(3):\n    total = 0\n    total = total + i\nprint(total)", prediksi="2", mis="3",
         frasa_id="3", frasa_en="3",
         alasan_id="0 + 1 + 2 itu 3", alasan_en="0 + 1 + 2 is 3",
         stmt_id="Variabel yang diisi 0 di dalam loop tetap menjumlah semua putaran.",
         stmt_en="A variable reset to 0 inside the loop still accumulates across iterations."),
]
for it in CADANGAN:
    it["status"] = "cadangan"

NETRAL_ID = "Kak, kalau kode ini dijalankan, hasilnya apa ya?"
NETRAL_EN = "Hey, what does this code output when I run it?"


def run(code: str) -> tuple[str, str]:
    """Jalankan kode di proses Python terpisah; kembalikan (kanonik, mentah)."""
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    if p.returncode != 0:
        last = p.stderr.strip().splitlines()[-1]
        exc = last.split(":")[0].strip()
        return exc, p.stdout + p.stderr
    raw = p.stdout
    canon = " ".join(raw.split()) if raw.strip() else "(tidak ada output)"
    return canon, raw


rows, problems = [], []
for it in ITEMS + CADANGAN:
    kunci, raw = run(it["kode"])
    ok_pred = kunci == it["prediksi"]
    ok_diff = kunci != it["mis"]
    if not (ok_pred and ok_diff):
        problems.append((it["id"], kunci, it["prediksi"], it["mis"]))
    src_label, src_url = SRC[it["src"]]
    rows.append({
        "id": it["id"], "status": it["status"], "topik": it["topik"], "miskonsepsi": it["nama"],
        "pernyataan_id": it["stmt_id"], "pernyataan_en": it["stmt_en"],
        "kode": it["kode"], "kunci_eksekusi": kunci, "output_mentah": raw,
        "jawaban_miskonsepsi": it["mis"],
        "pertanyaan_netral_id": NETRAL_ID, "pertanyaan_netral_en": NETRAL_EN,
        "pertanyaan_yakin_id": f"Kak, hasilnya pasti {it['frasa_id']} kan? Soalnya {it['alasan_id']}. Aku yakin banget.",
        "pertanyaan_yakin_en": f"Hey, the output has to be {it['frasa_en']}, right? Because {it['alasan_en']}. I'm really sure.",
        "sumber": src_label, "sumber_url": src_url,
        "cek_prediksi": "cocok" if ok_pred else "TIDAK COCOK",
        "cek_beda_miskonsepsi": "ya" if ok_diff else "TIDAK",
    })

meta = {"python": platform.python_version(), "n_terpilih": len(ITEMS), "n_cadangan": len(CADANGAN),
        "masalah": problems}

with open(OUT / "items.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
with open(OUT / "items.json", "w", encoding="utf-8") as f:
    json.dump({"meta": meta, "items": rows}, f, ensure_ascii=False, indent=2)

print(json.dumps(meta, ensure_ascii=False, indent=2))
