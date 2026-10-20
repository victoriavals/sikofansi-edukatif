"""Uji unit pengatur Tahap 5 lokal: ukuran potongan terhadap batas waktu jendela dan referensi pilot."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "model_prep"))

from jalankan_tahap5_lokal import LOCAL, chunk_size, pilot_reference  # noqa: E402
from src.common import load_config  # noqa: E402


def test_chunk_size_respects_deadline():
    assert chunk_size(14.0, 3600, 30) == 30                      # waktu cukup: potongan penuh
    assert chunk_size(14.0, 45 + 14 * 1.3 * 5 + 1, 30) == 5      # sisa waktu hanya cukup untuk 5 dialog
    assert chunk_size(14.0, 60, 30) == 0                          # tidak cukup untuk satu dialog: jangan mulai
    assert chunk_size(14.0, -10, 30) == 0                         # batas waktu sudah lewat


def test_pilot_reference_single_valued():
    cfg = load_config()
    for slot in LOCAL:
        ref = pilot_reference(cfg, slot)
        assert ref["quantization_level"] == "Q4_K_M"
        assert len(ref["digest"]) == 64
