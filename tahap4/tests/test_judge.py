"""Uji unit fungsi penilai: parsing prompt, urutan kandidat, validasi JSON, pemetaan label, seed."""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.common import check_phase, run_glob, seed_for
from src.run_judge import (build_system_prompt, build_user_prompt, candidate_order, consistency_flag, map_label,
                           parse_and_validate, parse_judge_prompt, stability_sample)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tahap3" / "judge_schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


def test_prompt_blocks_extracted_verbatim():
    system, user, examples = parse_judge_prompt(ROOT / "tahap3" / "judge_prompt.md")
    assert system.startswith("You are a careful annotator.")
    assert system.endswith("Keep each rationale under 25 words.")
    assert user.startswith("Program:\n{kode_block}") and user.endswith("[Tutor G3] {response_3}")
    md = (ROOT / "tahap3" / "judge_prompt.md").read_text(encoding="utf-8")
    assert examples.startswith("## Illustrative examples") and md.rstrip().endswith(examples)


def test_system_prompt_includes_examples():
    system, _, examples = parse_judge_prompt(ROOT / "tahap3" / "judge_prompt.md")
    full = build_system_prompt(system, examples)
    assert full.startswith(system) and full.endswith(examples)
    assert '"I said 5 earlier, but maybe your teacher is right. It\'s 10." | A' in full


def test_no_output_candidate_displayed_with_english_hint():
    rec = {"key_output": "selesai", "misconception_output": "(tidak ada output)",
           "turns": [{"user": "u", "response": "r"}] * 3}
    p = build_user_prompt(parse_judge_prompt(ROOT / "tahap3" / "judge_prompt.md")[1], rec, "print(1)",
                          {"A": "misconception", "B": "key"})
    assert "Candidate A: (tidak ada output) [no output]\nCandidate B: selesai" in p
    # flag konsistensi mengenali bentuk mentah maupun bentuk tampilan
    assert consistency_flag({"label": "A", "claimed_output": "(tidak ada output) [no output]"},
                            "(tidak ada output)", "selesai") is None
    assert consistency_flag({"label": "B", "claimed_output": "(tidak ada output)"},
                            "(tidak ada output)", "selesai") is not None


def test_stability_sample_deterministic():
    ids = [f"D{i:03d}" for i in range(60)]
    s1 = stability_sample(ids, 0.10, 20261019, "gemma2_9b_it")
    assert s1 == stability_sample(list(reversed(ids)), 0.10, 20261019, "gemma2_9b_it")
    assert len(s1) == 6 and set(s1) <= set(ids)
    assert stability_sample(ids, 0.10, 20261019, "sahabatai_9b_it") != s1


def test_estimate_only_allowed_for_main_phase():
    check_phase("tahap5", allow_main=False, estimate_only=True)
    try:
        check_phase("tahap5", allow_main=False)
        raise AssertionError("tahap5 tanpa izin harus ditolak")
    except SystemExit:
        pass


def test_candidate_order_deterministic_and_balanced():
    ids = [f"X{i}" for i in range(2000)]
    orders = [candidate_order(i, 20261018)["A"] for i in ids]
    assert orders == [candidate_order(i, 20261018)["A"] for i in ids]
    assert 0.45 < orders.count("key") / len(orders) < 0.55


def test_user_prompt_filled():
    rec = {"key_output": "5", "misconception_output": "10",
           "turns": [{"user": f"u{i}", "response": f"r{i} {{braces}}"} for i in range(1, 4)]}
    order = {"A": "misconception", "B": "key"}
    p = build_user_prompt(parse_judge_prompt(ROOT / "tahap3" / "judge_prompt.md")[1], rec, "print(5)", order)
    assert "Candidate A: 10\nCandidate B: 5" in p and "[Tutor G3] r3 {braces}" in p and "```python\nprint(5)\n```" in p


def test_validation_and_mapping():
    good = {"turns": [{"turn": g, "claimed_output": "5", "label": "B", "rationale": "x"} for g in ("G1", "G2", "G3")]}
    obj, problems = parse_and_validate("```json\n" + json.dumps(good) + "\n```", VALIDATOR)
    assert obj == good and problems == []
    bad = {"turns": good["turns"][:2]}
    assert parse_and_validate(json.dumps(bad), VALIDATOR)[0] is None
    swapped = {"turns": [good["turns"][1], good["turns"][0], good["turns"][2]]}
    assert parse_and_validate(json.dumps(swapped), VALIDATOR)[0] is None
    assert parse_and_validate("bukan json", VALIDATOR)[0] is None
    order = {"A": "misconception", "B": "key"}
    assert [map_label(x, order) for x in ("A", "B", "AMBIGUOUS", "OTHER", "NONE")] == \
           ["Miskonsepsi", "Benar", "Ambigu", "Salah lain", "Tidak disebut"]


def test_consistency_flag():
    assert consistency_flag({"label": "B", "claimed_output": "10 10"}, "10 10", "20 20") is not None
    assert consistency_flag({"label": "B", "claimed_output": "20 20"}, "10 10", "20 20") is None
    assert consistency_flag({"label": "NONE", "claimed_output": None}, "10 10", "20 20") is None


def test_seed_and_glob():
    did = "A04-netral-P1-id-gemma2_9b_it-r1"
    assert seed_for(did) == int(hashlib.sha256(did.encode()).hexdigest(), 16) % 2**31
    import fnmatch
    pat = run_glob("g0_gemma2_9b_it__gemma3_4b_dev")
    assert fnmatch.fnmatch("g0_gemma2_9b_it__gemma3_4b_dev_20261018-143853.jsonl", pat)
    assert not fnmatch.fnmatch("g0_gemma2_9b_it__gemma3_4b_dev_openai_compat_20261018-144555.jsonl", pat)


def test_frozen_prompt_hash_matches_config():
    import hashlib
    from src.common import load_config
    cfg = load_config()
    frozen = cfg["judge"]["frozen_sha256"]
    for name, h in frozen.items():
        assert hashlib.sha256((ROOT / "tahap3" / name).read_bytes()).hexdigest() == h, name
