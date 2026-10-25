"""Transparent initial scoring rules; weights require agronomist review."""
from math import isfinite
from typing import Optional, Dict, Any, Tuple, List

SCORING_METHOD = "rules-v1"
RISK_WEIGHTS = {
    "severity_score": 0.28,
    "area_score": 0.18,
    "stage_score": 0.14,
    "weather_score": 0.13,
    "economic_score": 0.12,
}
CATEGORY_THRESHOLDS = {"CRITICAL": 80.0, "HIGH": 60.0, "MEDIUM": 38.0}

SEVERITY_WEIGHT = {
    "critical": 100,
    "high": 92,
    "medium": 60,
    "low": 28,
    "healthy": 0
}

STAGE_VULNERABILITY = {
    "seedling": 95,      # Seedlings die quickly if infected
    "flowering": 88,     # Blight in flowering causes flower drop and total yield loss
    "vegetative": 62,    # Plants can regenerate some vegetative leaf tissue
    "maturity": 42,      # Crop already built grain/fruit, lower yield penalty
}

ISSUE_SPREAD_RISK = {
    "disease": 85,       # Airborne/waterborne fungal spores spread rapidly
    "pest": 75,          # Mobile chewing/sucking insects
    "water_stress": 45,  # Environmental, localized
    "nutrient": 35,      # Soil chemistry, localized
    "healthy": 0,
}


def _finite_number(value: Any, lower: float, upper: float) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and lower <= number <= upper else None


def sanitize_json_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json_values(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        return None
    return value


def compute_weather_risk_factor(weather: Optional[dict]) -> Tuple[Optional[float], List[str]]:
    """Apply initial weather heuristics only to present, in-range readings."""
    if not weather:
        return None, ["Weather data unavailable; it was not included in the score."]

    humidity = _finite_number(weather.get("humidity"), 0, 100)
    rain_prob = _finite_number(weather.get("rain_probability"), 0, 100)
    temp = _finite_number(weather.get("temperature"), -50, 60)

    risk = 0.0
    weather_reasons = []
    has_valid_reading = any(value is not None for value in (humidity, rain_prob, temp))

    if humidity is not None and humidity >= 80:
        risk += 35
        weather_reasons.append(f"High relative humidity recorded ({humidity}%).")
    elif humidity is not None and humidity >= 65:
        risk += 20
        weather_reasons.append(f"Elevated relative humidity recorded ({humidity}%).")

    if rain_prob is not None and rain_prob >= 60:
        risk += 30
        weather_reasons.append(f"Forecast precipitation probability is {rain_prob}%.")
    elif rain_prob is not None and rain_prob >= 35:
        risk += 15

    if temp is not None and 20 <= temp <= 32:
        risk += 25
        weather_reasons.append(f"Recorded temperature is {temp}°C.")
    elif temp is not None and temp > 35:
        risk += 15
        weather_reasons.append(f"High temperature recorded ({temp}°C).")

    if not has_valid_reading:
        return None, ["No valid weather readings were available for scoring."]
    if not weather_reasons:
        weather_reasons.append("Recorded weather did not cross the configured risk thresholds.")
    weather_reasons.append(f"Weather source: {weather.get('source', 'configured weather service')}.")
    return min(risk, 100.0), weather_reasons


def compute_economic_impact_factor(economic: Optional[dict]) -> Tuple[Optional[float], Optional[float], str]:
    """Calculates economic exposure only from user-provided estimates."""
    if not economic:
        return None, None, "Economic assumptions unavailable; none were included in the score."

    loss_pct = economic.get("estimated_yield_loss_pct", economic.get("projected_yield_loss_pct"))
    financial_loss = economic.get("estimated_financial_loss", economic.get("est_financial_loss"))
    loss_pct = _finite_number(loss_pct, 0, 100)
    financial_loss = _finite_number(financial_loss, 0, float("inf"))
    if loss_pct is None:
        return None, financial_loss, "No user-provided yield-loss assumption; economic impact was not scored."

    econ_score = min(loss_pct * 2.2, 100.0)
    summary = f"User-provided projected yield loss: {loss_pct:.1f}%."
    if financial_loss is not None:
        summary += f" Estimated exposure: ₹{financial_loss:,.0f}."
    return econ_score, financial_loss, summary


def compute_priority(
    severity: Optional[str] = None,
    confidence: Optional[float] = None,
    affected_area_pct: Optional[float] = None,
    issue_type: Optional[str] = None,
    growth_stage: Optional[str] = None,
    weather: Optional[dict] = None,
    economic: Optional[dict] = None,
    crop_type: Optional[str] = "Crop",
) -> Tuple[Optional[float], str, List[str], Dict[str, Any], str]:
    """Score only observed, supported factors and renormalize their weights.

    Returns ``(None, "UNASSESSED", ...)`` when no scoring input is available.
    Scan confidence is informational and never changes intervention urgency.
    """
    normalized_severity = (severity or "").strip().lower()
    normalized_stage = (growth_stage or "").strip().lower()
    available: Dict[str, float] = {}
    reasons: List[str] = []
    missing_information: List[str] = []

    severity_score = SEVERITY_WEIGHT.get(normalized_severity)
    if severity_score is not None:
        available["severity_score"] = float(severity_score)
        reasons.append(f"Farmer-recorded severity: {normalized_severity}.")
    else:
        missing_information.append("Observed severity")

    clamped_area = _finite_number(affected_area_pct, 0, 100)
    area_score = None
    if clamped_area is not None:
        area_score = min(clamped_area * 1.8 + (clamped_area ** 1.3) * 0.15, 100.0)
        available["area_score"] = area_score
        reasons.append(f"Recorded affected area: {clamped_area:.1f}%.")
    else:
        missing_information.append("Affected-area estimate")

    stage_score = STAGE_VULNERABILITY.get(normalized_stage)
    if stage_score is not None:
        available["stage_score"] = float(stage_score)
        reasons.append(f"Recorded crop growth stage: {normalized_stage}.")
    else:
        missing_information.append("Crop growth stage")

    weather_score, weather_reasons = compute_weather_risk_factor(weather)
    if weather_score is not None:
        available["weather_score"] = weather_score
        reasons.extend(weather_reasons)
    else:
        missing_information.append("Valid current or forecast weather")
        reasons.extend(weather_reasons)

    econ_score, financial_loss, econ_summary = compute_economic_impact_factor(economic)
    if econ_score is not None:
        available["economic_score"] = econ_score
        reasons.append(econ_summary)
    else:
        missing_information.append("User-provided yield-loss assumption")
        if economic:
            reasons.append(econ_summary)

    confidence_value = _finite_number(confidence, 0, 100)
    if confidence_value is None and confidence is not None:
        missing_information.append("Valid model confidence estimate")

    available_weight = sum(RISK_WEIGHTS[name] for name in available)
    has_issue_evidence = any(
        name in available
        for name in ("severity_score", "area_score", "economic_score")
    )
    if available_weight and has_issue_evidence:
        weighted_sum = sum(
            score * RISK_WEIGHTS[name] / available_weight
            for name, score in available.items()
        )
        final_score = round(max(0.0, min(weighted_sum, 100.0)), 1)
        if final_score >= CATEGORY_THRESHOLDS["CRITICAL"]:
            tier = "CRITICAL"
            suggested_timeframe = "Urgent field assessment recommended."
        elif final_score >= CATEGORY_THRESHOLDS["HIGH"]:
            tier = "HIGH"
            suggested_timeframe = "Prompt field review recommended."
        elif final_score >= CATEGORY_THRESHOLDS["MEDIUM"]:
            tier = "MEDIUM"
            suggested_timeframe = "Plan a field review and monitor for change."
        else:
            tier = "LOW"
            suggested_timeframe = "Continue routine monitoring."
    else:
        final_score = None
        tier = "UNASSESSED"
        suggested_timeframe = "Record field observations before assigning priority."
        reasons.append(
            "Severity, affected area, or a user-provided loss assumption is required before assigning urgency."
        )

    if confidence_value is not None:
        reasons.append(
            f"Scan confidence estimate: {confidence_value:.1f}% (informational; excluded from urgency score)."
        )
    if issue_type:
        reasons.append(
            "Spread risk was not scored because no validated field-specific spread estimate is available."
        )

    factors = {
        "scoring_method": SCORING_METHOD,
        "severity_score": round(available["severity_score"], 1) if "severity_score" in available else None,
        "area_score": round(area_score, 1) if area_score is not None else None,
        "spread_score": None,
        "stage_score": round(available["stage_score"], 1) if "stage_score" in available else None,
        "weather_score": round(weather_score, 1) if weather_score is not None else None,
        "economic_score": round(econ_score, 1) if econ_score is not None else None,
        "confidence_pct": round(confidence_value, 1) if confidence_value is not None else None,
        "financial_loss_est": round(financial_loss, 2) if financial_loss is not None else None,
        "weights_used": {
            name: round(RISK_WEIGHTS[name] / available_weight, 4)
            for name in available
        } if available_weight and has_issue_evidence else {},
        "missing_information": missing_information,
        "suggested_timeframe": suggested_timeframe,
    }

    return final_score, tier, reasons, factors, suggested_timeframe
