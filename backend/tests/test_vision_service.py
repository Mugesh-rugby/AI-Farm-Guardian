import asyncio
import io
import json
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

from backend.services import vision_service


class VisionServiceTests(unittest.TestCase):
    def test_local_classifier_is_limited_to_its_trained_crop(self):
        with patch.object(vision_service, "_model", object()), \
                patch.object(vision_service, "_classes", ["Tomato_healthy", "Tomato_Early_blight"]):
            self.assertTrue(vision_service.local_model_supports_crop("cherry tomato"))
            self.assertFalse(vision_service.local_model_supports_crop("potato"))
            self.assertFalse(vision_service.local_model_supports_crop(None))

    def test_groq_response_becomes_unassessed_result_with_alternatives(self):
        result = vision_service._parse_groq_response(json.dumps({
            "diagnosis": "Early blight",
            "confidence": 72,
            "alternatives": [{"diagnosis": "Septoria leaf spot", "confidence": 18}],
        }))

        self.assertEqual(result.disease_name, "Early blight")
        self.assertEqual(result.confidence, 72)
        self.assertEqual(result.severity, "unassessed")
        self.assertIsNone(result.affected_area_pct)
        self.assertEqual(result.detector_source, f"groq:{vision_service.GROQ_VISION_MODEL}")
        self.assertEqual(result.alternatives[0]["class_name"], "Septoria leaf spot")

    def test_groq_response_rejects_out_of_range_confidence(self):
        with self.assertRaises(vision_service.VisionProviderError):
            vision_service._parse_groq_response(json.dumps({
                "diagnosis": "Early blight",
                "confidence": 120,
            }))

    def test_groq_request_includes_compressed_image_and_crop_context(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (100, 100), color="green").save(image_buffer, format="PNG")
        image_bytes = image_buffer.getvalue()
        captured_payload = {}

        def handler(request):
            captured_payload.update(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "diagnosis": "No visible disease symptoms",
                            "confidence": 64,
                            "alternatives": [],
                        })
                    }
                }]
            })

        client_class = httpx.AsyncClient

        async def run_request():
            def create_client(**kwargs):
                return client_class(transport=httpx.MockTransport(handler), **kwargs)

            with patch.object(vision_service, "GROQ_API_KEY", "test-key"), \
                    patch.object(vision_service.httpx, "AsyncClient", side_effect=create_client):
                return await vision_service.analyze_image_with_groq(image_bytes, "tomato")

        result = asyncio.run(run_request())
        image_url = captured_payload["messages"][0]["content"][1]["image_url"]["url"]
        prompt = captured_payload["messages"][0]["content"][0]["text"]

        self.assertTrue(image_url.startswith("data:image/jpeg;base64,"))
        self.assertIn("tomato", prompt)
        self.assertEqual(result.disease_name, "No visible disease symptoms")


if __name__ == "__main__":
    unittest.main()
