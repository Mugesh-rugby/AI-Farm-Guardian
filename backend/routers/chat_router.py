import httpx
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models, schemas
from auth import get_current_user
from services.ai_service import GroqProviderError, chat_completion, is_configured
from services.weather_service import get_weather
from rate_limit import ai_rate_limit

router = APIRouter(prefix="/api/chat", tags=["chat"])

SYSTEM_PROMPT = """You are an agricultural extension assistant inside AI Farm Guardian.
Answer questions about crop production, plant diseases, pests, soil, irrigation,
fertilizers, weather impacts, harvest, and farm management. Give direct, practical,
concise answers (3-6 sentences), using the selected farm's crop, scan, and weather
context when relevant. If the question is unrelated to agriculture, briefly explain
that you specialize in farming and invite an agricultural question. If details are
missing, say what is uncertain and ask a focused follow-up. A classifier result is
only a prediction, not a confirmed diagnosis. Do not invent observations, weather,
model accuracy, product approvals, pesticide doses, or guaranteed outcomes. For
chemical crop-protection decisions, advise checking locally registered products and
labels with a qualified local agricultural professional."""


@router.get("/history", response_model=List[schemas.ChatMessageOut])
def history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.user_id == user.id)
        .order_by(models.ChatMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.delete("/history")
def clear_history(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    db.query(models.ChatMessage).filter(models.ChatMessage.user_id == user.id).delete()
    db.commit()
    return {"ok": True}


@router.post("", dependencies=[Depends(ai_rate_limit)])
async def send_message(payload: schemas.ChatRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if not is_configured():
        return {"connected": False, "reason": "GROQ_API_KEY not configured", "reply": None}

    context_parts = []
    if payload.field_id:
        field = (
            db.query(models.Field)
            .join(models.Farm)
            .filter(models.Field.id == payload.field_id, models.Farm.owner_id == user.id)
            .first()
        )
        if not field:
            raise HTTPException(status_code=404, detail="Field not found")
        context_parts.append(f"Crop: {field.crop}, growth stage: {field.growth_stage or 'not recorded'}")
        latest_scan = (
            db.query(models.Scan)
            .filter(models.Scan.field_id == field.id)
            .order_by(models.Scan.created_at.desc())
            .first()
        )
        if latest_scan:
            context_parts.append(
                f"Most recent classifier output: {latest_scan.disease_name}, "
                f"confidence {latest_scan.confidence}%, severity {latest_scan.severity}."
            )
        if field.farm and field.farm.latitude is not None and field.farm.longitude is not None:
            weather = await get_weather(field.farm.latitude, field.farm.longitude)
            if weather:
                context_parts.append(
                    f"Current weather: {weather['temperature']}C, humidity {weather['humidity']}%, "
                    f"forecast rain probability {weather['rain_probability']}%."
                )

    history_rows = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.user_id == user.id)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(11)
        .all()
    )
    history_rows.reverse()
    history = [{"role": m.role, "content": m.content} for m in history_rows[-10:]]

    context_str = "\n".join(context_parts)
    full_message = f"Context:\n{context_str}\n\nFarmer's question: {payload.message}" if context_str else payload.message

    try:
        reply = await chat_completion(SYSTEM_PROMPT, full_message, history)
    except GroqProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="The AI provider request failed.") from error
    if reply is None:
        return {"connected": False, "reason": "AI request failed", "reply": None}

    user_msg = models.ChatMessage(user_id=user.id, role="user", content=payload.message)
    assistant_msg = models.ChatMessage(user_id=user.id, role="assistant", content=reply)
    db.add_all([user_msg, assistant_msg])
    db.commit()

    return {"connected": True, "reason": None, "reply": reply}
