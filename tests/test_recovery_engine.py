#!/usr/bin/env python3
"""
Test suite for the Recovery Engine (Checkpoint 10).
"""

import json
import os
from datetime import datetime, timezone
import asyncio
from unittest.mock import Mock, patch, AsyncMock

import pytest

from app.recovery_engine import RecoveryEngine, RecoveryState


# Helper functions to create test data

def create_base_evidence_package():
    """Create a base evidence package that represents a valid incident."""
    return {
        "incident_metadata": {
            "incident_id": "test_merchant_20260822_100000",
            "merchant_id": "test_merchant",
            "detection_timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis_window": {
                "start": "2026-08-22T09:30:00Z",
                "end": "2026-08-22T10:00:00Z",
                "duration_minutes": 30
            },
            "severity": "MEDIUM",
            "detector_classification": "INCIDENT",
            "detector_confidence": "MEDIUM"
        },
        "affected_segment": {
            "payment_method": "UPI",
            "bank": "BANK_X",
            "device": "ANDROID",
            "upi_app": "PHONEPE",
            "hierarchy_level": "FULL_SEGMENT",
            "baseline_attempts": 1000,
            "baseline_success_rate": 0.95,
            "current_attempts": 800,
            "current_success_rate": 0.80,
            "segment_key": "UPI|BANK_X|ANDROID|PHONEPE"
        },
        "success_rate_evidence": {
            "baseline_success_rate": 0.95,
            "current_success_rate": 0.80,
            "absolute_change": -0.15,
            "absolute_percentage_point_change": -15.0,
            "relative_change": -0.1579,
            "baseline_attempts": 1000,
            "current_attempts": 800,
            "statistical_significance": {
                "statistically_significant": True,
                "p_value": 0.001,
                "z_score": -3.29,
                "confidence_level": 0.95
            },
            "test_type": "two_proportion_z_test",
            "interpretation": "Statistically significant severe degradation"
        },
        "error_evidence": {
            "baseline": {
                "customer_error_rate": 0.02,
                "technical_error_rate": 0.03,
                "other_error_rate": 0.00,
                "failure_rate": 0.05,
                "failure_breakdown": {
                    "customer_caused": 20,
                    "technical": 30,
                    "other": 0
                }
            },
            "current": {
                "customer_error_rate": 0.025,
                "technical_error_rate": 0.175,
                "other_error_rate": 0.00,
                "failure_rate": 0.20,
                "failure_breakdown": {
                    "customer_caused": 20,
                    "technical": 140,
                    "other": 0
                }
            },
            "changes": {
                "customer_error_rate_change": 0.005,
                "technical_error_rate_change": 0.145,
                "other_error_rate_change": 0.0,
                "customer_error_relative_change": 0.25,
                "technical_error_relative_change": 3.833
            },
            "error_code_distribution": {
                "TECHNICAL_ERROR_001": 100,
                "INSUFFICIENT_FUNDS": 20
            },
            "error_code_shifts": {}
        },
        "localization_evidence": {
            "affected_segment": {
                "payment_method": "UPI",
                "bank": "BANK_X",
                "device": "ANDROID",
                "upi_app": "PHONEPE",
                "success_rate": 0.80,
                "attempts": 800
            },
            "localization_status": "LOCALIZED",
            "control_analysis": {
                "status": "LOCALIZED",
                "message": "Control segments remain healthy",
                "control_segments": {
                    "Other banks (same device=ANDROID, upi_app=PHONEPE)": {
                        "attempts": 200,
                        "successes": 190,
                        "success_rate": 0.95,
                        "status": "HEALTHY"
                    }
                }
            }
        },
        "impact_evidence": {
            "revenue_at_risk": {
                "paise": 50000,  # 500 INR
                "currency": "INR",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "affected_users": 100,
            "affected_transactions": 50
        },
        "investigation_checklist": [
            {
                "check": "primarily_customer_caused",
                "result": "PASS",
                "details": "Customer error rate change is not greater than technical error rate change"
            },
            {
                "check": "control_analysis_healthy",
                "result": "PASS",
                "details": "All control segments are healthy"
            }
        ],
        "temporal_evidence": {},
        "volume_evidence": {},
        "latency_evidence": {},
        "sample_payments": [],
        "hypothesis_evidence": {}
    }


def create_base_llm_report():
    """Create a base LLM report that is valid and requests a PAYMENT_LINK."""
    return {
        "incident_id": "test_merchant_20260822_100000",
        "severity": "MEDIUM",
        "status": "ACTION_REQUIRED",
        "summary": {
            "title": "Service Degradation Detected",
            "what_happened": "Payment success rate dropped significantly",
            "where": {
                "payment_method": "UPI",
                "bank": "BANK_X",
                "device": "ANDROID",
                "upi_app": "PHONEPE"
            },
            "confidence": 0.9,
            "confidence_level": "HIGH",
            "confidence_explanation": "High confidence based on statistical significance and corroborating evidence",
            "evidence_summary": [
                "Success rate dropped from 95% to 80%",
                "Technical error rate increased from 3% to 17.5%",
                "Statistical significance confirmed with p-value < 0.01"
            ]
        },
        "likely_cause": {
            "primary": "Payment gateway timeout issue",
            "confidence": 0.8,
            "evidence_refs": ["error_evidence.changes.technical_error_rate_change"]
        },
        "alternative_hypotheses": [
            {
                "hypothesis": "Bank-side network issues",
                "evidence_refs": ["error_evidence.error_code_distribution"],
                "assessment": "CONTRADICTED"
            }
        ],
        "recommended_next_steps": [
            "Monitor the situation for the next 30 minutes",
            "Check with the bank for any known issues",
            "Ready to execute payment link recovery if authorized"
        ],
        "recovery": {
            "eligible": True,
            "recommendation": "PAYMENT_LINK",
            "amount": {"paise": 10000, "currency": "INR"},  # 100 INR
            "reason": "To compensate affected users for service degradation"
        },
        "timeline": [
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "event": "Incident detected"
            }
        ]
    }


def create_auto_approved_policy_decision():
    """Create a policy decision that autorizes recovery."""
    return {
        "incident_id": "test_merchant_20260822_100000",
        "decision": "AUTO_APPROVED",
        "action_type": "PAYMENT_LINK",
        "reason_codes": ["INCIDENT_CONFIRMED", "HIGH_CONFIDENCE", "LOW_REVENUE_RISK",
                        "LOCALIZED_INCIDENT", "NO_CONTRADICTORY_EVIDENCE", "SUFFICIENT_SAMPLE"],
        "human_readable_reason": "Decision is based on the following factors: Detector classification is INCIDENT; LLM confidence meets or exceeds threshold for auto-approval; Revenue at risk is within the approved limit for auto-approval; Incident is localized to a specific segment; No contradictory evidence found in the investigation checklist; Baseline sample size is sufficient for statistical decisions.",
        "policy_version": "v1",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_refs": []
    }


class TestRecoveryEngine:
    """Test suite for the RecoveryEngine class."""

    def test_init_without_razorpay_credentials(self):
        """Test that the RecoveryEngine initializes without Razorpay credentials."""
        with patch('app.recovery_engine.razorpay.Client') as mock_client:
            mock_client.return_value = None
            # Create a mock database session
            mock_session = Mock()
            engine = RecoveryEngine(db_session=mock_session)
            assert engine.razorpay_client is None
            assert engine.config == {}
            # Should not be in simulation mode by default
            assert engine.simulation_mode is False

    def test_init_with_simulation_mode_enabled(self):
        """Test that the RecoveryEngine recognizes SIMULATION_MODE environment variable."""
        with patch('app.recovery_engine.razorpay.Client') as mock_client:
            mock_client.return_value = None
            # Create a mock database session
            mock_session = Mock()

            # Test with SIMULATION_MODE=true
            with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                engine = RecoveryEngine(db_session=mock_session)
                assert engine.simulation_mode is True

            # Test with SIMULATION_MODE=1
            with patch.dict(os.environ, {'SIMULATION_MODE': '1'}):
                engine = RecoveryEngine(db_session=mock_session)
                assert engine.simulation_mode is True

            # Test with SIMULATION_MODE=yes
            with patch.dict(os.environ, {'SIMULATION_MODE': 'yes'}):
                engine = RecoveryEngine(db_session=mock_session)
                assert engine.simulation_mode is True

            # Test with SIMULATION_MODE=false (should be False)
            with patch.dict(os.environ, {'SIMULATION_MODE': 'false'}):
                engine = RecoveryEngine(db_session=mock_session)
                assert engine.simulation_mode is False

    def test_init_with_config_and_simulation_mode(self):
        """Test that the RecoveryEngine respects SIMULATION_MODE even with credentials."""
        with patch('app.recovery_engine.razorpay.Client') as mock_client:
            mock_client.return_value = Mock()
            config = {
                'razorpay_key_id': 'test_key_id',
                'razorpay_key_secret': 'test_key_secret'
            }
            # Create a mock database session
            mock_session = Mock()
            # Test with SIMULATION_MODE enabled
            with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                engine = RecoveryEngine(config, db_session=mock_session)
                assert engine.config == config
                assert engine.simulation_mode is True

    def test_init_with_config(self):
        """Test that the RecoveryEngine initializes with config."""
        with patch('app.recovery_engine.razorpay.Client') as mock_client:
            mock_client.return_value = Mock()
            config = {
                'razorpay_key_id': 'test_key_id',
                'razorpay_key_secret': 'test_key_secret'
            }
            # Create a mock database session
            mock_session = Mock()
            engine = RecoveryEngine(config, db_session=mock_session)
            assert engine.config == config
            # Since we are providing credentials (even if test), the Razorpay client should be initialized
            assert engine.razorpay_client is not None
            # Should not be in simulation mode by default when credentials are provided
            assert engine.simulation_mode is False

    def test_is_authorized_for_recovery_auto_approved(self):
        """Test that AUTO_APPROVED decisions are authorized."""
        # Create a mock database session
        mock_session = Mock()
        engine = RecoveryEngine(db_session=mock_session)
        policy_decision = create_auto_approved_policy_decision()
        assert engine._is_authorized_for_recovery(policy_decision) is True

    def test_is_authorized_for_recovery_human_approved(self):
        """Test that HUMAN_APPROVAL decisions are authorized."""
        # Create a mock database session
        mock_session = Mock()
        engine = RecoveryEngine(db_session=mock_session)
        policy_decision = create_auto_approved_policy_decision()
        policy_decision["decision"] = "HUMAN_APPROVAL"
        assert engine._is_authorized_for_recovery(policy_decision) is True

    def test_is_authorized_for_recovery_blocked(self):
        """Test that BLOCKED decisions are not authorized."""
        # Create a mock database session
        mock_session = Mock()
        engine = RecoveryEngine(db_session=mock_session)
        policy_decision = create_auto_approved_policy_decision()
        policy_decision["decision"] = "BLOCKED"
        assert engine._is_authorized_for_recovery(policy_decision) is False

    def test_execute_recovery_unauthorized(self):
        """Test that execution fails when not authorized."""
        async def run_test():
            mock_session = Mock()
            mock_repo = AsyncMock()
            mock_repo.create = AsyncMock(return_value=Mock())
            with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                engine = RecoveryEngine(db_session=mock_session)
                evidence = create_base_evidence_package()
                llm_report = create_base_llm_report()
                policy_decision = create_auto_approved_policy_decision()
                policy_decision["decision"] = "BLOCKED"  # Not authorized

                result = await engine.execute_recovery(policy_decision, evidence, llm_report)

                assert result["state"] == RecoveryState.FAILED.value
                assert "policy engine did not approve recovery action" in result.get("error", "").lower()

        asyncio.run(run_test())

    def test_execute_recovery_unsupported_action(self):
        """Test that execution fails for unsupported actions."""
        async def run_test():
            mock_session = Mock()
            mock_repo = AsyncMock()
            mock_repo.create = AsyncMock(return_value=Mock())
            with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                engine = RecoveryEngine(db_session=mock_session)
                evidence = create_base_evidence_package()
                llm_report = create_base_llm_report()
                policy_decision = create_auto_approved_policy_decision()
                policy_decision["action_type"] = "UNSUPPORTED_ACTION"

                result = await engine.execute_recovery(policy_decision, evidence, llm_report)

                assert result["state"] == RecoveryState.FAILED.value
                assert "unsupported" in result.get("error", "").lower()

        asyncio.run(run_test())

    def test_execute_recovery_simulation_mode(self):
        """Test recovery execution in simulation mode (no Razorpay credentials)."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client:
                mock_client.return_value = None
                mock_session = Mock()
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=Mock())
                mock_repo.update = AsyncMock(return_value=Mock())
                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                        engine = RecoveryEngine(db_session=mock_session)
                        evidence = create_base_evidence_package()
                        llm_report = create_base_llm_report()
                        policy_decision = create_auto_approved_policy_decision()

                        result = await engine.execute_recovery(policy_decision, evidence, llm_report)

                        assert result["state"] == RecoveryState.COMPLETED.value
                        assert result["payment_link_id"] is not None
                        assert result["payment_link_url"] is not None
                        assert result["payment_link_id"].startswith("plink_sim_")
                        assert result["amount_paise"] == 10000
                        assert result.get("amount_rupees", result["amount_paise"] / 100.0) == 100.0
                        assert result["currency"] == "INR"
                        assert len(result["audit_events"]) >= 2  # Start and completion events

        asyncio.run(run_test())

    def test_idempotency_prevents_duplicate_recovery(self):
        """Test that identical recovery requests return existing record."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client:
                mock_client.return_value = None
                mock_session = Mock()
                mock_repo = AsyncMock()
                saved_models = []

                async def mock_create(model):
                    if not getattr(model, 'id', None):
                        model.id = uuid.uuid4()
                    saved_models.append(model)
                    return model

                async def mock_get_by_incident_id(inc_id):
                    return [m for m in saved_models]

                mock_repo.create = AsyncMock(side_effect=mock_create)
                mock_repo.get_by_incident_id = AsyncMock(side_effect=mock_get_by_incident_id)
                mock_repo.get_by_idempotency_key = AsyncMock(side_effect=lambda key: next((m for m in saved_models if getattr(m, 'idempotency_key', None) == key), None))
                mock_repo.update = AsyncMock(return_value=Mock())

                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                        engine = RecoveryEngine(db_session=mock_session)
                        evidence = create_base_evidence_package()
                        llm_report = create_base_llm_report()
                        policy_decision = create_auto_approved_policy_decision()

                        # Execute first recovery
                        result1 = await engine.execute_recovery(policy_decision, evidence, llm_report)
                        assert result1["state"] == RecoveryState.COMPLETED.value
                        recovery_id_1 = result1["recovery_id"]

                        # Execute second recovery with same incident and action type
                        result2 = await engine.execute_recovery(policy_decision, evidence, llm_report)
                        assert result2["state"] == RecoveryState.COMPLETED.value
                        recovery_id_2 = result2["recovery_id"]

                        print(f"DEBUG idempotency: id1={recovery_id_1}, id2={recovery_id_2}")
                        # Should return the same recovery record due to idempotency
                        assert recovery_id_1 == recovery_id_2
                        assert result1["recovery_id"] == result2["recovery_id"]

        asyncio.run(run_test())

    def test_check_payment_status_simulation_mode(self):
        """Test payment status checking in simulation mode."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client:
                mock_client.return_value = None
                mock_session = Mock()
                mock_repo = AsyncMock()
                mock_model = Mock(id="rec_123", incident_id="inc_123", action_type="PAYMENT_LINK", state="PROCESSING", amount_paise=10000, currency="INR", razorpay_payment_link_id="plink_sim_123", razorpay_payment_status="paid", recovered_amount_paise=10000, error_message=None)
                mock_repo.create = AsyncMock(return_value=mock_model)
                mock_repo.update = AsyncMock(return_value=mock_model)
                mock_repo.get_by_id = AsyncMock(return_value=mock_model)

                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                        engine = RecoveryEngine(db_session=mock_session)
                        evidence = create_base_evidence_package()
                        llm_report = create_base_llm_report()
                        policy_decision = create_auto_approved_policy_decision()

                        # Execute recovery
                        result = await engine.execute_recovery(policy_decision, evidence, llm_report)
                        assert result["state"] == RecoveryState.COMPLETED.value

                        recovery_id = result["recovery_id"]

                        # Check payment status (should remain completed in simulation)
                        status_result = await engine.check_payment_status(recovery_id)
                        assert status_result["state"] == RecoveryState.COMPLETED.value
                        assert status_result.get("amount_paise") == 10000

        asyncio.run(run_test())

    def test_audit_events_created(self):
        """Test that audit events are created for state transitions."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client:
                mock_client.return_value = None
                mock_session = Mock()
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=Mock())
                mock_repo.update = AsyncMock(return_value=Mock())

                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                        engine = RecoveryEngine(db_session=mock_session)
                        evidence = create_base_evidence_package()
                        llm_report = create_base_llm_report()
                        policy_decision = create_auto_approved_policy_decision()

                        result = await engine.execute_recovery(policy_decision, evidence, llm_report)

                        assert "audit_events" in result
                        assert len(result["audit_events"]) >= 2

                        # Check first audit event (processing start)
                        first_event = result["audit_events"][0]
                        assert first_event["action"] == "payment_link_creation_start"
                        assert first_event["state"] == RecoveryState.PROCESSING.value
                        assert first_event["success"] is True

                        # Check last audit event (completion)
                        last_event = result["audit_events"][-1]
                        assert last_event["action"] == "payment_link_creation"
                        assert last_event["state"] == RecoveryState.COMPLETED.value
                        assert last_event["success"] is True

        asyncio.run(run_test())

    def test_recovery_record_storage_and_retrieval(self):
        """Test that recovery records are stored and can be retrieved."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client:
                mock_client.return_value = None
                mock_session = Mock()
                mock_model = Mock(id="rec_123", incident_id="test_merchant_20260822_100000", action_type="PAYMENT_LINK", state="COMPLETED", amount_paise=10000, currency="INR", razorpay_payment_link_id="plink_sim_123", razorpay_payment_status="created", recovered_amount_paise=0, error_message=None)
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=mock_model)
                mock_repo.get_by_id = AsyncMock(return_value=mock_model)

                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                        engine = RecoveryEngine(db_session=mock_session)
                        evidence = create_base_evidence_package()
                        llm_report = create_base_llm_report()
                        policy_decision = create_auto_approved_policy_decision()

                        result = await engine.execute_recovery(policy_decision, evidence, llm_report)
                        recovery_id = result["recovery_id"]

                        # Retrieve the record
                        record = await engine.get_recovery_record_async(recovery_id)
                        assert record is not None
                        assert record["state"] == RecoveryState.COMPLETED.value

        asyncio.run(run_test())

    def test_list_recoveries(self):
        """Test listing recovery records."""
        async def run_test():
            mock_session = Mock()
            mock_model = Mock(id="rec_123", incident_id="test_merchant_20260822_100000", action_type="PAYMENT_LINK", state="COMPLETED", amount_paise=10000, currency="INR", razorpay_payment_link_id="plink_sim_123", razorpay_payment_status="created", recovered_amount_paise=0, error_message=None)
            mock_repo = AsyncMock()
            mock_repo.create = AsyncMock(return_value=mock_model)
            mock_repo.get_all = AsyncMock(return_value=[mock_model])
            mock_repo.get_by_incident_id = AsyncMock(return_value=[mock_model])

            with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                    engine = RecoveryEngine(db_session=mock_session)
                    evidence = create_base_evidence_package()
                    llm_report = create_base_llm_report()
                    policy_decision = create_auto_approved_policy_decision()

                    # Execute a recovery
                    result = await engine.execute_recovery(policy_decision, evidence, llm_report)
                    incident_id = evidence["incident_metadata"]["incident_id"]

                    # List all recoveries
                    all_recoveries = await engine.list_recoveries_async()
                    assert len(all_recoveries) >= 1

                    # List recoveries for specific incident
                    incident_recoveries = await engine.list_recoveries_async(incident_id)
                    assert len(incident_recoveries) >= 1

        asyncio.run(run_test())

    def test_execute_recovery_with_mocked_razorpay(self):
        """Test recovery execution with mocked Razorpay client."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client_class:
                mock_client = Mock()
                mock_client_class.return_value = mock_client
                mock_client.payment_link.create.return_value = {
                    "id": "plink_test_123",
                    "short_url": "https://rzp.io/l/test123",
                    "reference_id": "ref_test_123",
                    "amount": 100,
                    "currency": "INR",
                    "status": "created"
                }

                config = {
                    'razorpay_key_id': 'test_key',
                    'razorpay_key_secret': 'test_secret'
                }
                mock_session = Mock()
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=Mock())
                mock_repo.update = AsyncMock(return_value=Mock())

                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    engine = RecoveryEngine(config, db_session=mock_session)
                    assert engine.razorpay_client is not None

                    evidence = create_base_evidence_package()
                    llm_report = create_base_llm_report()
                    policy_decision = create_auto_approved_policy_decision()

                    result = await engine.execute_recovery(policy_decision, evidence, llm_report)

                    mock_client.payment_link.create.assert_called_once()
                    assert result["state"] == RecoveryState.COMPLETED.value
                    assert result["payment_link_id"] == "plink_test_123"
                    assert result["payment_link_url"] == "https://rzp.io/l/test123"
                    assert result["amount_paise"] == 10000

        asyncio.run(run_test())

    def test_cleanup_old_records(self):
        """Test cleaning up old recovery records."""
        async def run_test():
            mock_session = Mock()
            mock_repo = AsyncMock()
            mock_repo.create = AsyncMock(return_value=Mock())
            mock_repo.delete_older_than = AsyncMock(return_value=2)
            mock_repo.get_all = AsyncMock(return_value=[])

            with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                engine = RecoveryEngine(db_session=mock_session)
                evidence = create_base_evidence_package()
                llm_report = create_base_llm_report()
                policy_decision = create_auto_approved_policy_decision()

                result1 = await engine.execute_recovery(policy_decision, evidence, llm_report)

                cleaned = await engine.cleanup_old_records_async(older_than_hours=0)
                assert cleaned >= 2

        asyncio.run(run_test())

    def test_maximum_recovery_amount_revenue_at_risk_limit(self):
        """Test that recovery fails when amount exceeds revenue_at_risk limit."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client:
                mock_client.return_value = None
                mock_session = Mock()
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=Mock())

                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    engine = RecoveryEngine(db_session=mock_session)

                    evidence = create_base_evidence_package()
                    evidence["impact_evidence"]["revenue_at_risk"]["paise"] = 1000  # 10 INR

                    llm_report = create_base_llm_report()
                    llm_report["recovery"]["amount"]["paise"] = 5000  # 50 INR

                    policy_decision = create_auto_approved_policy_decision()

                    result = await engine.execute_recovery(policy_decision, evidence, llm_report)

                    assert result["state"] == RecoveryState.FAILED.value
                    assert "exceeds maximum allowed" in result.get("error", "").lower()

        asyncio.run(run_test())

    def test_maximum_recovery_amount_config_limit(self):
        """Test that recovery fails when amount exceeds configured limit."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client:
                mock_client.return_value = None
                mock_session = Mock()
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=Mock())

                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    config = {'maximum_recovery_paise': 2000}  # 20 INR limit
                    with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                        engine = RecoveryEngine(config, db_session=mock_session)

                        evidence = create_base_evidence_package()
                        evidence["impact_evidence"]["revenue_at_risk"] = {}  # Clear revenue_at_risk to test config limit

                        llm_report = create_base_llm_report()
                        llm_report["recovery"]["amount"]["paise"] = 5000  # 50 INR

                        policy_decision = create_auto_approved_policy_decision()

                        result = await engine.execute_recovery(policy_decision, evidence, llm_report)

                        assert result["state"] == RecoveryState.FAILED.value
                        assert "exceeds maximum allowed" in result.get("error", "").lower()

        asyncio.run(run_test())

    def test_maximum_recovery_amount_env_limit(self):
        """Test that recovery fails when amount exceeds environment variable limit."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client:
                mock_client.return_value = None
                mock_session = Mock()
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=Mock())

                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    with patch.dict(os.environ, {'SIMULATION_MODE': 'true', 'MAXIMUM_RECOVERY_PAISA': '3000'}):
                        engine = RecoveryEngine(db_session=mock_session)

                        evidence = create_base_evidence_package()
                        evidence["impact_evidence"]["revenue_at_risk"] = {}  # Clear revenue_at_risk to test env limit

                        llm_report = create_base_llm_report()
                        llm_report["recovery"]["amount"]["paise"] = 5000  # 50 INR

                        policy_decision = create_auto_approved_policy_decision()

                        result = await engine.execute_recovery(policy_decision, evidence, llm_report)

                        assert result["state"] == RecoveryState.FAILED.value
                        assert "exceeds maximum allowed" in result.get("error", "").lower()

        asyncio.run(run_test())

    def test_maximum_recovery_amount_within_limits(self):
        """Test that recovery succeeds when amount is within limits."""
        async def run_test():
            with patch('app.recovery_engine.razorpay.Client') as mock_client:
                mock_client.return_value = None
                mock_session = Mock()
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=Mock())
                mock_repo.update = AsyncMock(return_value=Mock())

                with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                    with patch.dict(os.environ, {'SIMULATION_MODE': 'true'}):
                        engine = RecoveryEngine(db_session=mock_session)

                        evidence = create_base_evidence_package()
                        evidence["impact_evidence"]["revenue_at_risk"]["paise"] = 50000  # 500 INR

                        llm_report = create_base_llm_report()
                        llm_report["recovery"]["amount"]["paise"] = 10000  # 100 INR

                        policy_decision = create_auto_approved_policy_decision()

                        result = await engine.execute_recovery(policy_decision, evidence, llm_report)

                        assert result["state"] == RecoveryState.COMPLETED.value
                        assert result["amount_paise"] == 10000

        asyncio.run(run_test())

    def test_execute_recovery_with_uuid_incident_id(self):
        """Test recovery execution with a standard UUID string incident ID."""
        async def run_test():
            mock_session = Mock()
            mock_repo = AsyncMock()
            mock_repo.create = AsyncMock(return_value=Mock())
            mock_repo.update = AsyncMock(return_value=Mock())

            with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                engine = RecoveryEngine(db_session=mock_session)

                evidence = create_base_evidence_package()
                evidence["incident_metadata"]["incident_id"] = "123e4567-e89b-12d3-a456-426614174000"

                llm_report = create_base_llm_report()
                policy_decision = create_auto_approved_policy_decision()

                result = await engine.execute_recovery(policy_decision, evidence, llm_report)
                assert result["incident_id"] == "123e4567-e89b-12d3-a456-426614174000"

        asyncio.run(run_test())

    def test_execute_recovery_with_string_incident_id(self):
        """Test recovery execution with business string incident ID like scenario_a_merchant_20260822_100000."""
        async def run_test():
            mock_session = Mock()
            mock_repo = AsyncMock()
            mock_repo.create = AsyncMock(return_value=Mock())
            mock_repo.update = AsyncMock(return_value=Mock())

            with patch('app.repositories.recovery_repository.RecoveryRepository', return_value=mock_repo):
                engine = RecoveryEngine(db_session=mock_session)

                evidence = create_base_evidence_package()
                evidence["incident_metadata"]["incident_id"] = "scenario_a_merchant_20260822_100000"

                llm_report = create_base_llm_report()
                policy_decision = create_auto_approved_policy_decision()

                result = await engine.execute_recovery(policy_decision, evidence, llm_report)
                assert result["incident_id"] == "scenario_a_merchant_20260822_100000"

        asyncio.run(run_test())


if __name__ == "__main__":
    pytest.main([__file__])
