import json

import pytest

import api, run_arm

# these build a real Run, which loads a life; CI has no LongMemEval download
needs_life = pytest.mark.skipif(not (run_arm.ROOT / "data" / "lives_v2" / "life_s0.json").exists(),
                                reason="needs data/lives_v2 from scripts/rebuild_lives.py")


@needs_life
def test_resume_rejects_a_different_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "BACKEND", "fake")
    d = tmp_path / "faithful_s0"
    d.mkdir()
    (d / "state.json").write_text(json.dumps({
        "arm": "faithful", "seed": 0, "phases_done": [], "memory": "",
        "mem": {"items": [], "next_id": 1}, "answers": [], "nights": [], "timing": [],
        "battery": {}, "transfer": [], "started": 0, "backend": "api",
    }), encoding="utf-8")
    run = run_arm.Run("faithful", 0, 0, tmp_path)
    with pytest.raises(api.RunAborted, match="started on backend api"):
        run.run()


def test_refuses_to_start_inside_a_published_run(tmp_path):
    d = tmp_path / "faithful_s0"
    d.mkdir()
    (d / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="published summary.json"):
        run_arm.Run("faithful", 0, 0, tmp_path)


@needs_life
def test_skipped_parts_are_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "BACKEND", "fake")
    run = run_arm.Run("faithful", 0, 0, tmp_path, skip_final=False, skip_battery=True, skip_transfer=True)
    monkeypatch.setattr(run, "ask_many", lambda *a, **k: [])
    run.run()
    st = json.loads((tmp_path / "faithful_s0" / "state.json").read_text(encoding="utf-8"))
    assert st["skipped"] == ["battery", "transfer"] and "all" in st["phases_done"]
