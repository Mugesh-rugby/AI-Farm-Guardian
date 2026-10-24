from typing import Literal
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
import httpx
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import get_current_user
from services.ai_planner_service import generate_rescue_plan
from services.ai_service import GroqProviderError
from services.weather_service import get_weather
from config import UPLOAD_DIR

router = APIRouter(prefix="/api/rescue", tags=["rescue"])


class DeployRescueRequest(BaseModel):
    action_type: Literal["organic", "chemical"] = "organic"
    custom_notes: str = Field(min_length=10, max_length=2000)


@router.get("/{scan_id}")
async def get_rescue_plan(scan_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Return general AI guidance based on an authenticated user's recorded scan."""
    row = (
        db.query(models.Scan, models.Field, models.Farm)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(models.Scan.id == scan_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    scan, field, farm = row

    image_path = UPLOAD_DIR / Path(scan.image_path or "").name
    if not image_path.is_file():
        raise HTTPException(
            status_code=410,
            detail="The original scan photo is unavailable. Upload a new crop photo to generate an image-based diagnosis.",
        )
    try:
        image_bytes = image_path.read_bytes()
    except OSError as error:
        raise HTTPException(status_code=500, detail="The saved scan photo could not be read.") from error

    weather = None
    if farm.latitude and farm.longitude:
        weather = await get_weather(farm.latitude, farm.longitude)

    existing_plan = db.query(models.RescuePlan).filter(models.RescuePlan.scan_id == scan_id).first()
    try:
        plan_dict = await generate_rescue_plan(
            crop=field.crop,
            growth_stage=field.growth_stage,
            classifier_output=scan.disease_name,
            confidence=scan.confidence,
            severity=scan.severity,
            affected_area_pct=scan.affected_area_pct,
            weather=weather,
            is_healthy="healthy" in (scan.disease_name or "").lower(),
            image_bytes=image_bytes,
        )
    except GroqProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except httpx.TimeoutException as error:
        raise HTTPException(
            status_code=504,
            detail="Crop diagnosis timed out while waiting for the AI provider. Please retry.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="The AI provider request failed.") from error
    if plan_dict is None:
        return {
            "connected": False,
            "reason": "Configure GROQ_API_KEY to request general AI guidance.",
            "plan": None,
        }

    if existing_plan:
        plan_record = existing_plan
    else:
        plan_record = models.RescuePlan(scan_id=scan.id)
        db.add(plan_record)
    for key in (
        "immediate_action",
        "organic_treatment",
        "chemical_treatment",
        "application_guidance",
        "recovery_time",
        "prevention",
        "weather_consideration",
        "safety_warning",
        "evidence_summary",
    ):
        setattr(
            plan_record,
            key,
            plan_dict["prevention_text"] if key == "prevention" else plan_dict[key],
        )
    db.commit()

    facts = {
        "crop": field.crop,
        "growth_stage": field.growth_stage,
        "disease_name": scan.disease_name,
        "severity": scan.severity,
        "confidence": scan.confidence,
        "affected_area_pct": scan.affected_area_pct,
        "issue_type": scan.issue_type,
        "field_name": field.name,
        "farm_name": farm.name,
        "weather": weather,
    }

    return {
        "connected": True,
        "reason": None,
        "plan": plan_dict,
        "facts": facts,
        "source": plan_dict["source"]
    }


@router.post("/{scan_id}/deploy")
def deploy_rescue_treatment(
    scan_id: int,
    payload: DeployRescueRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    """Record a farmer-selected treatment in the Treatment Tracker."""
    row = (
        db.query(models.Scan, models.Field, models.Farm)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(models.Scan.id == scan_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    scan, field, farm = row

    plan = db.query(models.RescuePlan).filter(models.RescuePlan.scan_id == scan_id).first()
    if not plan:
        raise HTTPException(status_code=400, detail="Generate rescue plan first before deploying.")
    if not (plan.evidence_summary or "").startswith("AI-generated general guidance"):
        raise HTTPException(status_code=409, detail="This legacy rescue plan is unverified; generate a current plan first.")

    treatment = models.Treatment(
        scan_id=scan.id,
        action=payload.custom_notes,
        treatment_type=payload.action_type,
        status="pending",
        notes=f"Farmer-entered treatment from Rescue Planner. Review AI guidance before applying. Weather note: {plan.weather_consideration}",
    )
    db.add(treatment)

    notif = models.Notification(
        user_id=user.id,
        title=f"Treatment Deployed: {field.name}",
        message=f"Deployed {payload.action_type} rescue treatment for {scan.disease_name} to Treatment Tracker.",
        level="info",
        category="RESCUE",
        read=False,
        is_read=False
    )
    db.add(notif)
    db.commit()
    db.refresh(treatment)

    return {
        "success": True,
        "message": "Treatment successfully deployed to Treatment Tracker",
        "treatment_id": treatment.id,
        "action": treatment.action,
        "treatment_type": treatment.treatment_type
    }
