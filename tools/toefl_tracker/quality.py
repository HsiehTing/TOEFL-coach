from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Mapping

import yaml

from toefl_tracker.audio import AudioInspectionError


_POLICY_PATH = Path(__file__).parents[2] / "standards/ets-2026/audio-quality-policy.yaml"


@dataclass(frozen=True)
class QualityDecision:
    policy_version: int
    standard_basis: str
    usable: bool
    dimension_set: str


def _load_policy() -> dict:
    try:
        policy = yaml.safe_load(_POLICY_PATH.read_text(encoding="utf-8"))
        if not isinstance(policy, dict):
            raise ValueError
        if policy.get("policy_version") != 1 or policy.get("standard_basis") != "diagnostic_internal":
            raise ValueError
        thresholds = policy.get("thresholds_dbfs")
        if not isinstance(thresholds, dict) or set(thresholds) != {
            "clipping_peak_gte", "inaudible_peak_lte", "inaudible_mean_lte",
            "text_only_peak_lt", "text_only_mean_lt",
        }:
            raise ValueError
        return policy
    except (OSError, yaml.YAMLError, ValueError) as error:
        raise AudioInspectionError("invalid audio quality policy") from error


def _metric(metrics: Mapping[str, object], name: str) -> float:
    try:
        value = float(metrics[name])
    except (KeyError, TypeError, ValueError) as error:
        raise AudioInspectionError(f"invalid {name} metric") from error
    if not isfinite(value):
        raise AudioInspectionError(f"invalid {name} metric")
    return value


def quality_decision(metrics: Mapping[str, object]) -> QualityDecision:
    """Classify recording quality under the versioned local-only policy."""
    if not isinstance(metrics, Mapping):
        raise AudioInspectionError("invalid quality metrics")
    policy = _load_policy()
    thresholds = policy["thresholds_dbfs"]
    mean = _metric(metrics, "mean_dbfs")
    peak = _metric(metrics, "peak_dbfs")
    decodable = metrics.get("decodable", True)
    if not isinstance(decodable, bool):
        raise AudioInspectionError("invalid decodable metric")

    if (
        not decodable
        or peak >= float(thresholds["clipping_peak_gte"])
        or peak <= float(thresholds["inaudible_peak_lte"])
        or mean <= float(thresholds["inaudible_mean_lte"])
    ):
        return QualityDecision(1, "diagnostic_internal", False, "none")
    if mean < float(thresholds["text_only_mean_lt"]) or peak < float(thresholds["text_only_peak_lt"]):
        return QualityDecision(1, "diagnostic_internal", True, "text_only")
    return QualityDecision(1, "diagnostic_internal", True, "all")
