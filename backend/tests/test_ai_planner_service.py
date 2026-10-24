import json
import unittest
from unittest.mock import AsyncMock, patch

from backend.services.ai_planner_service import generate_rescue_plan


class RescueDiagnosisTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnosis_fields_are_returned_as_rescue_guidance(self):
        response = {
            "description": "Possible early blight symptoms are visible; confirm in person.",
            "symptoms": ["Concentric lesions may be present."],
            "causes": ["A fungal disease is one possibility."],
            "organicTreatment": ["Remove affected leaves using clean tools."],
            "chemicalTreatment": ["Ask a licensed local expert about locally registered options."],
            "prevention": ["Monitor nearby plants for changes."],
            "recoveryTimeDays": [None, None],
        }
        with patch(
            "backend.services.ai_planner_service.chat_completion",
            new=AsyncMock(return_value=json.dumps(response)),
        ):
            plan = await generate_rescue_plan(
                crop="tomato",
                classifier_output="Tomato_Early_blight",
                severity="unassessed",
            )

        self.assertEqual(plan["description"], response["description"])
        self.assertEqual(plan["symptoms"], response["symptoms"])
        self.assertEqual(plan["causes"], response["causes"])
        self.assertEqual(plan["prevention"], response["prevention"])
        self.assertEqual(plan["prevention_text"], "\n".join(response["prevention"]))
        self.assertIn("clean tools", plan["organic_treatment"])
        self.assertIn("licensed local expert", plan["chemical_treatment"])
        self.assertEqual(plan["recovery_time"], "Not estimated from the available evidence.")
        self.assertTrue(plan["evidence_summary"].startswith("AI-generated general guidance"))

    async def test_diagnosis_receives_the_scan_image_for_vision_review(self):
        response = {
            "description": "The photo shows leaf spots consistent with the model prediction.",
            "symptoms": ["Small dark lesions are visible."],
            "causes": ["The image alone cannot confirm the underlying cause."],
            "organicTreatment": ["Remove visibly affected leaves with clean tools."],
            "chemicalTreatment": ["Ask a licensed local agricultural expert for advice."],
            "prevention": ["Monitor nearby plants for new symptoms."],
            "recoveryTimeDays": [None, None],
        }
        image_bytes = b"original-scan-image"
        with patch(
            "backend.services.ai_planner_service.chat_completion",
            new=AsyncMock(return_value=json.dumps(response)),
        ) as completion:
            plan = await generate_rescue_plan(
                crop="tomato",
                classifier_output="Tomato_Early_blight",
                image_bytes=image_bytes,
            )

        completion.assert_awaited_once()
        self.assertEqual(completion.await_args.kwargs["image_bytes"], image_bytes)
        self.assertIsNotNone(completion.await_args.kwargs["model"])
        self.assertTrue(plan["image_assessed"])
        self.assertIn("image diagnosis", plan["source"])

    async def test_incomplete_diagnosis_is_rejected(self):
        response = {
            "description": "Possible symptoms.",
            "symptoms": [],
            "causes": [],
            "organicTreatment": [],
            "chemicalTreatment": [],
            "prevention": [],
            "recoveryTimeDays": [-1, 7],
        }
        with patch(
            "backend.services.ai_planner_service.chat_completion",
            new=AsyncMock(return_value=json.dumps(response)),
        ):
            with self.assertRaises(ValueError):
                await generate_rescue_plan(crop="tomato", classifier_output="uncertain")

    async def test_unexpected_diagnosis_fields_are_rejected(self):
        response = {
            "description": "Possible symptoms need review.",
            "symptoms": [],
            "causes": [],
            "organicTreatment": [],
            "chemicalTreatment": [],
            "prevention": [],
            "recoveryTimeDays": [None, None],
            "extra": "not part of the requested schema",
        }
        with patch(
            "backend.services.ai_planner_service.chat_completion",
            new=AsyncMock(return_value=json.dumps(response)),
        ):
            with self.assertRaises(ValueError):
                await generate_rescue_plan(crop="tomato", classifier_output="uncertain")


if __name__ == "__main__":
    unittest.main()
