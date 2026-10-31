from printlint.advisory import community_advisory
from printlint.policy import ROOT


def test_advisory_filters_progress_and_score_is_not_gate():
    r = community_advisory(ROOT / "tests/fixtures/cube.stl", 0.4)
    assert r["advisory_only"]
    assert r["result"]["thickness"]["min_mm"] > 9
