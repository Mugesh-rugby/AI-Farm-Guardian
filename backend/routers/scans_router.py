import io
import os
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError

from database import get_db
import models, schemas
from auth import get_current_user
from services.vision_service import (
    VisionProviderError,
    analyze_image_bytes,
    analyze_image_with_groq,
    local_model_supports_crop,
    model_status,
)
from config import MAX_UPLOAD_BYTES, UPLOAD_DIR
from services.priority_engine import SCORING_METHOD, compute_priority, sanitize_json_values
from services.weather_service import get_weather
from services.economic_engine import estimate_economic_risk

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.get("/model-status")
def get_model_status(user: models.User = Depends(get_current_user)):
    return model_status()


def _field_owned(db, field_id, user):
    field = (
        db.query(models.Field)
        .join(models.Farm)
        .filter(models.Field.id == field_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return field


async def _compute_and_store_priority(db: Session, scan: models.Scan, field: models.Field):
    weather = None
    if (
        field.farm
        and field.farm.latitude is not None
        and field.farm.longitude is not None
    ):
        weather = await get_weather(field.farm.latitude, field.farm.longitude)

    economic = None
    if scan.affected_area_pct is not None:
        economic = estimate_economic_risk(
            affected_area_pct=scan.affected_area_pct,
            field_size_acres=field.size_acres,
            crop_price_per_kg=field.crop_price_per_kg,
            expected_yield_kg_per_acre=field.expected_yield_kg_per_acre,
        )

    score, tier, reasons, factors, suggested_timeframe = compute_priority(
        severity=scan.severity,
        confidence=scan.confidence,
        affected_area_pct=scan.affected_area_pct,
        issue_type=scan.issue_type,
        growth_stage=field.growth_stage,
        weather=weather,
        economic=economic,
        crop_type=field.crop,
    )
    factors["weather_context"] = (
        {
            key: weather[key]
            for key in (
                "temperature", "feels_like", "humidity", "rainfall_mm",
                "rain_probability", "wind_speed_kmh", "condition", "updated_at", "source",
            )
            if weather.get(key) is not None
        }
        if weather else None
    )
    factors["economic_context"] = economic
    factors = sanitize_json_values(factors)

    if scan.disease_name:
        open_case = (
            db.query(models.PriorityScore)
            .join(models.Scan, models.PriorityScore.scan_id == models.Scan.id)
            .filter(
                models.Scan.field_id == field.id,
                func.lower(func.trim(models.Scan.disease_name)) == scan.disease_name.strip().casefold(),
                models.PriorityScore.status.in_(("pending", "in_progress")),
            )
            .first()
        )
        if open_case:
            return open_case

    existing = db.query(models.PriorityScore).filter(models.PriorityScore.scan_id == scan.id).first()
    if existing:
        existing.score = score
        existing.tier = tier
        existing.suggested_timeframe = suggested_timeframe
        existing.reasons_json = json.dumps(reasons)
        existing.factors_json = json.dumps(factors)
    else:
        existing = models.PriorityScore(
            scan_id=scan.id,
            score=score,
            tier=tier,
            status="pending",
            scoring_method=SCORING_METHOD,
            suggested_timeframe=suggested_timeframe,
            reasons_json=json.dumps(reasons),
            factors_json=json.dumps(factors),
        )
        db.add(existing)

    if tier in ("CRITICAL", "HIGH"):
        notif = models.Notification(
            user_id=field.farm.owner_id,
            title=f"{tier.title()} Priority Alert: {scan.disease_name}",
            message=f"{scan.disease_name} detected in '{field.name}' ({field.crop}) with {score}/100 priority score. Action required {suggested_timeframe.lower()}.",
            level="critical" if tier == "CRITICAL" else "warning",
            category="PRIORITY",
            read=False,
            is_read=False,
        )
        db.add(notif)

    db.commit()
    db.refresh(existing)
    return existing


@router.post("", response_model=schemas.ScanOut)
@router.post("/", response_model=schemas.ScanOut)
async def create_scan(
    field_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    field = _field_owned(db, field_id, user)

    extension = os.path.splitext(file.filename or "")[1].lower()
    accepted = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    if extension not in accepted or file.content_type not in (accepted[extension], "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP image.")

    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
    try:
        with Image.open(io.BytesIO(contents)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(status_code=415, detail="Image contents do not match a supported format.")
            if image.width < 64 or image.height < 64 or image.width > 8000 or image.height > 8000:
                raise HTTPException(status_code=422, detail="Image dimensions must be between 64 and 8000 pixels.")
            image.verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=422, detail="Uploaded file is not a valid image.")

    try:
        if local_model_supports_crop(field.crop):
            analysis = await run_in_threadpool(analyze_image_bytes, contents)
        else:
            analysis = await analyze_image_with_groq(contents, field.crop)
    except VisionProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    filename = f"{uuid.uuid4().hex}{extension}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(contents)

    scan = models.Scan(
        field_id=field_id,
        image_path=f"/uploads/{filename}",
        disease_name=analysis.disease_name,
        confidence=analysis.confidence,
        severity=analysis.severity,
        affected_area_pct=analysis.affected_area_pct,
        issue_type=analysis.issue_type,
        detector_source=analysis.detector_source,
        status="pending_review",
    )
    scan.alternatives = analysis.alternatives
    db.add(scan)
    try:
        db.commit()
        db.refresh(scan)
        if scan.severity != "unassessed":
            await _compute_and_store_priority(db, scan, field)
    except Exception:
        db.rollback()
        filepath.unlink(missing_ok=True)
        raise

    return scan


@router.get("", response_model=List[schemas.ScanOut])
@router.get("/", response_model=List[schemas.ScanOut])
def list_scans(
    field_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    q = (
        db.query(models.Scan)
        .join(models.Field)
        .join(models.Farm)
        .filter(models.Farm.owner_id == user.id)
    )
    if field_id:
        q = q.filter(models.Scan.field_id == field_id)
    if status:
        q = q.filter(models.Scan.status == status)
    return q.order_by(models.Scan.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{scan_id}", response_model=schemas.ScanOut)
def get_scan(scan_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    scan = (
        db.query(models.Scan)
        .join(models.Field)
        .join(models.Farm)
        .filter(models.Scan.id == scan_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.put("/{scan_id}/resolve")
def resolve_scan(scan_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    scan = (
        db.query(models.Scan)
        .join(models.Field)
        .join(models.Farm)
        .filter(models.Scan.id == scan_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    scan.status = "resolved"
    db.commit()
    return {"ok": True}
