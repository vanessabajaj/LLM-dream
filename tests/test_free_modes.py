import json
import api, arms, judge


def test_fake_sleep_reply_fits_schema_and_adds_items():
    prompt = "TODAY'S TRANSCRIPT:\n" + "\n".join(f"User: message number {i} about the garden" for i in range(25))
    r = api._call_fake("sys", [{"role": "user", "content": prompt}], tag="t", json_schema=arms.SLEEP_SCHEMA)
    delta = json.loads(r["text"])
    assert len(delta["add"]) == 3 and delta["update"] == [] and delta["merge"] == []
    assert r["usd"] == 0.0


def test_fake_corruption_edits_requested_turns():
    prompt = "TRANSCRIPT:\n[4] User: alpha beta gamma\n[5] Assistant: one two\n\nEDITS TO MAKE:\n- index 4: swap\n"
    edits = json.loads(api._call_fake("sys", [{"role": "user", "content": prompt}], tag="t",
                                      json_schema=arms.CORRUPT_SCHEMA)["text"])["edits"]
    assert edits == [{"index": 4, "text": "gamma beta alpha"}]


def test_fake_judge_schema_gives_enum_value():
    r = api._call_fake("sys", [{"role": "user", "content": "grade"}], tag="t", json_schema=judge.SCHEMA)
    assert json.loads(r["text"]) == {"answer": "yes"}


def test_opus_only_judge_makes_one_call(monkeypatch):
    calls = []
    monkeypatch.setattr(judge, "MAIN_JUDGE", "opus")
    monkeypatch.setattr(judge, "judge_opus", lambda p, t: calls.append("opus") or (True, "yes"))
    monkeypatch.setattr(judge, "judge_openai", lambda p, t: calls.append("openai") or (False, "no"))
    assert judge.judge_both("prompt", "t") == (True, "yes", True, "yes") and calls == ["opus"]


def test_two_judges_by_default(monkeypatch):
    monkeypatch.setattr(judge, "MAIN_JUDGE", "gpt-5.6-luna")
    monkeypatch.setattr(judge, "judge_opus", lambda p, t: (True, "yes"))
    monkeypatch.setattr(judge, "judge_openai", lambda p, t: (False, "no"))
    assert judge.judge_both("prompt", "t") == (False, "no", True, "yes")
