"""Uji unit alokasi sampling validasi manusia (angka buatan, bukan data penelitian)."""
from src.sample_validation import allocate


def test_allocation_sums_floors_caps_and_oversampling():
    counts = {"Benar": 300, "Miskonsepsi": 400, "Ambigu": 30, "Salah lain": 5, "Tidak disebut": 1}
    a = allocate(counts, 25, ambiguous_factor=3.0, min_per_label=2)
    assert sum(a.values()) == 25
    assert a["Tidak disebut"] == 1 and a["Salah lain"] >= 2          # lantai, dibatasi N
    # Ambigu disampling berlebih: proporsinya di sampel > proporsinya di populasi
    assert a["Ambigu"] / 25 > 30 / sum(counts.values())
    assert all(a[l] <= counts[l] for l in counts)
    assert a == allocate(counts, 25, 3.0, 2)                           # deterministik


def test_allocation_small_population():
    assert allocate({"Benar": 3, "Ambigu": 1}, 25, 3.0, 2) == {"Benar": 3, "Ambigu": 1}
    assert sum(allocate({"Benar": 10, "Miskonsepsi": 10, "Ambigu": 10}, 4, 3.0, 2).values()) == 4
