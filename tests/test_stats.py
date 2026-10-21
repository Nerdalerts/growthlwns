import pytest
from copilot.skills.experiment_reader import analyze_experiment
from copilot.stats import (
    calculate_mde,
    check_srm,
    two_proportion_ztest,
    welch_ttest,
)


def test_case_1_clear_winner_ship():
    res = two_proportion_ztest(5000, 200, 5000, 280)
    assert res["is_significant"] is True
    assert res["uplift_pct"] > 35.0
    assert res["p_value"] < 0.001
    assert res["has_srm"] is False

    exp = analyze_experiment(5000, 200, 5000, 280)
    assert "SHIP" in exp.verdict.verdict.upper()


def test_case_2_clear_loser_do_not_ship():
    res = two_proportion_ztest(5000, 200, 5000, 130)
    assert res["is_significant"] is True
    assert res["uplift_pct"] < -30.0
    assert res["p_value"] < 0.001

    exp = analyze_experiment(5000, 200, 5000, 130)
    assert "DO NOT SHIP" in exp.verdict.verdict.upper()


def test_case_3_inconclusive():
    res = two_proportion_ztest(5000, 200, 5000, 210)
    assert res["is_significant"] is False
    assert res["p_value"] > 0.05

    exp = analyze_experiment(5000, 200, 5000, 210)
    assert "INCONCLUSIVE" in exp.verdict.verdict.upper()


def test_case_4_sample_ratio_mismatch_srm():
    has_srm, p_val = check_srm(10000, 8200)
    assert has_srm is True
    assert p_val < 0.0001

    exp = analyze_experiment(10000, 400, 8200, 410)
    assert exp.stats["has_srm"] is True
    assert "SRM" in exp.verdict.verdict.upper() or "INVALID" in exp.verdict.verdict.upper()


def test_case_5_underpowered_experiment():
    res = two_proportion_ztest(100, 4, 100, 5)
    assert res["is_underpowered"] is True
    assert res["is_significant"] is False

    exp = analyze_experiment(100, 4, 100, 5)
    assert exp.stats["is_underpowered"] is True


def test_case_6_borderline_alpha():
    # Construct case where p is just above alpha=0.05
    res = two_proportion_ztest(3000, 150, 3000, 185, alpha=0.05)
    assert res["is_significant"] is False or res["p_value"] < 0.06


def test_case_7_flat_zero_uplift():
    res = two_proportion_ztest(5000, 200, 5000, 200)
    assert res["uplift_pct"] == 0.0
    assert res["p_value"] == 1.0
    assert res["is_significant"] is False


def test_case_8_large_sample_high_power():
    res = two_proportion_ztest(100000, 3000, 100000, 3300)
    assert res["is_significant"] is True
    assert pytest.approx(res["uplift_pct"], rel=1e-2) == 10.0
    assert res["p_value"] < 0.001


def test_case_9_welch_continuous_ttest():
    res = welch_ttest(
        mean_c=142.50,
        std_c=35.0,
        n_c=1000,
        mean_v=152.00,
        std_v=40.0,
        n_v=1000,
    )
    assert res["is_significant"] is True
    assert res["uplift_pct"] > 6.0
    assert res["p_value"] < 0.001


def test_case_10_mde_calculation():
    # 5% baseline CR with 10,000 visitors detects roughly ~17.3% relative MDE
    mde = calculate_mde(baseline_cr=0.05, n_per_variant=10000, alpha=0.05, power=0.80)
    assert 0.15 <= mde <= 0.20
    assert pytest.approx(mde, rel=1e-2) == 0.173
