import json
import analyze


def state_with_battery_night():
    nights = [{"day": d, "cap": 1000 + d, "tokens": 100 + d, "details_stripped": 1, "details_partial": 0,
               "items_deleted": 0, "output_tokens": 10 + d, "seconds": 1.0, "items": 5} for d in range(10)]
    nights.append({"day": 10, "cap": 2000, "tokens": 555, "details_stripped": 999, "details_partial": 0,
                   "items_deleted": 0, "output_tokens": 9999, "seconds": 1.0, "items": 6})
    return {"arm": "faithful", "seed": 0, "answers": [], "nights": nights, "phases_done": ["all"],
            "battery": {}, "transfer": [], "finished": 1}


def test_per_run_excludes_battery_night_from_ten_day_metrics():
    r = analyze.per_run(state_with_battery_night())
    assert r["nights"] == 10
    assert len(r["memory_tokens_by_night"]) == 10
    assert r["mean_memory_tokens"] == sum(100 + d for d in range(10)) / 10
    assert r["details_stripped"] == 10
    assert r["sleep_output_tokens"] == sum(10 + d for d in range(10)) / 10
    assert r["battery_night"]["tokens"] == 555
    assert r["battery_night"]["cap"] == 2000


def test_load_summaries_normalises_legacy_eleven_night_means(tmp_path):
    d = tmp_path / "faithful_s0"
    d.mkdir()
    arr = [100 + x for x in range(11)]
    caps = [1000 + x for x in range(11)]
    summary = {"arm": "faithful", "seed": 0, "nights": 11, "memory_tokens_by_night": arr, "cap_by_night": caps,
               "memory_fill_by_night": [a / c for a, c in zip(arr, caps)],
               "mean_memory_tokens": sum(arr) / 11, "mean_memory_fill": sum(a / c for a, c in zip(arr, caps)) / 11}
    (d / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    r = analyze.load_summaries(tmp_path)[("faithful", 0)]
    assert r["nights"] == 10
    assert r["memory_tokens_by_night"] == arr[:10]
    assert r["mean_memory_tokens"] == sum(arr[:10]) / 10
    assert r["battery_night"]["tokens"] == arr[10]
    assert r["legacy_includes_battery_totals"] is True
