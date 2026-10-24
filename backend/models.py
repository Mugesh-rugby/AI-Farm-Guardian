from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship
from datetime import datetime

try:
    from database import Base
except ImportError:
    from backend.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    farms = relationship("Farm", back_populates="owner", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")


class Farm(Base):
    __tablename__ = "farms"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    area_acres = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="farms")
    fields = relationship("Field", back_populates="farm", cascade="all, delete-orphan")
    predictive_alerts = relationship("PredictiveRiskAlert", back_populates="farm", cascade="all, delete-orphan")


class Field(Base):
    __tablename__ = "fields"
    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    crop = Column(String(255), nullable=False)
    size_acres = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    growth_stage = Column(String(100), nullable=True)  # seedling, vegetative, flowering, maturity
    planting_date = Column(DateTime, nullable=True)
    crop_price_per_kg = Column(Float, nullable=True)  # used for economic engine
    expected_yield_kg_per_acre = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    farm = relationship("Farm", back_populates="fields")
    scans = relationship("Scan", back_populates="field", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"
    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    image_path = Column(String(500), nullable=True)
    disease_name = Column(String(255), nullable=True)
    confidence = Column(Float, nullable=True)
    severity = Column(String(50), nullable=True)  # low, medium, high, critical
    affected_area_pct = Column(Float, nullable=True)
    issue_type = Column(String(100), default="disease")  # disease, water_stress, nutrient, pest
    status = Column(String(50), default="active")  # active, resolved
    detector_source = Column(String(100), default="heuristic-cv")  # heuristic-cv | yolov11 | manual
    created_at = Column(DateTime, default=datetime.utcnow)

    field = relationship("Field", back_populates="scans")
    priority = relationship("PriorityScore", back_populates="scan", uselist=False, cascade="all, delete-orphan")
    treatments = relationship("Treatment", back_populates="scan", cascade="all, delete-orphan")
    rescue_plan = relationship("RescuePlan", back_populates="scan", uselist=False, cascade="all, delete-orphan")


class PriorityScore(Base):
    __tablename__ = "priority_scores"
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id", ondelete="CASCADE"), unique=True, nullable=False)
    score = Column(Float, nullable=False)
    tier = Column(String(50), nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    suggested_timeframe = Column(String(100), default="Within 24 hours")
    reasons_json = Column(Text, nullable=False)  # JSON list of strings
    factors_json = Column(Text, nullable=False)  # JSON dict of sub-scores
    computed_at = Column(DateTime, default=datetime.utcnow)

    scan = relationship("Scan", back_populates="priority")


class Treatment(Base):
    __tablename__ = "treatments"
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    action = Column(Text, nullable=False)
    treatment_type = Column(String(50), default="organic")  # organic, chemical, cultural
    status = Column(String(50), default="pending")  # pending, in_progress, completed
    applied_at = Column(DateTime, nullable=True)
    cost = Column(Float, nullable=True)
    follow_up_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    scan = relationship("Scan", back_populates="treatments")


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    level = Column(String(50), default="info")  # info, warning, critical
    category = Column(String(50), default="ALERT")  # ALERT, WEATHER, RESCUE, PRIORITY
    read = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chat_messages")


class PredictiveRiskAlert(Base):
    """Predictive Crop Risk Alerts combining AI with real-time weather intelligence"""
    __tablename__ = "predictive_risk_alerts"
    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    crop = Column(String(255), nullable=True)
    risk_type = Column(String(100), nullable=False)  # Fungal Spore Explosion, Spray Washout Hazard, Heat Drought Stress, Pest Vector Multiplication
    risk_level = Column(String(50), nullable=False)  # CRITICAL, HIGH, MODERATE, LOW
    confidence = Column(Float, default=88.0)
    time_horizon = Column(String(100), default="Next 24-48 Hours")
    weather_trigger = Column(String(255), nullable=False)  # e.g., "Humidity: 84%, Temp: 27°C, Rain: 65%"
    advisory = Column(Text, nullable=False)
    preventive_action = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    farm = relationship("Farm", back_populates="predictive_alerts")


class RescuePlan(Base):
    """Evidence-Based AI Rescue Planner combining CV disease detection, RAG, and Generative AI"""
    __tablename__ = "rescue_plans"
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id", ondelete="CASCADE"), unique=True, nullable=False)
    immediate_action = Column(Text, nullable=False)
    organic_treatment = Column(Text, nullable=False)
    chemical_treatment = Column(Text, nullable=False)
    application_guidance = Column(Text, nullable=False)
    recovery_time = Column(String(100), nullable=False)
    prevention = Column(Text, nullable=False)
    weather_consideration = Column(Text, nullable=False)
    safety_warning = Column(Text, nullable=True)
    evidence_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    scan = relationship("Scan", back_populates="rescue_plan")
