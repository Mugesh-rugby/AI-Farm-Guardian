import asyncio
import json
import unittest
from unittest.mock import patch

import httpx
from PIL import Image
import io

from backend.services import ai_service


class AiServiceTests(unittest.TestCase):
    def test_vision_completion_sends_compressed_image_and_uses_vision_model(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (128, 128), color=(45, 125, 55)).save(image_buffer, format="PNG")
        captured_payload = {}

        def handler(request):
            captured_payload.update(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"message": {"content": '{"description":"reviewed"}'}}]
            })

        client_class = httpx.AsyncClient

        async def run_request():
            def create_client(**kwargs):
                return client_class(transport=httpx.MockTransport(handler), **kwargs)

            with patch.object(ai_service, "GROQ_API_KEY", "test-key"), \
                    patch.object(ai_service, "GROQ_VISION_MODEL", "test-vision-model"), \
                    patch.object(ai_service.httpx, "AsyncClient", side_effect=create_client):
                return await ai_service.chat_completion(
                    "Return JSON.",
                    '{"classifier_output":"Tomato_Early_blight"}',
                    image_bytes=image_buffer.getvalue(),
                )

        result = asyncio.run(run_request())
        message = captured_payload["messages"][-1]["content"]

        self.assertEqual(result, '{"description":"reviewed"}')
        self.assertEqual(captured_payload["model"], "test-vision-model")
        self.assertEqual(captured_payload["response_format"], {"type": "json_object"})
        self.assertIn("Tomato_Early_blight", message[0]["text"])
        self.assertTrue(message[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))


if __name__ == "__main__":
    unittest.main()
