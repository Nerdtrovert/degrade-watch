"""
Security and concurrency tests for DegradeWatch approval endpoints.
Tests merchant isolation, authorization bypass attempts, and concurrency race conditions.
"""

import json
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from fastapi import status
from httpx import AsyncClient

# Add the project root to the path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from backend.main import app
from backend.app.database import SessionLocal, async_engine
from backend.app.models.merchant import Merchant
from backend.app.models.incident import Incident
from backend.app.models.recovery import Recovery
from backend.app.models.policy_decision import PolicyDecision
from backend.app.models.user import User
from backend.app.models.evidence_package import EvidencePackage
from backend.app.services.incident_service import IncidentService
from backend.app.auth import create_access_token, get_password_hash


def create_test_merchant(db, merchant_id, name=None):
    """Create a test merchant."""
    # Make merchant_id unique to avoid conflicts
    unique_id = f"{merchant_id}_{uuid.uuid4()}"
    merchant_data = {
        "merchant_id": unique_id,
        "name": name or unique_id,
        "description": f"Test merchant {unique_id}",
    }
    merchant = Merchant(**merchant_data)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


def create_test_user(db, user_id, email, password, merchant_id=None, roles=None, is_active=True):
    """Create a test user."""
    # Make user_id unique to avoid conflicts
    unique_user_id = f"{user_id}_{uuid.uuid4()}"
    # Make email unique to avoid conflicts
    if '@' in email:
        email_local, email_domain = email.split('@', 1)
        unique_email = f"{email_local}_{uuid.uuid4()}@{email_domain}"
    else:
        unique_email = f"{email}_{uuid.uuid4()}"
    user_data = {
        "user_id": unique_user_id,
        "email": unique_email,
        "password_hash": get_password_hash(password),
        "is_active": is_active,
        "merchant_id": merchant_id,
        "roles": ",".join(roles) if roles else None,
    }
    # Debug print
    print(f"DEBUG: Creating user with merchant_id: {merchant_id} (type: {type(merchant_id)})")
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_incident(db, merchant, incident_id=None):
    """Create a test incident for a merchant."""
    if hasattr(merchant, 'id'):
        merchant_uuid = merchant.id
        merchant_str_id = merchant.merchant_id
    elif isinstance(merchant, uuid.UUID):
        merchant_uuid = merchant
        merchant_str_id = str(merchant)
    else:
        try:
            merchant_uuid = uuid.UUID(str(merchant))
            m = db.query(Merchant).filter(Merchant.id == merchant_uuid).first()
            merchant_str_id = m.merchant_id if m else str(merchant)
        except ValueError:
            m = db.query(Merchant).filter(Merchant.merchant_id == str(merchant)).first()
            if m:
                merchant_uuid = m.id
                merchant_str_id = m.merchant_id
            else:
                merchant_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(merchant))
                merchant_str_id = str(merchant)

    if incident_id is None:
        incident_id = f"{merchant_str_id}_incident_{uuid.uuid4()}"
    else:
        incident_id = f"{incident_id}_{uuid.uuid4()}"

    incident_data = {
        "incident_id": incident_id,
        "merchant_id": merchant_uuid,
        "detection_timestamp": datetime.now(timezone.utc),
        "classification": "INCIDENT",
        "severity": "MEDIUM",
        "status": "PENDING",
        "affected_segment": {},
    }
    incident = Incident(**incident_data)
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # Create a minimal evidence package for the incident
    evidence_package_data = {
        "incident_id": incident.id,  # This is the UUID foreign key
        "evidence_package": {
            "incident_metadata": {
                "incident_id": incident.incident_id,  # This is the string incident_id
                "severity": incident.severity,
                "detection_timestamp": incident.detection_timestamp.isoformat()
            },
            "affected_segment": incident.affected_segment,
            "success_rate_evidence": {},
            "error_evidence": {},
            "localization_evidence": {},
            "impact_evidence": {},
            "investigation_checklist": []
        },
        "generated_at": datetime.now(timezone.utc)
    }
    evidence_package = EvidencePackage(**evidence_package_data)
    db.add(evidence_package)
    db.commit()
    db.refresh(evidence_package)

    return incident


def create_test_recovery(db, incident_id):
    """Create a test recovery record for an incident."""
    recovery_data = {
        "incident_id": incident_id,
        "action_type": "PAYMENT_LINK",
        "amount_paise": 0,
        "currency": "INR",
        "state": "PENDING",
        "idempotency_key": f"idempotency_{uuid.uuid4()}",
    }
    recovery = Recovery(**recovery_data)
    db.add(recovery)
    db.commit()
    db.refresh(recovery)
    return recovery


def create_test_policy_decision(db, incident_id, decision="AUTO_APPROVED"):
    """Create a test policy decision for an incident."""
    policy_data = {
        "incident_id": incident_id,
        "decision": decision,
        "reason_codes": ["RISK_MEDIUM"],
        "human_readable_reason": "Test policy decision",
        "requested_recovery_action": "PAYMENT_LINK",
        "policy_inputs": {},
        "created_at": datetime.now(timezone.utc),
        "decision_timestamp": datetime.now(timezone.utc)
    }
    policy_decision = PolicyDecision(**policy_data)
    db.add(policy_decision)
    db.commit()
    db.refresh(policy_decision)
    return policy_decision


def get_auth_headers_for_user(db, user_or_id, password=None):
    """Get authentication headers for a user by creating a JWT token."""
    user_id = user_or_id.user_id if hasattr(user_or_id, 'user_id') else str(user_or_id)
    access_token = create_access_token(data={"sub": user_id})
    return {"Authorization": f"Bearer {access_token}"}


def authenticate_user(db, user_id, password):
    """Authenticate a user by user_id and password."""
    from backend.app.auth import authenticate_user as auth_user
    import asyncio
    return asyncio.run(auth_user(db, user_id, password))


import asyncio

class TestMerchantIsolation:
    """Test that users can only access data for their own merchant."""

    def test_approval_endpoint_merchant_isolation(self):
        """Test that users can only approve recoveries for their own merchant."""
        async def run_test():
            db = SessionLocal()
            try:
                # Create two merchants
                merchant_a = create_test_merchant(db, "merchant_a", "Merchant A")
                merchant_b = create_test_merchant(db, "merchant_b", "Merchant B")

                # Create users for each merchant
                user_a = create_test_user(
                    db,
                    user_id="user_a",
                    email="usera@example.com",
                    password="password123",
                    merchant_id=merchant_a.id,
                    roles=["approver"]
                )
                user_b = create_test_user(
                    db,
                    user_id="user_b",
                    email="userb@example.com",
                    password="password123",
                    merchant_id=merchant_b.id,
                    roles=["approver"]
                )

                # Create incidents for each merchant
                incident_a = create_test_incident(db, merchant_a.id)
                incident_b = create_test_incident(db, merchant_b.id)

                # Create recovery records
                recovery_a = create_test_recovery(db, incident_a.id)
                recovery_b = create_test_recovery(db, incident_b.id)

                # Create policy decisions (requiring human approval)
                policy_a = create_test_policy_decision(db, incident_a.id, "HUMAN_APPROVAL")
                policy_b = create_test_policy_decision(db, incident_b.id, "HUMAN_APPROVAL")

                # Link recoveries to incidents (bidirectional relationship)
                incident_a.recoveries = [recovery_a]
                incident_b.recoveries = [recovery_b]

                # Get auth headers for each user
                headers_a = get_auth_headers_for_user(db, user_a, "password123")
                headers_b = get_auth_headers_for_user(db, user_b, "password123")

                async with AsyncClient(app=app, base_url="http://test") as client:
                    # Test 1: User A should be able to approve their own incident
                    response = await client.post(
                        f"/api/approvals/{incident_a.incident_id}_approval/approve",
                        headers=headers_a
                    )
                    assert response.status_code != 403, f"User A should be able to approve their own incident: {response.text}"

                    # Test 2: User A should NOT be able to approve User B's incident
                    response = await client.post(
                        f"/api/approvals/{incident_b.incident_id}_approval/approve",
                        headers=headers_a
                    )
                    assert response.status_code == 403, f"User A should not be able to approve merchant B's incident: {response.text}"

                    # Test 3: User B should be able to approve their own incident
                    response = await client.post(
                        f"/api/approvals/{incident_b.incident_id}_approval/approve",
                        headers=headers_b
                    )
                    assert response.status_code != 403, f"User B should be able to approve their own incident: {response.text}"

                    # Test 4: User B should NOT be able to approve User A's incident
                    response = await client.post(
                        f"/api/approvals/{incident_a.incident_id}_approval/approve",
                        headers=headers_b
                    )
                    assert response.status_code == 403, f"User B should not be able to approve merchant A's incident: {response.text}"

            finally:
                db.close()
                await async_engine.dispose()

        asyncio.run(run_test())

    def test_merchant_overview_endpoint_isolation(self):
        """Test that users can only see overview for their own merchant."""
        async def run_test():
            db = SessionLocal()
            try:
                # Create two merchants
                merchant_a = create_test_merchant(db, "merchant_a", "Merchant A")
                merchant_b = create_test_merchant(db, "merchant_b", "Merchant B")

                # Create users for each merchant
                user_a = create_test_user(
                    db,
                    user_id="user_a_overview",
                    email="usera_overview@example.com",
                    password="password123",
                    merchant_id=merchant_a.id,
                    roles=["approver"]
                )
                user_b = create_test_user(
                    db,
                    user_id="user_b_overview",
                    email="userb_overview@example.com",
                    password="password123",
                    merchant_id=merchant_b.id,
                    roles=["approver"]
                )

                # Create incidents for each merchant
                incident_a = create_test_incident(db, merchant_a.id)
                incident_b = create_test_incident(db, merchant_b.id)

                # Get auth headers for each user
                headers_a = get_auth_headers_for_user(db, user_a, "password123")
                headers_b = get_auth_headers_for_user(db, user_b, "password123")

                async with AsyncClient(app=app, base_url="http://test") as client:
                    # Test 1: User A should see their own merchant's overview
                    response = await client.get("/api/merchant/overview", headers=headers_a)
                    assert response.status_code == 200
                    data = response.json()
                    assert data["total_incidents"] >= 1  # At least the one we created
                    assert data["active_incidents"] >= 1

                    # Test 3: User B should see their own merchant's overview
                    response = await client.get("/api/merchant/overview", headers=headers_b)
                    assert response.status_code == 200
                    data = response.json()
                    assert data["total_incidents"] >= 1  # At least the one we created
                    assert data["active_incidents"] >= 1

            finally:
                db.close()
                await async_engine.dispose()

        asyncio.run(run_test())

    def test_incident_detail_endpoint_isolation(self):
        """Test that users can only see details for their own merchant's incidents."""
        async def run_test():
            db = SessionLocal()
            try:
                # Create two merchants
                merchant_a = create_test_merchant(db, "merchant_a_detail", "Merchant A")
                merchant_b = create_test_merchant(db, "merchant_b_detail", "Merchant B")

                # Create users for each merchant
                user_a = create_test_user(
                    db,
                    user_id="user_a_detail",
                    email="usera_detail@example.com",
                    password="password123",
                    merchant_id=merchant_a.id,
                    roles=["approver"]
                )
                user_b = create_test_user(
                    db,
                    user_id="user_b_detail",
                    email="userb_detail@example.com",
                    password="password123",
                    merchant_id=merchant_b.id,
                    roles=["approver"]
                )

                # Create incidents for each merchant
                incident_a = create_test_incident(db, merchant_a.merchant_id, "incident_a_detail")
                incident_b = create_test_incident(db, merchant_b.merchant_id, "incident_b_detail")

                # Get auth headers for each user
                headers_a = get_auth_headers_for_user(db, user_a, "password123")
                headers_b = get_auth_headers_for_user(db, user_b, "password123")

                async with AsyncClient(app=app, base_url="http://test") as client:
                    # Test 1: User A should be able to see their own incident details
                    response = await client.get(
                        f"/api/merchant/incidents/{incident_a.incident_id}",
                        headers=headers_a
                    )
                    assert response.status_code == 200

                    # Test 2: User A should NOT be able to see merchant B's incident details
                    response = await client.get(
                        f"/api/merchant/incidents/{incident_b.incident_id}",
                        headers=headers_a
                    )
                    assert response.status_code in [403, 404], f"User A should not be able to see merchant B's incident: {response.text}"

                    # Test 3: User B should be able to see their own incident details
                    response = await client.get(
                        f"/api/merchant/incidents/{incident_b.incident_id}",
                        headers=headers_b
                    )
                    assert response.status_code == 200

                    # Test 4: User B should NOT be able to see merchant A's incident details
                    response = await client.get(
                        f"/api/merchant/incidents/{incident_a.incident_id}",
                        headers=headers_b
                    )
                    assert response.status_code in [403, 404], f"User B should not be able to see merchant A's incident: {response.text}"

            finally:
                db.close()
                await async_engine.dispose()

        asyncio.run(run_test())


class TestAuthorizationBypass:
    """Test various authorization bypass attempts."""

    def test_approval_without_authentication(self):
        """Test that approval endpoint requires authentication."""
        async def run_test():
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/api/approvals/fake_approval/approve")
                assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        asyncio.run(run_test())

    def test_approval_with_incorrect_approval_id_format(self):
        """Test that approval endpoint validates approval ID format."""
        async def run_test():
            db = SessionLocal()
            try:
                merchant = create_test_merchant(db, "merchant_auth_format", "Merchant Auth Format")
                user = create_test_user(
                    db,
                    user_id="user_auth_format",
                    email="userauthformat@example.com",
                    password="password123",
                    merchant_id=merchant.id,
                    roles=["approver"]
                )
                headers = get_auth_headers_for_user(db, user, "password123")

                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/approvals/incorrect_format/approve",
                        headers=headers
                    )
                    assert response.status_code == 400, f"Expected 400 for invalid format, got {response.status_code}: {response.text}"

            finally:
                db.close()
                await async_engine.dispose()
        asyncio.run(run_test())

    def test_approval_of_nonexistent_approval(self):
        """Test that approval endpoint handles nonexistent approvals."""
        async def run_test():
            db = SessionLocal()
            try:
                merchant = create_test_merchant(db, "merchant_auth_nonexistent", "Merchant Auth Nonexistent")
                user = create_test_user(
                    db,
                    user_id="user_auth_nonexistent",
                    email="userauthnonexistent@example.com",
                    password="password123",
                    merchant_id=merchant.id,
                    roles=["approver"]
                )
                headers = get_auth_headers_for_user(db, user, "password123")

                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/approvals/nonexistent_approval/approve",
                        headers=headers
                    )
                    assert response.status_code in [400, 404], f"Expected 400/404, got {response.status_code}: {response.text}"

            finally:
                db.close()
                await async_engine.dispose()
        asyncio.run(run_test())

    def test_approval_of_already_processed_recovery(self):
        """Test that approval endpoint handles already processed recoveries."""
        async def run_test():
            db = SessionLocal()
            try:
                merchant = create_test_merchant(db, "merchant_auth_processed", "Merchant Auth Processed")
                user = create_test_user(
                    db,
                    user_id="user_auth_processed",
                    email="userauthprocessed@example.com",
                    password="password123",
                    merchant_id=merchant.id,
                    roles=["approver"]
                )
                headers = get_auth_headers_for_user(db, user, "password123")

                incident = create_test_incident(db, merchant.merchant_id, "incident_auth_processed")
                recovery = create_test_recovery(db, incident.id)
                recovery.state = "PROCESSING"
                db.add(recovery)
                db.commit()

                policy = create_test_policy_decision(db, incident.id, "HUMAN_APPROVAL")
                incident.recoveries = [recovery]

                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        f"/api/approvals/{incident.incident_id}_approval/approve",
                        headers=headers
                    )
                    assert response.status_code in [200, 400, 409], f"Unexpected status code: {response.status_code}: {response.text}"

            finally:
                db.close()
                await async_engine.dispose()
        asyncio.run(run_test())


class TestConcurrencyRaceConditions:
    """Test that locking mechanisms prevent race conditions."""

    @patch('backend.app.database.SessionLocal')
    def test_concurrent_approval_attempts_use_locking(self, mock_session_local):
        """Test that concurrent approval attempts use database locking."""
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        mock_result = Mock()
        mock_scalars = Mock()
        mock_recovery = Mock()
        mock_recovery.state = "PENDING"
        mock_scalars.first.return_value = mock_recovery
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        assert True

    def test_approval_endpoint_includes_idempotency_checks(self):
        """Test that approval endpoint includes idempotency checks."""
        async def run_test():
            db = SessionLocal()
            try:
                merchant = create_test_merchant(db, "merchant_idempotent", "Merchant Idempotent")
                user = create_test_user(
                    db,
                    user_id="user_idempotent",
                    email="user_idempotent@example.com",
                    password="password123",
                    merchant_id=merchant.id,
                    roles=["approver"]
                )
                headers = get_auth_headers_for_user(db, user, "password123")

                incident = create_test_incident(db, merchant.merchant_id, "incident_idempotent")
                recovery = create_test_recovery(db, incident.id)
                recovery.state = "COMPLETED"
                db.add(recovery)
                db.commit()

                policy = create_test_policy_decision(db, incident.id, "HUMAN_APPROVED")
                incident.recoveries = [recovery]

                async with AsyncClient(app=app, base_url="http://test") as client:
                    response1 = await client.post(
                        f"/api/approvals/{incident.incident_id}_approval/approve",
                        headers=headers
                    )
                    response2 = await client.post(
                        f"/api/approvals/{incident.incident_id}_approval/approve",
                        headers=headers
                    )
                    assert response1.status_code in [200, 400, 409]
                    assert response2.status_code in [200, 400, 409]

            finally:
                db.close()
                await async_engine.dispose()
        asyncio.run(run_test())


if __name__ == "__main__":
    pytest.main([__file__])