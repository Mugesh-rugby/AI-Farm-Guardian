from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models, schemas
from auth import get_current_user

router = APIRouter(prefix="/api/farms", tags=["farms"])


@router.get("", response_model=List[schemas.FarmOut])
@router.get("/", response_model=List[schemas.FarmOut])
def list_farms(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Farm).filter(models.Farm.owner_id == user.id).all()


@router.post("", response_model=schemas.FarmOut)
@router.post("/", response_model=schemas.FarmOut)
def create_farm(payload: schemas.FarmCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    farm = models.Farm(owner_id=user.id, **payload.dict())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


@router.put("/{farm_id}", response_model=schemas.FarmOut)
def update_farm(farm_id: int, payload: schemas.FarmCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id, models.Farm.owner_id == user.id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    for k, v in payload.dict().items():
        setattr(farm, k, v)
    db.commit()
    db.refresh(farm)
    return farm


@router.delete("/{farm_id}")
def delete_farm(farm_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id, models.Farm.owner_id == user.id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    db.delete(farm)
    db.commit()
    return {"ok": True}
