import base64
import io

import httpx
from PIL import Image, UnidentifiedImageError

try:
    from config import GROQ_API_KEY, GROQ_MODEL, GROQ_VISION_MODEL
except ImportError:
    from backend.config import GROQ_API_KEY, GROQ_MODEL, GROQ_VISION_MODEL

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProviderError(httpx.HTTPError):
    pass


def is_configured() -> bool:
    return bool(GROQ_API_KEY)


def _image_data_url(image_bytes: bytes) -> str:
    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise GroqProviderError("The saved crop scan image cannot be read. Upload the photo again.") from error

    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


async def chat_completion(
    system_prompt: str,
    user_message: str,
    history=None,
    image_bytes: bytes | None = None,
    model: str | None = None,
):
    """Calls Groq's OpenAI-compatible chat endpoint. Returns None if no key
    is configured -- caller must show a 'Connect API' state, never a canned
    fake answer."""
    if not GROQ_API_KEY:
        return None

    messages = [{"role": "system", "content": system_prompt}]
    for h in (history or [])[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    content = user_message
    if image_bytes is not None:
        content = [
            {"type": "text", "text": user_message},
            {"type": "image_url", "image_url": {"url": _image_data_url(image_bytes)}},
        ]
    messages.append({"role": "user", "content": content})
    selected_model = model or (GROQ_VISION_MODEL if image_bytes is not None else GROQ_MODEL)
    model_setting = "GROQ_VISION_MODEL" if image_bytes is not None else "GROQ_MODEL"

    async with httpx.AsyncClient(timeout=httpx.Timeout(65.0, connect=10.0)) as client:
        resp = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": selected_model,
                "messages": messages,
                "temperature": 0.2 if image_bytes is not None else 0.4,
                **({"response_format": {"type": "json_object"}} if image_bytes is not None else {}),
            },
        )
        if resp.status_code in (400, 404):
            raise GroqProviderError(
                f"Groq model '{selected_model}' is unavailable. Update {model_setting} in backend/.env."
            )
        if resp.status_code == 401:
            raise GroqProviderError("Groq rejected the API key. Check GROQ_API_KEY in backend/.env.")
        if resp.status_code == 429:
            raise GroqProviderError("Groq rate limit reached. Please wait and retry.")
        if resp.is_error:
            raise GroqProviderError(f"Groq request failed with HTTP {resp.status_code}.")
        data = resp.json()
        return data["choices"][0]["message"]["content"]
