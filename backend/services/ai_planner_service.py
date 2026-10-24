import json
from typing import Any

try:
    from config import GROQ_VISION_MODEL
    from services.ai_service import chat_completion, is_configured
except ImportError:
    from backend.config import GROQ_VISION_MODEL
    from backend.services.ai_service import chat_completion, is_configured

_SYSTEM_PROMPT = (
    "You are a cautious crop pathologist providing decision support, not a confirmed "
    "diagnosis. Inspect the attached original crop photo and compare visible evidence "
    "with the classifier prediction and recorded crop context. The classifier label "
    "is a prediction, not a confirmed diagnosis. Clearly say when visible evidence "
    "does not support it or when the photo is inconclusive. Use only the image and "
    "provided crop, field, and weather observations; do not invent symptoms or causes. "
    "Return only valid JSON with exactly these keys and no markdown: description "
    "(2-3 plain sentences), symptoms (array of visible signs), causes (array of "
    "possible causes marked uncertain), organicTreatment (array of safe general steps), "
    "chemicalTreatment (array directing the grower to a qualified local expert and "
    "locally approved label; do not name a product or dose), prevention (array of "
    "practical prevention tips), recoveryTimeDays (two non-negative integers or null "
    "values; use null when not supportable). If the classifier says healthy, describe "
    "only that no disease symptoms were identified in this photo, do not guarantee "
    "plant health, and do not recommend treatment. Never invent product approvals, "
    "pesticide or chemical names, application rates, or guaranteed outcomes."
)


async def generate_rescue_plan(**context: Any) -> dict[str, Any] | None:
    if not is_configured():
        return None

    image_bytes = context.pop("image_bytes", None)
    reply = await chat_completion(
        _SYSTEM_PROMPT,
        json.dumps(context, ensure_ascii=True),
        image_bytes=image_bytes,
        model=GROQ_VISION_MODEL if image_bytes is not None else None,
    )
    if reply is None:
        return None
    try:
        result = json.loads(reply)
    except json.JSONDecodeError as error:
        raise ValueError("AI provider returned an invalid rescue-plan format.") from error
    expected = (
        "description",
        "symptoms",
        "causes",
        "organicTreatment",
        "chemicalTreatment",
        "prevention",
        "recoveryTimeDays",
    )
    if not isinstance(result, dict) or set(result) != set(expected) or any(
        not isinstance(result.get(key), str if key == "description" else list)
        for key in expected[:-1]
    ):
        raise ValueError("AI provider returned an incomplete rescue plan.")

    if not result["description"].strip():
        raise ValueError("AI provider returned an empty crop diagnosis.")
    for key in expected[1:-1]:
        if any(not isinstance(item, str) or not item.strip() for item in result[key]):
            raise ValueError("AI provider returned invalid diagnosis details.")
    recovery = result.get("recoveryTimeDays")
    if recovery is not None and (
        not isinstance(recovery, list)
        or len(recovery) != 2
        or any(
            value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0)
            for value in recovery
        )
    ):
        raise ValueError("AI provider returned an invalid recovery estimate.")

    diagnosis_details = [
        result["description"],
        "Visible symptoms: " + "; ".join(result["symptoms"]) if result["symptoms"] else "No distinct symptoms were confirmed from the available image.",
        "Possible causes: " + "; ".join(result["causes"]) if result["causes"] else "Causes are uncertain from the available evidence.",
    ]
    recovery_text = "Not estimated from the available evidence."
    if recovery and all(value is not None for value in recovery):
        recovery_text = f"AI estimate: {recovery[0]}–{recovery[1]} days; actual recovery varies and is not guaranteed."

    return {
        "description": result["description"],
        "symptoms": result["symptoms"],
        "causes": result["causes"],
        "organicTreatment": result["organicTreatment"],
        "chemicalTreatment": result["chemicalTreatment"],
        "prevention": result["prevention"],
        "prevention_text": "\n".join(result["prevention"]),
        "recoveryTimeDays": recovery,
        "immediate_action": "\n".join(diagnosis_details),
        "organic_treatment": "\n".join(result["organicTreatment"]) or "No organic treatment is suggested from the available evidence.",
        "chemical_treatment": "\n".join(result["chemicalTreatment"]) or "Consult a licensed local agricultural expert; no product or dose is recommended.",
        "application_guidance": "Monitor the field and follow up with an agricultural expert if symptoms spread or the assessment is uncertain.",
        "recovery_time": recovery_text,
        "weather_consideration": (
            f"Recorded weather context: {json.dumps(context['weather'], ensure_ascii=True)}"
            if context.get("weather")
            else "No current farm weather data was provided for this assessment."
        ),
        "safety_warning": "This AI output is unverified decision support, not a confirmed diagnosis or treatment prescription. Follow local agricultural guidance.",
        "evidence_summary": (
            "AI-generated general guidance based on image assessment and recorded farm context; "
            "not independently verified. " + result["description"]
        ),
        "image_assessed": image_bytes is not None,
        "source": (
            "Groq image diagnosis and general guidance"
            if image_bytes is not None
            else "Groq-generated general guidance"
        ),
    }
