import asyncio
import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import models
import schemas
from database import Base
from routers import priority_router, rescue_router, scans_router, treatments_router


class InterventionApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.owner = models.User(name="Owner", email="owner@example.test", hashed_password="x")
        self.other_user = models.User(name="Other", email="other@example.test", hashed_password="x")
        self.session.add_all([self.owner, self.other_user])
        self.session.flush()
        self.farm = models.Farm(owner_id=self.owner.id, name="North farm")
        self.other_farm = models.Farm(owner_id=self.other_user.id, name="Private farm")
        self.session.add_all([self.farm, self.other_farm])
        self.session.flush()
        self.tomato_field = models.Field(
            farm_id=self.farm.id,
            name="Tomato field",
            crop="Tomato",
            growth_stage="flowering",
        )
        self.potato_field = models.Field(
            farm_id=self.farm.id,
            name="Potato field",
            crop="Potato",
            growth_stage="vegetative",
        )
        self.other_field = models.Field(
            farm_id=self.other_farm.id,
            name="Private field",
            crop="Tomato",
        )
        self.session.add_all([self.tomato_field, self.potato_field, self.other_field])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def add_priority(self, field, issue, tier="HIGH", status="pending", created_at=None, score=72.0):
        scan = models.Scan(
            field_id=field.id,
            disease_name=issue,
            severity="high",
            affected_area_pct=25,
            issue_type="disease",
            status="active",
            created_at=created_at or datetime.utcnow(),
        )
        self.session.add(scan)
        self.session.flush()
        priority = models.PriorityScore(
            scan_id=scan.id,
            score=score,
            tier=tier,
            status=status,
            scoring_method="rules-v1",
            suggested_timeframe="Prompt field review recommended.",
            reasons_json=json.dumps(["Farmer-recorded severity: high."]),
            factors_json=json.dumps({"missing_information": ["Weather"]}),
        )
        self.session.add(priority)
        self.session.commit()
        return priority, scan

    def test_filters_and_summary_use_only_the_authenticated_users_records(self):
        self.add_priority(self.tomato_field, "Early blight", "HIGH")
        self.add_priority(self.potato_field, "Late blight", "LOW", "completed")
        self.add_priority(self.other_field, "Early blight", "CRITICAL")

        results = priority_router.list_priorities(
            crop_type="Tomato",
            problem="early",
            tier="HIGH",
            db=self.session,
            user=self.owner,
        )
        summary = priority_router.intervention_summary(db=self.session, user=self.owner)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["farm_name"], "North farm")
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["high"], 1)
        self.assertEqual(summary["low"], 1)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["completed"], 1)

    def test_unassessed_cases_sort_after_scored_cases(self):
        scored, _ = self.add_priority(self.tomato_field, "Early blight", "HIGH")
        unassessed, _ = self.add_priority(
            self.potato_field, "Unassessed scan", "UNASSESSED", score=None
        )

        results = priority_router.list_priorities(db=self.session, user=self.owner)

        self.assertEqual([item["id"] for item in results], [scored.id, unassessed.id])

    def test_status_and_follow_up_updates_persist_and_are_owner_scoped(self):
        priority, scan = self.add_priority(self.tomato_field, "Early blight")
        follow_up = datetime.utcnow() + timedelta(days=2)

        with self.assertRaises(HTTPException) as error:
            priority_router.update_intervention_case(
                priority.id,
                schemas.InterventionUpdate(status="completed"),
                db=self.session,
                user=self.other_user,
            )
        self.assertEqual(error.exception.status_code, 404)

        priority_router.update_intervention_case(
            priority.id,
            schemas.InterventionUpdate(
                status="in_progress",
                follow_up_at=follow_up,
                chosen_action="Inspect affected plants",
            ),
            db=self.session,
            user=self.owner,
        )
        self.session.expire_all()
        persisted = self.session.get(models.PriorityScore, priority.id)
        persisted_scan = self.session.get(models.Scan, scan.id)

        self.assertEqual(persisted.status, "in_progress")
        self.assertEqual(persisted.follow_up_at, follow_up)
        self.assertEqual(persisted.chosen_action, "Inspect affected plants")
        self.assertEqual(persisted_scan.status, "active")

    def test_scan_can_create_intervention_without_weather_or_duplicate_case(self):
        scan = models.Scan(
            field_id=self.tomato_field.id,
            disease_name="Leaf spot",
            severity="unassessed",
            confidence=90,
            issue_type="disease",
            status="pending_review",
        )
        self.session.add(scan)
        self.session.commit()

        result = asyncio.run(
            priority_router.create_intervention_from_scan(
                scan.id,
                schemas.InterventionCreate(severity="medium", affected_area_pct=10),
                db=self.session,
                user=self.owner,
            )
        )

        self.assertEqual(result["tier"], "MEDIUM")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["scoring_method"], "rules-v1")
        self.assertEqual(result["confidence"], 90)
        self.assertTrue(result["factors"]["missing_information"])

        duplicate_scan = models.Scan(
            field_id=self.tomato_field.id,
            disease_name="leaf spot",
            severity="unassessed",
            issue_type="disease",
            status="pending_review",
        )
        self.session.add(duplicate_scan)
        self.session.commit()
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                priority_router.create_intervention_from_scan(
                    duplicate_scan.id,
                    schemas.InterventionCreate(severity="medium"),
                    db=self.session,
                    user=self.owner,
                )
            )
        self.assertEqual(error.exception.status_code, 409)

    def test_scan_automation_and_candidate_list_avoid_open_duplicates(self):
        first_scan = models.Scan(
            field_id=self.tomato_field.id,
            disease_name="Leaf spot",
            severity="medium",
            affected_area_pct=10,
            issue_type="disease",
            status="active",
        )
        self.session.add(first_scan)
        self.session.commit()
        first_priority = asyncio.run(
            scans_router._compute_and_store_priority(self.session, first_scan, self.tomato_field)
        )

        repeated_scan = models.Scan(
            field_id=self.tomato_field.id,
            disease_name="leaf spot",
            severity="medium",
            affected_area_pct=12,
            issue_type="disease",
            status="active",
        )
        self.session.add(repeated_scan)
        self.session.commit()
        repeated_priority = asyncio.run(
            scans_router._compute_and_store_priority(self.session, repeated_scan, self.tomato_field)
        )
        candidates = priority_router.intervention_candidates(db=self.session, user=self.owner)

        self.assertEqual(repeated_priority.id, first_priority.id)
        self.assertEqual(self.session.query(models.PriorityScore).count(), 1)
        self.assertFalse(any(item["issue_name"].casefold() == "leaf spot" for item in candidates))

    def test_intervention_schemas_reject_invalid_or_empty_updates(self):
        with self.assertRaises(ValidationError):
            schemas.InterventionCreate(severity="urgent")
        with self.assertRaises(ValidationError):
            schemas.InterventionCreate(severity="high", affected_area_pct=101)
        with self.assertRaises(ValidationError):
            schemas.InterventionUpdate()

    def test_treatment_progress_does_not_mark_crop_issue_resolved(self):
        priority, scan = self.add_priority(self.tomato_field, "Early blight")
        treatment = treatments_router.create_treatment(
            schemas.TreatmentCreate(
                scan_id=scan.id,
                action="Inspect and record progress",
                status="in_progress",
            ),
            db=self.session,
            user=self.owner,
        )
        self.assertEqual(treatment.status, "in_progress")
        self.assertEqual(self.session.get(models.PriorityScore, priority.id).status, "in_progress")

        treatments_router.update_treatment(
            treatment.id,
            schemas.TreatmentUpdate(status="completed"),
            db=self.session,
            user=self.owner,
        )
        self.session.expire_all()

        self.assertEqual(self.session.get(models.PriorityScore, priority.id).status, "in_progress")
        self.assertEqual(self.session.get(models.Scan, scan.id).status, "active")

    def test_rescue_deployment_does_not_copy_weather_payload_to_treatment_notes(self):
        scan = models.Scan(
            field_id=self.tomato_field.id,
            disease_name="Leaf spot",
            severity="medium",
            issue_type="disease",
            status="active",
        )
        self.session.add(scan)
        self.session.flush()
        self.session.add(models.RescuePlan(
            scan_id=scan.id,
            immediate_action="Inspect the affected leaves.",
            organic_treatment="Remove affected leaves.",
            chemical_treatment="Ask a local expert.",
            application_guidance="Generic application guidance.",
            recovery_time="Not estimated.",
            prevention="Monitor the field.",
            weather_consideration='Recorded weather context: {"forecast":["large payload"]}',
            evidence_summary="AI-generated general guidance; unverified.",
        ))
        self.session.commit()

        result = rescue_router.deploy_rescue_treatment(
            scan.id,
            rescue_router.DeployRescueRequest(
                action_type="organic",
                custom_notes="Inspect and remove visibly affected leaves.",
            ),
            db=self.session,
            user=self.owner,
        )
        treatment = self.session.get(models.Treatment, result["treatment_id"])

        self.assertNotIn("weather", treatment.notes.lower())
        self.assertNotIn("forecast", treatment.notes.lower())
        self.assertEqual(treatment.notes, "Rescue Planner guidance: Remove affected leaves.")
        self.assertNotIn("Farmer-entered plan from Rescue Planner", treatment.notes)
        self.assertNotIn("Generic application guidance", treatment.notes)
        self.assertEqual(treatment.action, "Inspect and remove visibly affected leaves.")


if __name__ == "__main__":
    unittest.main()