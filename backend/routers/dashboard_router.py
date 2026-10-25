from datetime import datetime, time, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

SEVERITY_PENALTY = {"low": 5, "medium": 15, "high": 25, "critical": 40}


@router.get("")
@router.get("/")
@router.get("/summary")
def summary(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    farms = db.query(models.Farm).filter(models.Farm.owner_id == user.id).all()
    farm_ids = [f.id for f in farms]

    if not farm_ids:
        return {
            "has_data": False,
            "farm_count": 0,
            "farms_count": 0,
            "field_count": 0,
            "fields_count": 0,
            "scan_count": 0,
            "health_score": None,
            "farm_health_score": None,
            "active_issues_count": 0,
            "treatment_stats": {"completed": 0, "scheduled": 0, "in_progress": 0},
            "intervention_summary": {
                "critical": 0, "high": 0, "medium": 0, "low": 0,
                "pending": 0, "in_progress": 0, "completed": 0, "total": 0,
            },
        }

    active_scans = (
        db.query(models.Scan)
        .join(models.Field)
        .filter(
            models.Field.farm_id.in_(farm_ids),
            models.Scan.status == "active",
            models.Scan.issue_type != "healthy",
            models.Scan.severity != "unassessed",
        )
        .all()
    )

    all_scans = (
        db.query(models.Scan).join(models.Field).filter(models.Field.farm_id.in_(farm_ids)).all()
    )

    field_count = db.query(models.Field).filter(models.Field.farm_id.in_(farm_ids)).count()

    assessed_scans = [
        scan for scan in all_scans
        if scan.severity and scan.severity.lower() != "unassessed"
    ]
    health_score = None
    if assessed_scans:
        health_score = 100
    for s in active_scans:
        health_score -= SEVERITY_PENALTY.get((s.severity or "low").lower(), 10)
    if health_score is not None:
        health_score = max(health_score, 0)

    # Top / Highest priority issue
    top_priority_row = (
        db.query(models.PriorityScore, models.Scan, models.Field, models.Farm)
        .join(models.Scan, models.PriorityScore.scan_id == models.Scan.id)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .filter(
            models.Field.farm_id.in_(farm_ids),
            models.PriorityScore.status.in_(("pending", "in_progress")),
        )
        .order_by(models.PriorityScore.score.desc())
        .first()
    )

    top_priority_data = None
    if top_priority_row:
        priority, scan, field, farm = top_priority_row
        top_priority_data = {
            "scan_id": scan.id,
            "issue_name": scan.disease_name,
            "disease_name": scan.disease_name,
            "tier": priority.tier,
            "priority_category": priority.tier,
            "score": priority.score,
            "priority_score": priority.score,
            "field_name": field.name,
            "farm_name": farm.name,
            "crop": field.crop,
            "timeframe": priority.suggested_timeframe,
        }

    # Treatments statistics
    treatments = (
        db.query(models.Treatment)
        .join(models.Scan)
        .join(models.Field)
        .filter(models.Field.farm_id.in_(farm_ids))
        .all()
    )
    completed_treatments = len([t for t in treatments if t.status == "completed"])
    in_progress_treatments = len([t for t in treatments if t.status == "in_progress"])
    scheduled_treatments = len([t for t in treatments if t.status == "pending"])

    recent_scans = sorted(all_scans, key=lambda s: s.created_at, reverse=True)[:5]

    # Priority distribution for charts
    priorities = (
        db.query(models.PriorityScore)
        .join(models.Scan, models.PriorityScore.scan_id == models.Scan.id)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .filter(
            models.Field.farm_id.in_(farm_ids),
            models.PriorityScore.status.in_(("pending", "in_progress")),
        )
        .all()
    )
    tier_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for p in priorities:
        tier_counts[p.tier] = tier_counts.get(p.tier, 0) + 1

    all_priorities = (
        db.query(models.PriorityScore)
        .join(models.Scan, models.PriorityScore.scan_id == models.Scan.id)
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .filter(models.Field.farm_id.in_(farm_ids))
        .all()
    )
    intervention_summary = {
        "critical": 0, "high": 0, "medium": 0, "low": 0,
        "pending": 0, "in_progress": 0, "completed": 0,
        "total": len(all_priorities),
    }
    for priority in all_priorities:
        tier_key = priority.tier.lower()
        if tier_key in intervention_summary:
            intervention_summary[tier_key] += 1
        if priority.status in intervention_summary:
            intervention_summary[priority.status] += 1

    # Keep the dashboard chart scoped to the most recent 30 calendar days.
    today = datetime.utcnow().date()
    first_day = today - timedelta(days=29)
    activity_rows = (
        db.query(func.date(models.Scan.created_at), func.count(models.Scan.id))
        .join(models.Field, models.Scan.field_id == models.Field.id)
        .filter(
            models.Field.farm_id.in_(farm_ids),
            models.Scan.created_at >= datetime.combine(first_day, time.min),
            models.Scan.created_at < datetime.combine(today + timedelta(days=1), time.min),
        )
        .group_by(func.date(models.Scan.created_at))
        .all()
    )
    scans_by_day = {
        day.isoformat() if hasattr(day, "isoformat") else str(day): count
        for day, count in activity_rows
    }
    scan_activity = [
        {
            "date": (first_day + timedelta(days=offset)).isoformat(),
            "scans": scans_by_day.get((first_day + timedelta(days=offset)).isoformat(), 0),
        }
        for offset in range(30)
    ]

    return {
        "has_data": True,
        "has_scans": len(all_scans) > 0,
        "farm_count": len(farms),
        "farms_count": len(farms),
        "field_count": field_count,
        "fields_count": field_count,
        "scan_count": len(all_scans),
        "health_score": health_score,
        "farm_health_score": health_score,
        "active_issues_count": len(active_scans),
        "top_priority": top_priority_data,
        "highest_priority": top_priority_data,
        "treatments_completed": completed_treatments,
        "treatments_total": len(treatments),
        "treatment_stats": {
            "completed": completed_treatments,
            "scheduled": scheduled_treatments,
            "in_progress": in_progress_treatments,
            "total": len(treatments)
        },
        "recent_scans": [
            {
                "id": s.id,
                "disease_name": s.disease_name,
                "severity": s.severity,
                "created_at": s.created_at.isoformat(),
                "image_path": s.image_path,
            }
            for s in recent_scans
        ],
        "priority_distribution": tier_counts,
        "intervention_summary": intervention_summary,
        "scan_activity": scan_activity
    }
