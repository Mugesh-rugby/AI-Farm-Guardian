from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List, Any, Literal
from datetime import datetime


# ---- Auth ----
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=10, max_length=72)
    phone: Optional[str] = Field(default=None, max_length=50)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes.")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes.")
        return value


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    user: UserOut


# ---- Field ----
class FieldCreate(BaseModel):
    farm_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    crop: str = Field(min_length=1, max_length=255)
    size_acres: Optional[float] = Field(default=None, gt=0)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    growth_stage: Optional[str] = Field(default="vegetative", max_length=100)
    planting_date: Optional[datetime] = None
    crop_price_per_kg: Optional[float] = Field(default=None, ge=0)
    expected_yield_kg_per_acre: Optional[float] = Field(default=None, ge=0)


class FieldOut(BaseModel):
    id: int
    farm_id: int
    name: str
    crop: str
    crop_type: Optional[str] = None
    size_acres: Optional[float] = None
    area: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    growth_stage: Optional[str] = None
    planting_date: Optional[datetime] = None
    crop_price_per_kg: Optional[float] = None
    expected_yield_kg_per_acre: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any):
        if hasattr(data, "crop"):
            if not getattr(data, "crop_type", None):
                try: setattr(data, "crop_type", data.crop)
                except Exception: pass
            if not getattr(data, "area", None):
                try: setattr(data, "area", data.size_acres)
                except Exception: pass
        elif isinstance(data, dict):
            if "crop" in data and "crop_type" not in data:
                data["crop_type"] = data["crop"]
            if "size_acres" in data and "area" not in data:
                data["area"] = data["size_acres"]
        return data

    class Config:
        from_attributes = True


# ---- Farm ----
class FarmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    area_acres: Optional[float] = Field(default=None, gt=0)


class FarmOut(BaseModel):
    id: int
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    area_acres: Optional[float] = None
    created_at: datetime
    fields: List[FieldOut] = []

    class Config:
        from_attributes = True


# ---- Scan / Priority ----
class ScanOut(BaseModel):
    id: int
    field_id: int
    image_path: Optional[str] = None
    disease_name: Optional[str] = None
    confidence: Optional[float] = None
    severity: Optional[str] = None
    affected_area_pct: Optional[float] = None
    issue_type: str = "disease"
    status: str = "active"
    detector_source: str = "efficientnetv2-s"
    alternatives: List[dict] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class PriorityOut(BaseModel):
    id: int
    scan_id: int
    score: Optional[float] = None
    tier: str
    reasons: List[str]
    factors: dict
    computed_at: datetime


class InterventionCreate(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    affected_area_pct: Optional[float] = Field(default=None, ge=0, le=100)
    follow_up_at: Optional[datetime] = None
    chosen_action: Optional[str] = Field(default=None, max_length=2000)
    allow_duplicate: bool = False


class InterventionUpdate(BaseModel):
    status: Optional[Literal["pending", "in_progress", "completed"]] = None
    follow_up_at: Optional[datetime] = None
    chosen_action: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_an_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one intervention field must be updated.")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Intervention status cannot be cleared.")
        return self


# ---- Treatment ----
class TreatmentCreate(BaseModel):
    scan_id: int = Field(gt=0)
    action: str = Field(min_length=1, max_length=2000)
    treatment_type: Literal["organic", "chemical", "cultural"] = "organic"
    status: Literal["pending", "in_progress", "completed"] = "pending"
    applied_at: Optional[datetime] = None
    cost: Optional[float] = Field(default=None, ge=0)
    follow_up_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class TreatmentUpdate(BaseModel):
    action: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    treatment_type: Optional[Literal["organic", "chemical", "cultural"]] = None
    status: Optional[Literal["pending", "in_progress", "completed"]] = None
    applied_at: Optional[datetime] = None
    cost: Optional[float] = Field(default=None, ge=0)
    follow_up_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class TreatmentOut(BaseModel):
    id: int
    scan_id: int
    action: str
    treatment_type: str
    status: str
    applied_at: Optional[datetime] = None
    cost: Optional[float] = None
    follow_up_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Notification ----
class NotificationOut(BaseModel):
    id: int
    title: str
    message: str
    level: str
    category: Optional[str] = None
    read: bool
    is_read: Optional[bool] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Chat ----
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    field_id: Optional[int] = None


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
