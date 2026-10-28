import random
import api, memory


def item(i, gist_words, details="", score=3, night=0):
    return {"id": f"m{i}", "gist": " ".join(["g"] * gist_words), "details": details, "score": score,
            "night": night, "born": night}


# ---- apply_delta ---------------------------------------------------------------------------------
def test_add_update_merge():
    items = [item(1, 2, "d1"), item(2, 2, "d2"), item(3, 2, "d3")]
    delta = {"add": [{"gist": "new", "details": "x", "score": 9}],
             "update": [{"id": "m1", "gist": "changed", "details": "y", "score": 0}],
             "merge": [{"ids": ["m2", "m3"], "gist": "both", "details": "z", "score": 4}]}
    out, next_id, rep = memory.apply_delta(items, delta, night=2, next_id=4)
    by_gist = {it["gist"]: it for it in out}
    assert [it["gist"] for it in out] == ["changed", "both", "new"]  # merged item takes the first source's slot
    assert by_gist["changed"]["score"] == 1 and by_gist["new"]["score"] == 5  # clamped to 1..5
    assert by_gist["both"]["born"] == 0 and by_gist["new"]["born"] == 2
    assert next_id == 6
    assert rep["added"] == 1 and rep["updated"] == 1 and rep["merged_groups"] == 1 and rep["merged_away"] == 2


def test_unknown_update_id_becomes_new_item_and_empty_gist_is_dropped():
    out, _, rep = memory.apply_delta([item(1, 2)], {"update": [{"id": "m99", "gist": "orphan", "details": "", "score": 3},
                                                             {"id": "m1", "gist": "  ", "details": "x", "score": 3}]}, 1, 2)
    assert [it["gist"] for it in out] == ["g g", "orphan"]
    assert rep["unknown_ids"] == 1 and rep["dropped_empty"] == 1


def test_apply_delta_does_not_mutate_input():
    items = [item(1, 2, "d")]
    memory.apply_delta(items, {"update": [{"id": "m1", "gist": "new", "details": "", "score": 3}]}, 1, 2)
    assert items[0]["gist"] == "g g"


# ---- enforce_cap ---------------------------------------------------------------------------------
def test_under_cap_untouched():
    items = [item(1, 3, "one two three."), item(2, 3, "four five six.")]
    out, rep = memory.enforce_cap(items, 100)
    assert rep["details_stripped"] == rep["items_deleted"] == 0 and out[0]["details"]


def test_details_fade_before_items_lowest_score_first():
    # rendering is 14 words: "- g g g" (4) + 3 detail words, twice
    items = [item(1, 3, "keep these words.", score=5), item(2, 3, "lose these words.", score=1)]
    out, rep = memory.enforce_cap(items, 11)
    assert len(out) == 2 and rep["items_deleted"] == 0
    assert out[0]["details"] and not out[1]["details"]
    assert memory.tokens(out) <= 11


def test_partial_cut_keeps_leading_sentences():
    # rendering is 9 words ("- g g" + 6); each detail line is budgeted one extra token for its line break
    items = [item(1, 2, "a b. c d. e f.")]
    out, rep = memory.enforce_cap(items, 7)
    assert out[0]["details"] == "a b. c d." and rep["details_partial"] == 1


def test_overshoot_after_partial_cut_deletes_items(monkeypatch):
    # BPE counts are not additive: here a long detail line counts higher on its own than inside the rendering.
    # Before the fix this ended at 22 tokens against a cap of 19.
    monkeypatch.setattr(api, "count_tokens",
                        lambda s: len(s.split()) + (10 if s.startswith("  ") and len(s.split()) >= 6 else 0))
    items = [item(1, 10, "a b. c d. e f.", score=1), item(2, 10, score=5)]
    out, rep = memory.enforce_cap(items, 19)
    assert memory.tokens(out) <= 19 and rep["items_deleted"] == 1


def test_never_over_cap_random():
    rng = random.Random(0)
    for _ in range(500):
        items = [item(i, rng.randint(1, 8),
                      " ".join("w " * rng.randint(1, 5) + "x." for _ in range(rng.randint(0, 4))).strip(),
                      score=rng.randint(1, 5), night=rng.randint(0, 3)) for i in range(1, rng.randint(2, 7))]
        cap = rng.randint(1, memory.tokens(items) + 5)
        out, rep = memory.enforce_cap(items, cap)
        assert memory.tokens(out) <= cap
        assert rep["tokens_after"] == memory.tokens(out)
