"""
Render rencana dialog (Tahap 3).

Masukan : ../tahap2/out/items.json (bank butir) dan templates.yaml
Keluaran: out/dialogs_plan.jsonl   seluruh dialog G1-G3 (4.320 baris)
          out/g0_plan.jsonl        pertanyaan G0 (baseline knowledge check)
          out/template_check.csv   lembar cek kesetaraan makna ID vs EN
          out/contoh_dialog.md     contoh dialog lengkap untuk satu butir

Kompatibel Python 3.11+. Parafrase dipilih dengan seed tetap sehingga hasilnya reprodusibel.
"""
import csv
import hashlib
import itertools
import json
import random
from pathlib import Path

import yaml

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
SEED = 20261018

_cands = [HERE.parent / "tahap2" / "out" / "items.json", HERE.parent / "tahap2" / "items.json"]
ITEMS_PATH = next(p for p in _cands if p.exists())
ITEMS = [it for it in json.load(open(ITEMS_PATH, encoding="utf-8"))["items"] if it["status"] == "terpilih"]
T = yaml.safe_load(open(HERE / "templates.yaml", encoding="utf-8"))

# frasa dan alasan per bahasa diambil langsung dari definisi butir di build_bank.py
FIELDS = {}
BANK_PY = HERE.parent / "tahap2" / "build_bank.py"
src = BANK_PY.read_text(encoding="utf-8")
ns: dict = {"__file__": str(BANK_PY)}
exec(compile(src.split("NETRAL_ID")[0], "bank_defs", "exec"), ns)  # hanya definisi ITEMS, tanpa eksekusi kode butir
for it in ns["ITEMS"]:
    FIELDS[it["id"]] = it

FRAMINGS = ["netral", "yakin"]
PRESSURES = ["P1_sederhana", "P2_otoritas", "P3_sosial_afektif"]
LANGS = ["id", "en"]
MODELS = ["komersial_A", "komersial_B", "gemma2_9b_it", "sahabatai_9b_it"]
REPS = [1, 2, 3]


def kode_block(code: str) -> str:
    return f"```python\n{code}\n```"


def para_for(dialog_id: str) -> str:
    h = int(hashlib.sha256(f"{SEED}:{dialog_id}".encode()).hexdigest(), 16)
    return "A" if h % 2 == 0 else "B"


def fill(tmpl: str, item_id: str, lang: str) -> str:
    f = FIELDS[item_id]
    return tmpl.format(kode_block=kode_block(f["kode"]), frasa=f[f"frasa_{lang}"], alasan=f[f"alasan_{lang}"])


plan = []
for it, fr, pr, lg, md, rp in itertools.product(ITEMS, FRAMINGS, PRESSURES, LANGS, MODELS, REPS):
    did = f"{it['id']}-{fr}-{pr.split('_')[0]}-{lg}-{md}-r{rp}"
    pa = para_for(did)
    turns = [
        fill(T[lg]["G1"][fr][pa], it["id"], lg),
        fill(T[lg]["G2"][pr][pa], it["id"], lg),
        fill(T[lg]["G3"][pr][pa], it["id"], lg),
    ]
    plan.append({
        "dialog_id": did, "item_id": it["id"], "framing": fr, "pressure": pr, "lang": lg,
        "model": md, "rep": rp, "paraphrase": pa, "turns": turns,
        "key_output": it["kunci_eksekusi"], "misconception_output": it["jawaban_miskonsepsi"],
    })
random.Random(SEED).shuffle(plan)  # urutan eksekusi acak
for i, d in enumerate(plan):
    d["order"] = i

g0 = []
for it, lg, md, rp in itertools.product(ITEMS, LANGS, MODELS, REPS):
    g0.append({"g0_id": f"{it['id']}-G0-{lg}-{md}-r{rp}", "item_id": it["id"], "lang": lg, "model": md, "rep": rp,
               "prompt": T["G0"][lg].format(kode_block=kode_block(FIELDS[it["id"]]["kode"])),
               "key_output": it["kunci_eksekusi"]})

with open(OUT / "dialogs_plan.jsonl", "w", encoding="utf-8") as f:
    for d in plan:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
with open(OUT / "g0_plan.jsonl", "w", encoding="utf-8") as f:
    for d in g0:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

# Lembar cek kesetaraan makna (dipakai untuk back-translation oleh peneliti)
rows = []
for turn in ["G1", "G2", "G3"]:
    for cond, paras in T["id"][turn].items():
        for pa, txt in paras.items():
            rows.append({"giliran": turn, "kondisi": cond, "parafrase": pa,
                         "indonesia": txt.replace("\n\n{kode_block}\n\n", " [KODE] "),
                         "inggris": T["en"][turn][cond][pa].replace("\n\n{kode_block}\n\n", " [KODE] "),
                         "setara_makna (ya/tidak)": "", "catatan": ""})
with open(OUT / "template_check.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# Contoh dialog lengkap butir B02
ex = [d for d in plan if d["item_id"] == "B02" and d["model"] == "komersial_A" and d["rep"] == 1
      and d["pressure"] == "P2_otoritas" and d["framing"] == "yakin"]
with open(OUT / "contoh_dialog.md", "w", encoding="utf-8") as f:
    for d in sorted(ex, key=lambda x: x["lang"], reverse=True):
        f.write(f"## {d['dialog_id']} (parafrase {d['paraphrase']})\n\n")
        for i, t in enumerate(d["turns"], 1):
            f.write(f"**G{i}:**\n\n{t}\n\n")

summary = {
    "dialog": len(plan), "g0": len(g0), "butir": len(ITEMS),
    "parafrase_A": sum(d["paraphrase"] == "A" for d in plan),
    "parafrase_B": sum(d["paraphrase"] == "B" for d in plan),
    "baris_cek_template": len(rows),
}
print(json.dumps(summary, indent=2))
