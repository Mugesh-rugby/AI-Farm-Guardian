import unittest
from math import isfinite

from backend.services.economic_engine import estimate_economic_risk
from backend.services.priority_engine import compute_priority


class EconomicRiskTests(unittest.TestCase):
    def test_missing_economic_inputs_are_not_fabricated(self):
        result = estimate_economic_risk(
            affected_area_pct=25,
            field_size_acres=2,
            crop_price_per_kg=None,
            expected_yield_kg_per_acre=None,
        )

        self.assertIsNone(result["crop_value_at_risk"])
        self.assertIsNone(result["estimated_financial_loss"])
        self.assertIsNone(result["potential_savings"])

    def test_value_at_risk_uses_recorded_inputs(self):
        result = estimate_economic_risk(
            affected_area_pct=25,
            field_size_acres=2,
            crop_price_per_kg=5,
            expected_yield_kg_per_acre=1000,
        )

        self.assertEqual(result["crop_value_at_risk"], 2500)
        self.assertIsNone(result["estimated_financial_loss"])

    def test_loss_requires_explicit_yield_reduction(self):
        result = estimate_economic_risk(
            affected_area_pct=25,
            field_size_acres=2,
            crop_price_per_kg=5,
            expected_yield_kg_per_acre=1000,
            yield_reduction_pct=20,
        )

        self.assertEqual(result["estimated_financial_loss"], 500)
        self.assertEqual(result["estimated_yield_loss_pct"], 20)

    def test_zero_affected_area_has_zero_exposure(self):
        result = estimate_economic_risk(
            affected_area_pct=0,
            field_size_acres=2,
            crop_price_per_kg=5,
            expected_yield_kg_per_acre=1000,
            yield_reduction_pct=20,
        )

        self.assertEqual(result["crop_value_at_risk"], 0)
        self.assertEqual(result["estimated_financial_loss"], 0)


class PriorityScoringTests(unittest.TestCase):
    def test_manual_assessment_does_not_claim_model_confidence(self):
        _, _, reasons, _, _ = compute_priority(
            severity="medium",
            confidence=None,
            affected_area_pct=10,
        )

        self.assertFalse(any("Model confidence" in reason for reason in reasons))

    def test_unavailable_weather_is_reported_without_weather_risk(self):
        _, _, reasons, factors, _ = compute_priority(
            severity="medium",
            confidence=None,
            affected_area_pct=10,
            weather=None,
        )

        self.assertIsNone(factors["weather_score"])
        self.assertTrue(any("Weather data unavailable" in reason for reason in reasons))

    def test_missing_inputs_do_not_receive_a_fabricated_score(self):
        score, tier, reasons, factors, _ = compute_priority(
            confidence=98.0,
            severity=None,
            affected_area_pct=None,
            growth_stage=None,
        )

        self.assertIsNone(score)
        self.assertEqual(tier, "UNASSESSED")
        self.assertEqual(factors["weights_used"], {})
        self.assertEqual(factors["confidence_pct"], 98.0)
        self.assertTrue(factors["missing_information"])
        self.assertTrue(any("excluded from urgency score" in reason for reason in reasons))

    def test_confidence_does_not_change_priority_score(self):
        low_confidence = compute_priority("high", 15.0, 25.0)[0]
        high_confidence = compute_priority("high", 99.0, 25.0)[0]

        self.assertEqual(low_confidence, high_confidence)

    def test_weather_and_growth_stage_alone_do_not_create_urgency(self):
        score, tier, _, factors, _ = compute_priority(
            severity=None,
            affected_area_pct=None,
            growth_stage="seedling",
            weather={"temperature": 28, "humidity": 88},
        )

        self.assertIsNone(score)
        self.assertEqual(tier, "UNASSESSED")
        self.assertEqual(factors["weights_used"], {})

    def test_non_finite_weather_values_are_excluded_from_scoring(self):
        score, _, _, factors, _ = compute_priority(
            severity="medium",
            affected_area_pct=None,
            weather={"temperature": float("nan"), "humidity": float("inf")},
        )

        self.assertTrue(isfinite(score))
        self.assertIsNone(factors["weather_score"])


if __name__ == "__main__":
    unittest.main()
