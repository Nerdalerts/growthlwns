from typing import Any, Dict, Optional
from pydantic import BaseModel
from copilot.llm import LLMClient
from copilot.stats import two_proportion_ztest


class ExperimentVerdict(BaseModel):
    verdict: str  # "SHIP" | "DO NOT SHIP" | "INCONCLUSIVE" | "INVALID (SRM)"
    summary: str
    recommendation: str
    confidence_interval_text: str
    risk_flags: Optional[str] = None


class ExperimentResult(BaseModel):
    stats: Dict[str, Any]
    verdict: ExperimentVerdict


def analyze_experiment(
    n_control: int,
    conv_control: int,
    n_variant: int,
    conv_variant: int,
    alpha: float = 0.05,
    llm_client: Optional[LLMClient] = None,
) -> ExperimentResult:
    # 1. Deterministic statistics computed in code
    computed_stats = two_proportion_ztest(
        n_control=n_control,
        conv_control=conv_control,
        n_variant=n_variant,
        conv_variant=conv_variant,
        alpha=alpha,
    )

    # 2. Grounded system prompt strictly feeding numbers to LLM
    system_prompt = (
        "You are an expert A/B experiment analyst. "
        "You receive pre-computed statistics from an A/B test. "
        "You must NEVER calculate or invent numbers yourself. "
        "Strict rules:\n"
        "1. If has_srm is True, the experiment is INVALID due to Sample Ratio Mismatch. Verdict must be 'INVALID (SRM)'.\n"
        "2. If is_significant is False, the result is inconclusive. You MUST state 'INCONCLUSIVE' and cannot recommend shipping.\n"
        "3. If is_underpowered is True, you MUST explicitly flag that the experiment is underpowered.\n"
        "4. If is_significant is True and uplift_pct > 0, verdict is 'SHIP'.\n"
        "5. If is_significant is True and uplift_pct < 0, verdict is 'DO NOT SHIP'."
    )

    stats_prompt = (
        f"Pre-computed Experiment Statistics:\n"
        f"- Control: {computed_stats['conv_control']:,} / {computed_stats['n_control']:,} ({computed_stats['cvr_control']*100:.2f}% CVR)\n"
        f"- Variant: {computed_stats['conv_variant']:,} / {computed_stats['n_variant']:,} ({computed_stats['cvr_variant']*100:.2f}% CVR)\n"
        f"- Relative Uplift: {computed_stats['uplift_pct']:+.2f}%\n"
        f"- p-value: {computed_stats['p_value']:.4f} (alpha = {computed_stats['alpha']})\n"
        f"- 95% Confidence Interval: [{computed_stats['ci_low']*100:+.2f}pp, {computed_stats['ci_high']*100:+.2f}pp]\n"
        f"- Statistically Significant: {computed_stats['is_significant']}\n"
        f"- Sample Ratio Mismatch (SRM): {computed_stats['has_srm']} (p = {computed_stats['srm_p_value']:.4f})\n"
        f"- Underpowered: {computed_stats['is_underpowered']}\n\n"
        "Please provide the verdict, summary, and recommendation in JSON."
    )

    # If mock or no LLM client, generate deterministic verdict
    if not llm_client:
        llm_client = LLMClient()

    try:
        res = llm_client.call_structured(
            prompt=stats_prompt,
            system_prompt=system_prompt,
            response_model=ExperimentVerdict,
        )
        verdict = res.data
    except Exception:
        # Deterministic rule-based fallback if LLM is unavailable
        if computed_stats["has_srm"]:
            v = "INVALID (SRM)"
            rec = "Do not ship. Sample ratio mismatch indicates bucketing corruption."
        elif not computed_stats["is_significant"]:
            v = "INCONCLUSIVE"
            rec = "Continue running the experiment or gather more sample."
        elif computed_stats["uplift_pct"] > 0:
            v = "SHIP"
            rec = "Statistically significant positive uplift. Ship to 100% of users."
        else:
            v = "DO NOT SHIP"
            rec = "Statistically significant negative uplift. Abort variant."

        verdict = ExperimentVerdict(
            verdict=v,
            summary=f"Variant observed uplift of {computed_stats['uplift_pct']:+.2f}% with p={computed_stats['p_value']:.4f}.",
            recommendation=rec,
            confidence_interval_text=f"[{computed_stats['ci_low']*100:+.2f}pp to {computed_stats['ci_high']*100:+.2f}pp]",
            risk_flags="Underpowered" if computed_stats["is_underpowered"] else None,
        )

    return ExperimentResult(stats=computed_stats, verdict=verdict)
