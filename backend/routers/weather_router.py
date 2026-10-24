from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import get_current_user
from services.weather_service import get_weather
from config import OPENWEATHER_API_KEY

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("")
@router.get("/")
async def weather_for_farm(
    farm_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    if farm_id is None:
        farm = (
            db.query(models.Farm)
            .filter(
                models.Farm.owner_id == user.id,
                models.Farm.latitude.isnot(None),
                models.Farm.longitude.isnot(None),
            )
            .first()
        )
    else:
        farm = (
            db.query(models.Farm)
            .filter(models.Farm.owner_id == user.id, models.Farm.id == farm_id)
            .first()
        )
        if not farm:
            raise HTTPException(status_code=404, detail="Farm not found")

    if not farm:
        return {"connected": False, "reason": "No farms registered yet", "data": None}
    if farm.latitude is None or farm.longitude is None:
        return {"connected": False, "reason": "Add latitude and longitude to this farm.", "data": None}

    data = await get_weather(farm.latitude, farm.longitude)
    if data is None:
        reason = (
            "OPENWEATHER_API_KEY is not configured."
            if not OPENWEATHER_API_KEY
            else "OpenWeather is unavailable. Try again later."
        )
        return {"connected": False, "reason": reason, "data": None}

    return {
        "connected": True,
        "farm_id": farm.id,
        "farm_name": farm.name,
        "crops": [field.crop for field in farm.fields],
        "reason": None,
        "data": data,
        "insights": data.get("advisories", []),
        "predictive_risks": [],
    }


@router.get("/predictive-alerts")
def get_predictive_alerts(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Returns all real-time and recorded predictive crop risk alerts across user's farms."""
    alerts = (
        db.query(models.PredictiveRiskAlert, models.Farm)
        .join(models.Farm, models.PredictiveRiskAlert.farm_id == models.Farm.id)
        .filter(models.Farm.owner_id == user.id)
        .order_by(models.PredictiveRiskAlert.created_at.desc())
        .limit(20)
        .all()
    )

    result = []
    for alert, farm in alerts:
        result.append({
            "id": alert.id,
            "farm_id": farm.id,
            "farm_name": farm.name,
            "crop": alert.crop,
            "risk_type": alert.risk_type,
            "risk_level": alert.risk_level,
            "confidence": alert.confidence,
            "time_horizon": alert.time_horizon,
            "weather_trigger": alert.weather_trigger,
            "advisory": alert.advisory,
            "preventive_action": alert.preventive_action,
            "created_at": alert.created_at.isoformat()
        })
    return result
