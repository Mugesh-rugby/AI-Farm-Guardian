from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models, schemas
from auth import get_current_user

router = APIRouter(prefix="/api/treatments", tags=["treatments"])


def _sync_intervention_status(db: Session, scan_id: int, treatment_status: str):
    priority = (
        db.query(models.PriorityScore)
        .filter(models.PriorityScore.scan_id == scan_id)
        .first()
    )
    if priority and treatment_status == "in_progress" and priority.status == "pending":
        priority.status = "in_progress"


@router.get("", response_model=List[schemas.TreatmentOut])
@router.get("/", response_model=List[schemas.TreatmentOut])
def list_treatments(
    scan_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    q = (
        db.query(models.Treatment)
        .join(models.Scan, models.Treatment.scan_id == models.Scan.id)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(models.Farm.owner_id == user.id)
    )
    if scan_id:
        q = q.filter(models.Treatment.scan_id == scan_id)
    return q.order_by(models.Treatment.created_at.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=schemas.TreatmentOut)
@router.post("/", response_model=schemas.TreatmentOut)
def create_treatment(payload: schemas.TreatmentCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    scan = (
        db.query(models.Scan)
        .join(models.Field)
        .join(models.Farm)
        .filter(models.Scan.id == payload.scan_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    treatment = models.Treatment(**payload.model_dump())
    if treatment.status == "completed" and treatment.applied_at is None:
        treatment.applied_at = datetime.utcnow()
    db.add(treatment)
    _sync_intervention_status(db, scan.id, treatment.status)
    db.commit()
    db.refresh(treatment)
    return treatment


@router.put("/{treatment_id}", response_model=schemas.TreatmentOut)
def update_treatment(treatment_id: int, payload: schemas.TreatmentUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    treatment = (
        db.query(models.Treatment)
        .join(models.Scan)
        .join(models.Field)
        .join(models.Farm)
        .filter(models.Treatment.id == treatment_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")

    updates = payload.model_dump(exclude_unset=True)
    for name, value in updates.items():
        setattr(treatment, name, value)
    if treatment.status == "completed" and treatment.applied_at is None:
        treatment.applied_at = datetime.utcnow()
    _sync_intervention_status(db, treatment.scan_id, treatment.status)

    db.commit()
    db.refresh(treatment)
    return treatment


@router.delete("/{treatment_id}")
def delete_treatment(treatment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    treatment = (
        db.query(models.Treatment)
        .join(models.Scan)
        .join(models.Field)
        .join(models.Farm)
        .filter(models.Treatment.id == treatment_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")
    db.delete(treatment)
    db.commit()
    return {"ok": True}
