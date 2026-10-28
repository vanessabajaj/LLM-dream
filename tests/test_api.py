import json
import pytest
import api

SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}}


def fake_reply(monkeypatch, body):
    monkeypatch.setattr(api, "check_cap", lambda: 0)
    monkeypatch.setattr(api, "check_budget", lambda: 1)
    monkeypatch.setattr(api, "_sub_once", lambda *a, **k: (body, 0.0, 1.0))


def test_refusal_with_schema_raises_refusal_not_abort(monkeypatch, offline):
    # a refused judge or sleep call has no structured output and may list no model; it must count as a refusal
    fake_reply(monkeypatch, {"stop_reason": "refusal", "result": "Details: `[bio]`", "usage": {}, "modelUsage": {}})
    with pytest.raises(api.Refusal) as e:
        api._call_subscription("sys", [{"role": "user", "content": "q"}], tag="t", json_schema=SCHEMA)
    assert e.value.category == "bio"
    rec = json.loads((offline / "cost.jsonl").read_text(encoding="utf-8"))
    assert rec["error"] == "REFUSAL"


def test_model_mismatch_still_aborts(monkeypatch):
    fake_reply(monkeypatch, {"stop_reason": "end_turn", "result": "hi", "usage": {}, "modelUsage": {"claude-opus-5": {}}})
    with pytest.raises(api.RunAborted):
        api._call_subscription("sys", [{"role": "user", "content": "q"}], tag="t")


def test_structured_output_returned(monkeypatch):
    fake_reply(monkeypatch, {"stop_reason": "end_turn", "result": "", "structured_output": {"answer": "yes"},
                             "usage": {"output_tokens": 3}, "modelUsage": {api.MODEL: {}}, "total_cost_usd": 0.01})
    r = api._call_subscription("sys", [{"role": "user", "content": "q"}], tag="t", json_schema=SCHEMA)
    assert json.loads(r["text"]) == {"answer": "yes"}


def test_log_cost_appends_jsonl_and_tallies(offline):
    for usd in (0.5, 0.25):
        api.log_cost({"provider": "openai", "usd": usd, "ts": api.V2_START + 1})
    lines = (offline / "cost.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["usd"] for l in lines] == [0.5, 0.25]
    assert api.real_spend_v2() == pytest.approx(0.75)
