from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
import models, schemas
from auth import get_current_user

router = APIRouter(prefix="/api/fields", tags=["fields"])


def _assert_farm_ownership(db, farm_id, user):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id, models.Farm.owner_id == user.id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


@router.get("", response_model=List[schemas.FieldOut])
@router.get("/", response_model=List[schemas.FieldOut])
def list_fields(farm_id: Optional[int] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Field).join(models.Farm).filter(models.Farm.owner_id == user.id)
    if farm_id:
        q = q.filter(models.Field.farm_id == farm_id)
    return q.all()


@router.post("", response_model=schemas.FieldOut)
@router.post("/", response_model=schemas.FieldOut)
def create_field(payload: schemas.FieldCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _assert_farm_ownership(db, payload.farm_id, user)
    field = models.Field(**payload.dict())
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


@router.put("/{field_id}", response_model=schemas.FieldOut)
def update_field(
    field_id: int,
    payload: schemas.FieldCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    field = (
        db.query(models.Field)
        .join(models.Farm)
        .filter(models.Field.id == field_id, models.Farm.owner_id == user.id)
        .first()
    )
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    _assert_farm_ownership(db, payload.farm_id, user)
    for name, value in payload.model_dump().items():
        setattr(field, name, value)
    db.commit()
    db.refresh(field)
    return field


@router.delete("/{field_id}")
def delete_field(field_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    field = db.query(models.Field).join(models.Farm).filter(models.Field.id == field_id, models.Farm.owner_id == user.id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    db.delete(field)
    db.commit()
    return {"ok": True}
