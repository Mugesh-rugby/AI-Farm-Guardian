import base64
import io
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

try:
    from config import GROQ_API_KEY, GROQ_VISION_MODEL, MODEL_CHECKPOINT
except ImportError:
    from backend.config import GROQ_API_KEY, GROQ_VISION_MODEL, MODEL_CHECKPOINT

logger = logging.getLogger(__name__)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_model: Any = None
_transform: Any = None
_classes: list[str] = []
_device: Any = None
_model_error: str | None = None
_model_name: str | None = None
_model_metrics: dict[str, Any] = {}


@dataclass
class AnalysisResult:
    disease_name: str
    confidence: float
    severity: str
    affected_area_pct: float | None
    issue_type: str
    detector_source: str
    alternatives: list[dict[str, Any]]


class VisionProviderError(RuntimeError):
    pass


def initialize_model() -> bool:
    global _model, _transform, _classes, _device, _model_error, _model_name, _model_metrics

    _model = None
    _transform = None
    _classes = []
    _device = None
    _model_error = None
    _model_name = None
    _model_metrics = {}
    if not MODEL_CHECKPOINT.is_file():
        _model_error = f"Trained crop checkpoint is not installed: {MODEL_CHECKPOINT}"
        logger.info("%s; Groq vision will be used when configured.", _model_error)
        return bool(GROQ_API_KEY)

    try:
        import timm
        import torch
        from timm.data import create_transform

        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(MODEL_CHECKPOINT, map_location=_device, weights_only=True)
        _classes = checkpoint["classes"]
        _model_metrics = {
            "held_out_test_accuracy": checkpoint.get("held_out_test_accuracy"),
            "held_out_test_samples": checkpoint.get("held_out_test_samples"),
        }
        if not _classes or not isinstance(_classes, list):
            raise ValueError("Checkpoint has no valid class mapping.")

        architecture = checkpoint.get("architecture", "tf_efficientnetv2_s")
        _model_name = architecture
        model = timm.create_model(
            architecture,
            pretrained=False,
            num_classes=len(_classes),
        )
        model.load_state_dict(checkpoint["state_dict"], strict=True)
        model.eval()
        model.to(_device)
        _model = model
        _transform = create_transform(**checkpoint["data_config"], is_training=False)
        return True
    except (ImportError, KeyError, OSError, RuntimeError, ValueError) as error:
        _model_error = f"Trained crop model could not be loaded: {error}"
        logger.error("%s; using Groq vision if configured.", _model_error)
        return bool(GROQ_API_KEY)


def model_status() -> dict[str, Any]:
    local_available = _model is not None
    groq_available = bool(GROQ_API_KEY)
    provider = "local" if local_available else "groq" if groq_available else None
    model_name = (
        _model_name
        if local_available
        else GROQ_VISION_MODEL if groq_available else None
    )
    status = {
        "available": local_available or groq_available,
        "provider": provider,
        "model": model_name,
        "groq_available": groq_available,
        "groq_model": GROQ_VISION_MODEL if groq_available else None,
        "device": str(_device) if local_available else None,
        "error": _model_error if not groq_available else None,
    }
    if local_available:
        status["classes"] = _classes
        status.update(_model_metrics)
    return status


def local_model_supports_crop(crop_name: str | None) -> bool:
    if _model is None or not crop_name:
        return False
    normalized_crop = "".join(character for character in crop_name.lower() if character.isalnum())
    supported_crops = {
        "".join(character for character in class_name.split("_", 1)[0].lower() if character.isalnum())
        for class_name in _classes
    }
    return any(crop in normalized_crop for crop in supported_crops)


def _decode_image(image_bytes: bytes) -> tuple[Image.Image, str]:
    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("Uploaded file is not a readable image.") from error

    if image.width < 64 or image.height < 64:
        raise ValueError("Image dimensions must be at least 64 by 64 pixels.")

    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    return image, base64.b64encode(buffer.getvalue()).decode("ascii")


def _parse_groq_response(content: str) -> AnalysisResult:
    try:
        result = json.loads(content)
        diagnosis = result["diagnosis"]
        confidence_value = result["confidence"]
        alternatives = result.get("alternatives", [])
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as error:
        raise VisionProviderError("Groq returned an invalid crop assessment. Please retry the scan.") from error

    if not isinstance(diagnosis, str) or not diagnosis.strip():
        raise VisionProviderError("Groq did not return a crop assessment. Please retry with a clearer image.")
    if isinstance(confidence_value, bool) or not isinstance(confidence_value, (int, float)):
        raise VisionProviderError("Groq returned an invalid confidence estimate. Please retry the scan.")
    confidence = float(confidence_value)
    if not 0 <= confidence <= 100:
        raise VisionProviderError("Groq returned an invalid confidence estimate. Please retry the scan.")
    if not isinstance(alternatives, list):
        alternatives = []

    cleaned_alternatives = []
    for alternative in alternatives[:3]:
        if not isinstance(alternative, dict):
            continue
        name = alternative.get("diagnosis")
        score_value = alternative.get("confidence")
        if isinstance(score_value, bool) or not isinstance(score_value, (int, float)):
            continue
        score = float(score_value)
        if isinstance(name, str) and name.strip() and 0 <= score <= 100:
            cleaned_alternatives.append({
                "class_name": name.strip(),
                "confidence": round(score, 1),
            })

    return AnalysisResult(
        disease_name=diagnosis.strip(),
        confidence=round(confidence, 1),
        severity="unassessed",
        affected_area_pct=None,
        issue_type="disease",
        detector_source=f"groq:{GROQ_VISION_MODEL}",
        alternatives=cleaned_alternatives,
    )


async def analyze_image_with_groq(image_bytes: bytes, crop_type: str | None = None) -> AnalysisResult:
    if not GROQ_API_KEY:
        raise VisionProviderError(
            "Crop analysis is unavailable: configure GROQ_API_KEY or install the trained model checkpoint."
        )

    _, encoded_image = _decode_image(image_bytes)
    crop_context = crop_type.strip() if crop_type else "not specified"
    prompt = (
        "Visually assess this crop photo for plant disease. The grower reports the crop as "
        f"{crop_context}. Return a JSON object with exactly these fields: "
        '{"diagnosis": string, "confidence": number from 0 to 100, '
        '"alternatives": [{"diagnosis": string, "confidence": number}]}. '
        "Give a concise likely disease or visible condition, not a treatment prescription. "
        "If no disease is visible, say 'No visible disease symptoms'. If the crop/image cannot "
        "be identified, say 'Uncertain - image needs expert review' and use a low confidence. "
        "Only assess visible evidence; do not invent crop details. Confidence is a model estimate, "
        "not validated diagnostic accuracy. Include at most two plausible alternatives."
    )
    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
                },
            ],
        }],
        "temperature": 0.1,
        "max_completion_tokens": 500,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json=payload,
            )
    except httpx.TimeoutException as error:
        raise VisionProviderError("Groq crop analysis timed out. Please retry in a moment.") from error
    except httpx.HTTPError as error:
        logger.warning("Groq vision request failed: %s", type(error).__name__)
        raise VisionProviderError("Could not connect to Groq for crop analysis. Check the backend connection.") from error

    if response.is_error:
        logger.warning("Groq vision request returned HTTP %s.", response.status_code)
        if response.status_code == 401:
            detail = "Groq rejected the API key. Check GROQ_API_KEY in backend/.env."
        elif response.status_code == 429:
            detail = "Groq rate limit reached. Please wait and retry."
        elif response.status_code == 400 or response.status_code == 404:
            detail = f"Groq rejected vision model '{GROQ_VISION_MODEL}'. Check GROQ_VISION_MODEL in backend/.env."
        else:
            detail = f"Groq crop analysis failed (HTTP {response.status_code}). Please retry."
        raise VisionProviderError(detail)

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise VisionProviderError("Groq returned an incomplete crop assessment. Please retry.") from error
    if not isinstance(content, str):
        raise VisionProviderError("Groq returned an unsupported crop assessment format. Please retry.")
    return _parse_groq_response(content)


def analyze_image_bytes(image_bytes: bytes) -> AnalysisResult:
    if _model is None or _transform is None or _device is None:
        raise RuntimeError(_model_error or "Crop model is not available.")

    image, _ = _decode_image(image_bytes)
    import torch

    tensor = _transform(image).unsqueeze(0).to(_device)
    with torch.inference_mode():
        probabilities = torch.softmax(_model(tensor), dim=1)[0]
        values, indices = torch.topk(probabilities, min(3, len(_classes)))

    choices = [
        {"class_name": _classes[index], "confidence": round(float(value) * 100, 2)}
        for value, index in zip(values.cpu().tolist(), indices.cpu().tolist())
    ]
    primary = choices[0]
    return AnalysisResult(
        disease_name=primary["class_name"],
        confidence=primary["confidence"],
        severity="unassessed",
        affected_area_pct=None,
        issue_type="disease",
        detector_source=_model_name or "local-model",
        alternatives=choices[1:],
    )
