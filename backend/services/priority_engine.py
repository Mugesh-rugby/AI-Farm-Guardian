"""
Intelligent Farm Risk Prioritization Engine (Rank 1 Feature)
The strongest differentiating feature of AI Farm Guardian.

A multi-criteria, context-grounded dynamic risk engine combining:
1. Disease Classification & Visual Severity
2. Leaf Area Affected % (Computer Vision Evidence)
3. Crop Phenological Growth Stage Vulnerability
4. Pathogen/Pest Spread Dynamics
5. Live Microclimate Weather Multipliers (humidity, temp, rain)
6. Economic Exposure / Financial Loss Stakes
7. AI Detection Confidence Calibration

Provides full explainability, factor attribution breakdown, and action urgency timeframes.
"""
from typing import Optional, Dict, Any, Tuple, List

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


def compute_weather_risk_factor(weather: Optional[dict]) -> Tuple[float, List[str]]:
    """Scores weather only when recent observations are available."""
    if not weather:
        return 0.0, ["Weather data unavailable; no weather risk was added."]

    humidity = weather.get("humidity")
    rain_prob = weather.get("rain_probability")
    temp = weather.get("temperature")

    risk = 0.0
    weather_reasons = []

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

    return min(risk, 100.0), weather_reasons


def compute_economic_impact_factor(economic: Optional[dict]) -> Tuple[float, float, str]:
    """Calculates economic exposure only from user-provided estimates."""
    if not economic:
        return 0.0, None, "Economic data unavailable; no financial exposure was added."

    loss_pct = economic.get("estimated_yield_loss_pct", economic.get("projected_yield_loss_pct"))
    financial_loss = economic.get("estimated_financial_loss", economic.get("est_financial_loss"))
    if loss_pct is None:
        return 0.0, financial_loss, "Yield-loss assumptions are unavailable."

    econ_score = min(loss_pct * 2.2, 100.0)
    summary = f"User-provided projected yield loss: {loss_pct:.1f}%."
    if financial_loss is not None:
        summary += f" Estimated exposure: ₹{financial_loss:,.0f}."
    return econ_score, financial_loss, summary


def compute_priority(
    severity: str,
    confidence: Optional[float],
    affected_area_pct: float,
    issue_type: str = "disease",
    growth_stage: Optional[str] = "vegetative",
    weather: Optional[dict] = None,
    economic: Optional[dict] = None,
    crop_type: Optional[str] = "Crop",
) -> Tuple[float, str, List[str], Dict[str, Any], str]:
    """
    Intelligent Multi-Factor Priority Computation.
    Returns: (score, tier, reasons, factors, suggested_timeframe)
    """
    sev_key = (severity or "low").strip().lower()
    stage_key = (growth_stage or "vegetative").strip().lower()
    issue_key = (issue_type or "disease").strip().lower()

    severity_score = SEVERITY_WEIGHT.get(sev_key, 50)
    stage_score = STAGE_VULNERABILITY.get(stage_key, 60)
    spread_score = ISSUE_SPREAD_RISK.get(issue_key, 55)

    # Area score: quadratic scale for high coverage
    clamped_area = max(0.0, min(float(affected_area_pct or 0.0), 100.0))
    area_score = min(clamped_area * 1.8 + (clamped_area ** 1.3) * 0.15, 100.0)

    weather_score, weather_reasons = compute_weather_risk_factor(weather)
    econ_score, financial_loss, econ_summary = compute_economic_impact_factor(economic)

    # Confidence calibration factor (0.60 to 1.0)
    conf_val = (
        max(min(float(confidence), 100.0), 0.0)
        if confidence is not None
        else None
    )

    # Core weighted blend (weights sum to 1.00)
    weighted_sum = (
        severity_score * 0.28 +
        area_score * 0.18 +
        spread_score * 0.15 +
        stage_score * 0.14 +
        weather_score * 0.13 +
        econ_score * 0.12
    )

    final_score = round(max(0.0, min(weighted_sum, 100.0)), 1)

    # Determine Tier and Action Window
    if final_score >= 80.0:
        tier = "CRITICAL"
        suggested_timeframe = "Emergency: Intervene within 12–24 hours"
    elif final_score >= 60.0:
        tier = "HIGH"
        suggested_timeframe = "Urgent: Intervene within 24–48 hours"
    elif final_score >= 38.0:
        tier = "MEDIUM"
        suggested_timeframe = "Scheduled: Address within 3–5 days"
    else:
        tier = "LOW"
        suggested_timeframe = "Routine: Monitor during regular weekly scouting"

    # Context-grounded explainability reasons
    reasons = []
    if severity_score >= 85:
        reasons.append(f"Recorded severity is {sev_key.upper()}.")
    elif severity_score >= 60:
        reasons.append("Recorded severity is moderate.")

    if clamped_area >= 40:
        reasons.append(f"Recorded affected area is {clamped_area:.1f}%.")
    elif clamped_area >= 20:
        reasons.append(f"Recorded affected area is {clamped_area:.1f}%.")

    if stage_score >= 85:
        reasons.append(f"Recorded growth stage is {stage_key.capitalize()}.")

    reasons.extend(weather_reasons)

    if econ_score >= 40:
        reasons.append(econ_summary)

    if conf_val is not None and conf_val < 70.0:
        reasons.append(f"Model confidence is {conf_val:.1f}%; verify the observation in the field.")

    if not reasons:
        reasons.append("No acute risk factors detected — crop condition is currently stable.")

    factors = {
        "severity_score": round(severity_score, 1),
        "area_score": round(area_score, 1),
        "spread_score": round(spread_score, 1),
        "stage_score": round(stage_score, 1),
        "weather_score": round(weather_score, 1),
        "economic_score": round(econ_score, 1),
        "confidence_pct": round(conf_val, 1) if conf_val is not None else None,
        "financial_loss_est": round(financial_loss, 0) if financial_loss is not None else None,
        "suggested_timeframe": suggested_timeframe,
    }

    return final_score, tier, reasons, factors, suggested_timeframe
