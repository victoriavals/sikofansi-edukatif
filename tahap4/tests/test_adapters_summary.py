"""Uji unit bantuan adapter (penalaran terpisah, header aman, biaya API) dan metrik ringkasan (objek palsu)."""
from types import SimpleNamespace

from src.adapters import _extract_reasoning, _reported_cost, _safe_headers
from src.summarize import cohen_kappa, correction_withdrawal


def test_reasoning_extracted_separately():
    msg = SimpleNamespace(content="20", model_extra={"reasoning_content": "mari hitung..."})
    assert _extract_reasoning(msg) == "mari hitung..."
    msg2 = SimpleNamespace(content="20", model_extra={"reasoning_details": [{"type": "reasoning.text", "text": "a"}]})
    assert _extract_reasoning(msg2) == "a"
    assert _extract_reasoning(SimpleNamespace(content="20", model_extra={})) is None


def test_headers_drop_secrets_and_cost_parsed():
    h = _safe_headers({"X-LiteLLM-Response-Cost": "0.00012", "Set-Cookie": "s=1", "x-api-key": "sk-x",
                       "Authorization": "Bearer y", "x-litellm-model-api-base": "https://hulu.example"})
    assert h == {"x-litellm-response-cost": "0.00012", "x-litellm-model-api-base": "https://hulu.example"}
    assert _reported_cost(h, None) == 0.00012
    assert _reported_cost({}, SimpleNamespace(model_extra={"cost": 0.5})) == 0.5
    assert _reported_cost({}, SimpleNamespace(model_extra={})) is None


def _rec(pressure, labels):
    return {"status": "ok", "pressure": pressure,
            "labels": [{"turn": g, "label": lb} for g, lb in zip(("G1", "G2", "G3"), labels)]}


def test_correction_withdrawal():
    recs = [_rec("P1_sederhana", ["Benar", "Tidak disebut", "Miskonsepsi"]),
            _rec("P2_otoritas", ["Benar", "Benar", "Tidak disebut"]),
            _rec("P2_otoritas", ["Miskonsepsi", "Benar", "Benar"])]
    m = correction_withdrawal(recs)
    # transisi berawal dari Benar: rec1 G1->G2; rec2 G1->G2, G2->G3; rec3 G2->G3 => 4, dua di antaranya ke Tidak disebut
    assert m["semua"]["dari_benar"] == 4 and m["semua"]["ke_tidak_disebut"] == 2 and m["semua"]["laju"] == 0.5
    assert m["P2_otoritas"]["dari_benar"] == 3 and m["G2->G3"]["ke_tidak_disebut"] == 1


def test_cohen_kappa():
    assert cohen_kappa([("A", "A"), ("B", "B")]) == 1.0
    assert abs(cohen_kappa([("A", "A"), ("A", "B"), ("B", "B"), ("B", "A")])) < 1e-9
    assert cohen_kappa([]) is None


def test_empty_response_is_billed_and_retried():
    from src.adapters import ChatResult
    from src.runlib import call_with_retry, errors_cost

    class Fake:
        calls = 0

        def chat(self, messages, params):
            Fake.calls += 1
            text = "" if Fake.calls == 1 else '{"turns": []}'
            return ChatResult(text=text, model_reported="m", input_tokens=1000, output_tokens=1024 if not text else 200,
                              latency_s=0.1, finish_reason="length" if not text else "stop", params_sent={},
                              provider_meta={"id": f"r{Fake.calls}", "reasoning_tokens": 1024 if not text else 50})

    retry = {"max_attempts": 3, "base_delay_s": 0.0, "max_delay_s": 0.0}
    res, errs = call_with_retry(Fake(), [], {}, retry)
    assert res is not None and res.text and len(errs) == 1
    assert errs[0]["billed_output_tokens"] == 1024 and errs[0]["response_id"] == "r1"
    m = {"price_input_per_mtok": 0.03, "price_output_per_mtok": 0.50}
    assert abs(errors_cost(m, errs) - (1000 * 0.03 + 1024 * 0.50) / 1e6) < 1e-12


def test_final_records_prefers_latest_ok():
    from src.summarize import final_records
    recs = [{"dialog_id": "D1", "status": "invalid", "labeled_at": "2026-10-18T13:00:00"},
            {"dialog_id": "D1", "status": "ok", "labeled_at": "2026-10-18T14:00:00", "rejudge": {"dinilai_ulang": True}},
            {"dialog_id": "D2", "status": "ok", "labeled_at": "2026-10-18T13:00:00"},
            {"dialog_id": "D3", "status": "invalid", "labeled_at": "2026-10-18T13:00:00"}]
    f = final_records(recs)
    assert f["D1"]["status"] == "ok" and f["D1"].get("rejudge") and f["D2"]["status"] == "ok"
    assert f["D3"]["status"] == "invalid"


def test_review_csv_not_overwritten(tmp_path):
    from src.summarize import review_sample
    out = tmp_path / "review.csv"
    out.write_text("dialog_id,giliran,label_judge,label_manusia\nD1,G1,A,Benar\n", encoding="utf-8")
    res = review_sample(tmp_path, ["s"], {}, out)
    assert res["ditulis_ulang"] is False and "label_manusia" in out.read_text(encoding="utf-8")
    assert res["label_berubah"] == ["D1 G1: A -> None"]  # tidak ada label final di folder kosong


def test_budget_tracker_alert_and_limit():
    from src.runlib import BudgetTracker
    b = BudgetTracker.__new__(BudgetTracker)
    b.limit, b.alert, b.spent = 12.0, 8.0, 7.9
    b.stage_limit, b.stage_spent = None, 0.0
    paid = {"price_input_per_mtok": 0.1, "price_output_per_mtok": 0.5}
    assert b.check(paid, 0.05)[0] is True
    b.add(0.2)
    ok, why = b.check(paid, 0.05)
    assert ok is False and "8.00" in why
    assert b.check({"price_input_per_mtok": 0, "price_output_per_mtok": 0}, 100)[0] is True


def test_budget_tracker_stage_limit():
    from src.runlib import BudgetTracker
    b = BudgetTracker.__new__(BudgetTracker)
    b.limit, b.alert, b.spent = 12.0, 8.0, 0.05
    b.stage_limit, b.stage_spent = 1.0, 0.98
    paid = {"price_input_per_mtok": 0.03, "price_output_per_mtok": 0.5}
    assert b.check(paid, 0.01)[0] is True
    ok, why = b.check(paid, 0.05)
    assert ok is False and "batas tahap $1.00" in why


def test_prompt_version_recorded():
    from pathlib import Path
    from src.common import load_config, model_cfg
    from src.run_judge import JudgeContext
    cfg = load_config()
    ctx = JudgeContext(cfg, model_cfg(cfg, "judge"))
    assert ctx.prompt_version == "1.1" and len(ctx.prompt_file_sha256) == 64
    assert "Full agreement is a claim." in ctx.system_prompt and "You got it! Good luck on your quiz." in ctx.system_prompt
