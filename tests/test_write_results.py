"""The results prose is computed from results/summary_v2.json; check it against the committed numbers."""
import write_results as wr


def test_no_negative_zero():
    assert wr.f({"mean": -0.004, "sd": 0.02}) == "0 ± 2"
    assert wr.f(-0.004) == "0"


def test_outcome_matches_committed_summary():
    lead = wr.outcome_lead()
    assert "not supported" in lead and "8 of 8 noisy arms" in lead
    assert "Random noise, 5 percent" in lead  # the one arm above faithful on recall beyond one seed SD


def test_battery_ranges_are_computed():
    assert wr.percent_range("drm_lure_fa") == "0 percent in every arm"
    assert wr.percent_range("drm_hit") == "81 to 100 percent"
