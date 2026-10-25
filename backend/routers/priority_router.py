import json
from datetime import date, datetime, time, timedelta
from math import isfinite
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from database import get_db
import models, schemas
from auth import get_current_user
from services.priority_engine import SCORING_METHOD, compute_priority, sanitize_json_values
from services.economic_engine import estimate_economic_risk
from services.weather_service import get_weather

router = APIRouter(prefix="/api/priority", tags=["priority"])


def _json_value(value, default):
    try:
        parsed = json.loads(value) if value else default
        return parsed if isinstance(parsed, type(default)) else default
    except (TypeError, ValueError):
        return default


def _priority_query(db: Session, user: models.User):
    return (
        db.query(models.PriorityScore, models.Scan, models.Field, models.Farm)
        .join(models.Scan, models.PriorityScore.scan_id == models.Scan.id)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(models.Farm.owner_id == user.id)
    )


def _apply_priority_filters(
    query,
    farm_id=None,
    field_id=None,
    crop_type=None,
    issue_type=None,
    problem=None,
    tier=None,
    status=None,
    date_from=None,
    date_to=None,
):
    if farm_id is not None:
        query = query.filter(models.Farm.id == farm_id)
    if field_id is not None:
        query = query.filter(models.Field.id == field_id)
    if crop_type:
        query = query.filter(models.Field.crop == crop_type)
    if issue_type:
        query = query.filter(models.Scan.issue_type == issue_type)
    if problem:
        query = query.filter(models.Scan.disease_name.ilike(f"%{problem.strip()}%"))
    if tier:
        query = query.filter(models.PriorityScore.tier == tier.upper())
    if status:
        query = query.filter(models.PriorityScore.status == status)
    if date_from:
        query = query.filter(models.Scan.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(models.Scan.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    return query


def _recommended_action(tier: str) -> str:
    return {
        "CRITICAL": "Arrange an urgent field assessment; confirm next steps with a local agronomist.",
        "HIGH": "Inspect affected plants promptly and record the observed extent before choosing an intervention.",
        "MEDIUM": "Schedule a field review and monitor for changes.",
        "LOW": "Continue routine scouting and record any changes.",
        "UNASSESSED": "Record field observations before assigning an intervention priority.",
    }.get(tier, "Review the field and record an appropriate next step.")


def _serialize_priority(priority, scan, field, farm, include_treatments=False):
    reasons = _json_value(priority.reasons_json, [])
    factors = _json_value(priority.factors_json, {})
    result = {
        "id": priority.id,
        "priority_id": priority.id,
        "scan_id": scan.id,
        "score": priority.score,
        "priority_score": priority.score,
        "tier": priority.tier,
        "priority_category": priority.tier,
        "status": priority.status,
        "scoring_method": priority.scoring_method or SCORING_METHOD,
        "suggested_timeframe": priority.suggested_timeframe,
        "recommended_next_action": _recommended_action(priority.tier),
        "chosen_action": priority.chosen_action,
        "follow_up_at": priority.follow_up_at.isoformat() if priority.follow_up_at else None,
        "completed_at": priority.completed_at.isoformat() if priority.completed_at else None,
        "computed_at": priority.computed_at.isoformat() if priority.computed_at else None,
        "updated_at": priority.updated_at.isoformat() if priority.updated_at else None,
        "reasons": reasons,
        "factors": factors,
        "missing_information": factors.get("missing_information", []),
        "weather_context": factors.get("weather_context"),
        "economic_context": factors.get("economic_context"),
        "disease_name": scan.disease_name,
        "issue_name": scan.disease_name or "Crop issue",
        "severity": scan.severity,
        "confidence": scan.confidence,
        "affected_area_pct": scan.affected_area_pct,
        "issue_type": scan.issue_type,
        "scan_status": scan.status,
        "field_name": field.name,
        "field_id": field.id,
        "crop": field.crop,
        "crop_type": field.crop,
        "growth_stage": field.growth_stage,
        "farm_name": farm.name,
        "farm_id": farm.id,
        "image_path": scan.image_path,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
    }
    if include_treatments:
        result["treatments"] = [
            {
                "id": treatment.id,
                "action": treatment.action,
                "status": treatment.status,
                "treatment_type": treatment.treatment_type,
                "follow_up_at": treatment.follow_up_at.isoformat() if treatment.follow_up_at else None,
                "created_at": treatment.created_at.isoformat() if treatment.created_at else None,
            }
            for treatment in scan.treatments
        ]
    return result


def _priority_summary(rows):
    summary = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "unassessed": 0,
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "total": len(rows),
    }
    for priority, *_ in rows:
        summary[priority.tier.lower()] = summary.get(priority.tier.lower(), 0) + 1
        summary[priority.status] = summary.get(priority.status, 0) + 1
    return summary


def _weather_snapshot(weather):
    if not weather:
        return None
    keys = (
        "temperature", "feels_like", "humidity", "rainfall_mm",
        "rain_probability", "wind_speed_kmh", "condition", "updated_at", "source",
    )
    numeric_ranges = {
        "temperature": (-50, 60),
        "feels_like": (-50, 60),
        "humidity": (0, 100),
        "rainfall_mm": (0, 1000),
        "rain_probability": (0, 100),
        "wind_speed_kmh": (0, 300),
    }
    result = {}
    for key in keys:
        value = weather.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if key in numeric_ranges:
            if isinstance(value, (int, float)) and isfinite(value):
                lower, upper = numeric_ranges[key]
                if lower <= value <= upper:
                    result[key] = value
        elif isinstance(value, (int, float)):
            if isfinite(value):
                result[key] = value
        elif isinstance(value, str):
            result[key] = value
    return result or None


def _score_scan(scan, field, weather):
    economic = None
    if scan.affected_area_pct is not None:
        economic = estimate_economic_risk(
            affected_area_pct=scan.affected_area_pct,
            field_size_acres=field.size_acres,
            crop_price_per_kg=field.crop_price_per_kg,
            expected_yield_kg_per_acre=field.expected_yield_kg_per_acre,
        )
    score, tier, reasons, factors, timeframe = compute_priority(
        severity=scan.severity,
        confidence=scan.confidence,
        affected_area_pct=scan.affected_area_pct,
        issue_type=scan.issue_type,
        growth_stage=field.growth_stage,
        weather=weather,
        economic=economic,
        crop_type=field.crop,
    )
    factors["weather_context"] = _weather_snapshot(weather)
    factors["economic_context"] = economic
    return score, tier, reasons, sanitize_json_values(factors), timeframe


async def _weather_for_field(field):
    farm = field.farm
    if farm and farm.latitude is not None and farm.longitude is not None:
        return await get_weather(farm.latitude, farm.longitude)
    return None


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
def list_priorities(
    farm_id: Optional[int] = None,
    field_id: Optional[int] = None,
    crop_type: Optional[str] = None,
    issue_type: Optional[str] = None,
    problem: Optional[str] = None,
    tier: Optional[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNASSESSED"]] = None,
    status: Optional[Literal["pending", "in_progress", "completed"]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    rows = _apply_priority_filters(
        _priority_query(db, user), farm_id, field_id, crop_type, issue_type,
        problem, tier, status, date_from, date_to,
    ).order_by(
        case((models.PriorityScore.score.is_(None), 1), else_=0),
        models.PriorityScore.score.desc(),
        models.Scan.created_at.asc(),
    ).all()
    return [_serialize_priority(*row) for row in rows]


@router.get("/summary")
def intervention_summary(
    farm_id: Optional[int] = None,
    field_id: Optional[int] = None,
    crop_type: Optional[str] = None,
    issue_type: Optional[str] = None,
    problem: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    rows = _apply_priority_filters(
        _priority_query(db, user), farm_id, field_id, crop_type, issue_type,
        problem=problem, date_from=date_from, date_to=date_to,
    ).all()
    return _priority_summary(rows)


@router.get("/candidates")
def intervention_candidates(
    farm_id: Optional[int] = None,
    field_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = (
        db.query(models.Scan, models.Field, models.Farm)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .outerjoin(models.PriorityScore, models.PriorityScore.scan_id == models.Scan.id)
        .filter(
            models.Farm.owner_id == user.id,
            models.PriorityScore.id.is_(None),
            models.Scan.status != "resolved",
            models.Scan.issue_type != "healthy",
            or_(
                models.Scan.disease_name.is_(None),
                ~func.lower(models.Scan.disease_name).like("%healthy%"),
            ),
        )
    )
    if farm_id is not None:
        query = query.filter(models.Farm.id == farm_id)
    if field_id is not None:
        query = query.filter(models.Field.id == field_id)
    open_issues = {
        (field_id, (issue_name or "").strip().casefold())
        for field_id, issue_name in (
            db.query(models.Scan.field_id, models.Scan.disease_name)
            .join(models.PriorityScore, models.PriorityScore.scan_id == models.Scan.id)
            .join(models.Field, models.Scan.field_id == models.Field.id)
            .join(models.Farm, models.Field.farm_id == models.Farm.id)
            .filter(
                models.Farm.owner_id == user.id,
                models.PriorityScore.status.in_(("pending", "in_progress")),
            )
            .all()
        )
    }
    rows = query.order_by(models.Scan.created_at.desc()).limit(100).all()
    return [
        {
            "scan_id": scan.id,
            "field_id": field.id,
            "field_name": field.name,
            "farm_id": farm.id,
            "farm_name": farm.name,
            "crop": field.crop,
            "growth_stage": field.growth_stage,
            "issue_name": scan.disease_name or "Crop issue",
            "issue_type": scan.issue_type,
            "severity": scan.severity,
            "confidence": scan.confidence,
            "status": scan.status,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
        }
        for scan, field, farm in rows
        if (field.id, (scan.disease_name or "").strip().casefold()) not in open_issues
    ]


@router.post("/from-scan/{scan_id}")
async def create_intervention_from_scan(
    scan_id: int,
    payload: schemas.InterventionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    scan = (
        db.query(models.Scan)
        .join(models.Field)
        .join(models.Farm)
        .filter(models.Scan.id == scan_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.issue_type == "healthy" or "healthy" in (scan.disease_name or "").casefold():
        raise HTTPException(status_code=422, detail="A healthy scan cannot be added as an intervention.")
    field = scan.field
    existing = db.query(models.PriorityScore).filter_by(scan_id=scan.id).first()
    if existing:
        row = _priority_query(db, user).filter(models.PriorityScore.id == existing.id).first()
        return _serialize_priority(*row)

    issue_name = (scan.disease_name or "").strip().casefold()
    if issue_name and not payload.allow_duplicate:
        duplicate = (
            db.query(models.PriorityScore, models.Scan)
            .join(models.Scan, models.PriorityScore.scan_id == models.Scan.id)
            .filter(
                models.Scan.field_id == field.id,
                func.lower(func.trim(models.Scan.disease_name)) == issue_name,
                models.PriorityScore.status.in_(("pending", "in_progress")),
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "An open intervention already exists for this issue in this field.",
                    "priority_id": duplicate[0].id,
                    "scan_id": duplicate[1].id,
                },
            )

    scan.severity = payload.severity
    if payload.affected_area_pct is not None:
        scan.affected_area_pct = payload.affected_area_pct
    weather = await _weather_for_field(field)
    score, tier, reasons, factors, timeframe = _score_scan(scan, field, weather)
    priority = models.PriorityScore(
        scan_id=scan.id,
        score=score,
        tier=tier,
        status="pending",
        scoring_method=SCORING_METHOD,
        chosen_action=payload.chosen_action,
        follow_up_at=payload.follow_up_at,
        suggested_timeframe=timeframe,
        reasons_json=json.dumps(reasons),
        factors_json=json.dumps(factors),
    )
    scan.status = "active"
    db.add(priority)
    db.commit()
    db.refresh(priority)
    row = _priority_query(db, user).filter(models.PriorityScore.id == priority.id).first()
    return _serialize_priority(*row)


@router.get("/cases/{priority_id}")
def get_intervention_case(
    priority_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    row = _priority_query(db, user).filter(models.PriorityScore.id == priority_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Intervention not found")
    return _serialize_priority(*row, include_treatments=True)


@router.patch("/cases/{priority_id}")
def update_intervention_case(
    priority_id: int,
    payload: schemas.InterventionUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    row = _priority_query(db, user).filter(models.PriorityScore.id == priority_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Intervention not found")
    priority, scan, field, farm = row
    updates = payload.model_dump(exclude_unset=True)
    for name, value in updates.items():
        setattr(priority, name, value)
    if payload.status == "completed":
        priority.completed_at = datetime.utcnow()
        scan.status = "resolved"
    elif payload.status in ("pending", "in_progress"):
        priority.completed_at = None
        scan.status = "active"
    db.commit()
    db.refresh(priority)
    return _serialize_priority(priority, scan, field, farm)


@router.post("/cases/{priority_id}/reassess")
async def reassess_intervention_case(
    priority_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    row = _priority_query(db, user).filter(models.PriorityScore.id == priority_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Intervention not found")
    priority, scan, field, farm = row
    weather = await _weather_for_field(field)
    score, tier, reasons, factors, timeframe = _score_scan(scan, field, weather)
    priority.score = score
    priority.tier = tier
    priority.scoring_method = SCORING_METHOD
    priority.suggested_timeframe = timeframe
    priority.reasons_json = json.dumps(reasons)
    priority.factors_json = json.dumps(factors)
    priority.computed_at = datetime.utcnow()
    db.commit()
    db.refresh(priority)
    return _serialize_priority(priority, scan, field, farm)


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

    weather = await _weather_for_field(field)

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
        status="pending",
        scoring_method=SCORING_METHOD,
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
        .filter(
            models.Farm.owner_id == user.id,
            models.PriorityScore.status.in_(("pending", "in_progress")),
        )
    )
    if payload.farm_id:
        q = q.filter(models.Farm.id == payload.farm_id)
    if payload.scan_id:
        q = q.filter(models.Scan.id == payload.scan_id)

    rows = q.all()
    count = 0
    for priority, scan, field, farm in rows:
        weather = await _weather_for_field(field)
        score, tier, reasons, factors, timeframe = _score_scan(scan, field, weather)
        priority.score = score
        priority.tier = tier
        priority.scoring_method = SCORING_METHOD
        priority.suggested_timeframe = timeframe
        priority.reasons_json = json.dumps(reasons)
        priority.factors_json = json.dumps(factors)
        priority.computed_at = datetime.utcnow()
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
    return _serialize_priority(priority, scan, field, farm)


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
    priority.status = "completed" if status == "resolved" else "in_progress"
    priority.completed_at = datetime.utcnow() if status == "resolved" else None
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
