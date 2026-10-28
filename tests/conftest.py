"""Offline test setup: harness/ on the path, Claude token counts replaced by a word count, call logs in a temp dir."""
import sys, pathlib
import pytest
from filelock import FileLock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "harness"))
import api


def words(s):
    return len(s.split())


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "count_tokens", words)
    monkeypatch.setattr(api, "CALLS_DIR", tmp_path)
    monkeypatch.setattr(api, "COST_FILE", tmp_path / "cost.jsonl")
    monkeypatch.setattr(api, "_cost_lock", FileLock(str(tmp_path / "cost.jsonl.lock")))
    monkeypatch.setattr(api, "_tally", api._CostTally())
    return tmp_path
