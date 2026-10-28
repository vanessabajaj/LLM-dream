import random
import pytest
import arms, battery


def sessions(n_turns=20):
    return [{"turns": [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i} says something here"}
                       for i in range(n_turns)]}]


def test_cap_for():
    assert arms.cap_for(0) == 19500 and arms.cap_for(10) == 124500 and arms.cap_for(99) == 124500
    assert arms.cap_for(0, scale=0.5) == 9750


def test_every_arm_has_a_night_step():
    assert set(arms.ARMS) == set(arms.NIGHT)


def test_format_log():
    log = arms.format_log([{"turns": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}])
    assert log == "Session 1\nUser: hi\nAssistant: hello\n"


def test_corrupt_random_rate_and_determinism(monkeypatch):
    monkeypatch.setattr(arms, "_corpus", (["p"], [f"whale{i}" for i in range(500)]))
    s = sessions(20)
    a, rep_a = arms.corrupt_random(s, random.Random("x"), 0.2)
    b, rep_b = arms.corrupt_random(s, random.Random("x"), 0.2)
    assert rep_a["n_corrupted"] == 4 and a == b  # same seed corrupts the same turns the same way
    changed = [i for i, t in enumerate(arms.flat_turns(a)) if t["content"] != s[0]["turns"][i]["content"]]
    assert len(changed) == 4 and s[0]["turns"][0]["content"] == "turn 0 says something here"  # input untouched


def test_nosleep_window_keeps_latest_turns_under_cap():
    mem, info = arms.night_nosleep({"window": ""}, sessions(20), [], None, "t", cap=30, night=0)
    assert info["tokens"] <= 30 and mem["window"].endswith("turn 19 says something here")


def test_parse_answers_json_and_fallback():
    assert battery.parse_answers('Sure: {"1": "Old", "2": "new"}', 3) == {1: "old", 2: "new", 3: None}
    assert battery.parse_answers("1. Old\n2: Yes\n3) no", 3) == {1: "old", 2: "yes", 3: "no"}


def test_score_drm():
    items = [{"kind": "studied"}, {"kind": "studied"}, {"kind": "lure"}, {"kind": "unrelated"}]
    res, rows = battery.score("drm", items, {1: "old", 2: "new", 3: "old", 4: "no record"})
    assert res["hit_rate"] == 0.5 and res["lure_false_alarm"] == 1.0
    assert res["unrelated_false_alarm"] is None and res["unanswered"] == 1


@pytest.mark.skipif(not (battery.ROOT / "external" / "LLM_CognitivePsychology" / "prompt.txt").exists(),
                    reason="needs the Cao repo clone from the README setup")
def test_battery_material_is_deterministic():
    a, b = battery.material(random.Random(0)), battery.material(random.Random(0))
    assert a == b and len(a["pl_study"]) == 48 and len(a["pl_items"]) == 96
    assert len(battery.study_sessions(a)) == 10
