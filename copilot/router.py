import re
from typing import Any, Callable, Dict, Optional, Tuple
from pydantic import BaseModel

from copilot.skills import experiment_reader, metric_qa, movement_explainer


class SkillRegistryEntry(BaseModel):
    name: str
    description: str
    runner: Optional[Any] = None


SKILL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "metric_qa": {
        "name": "metric_qa",
        "description": "Answers natural-language metric queries by generating safe, validated DuckDB SQL.",
        "keywords": [
            "what was",
            "how many",
            "total",
            "average",
            "aov",
            "gmv",
            "orders",
            "revenue",
            "rate",
            "score",
            "trend",
            "highest",
            "lowest",
        ],
        "runner": metric_qa.run_metric_qa,
    },
    "experiment_reader": {
        "name": "experiment_reader",
        "description": "Calculates A/B test statistics, sample ratio mismatch, and statistical significance.",
        "keywords": [
            "a/b",
            "ab test",
            "experiment",
            "variant",
            "control",
            "sample size",
            "significance",
            "p-value",
            "uplift",
            "mde",
            "srm",
        ],
        "runner": experiment_reader.analyze_experiment,
    },
    "movement_explainer": {
        "name": "movement_explainer",
        "description": "Decomposes metric movement between two periods into volume effect, rate effect, and category/state contributions.",
        "keywords": [
            "why did",
            "decompose",
            "movement",
            "change between",
            "drop between",
            "increase between",
            "drivers of",
            "drove the",
        ],
        "runner": movement_explainer.run,
    },
}


def register_skill(
    name: str,
    description: str,
    keywords: list[str],
    runner: Callable,
) -> None:
    """Allows adding new skills dynamically without modifying UI code."""
    SKILL_REGISTRY[name] = {
        "name": name,
        "description": description,
        "keywords": keywords,
        "runner": runner,
    }


def route_intent(query: str) -> Tuple[str, float]:
    """
    Classifies a natural-language query into one of the registered skills based on keyword matching and intent.
    Returns (skill_name, confidence).
    """
    clean_q = query.lower().strip()

    best_skill = "metric_qa"
    max_hits = 0

    # Dynamically scan all registered skills (prioritizing specialized skills over metric_qa)
    for name, skill in SKILL_REGISTRY.items():
        if name == "metric_qa":
            continue
        hits = sum(1 for kw in skill.get("keywords", []) if kw in clean_q)
        if hits > max_hits:
            max_hits = hits
            best_skill = name

    if max_hits > 0:
        return best_skill, min(1.0, 0.7 + 0.1 * max_hits)

    # Default to Metric Q&A
    return "metric_qa", 0.90


def get_skill(name: str) -> Optional[Dict[str, Any]]:
    return SKILL_REGISTRY.get(name)
