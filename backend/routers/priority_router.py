import json
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models, schemas
from auth import get_current_user
from services.priority_engine import compute_priority
from services.economic_engine import estimate_economic_risk
from services.weather_service import get_weather

router = APIRouter(prefix="/api/priority", tags=["priority"])


class SimulationRequest(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0, le=100)
    affected_area_pct: float = Field(ge=0, le=100)
    issue_type: Literal["disease", "pest", "water_stress", "nutrient", "healthy"] = "disease"
    growth_stage: Literal["seedling", "vegetative", "flowering", "maturity"]
    crop: str = Field(min_length=1, max_length=100)
    temperature: Optional[float] = None
    humidity: Optional[float] = Field(None, ge=0, le=100)
    rain_probability: Optional[float] = Field(None, ge=0, le=100)
    wind_speed_kmh: Optional[float] = Field(None, ge=0)
    field_size_acres: Optional[float] = Field(None, gt=0)


class AnalyzeRequest(BaseModel):
    farm_id: int
    field_id: int
    issue_name: str = Field(min_length=1, max_length=255)
    issue_type: Literal["disease", "pest", "water_stress", "nutrient"] = "disease"
    severity: Literal["low", "medium", "high", "critical"]
    affected_area_pct: float = Field(ge=0, le=100)
    confidence: Optional[float] = Field(None, ge=0, le=100)
    economic_loss_est: Optional[float] = Field(None, ge=0)


class RecalculateRequest(BaseModel):
    farm_id: Optional[int] = None
    scan_id: Optional[int] = None


@router.get("")
@router.get("/")
def list_priorities(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = (
        db.query(models.PriorityScore, models.Scan, models.Field, models.Farm)
        .join(models.Scan, models.PriorityScore.scan_id == models.Scan.id)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(models.Farm.owner_id == user.id, models.Scan.status == "active")
        .order_by(models.PriorityScore.score.desc())
        .all()
    )

    result = []
    for priority, scan, field, farm in rows:
        reasons = []
        try:
            reasons = json.loads(priority.reasons_json)
        except Exception:
            reasons = [priority.reasons_json]

        factors = {}
        try:
            factors = json.loads(priority.factors_json)
        except Exception:
            factors = {}

        result.append(
            {
                "id": priority.id,
                "priority_id": priority.id,
                "scan_id": scan.id,
                "score": priority.score,
                "priority_score": priority.score,
                "tier": priority.tier,
                "priority_category": priority.tier,
                "suggested_timeframe": priority.suggested_timeframe or "Within 24 hours",
                "reasons": reasons,
                "factors": factors,
                "disease_name": scan.disease_name,
                "issue_name": scan.disease_name,
                "severity": scan.severity,
                "confidence": scan.confidence,
                "affected_area_pct": scan.affected_area_pct,
                "issue_type": scan.issue_type,
                "status": scan.status,
                "field_name": field.name,
                "field_id": field.id,
                "crop": field.crop,
                "crop_type": field.crop,
                "growth_stage": field.growth_stage,
                "farm_name": farm.name,
                "farm_id": farm.id,
                "image_path": scan.image_path,
                "economic_loss_est": factors.get("financial_loss_est"),
                "potential_savings": None,
                "computed_at": priority.computed_at.isoformat() if priority.computed_at else None,
            }
        )
    return result


@router.post("/analyze")
async def analyze_priority(payload: AnalyzeRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    Intelligent Farm Risk Prioritization: Creates and computes priority for an issue.
    """
    field = (
        db.query(models.Field)
        .join(models.Farm)
        .filter(models.Field.id == payload.field_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    if field.farm_id != payload.farm_id:
        raise HTTPException(status_code=400, detail="Field does not belong to the selected farm.")

    weather = None
    if field.farm and field.farm.latitude and field.farm.longitude:
        weather = await get_weather(field.farm.latitude, field.farm.longitude)

    economic = {"estimated_financial_loss": payload.economic_loss_est}

    score, tier, reasons, factors, timeframe = compute_priority(
        severity=payload.severity,
        confidence=payload.confidence,
        affected_area_pct=payload.affected_area_pct,
        issue_type=payload.issue_type,
        growth_stage=field.growth_stage,
        weather=weather,
        economic=economic,
        crop_type=field.crop,
    )

    # Create scan record
    scan = models.Scan(
        field_id=field.id,
        disease_name=payload.issue_name,
        confidence=payload.confidence,
        severity=payload.severity,
        affected_area_pct=payload.affected_area_pct,
        issue_type=payload.issue_type,
        detector_source="manual-assessment"
    )
    db.add(scan)
    db.flush()

    priority = models.PriorityScore(
        scan_id=scan.id,
        score=score,
        tier=tier,
        suggested_timeframe=timeframe,
        reasons_json=json.dumps(reasons),
        factors_json=json.dumps(factors),
    )
    db.add(priority)

    db.commit()
    db.refresh(priority)

    return {
        "id": priority.id,
        "priority_id": priority.id,
        "scan_id": scan.id,
        "priority_score": score,
        "priority_category": tier,
        "tier": tier,
        "suggested_timeframe": timeframe,
        "economic_loss_est": factors.get("financial_loss_est"),
        "reasons": reasons,
        "factors": factors
    }


@router.post("/recalculate")
async def recalculate_farm_priorities(
    payload: RecalculateRequest = RecalculateRequest(),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    """Recalculates all active priorities using real-time microclimate weather."""
    q = (
        db.query(models.PriorityScore, models.Scan, models.Field, models.Farm)
        .join(models.Scan, models.PriorityScore.scan_id == models.Scan.id)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(models.Farm.owner_id == user.id, models.Scan.status == "active")
    )
    if payload.farm_id:
        q = q.filter(models.Farm.id == payload.farm_id)
    if payload.scan_id:
        q = q.filter(models.Scan.id == payload.scan_id)

    rows = q.all()
    count = 0
    for priority, scan, field, farm in rows:
        weather = None
        if farm.latitude is not None and farm.longitude is not None:
            weather = await get_weather(farm.latitude, farm.longitude)

        economic = estimate_economic_risk(
            affected_area_pct=scan.affected_area_pct or 0,
            field_size_acres=field.size_acres,
            crop_price_per_kg=field.crop_price_per_kg,
            expected_yield_kg_per_acre=field.expected_yield_kg_per_acre,
        )

        score, tier, reasons, factors, timeframe = compute_priority(
            severity=scan.severity,
            confidence=scan.confidence,
            affected_area_pct=scan.affected_area_pct or 0,
            issue_type=scan.issue_type,
            growth_stage=field.growth_stage,
            weather=weather,
            economic=economic,
            crop_type=field.crop,
        )
        priority.score = score
        priority.tier = tier
        priority.suggested_timeframe = timeframe
        priority.reasons_json = json.dumps(reasons)
        priority.factors_json = json.dumps(factors)
        count += 1

    db.commit()
    return {"success": True, "recalculated_count": count, "message": f"Successfully recalculated {count} dynamic priorities with live weather intelligence!"}


@router.get("/{scan_id}")
def get_priority(scan_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    row = (
        db.query(models.PriorityScore, models.Scan, models.Field, models.Farm)
        .join(models.Scan, models.PriorityScore.scan_id == models.Scan.id)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(models.Scan.id == scan_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Priority not found for this scan")
    priority, scan, field, farm = row
    return {
        "id": priority.id,
        "priority_id": priority.id,
        "scan_id": scan.id,
        "score": priority.score,
        "priority_score": priority.score,
        "tier": priority.tier,
        "priority_category": priority.tier,
        "suggested_timeframe": priority.suggested_timeframe or "Within 24 hours",
        "reasons": json.loads(priority.reasons_json) if priority.reasons_json else [],
        "factors": json.loads(priority.factors_json) if priority.factors_json else {},
        "disease_name": scan.disease_name,
        "issue_name": scan.disease_name,
        "severity": scan.severity,
        "confidence": scan.confidence,
        "affected_area_pct": scan.affected_area_pct,
        "issue_type": scan.issue_type,
        "field_name": field.name,
        "crop": field.crop,
        "growth_stage": field.growth_stage,
        "farm_name": farm.name,
        "farm_id": farm.id,
        "field_id": field.id,
        "image_path": scan.image_path,
    }


@router.patch("/{priority_id}/status")
def update_priority_status(
    priority_id: int,
    status: Literal["active", "resolved"] = Query(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    priority = (
        db.query(models.PriorityScore)
        .join(models.Scan)
        .join(models.Field)
        .join(models.Farm)
        .filter(models.PriorityScore.id == priority_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not priority:
        raise HTTPException(status_code=404, detail="Priority item not found")

    priority.scan.status = status
    db.commit()
    return {"success": True, "status": status}


@router.delete("/{priority_id}")
def delete_priority(priority_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    priority = (
        db.query(models.PriorityScore)
        .join(models.Scan)
        .join(models.Field)
        .join(models.Farm)
        .filter(models.PriorityScore.id == priority_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not priority:
        raise HTTPException(status_code=404, detail="Priority item not found")

    db.delete(priority.scan)
    db.commit()
    return {"ok": True}


@router.post("/simulate")
def simulate_priority(req: SimulationRequest):
    """
    Intelligent Farm Risk Prioritization Simulation Sandbox.
    """
    weather = {
        "temperature": req.temperature,
        "humidity": req.humidity,
        "rain_probability": req.rain_probability,
        "wind_speed_kmh": req.wind_speed_kmh,
    }
    if req.temperature is None and req.humidity is None and req.rain_probability is None:
        weather = None
    economic = estimate_economic_risk(
        affected_area_pct=req.affected_area_pct,
        field_size_acres=req.field_size_acres,
        crop_price_per_kg=None,
        expected_yield_kg_per_acre=None,
    )
    score, tier, reasons, factors, timeframe = compute_priority(
        severity=req.severity,
        confidence=req.confidence,
        affected_area_pct=req.affected_area_pct,
        issue_type=req.issue_type,
        growth_stage=req.growth_stage,
        weather=weather,
        economic=economic,
        crop_type=req.crop,
    )
    return {
        "simulated": True,
        "score": score,
        "priority_score": score,
        "tier": tier,
        "priority_category": tier,
        "suggested_timeframe": timeframe,
        "reasons": reasons,
        "factors": factors,
        "economic_impact": economic,
    }
