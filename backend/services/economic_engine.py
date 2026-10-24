"""Calculate crop-value exposure and optional losses from farmer-provided inputs."""
from typing import Optional


def estimate_economic_risk(
    affected_area_pct: float,
    field_size_acres: Optional[float],
    crop_price_per_kg: Optional[float],
    expected_yield_kg_per_acre: Optional[float],
    yield_reduction_pct: Optional[float] = None,
    treatment_cost: Optional[float] = None,
):
    area_fraction = max(0.0, min(float(affected_area_pct or 0.0), 100.0)) / 100.0
    expected_yield = None
    crop_value_at_risk = None
    if (
        field_size_acres is not None
        and crop_price_per_kg is not None
        and expected_yield_kg_per_acre is not None
        and field_size_acres > 0
        and crop_price_per_kg >= 0
        and expected_yield_kg_per_acre >= 0
    ):
        expected_yield = field_size_acres * expected_yield_kg_per_acre
        crop_value_at_risk = round(expected_yield * crop_price_per_kg * area_fraction, 2)

    estimated_loss = None
    estimated_yield_loss_pct = None
    if yield_reduction_pct is not None and 0 <= yield_reduction_pct <= 100:
        estimated_yield_loss_pct = round(yield_reduction_pct, 1)
        if expected_yield is not None:
            estimated_loss = round(
                expected_yield * (yield_reduction_pct / 100) * crop_price_per_kg * area_fraction,
                2,
            )
    result = {
        "estimated_yield_loss_pct": estimated_yield_loss_pct,
        "crop_value_at_risk": crop_value_at_risk,
        "estimated_financial_loss": estimated_loss,
        "treatment_cost_estimate": treatment_cost,
        "potential_savings": None,
        "currency": "INR",
        "assumptions": [
            "Affected-area exposure is based on the recorded affected-area percentage.",
            "Estimated loss is calculated only when the user supplies a yield-reduction assumption.",
            "This scenario estimate is not a measured loss or a guaranteed saving.",
        ],
    }
    return result
