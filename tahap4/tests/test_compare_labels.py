"""Uji unit pembanding label v1.0 vs v1.1 (rekaman buatan, bukan data penelitian)."""
from src.compare_labels import compare_sets


def _rec(did, letters, analyses, slot="s"):
    return {"dialog_id": did, "status": "ok", "slot": slot, "pressure": "P1_sederhana", "kandidat_A": "1",
            "kandidat_B": "2", "labeled_at": "2026-10-19T00:00:00",
            "labels": [{"turn": t, "label_judge": l, "label": a, "claimed_output": None, "rationale": "r"}
                       for t, l, a in zip(("G1", "G2", "G3"), letters, analyses)]}


def test_compare_sets_counts_changes_and_agreement():
    base = {"D1": _rec("D1", "ABB", ["Benar", "Miskonsepsi", "Miskonsepsi"]),
            "D2": _rec("D2", ["A", "OTHER", "B"], ["Benar", "Salah lain", "Miskonsepsi"])}
    new = {"D1": _rec("D1", "ABB", ["Benar", "Miskonsepsi", "Miskonsepsi"]),
           "D2": _rec("D2", ["A", "AMBIGUOUS", "B"], ["Benar", "Ambigu", "Miskonsepsi"])}
    c = compare_sets(base, new)
    assert c["giliran"] == 6 and c["sepakat"] == 5
    assert [(x["dialog_id"], x["giliran"], x["label_v10"], x["label_v11"]) for x in c["berubah"]] == \
           [("D2", "G2", "OTHER", "AMBIGUOUS")]
    assert c["transisi_analisis"] == {"Salah lain -> Ambigu": 1}
    assert c["per_giliran"]["G2"]["kesepakatan"] == 0.5
