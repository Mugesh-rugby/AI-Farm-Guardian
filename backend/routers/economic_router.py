from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
import models
from auth import get_current_user
from services.economic_engine import estimate_economic_risk

router = APIRouter(prefix="/api/economic", tags=["economic"])


@router.get("")
@router.get("/")
def economic_overview(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    scans = (
        db.query(models.Scan, models.Field)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(models.Farm.owner_id == user.id, models.Scan.status == "active")
        .all()
    )

    results = []
    for scan, field in scans:
        risk = estimate_economic_risk(
            affected_area_pct=scan.affected_area_pct or 0,
            field_size_acres=field.size_acres,
            crop_price_per_kg=field.crop_price_per_kg,
            expected_yield_kg_per_acre=field.expected_yield_kg_per_acre,
        )
        results.append(
            {
                "scan_id": scan.id,
                "field_name": field.name,
                "crop": field.crop,
                "disease_name": scan.disease_name,
                "severity": scan.severity,
                "needs_crop_economics": field.crop_price_per_kg is None or field.expected_yield_kg_per_acre is None,
                **risk,
            }
        )
    return results


@router.get("/estimate")
def estimate_risk_query(
    crop_type: str = Query(..., min_length=1, max_length=100),
    field_area_acres: float = Query(..., gt=0),
    affected_area_pct: float = Query(..., ge=0, le=100),
    growth_stage: str = Query(..., min_length=1, max_length=50),
    crop_price_per_kg: Optional[float] = Query(None, ge=0),
    expected_yield_kg_per_acre: Optional[float] = Query(None, ge=0),
    yield_reduction_pct: Optional[float] = Query(None, ge=0, le=100),
    treatment_cost: Optional[float] = Query(None, ge=0),
    user: models.User = Depends(get_current_user),
):
    """Scenario estimate based only on values explicitly entered by the farmer."""
    risk = estimate_economic_risk(
        affected_area_pct=affected_area_pct,
        field_size_acres=field_area_acres,
        crop_price_per_kg=crop_price_per_kg,
        expected_yield_kg_per_acre=expected_yield_kg_per_acre,
        yield_reduction_pct=yield_reduction_pct,
        treatment_cost=treatment_cost,
    )
    return {
        "crop_type": crop_type,
        "growth_stage": growth_stage,
        "est_financial_loss": risk["estimated_financial_loss"],
        "projected_yield_loss_pct": risk["estimated_yield_loss_pct"],
        **risk
    }


@router.get("/{scan_id}")
def economic_for_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    row = (
        db.query(models.Scan, models.Field)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(models.Scan.id == scan_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    scan, field = row
    risk = estimate_economic_risk(
        affected_area_pct=scan.affected_area_pct or 0,
        field_size_acres=field.size_acres,
        crop_price_per_kg=field.crop_price_per_kg,
        expected_yield_kg_per_acre=field.expected_yield_kg_per_acre,
    )
    return {
        "needs_crop_economics": field.crop_price_per_kg is None or field.expected_yield_kg_per_acre is None,
        **risk,
    }
