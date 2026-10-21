import math
from typing import Any, Dict, Optional, Tuple
import numpy as np
from scipy import stats


def check_srm(
    n_control: int,
    n_variant: int,
    expected_ratio: float = 0.5,
) -> Tuple[bool, float]:
    """
    Sample Ratio Mismatch (SRM) test using Pearson's Chi-Squared goodness-of-fit.
    Returns (has_srm: bool, p_value: float).
    Flagged if p-value < 0.001 (standard rigorous threshold).
    """
    total = n_control + n_variant
    if total == 0:
        return False, 1.0

    exp_control = total * expected_ratio
    exp_variant = total * (1.0 - expected_ratio)

    chi2 = ((n_control - exp_control) ** 2 / exp_control) + (
        (n_variant - exp_variant) ** 2 / exp_variant
    )
    p_val = float(1.0 - stats.chi2.cdf(chi2, df=1))
    has_srm = p_val < 0.001
    return has_srm, p_val


def calculate_mde(
    baseline_cr: float,
    n_per_variant: int,
    alpha: float = 0.05,
    power: float = 0.80,
) -> float:
    """
    Calculates the Minimum Detectable Effect (relative MDE) given sample size per variant.
    """
    if n_per_variant <= 0 or baseline_cr <= 0 or baseline_cr >= 1.0:
        return 0.0

    z_alpha = stats.norm.ppf(1.0 - alpha / 2.0)
    z_beta = stats.norm.ppf(power)

    # Approximate MDE using standard normal approximation
    var_baseline = 2.0 * baseline_cr * (1.0 - baseline_cr)
    abs_mde = (z_alpha + z_beta) * math.sqrt(var_baseline / n_per_variant)
    rel_mde = abs_mde / baseline_cr
    return float(rel_mde)


def two_proportion_ztest(
    n_control: int,
    conv_control: int,
    n_variant: int,
    conv_variant: int,
    alpha: float = 0.05,
    power: float = 0.80,
) -> Dict[str, Any]:
    """
    Computes two-proportion z-test, effect size, confidence intervals, SRM check, and power analysis.
    """
    if n_control <= 0 or n_variant <= 0:
        raise ValueError("Sample sizes must be greater than zero.")

    p_c = conv_control / n_control
    p_v = conv_variant / n_variant
    uplift = ((p_v - p_c) / p_c * 100.0) if p_c > 0 else 0.0

    # Pooled variance for hypothesis test
    p_pool = (conv_control + conv_variant) / (n_control + n_variant)
    se_pool = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n_control + 1.0 / n_variant))

    z_score = float((p_v - p_c) / se_pool) if se_pool > 0 else 0.0
    p_value = float(2.0 * (1.0 - stats.norm.cdf(abs(z_score))))

    # Unpooled standard error for confidence interval
    se_unpooled = math.sqrt(
        (p_c * (1.0 - p_c) / n_control) + (p_v * (1.0 - p_v) / n_variant)
    )
    z_crit = stats.norm.ppf(1.0 - alpha / 2.0)
    ci_low = float((p_v - p_c) - z_crit * se_unpooled)
    ci_high = float((p_v - p_c) + z_crit * se_unpooled)

    is_significant = p_value < alpha

    # SRM Check
    has_srm, srm_p_value = check_srm(n_control, n_variant)

    # Power & MDE Check
    mde = calculate_mde(p_c, n_control, alpha=alpha, power=power)
    # Check if test was underpowered for the observed effect size
    is_underpowered = abs(uplift / 100.0) < (mde * 0.7) and not is_significant

    return {
        "n_control": n_control,
        "conv_control": conv_control,
        "cvr_control": float(p_c),
        "n_variant": n_variant,
        "conv_variant": conv_variant,
        "cvr_variant": float(p_v),
        "uplift_pct": float(uplift),
        "z_score": z_score,
        "p_value": p_value,
        "alpha": alpha,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "is_significant": is_significant,
        "has_srm": has_srm,
        "srm_p_value": srm_p_value,
        "mde_rel": mde,
        "is_underpowered": is_underpowered,
    }


def welch_ttest(
    mean_c: float,
    std_c: float,
    n_c: int,
    mean_v: float,
    std_v: float,
    n_v: int,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Welch's t-test for continuous metrics (AOV, Revenue per User) with unequal variances.
    """
    if n_c <= 1 or n_v <= 1:
        raise ValueError("Sample sizes must be > 1 for t-test.")

    var_c = std_c ** 2
    var_v = std_v ** 2

    se = math.sqrt(var_c / n_c + var_v / n_v)
    t_stat = (mean_v - mean_c) / se if se > 0 else 0.0

    # Welch-Satterthwaite degrees of freedom
    df = (var_c / n_c + var_v / n_v) ** 2 / (
        ((var_c / n_c) ** 2 / (n_c - 1)) + ((var_v / n_v) ** 2 / (n_v - 1))
    )

    p_value = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=df)))
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=df))
    ci_low = float((mean_v - mean_c) - t_crit * se)
    ci_high = float((mean_v - mean_c) + t_crit * se)

    uplift = ((mean_v - mean_c) / mean_c * 100.0) if mean_c != 0 else 0.0
    is_significant = p_value < alpha

    return {
        "mean_control": mean_c,
        "mean_variant": mean_v,
        "uplift_pct": float(uplift),
        "t_stat": float(t_stat),
        "df": float(df),
        "p_value": p_value,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "is_significant": is_significant,
    }
