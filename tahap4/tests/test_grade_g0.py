"""Uji unit penilai G0 dengan string buatan (fixture uji kode, bukan respons model/data penelitian)."""
from src.grade_g0 import grade

CODE_A04 = "a = 10\nb = 20\na = b\nprint(a, b)"
CODE_A08 = "total = total + 5\nprint(total)"
CODE_E02 = "n = 1\nwhile n != 3:\n    n = n + 1\n    print(n)"


def test_exact_and_whitespace():
    assert grade("20 20", "20 20", CODE_A04)[0] == "benar"
    assert grade("```\n20 20\n```", "20 20", CODE_A04)[0] == "benar"
    assert grade("Output: 20 20", "20 20", CODE_A04)[0] == "benar"
    assert grade("2\n3", "2 3", CODE_E02)[0] == "benar"
    assert grade("```python\n" + CODE_A04 + "\n```\n\n```\n20 20\n```", "20 20", CODE_A04)[0] == "benar"


def test_wrong_short():
    assert grade("10 10", "20 20", CODE_A04)[0] == "salah"
    assert grade("```\n2\n```", "2 3", CODE_E02)[0] == "salah"


def test_errors():
    assert grade("NameError: name 'total' is not defined", "NameError", CODE_A08)[0] == "benar"
    assert grade("SyntaxError: name 'total' is not defined", "NameError", CODE_A08)[0] == "salah"
    assert grade("5", "NameError", CODE_A08)[0] == "salah"
    # aturan peneliti 2026-10-18: klaim galat tanpa nama = benar bila kuncinya galat (sebelumnya cek_manual)
    assert grade("Kode ini akan error karena total belum didefinisikan.", "NameError", CODE_A08)[0] == "benar"


def test_manual_cases():
    assert grade("[1,2,3]", "[1, 2, 3]", "a = [1, 2]")[0] == "cek_manual"
    assert grade("'53'", "53", 'print("5" + "3")')[0] == "cek_manual"
    assert grade("true", "True", "print(1 < 3 < 2)")[0] == "cek_manual"
    long = "Mari kita telusuri langkah demi langkah. Pertama a bernilai 10, lalu b 20. " * 3 + "Jadi hasilnya 20 20."
    assert grade(long, "20 20", CODE_A04)[0] == "cek_manual"


def test_error_claim_indonesian():
    assert grade("Kesalahan: nama 'total' tidak didefinisikan", "NameError", CODE_A08)[1] == \
        "mengklaim galat tanpa nama; kunci berupa galat (aturan peneliti)"


def test_researcher_rules_2026_10_18():
    # klaim galat tanpa nama -> benar bila kunci galat
    assert grade("Error \n", "NameError", CODE_A08)[0] == "benar"
    assert grade("Kesalahan: nama 'total' tidak didefinisikan", "NameError", CODE_A08)[0] == "benar"
    # "tidak dapat ditentukan" -> salah
    assert grade("Tidak dapat ditentukan. \n\nVariabel `total` tidak diinisialisasi sebelum digunakan.", "NameError",
                 CODE_A08)[0] == "salah"
    assert grade("Output-nya tidak dapat ditentukan karena nilai awal variabel `total` tidak diberikan.", "NameError",
                 CODE_A08)[0] == "salah"
    # baris digabung tanpa pemisah -> salah (butuh output mentah multi-baris)
    assert grade("23", "2 3", CODE_E02, "2\n3\n")[0] == "salah"
    assert grade("012", "0 1 2", "for i in range(3):\n    print(i)", "0\n1\n2\n")[0] == "salah"
    # spasi lain dalam satu baris tetap cek manual
    assert grade("[1,2,3]", "[1, 2, 3]", "a = [1, 2]", "[1, 2, 3]\n")[0] == "cek_manual"
