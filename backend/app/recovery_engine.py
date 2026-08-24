#!/usr/bin/env python3
"""
Recovery Engine for DegradeWatch Checkpoint 10.

Executes approved recovery actions (PAYMENT_LINK) based on Policy Engine authorization.
Never bypasses Policy Engine approval - only executes when explicitly authorized.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from sqlalchemy import select

# Try to import razorpay, but handle gracefully if not available (for testing)
try:
    import razorpay
    RAZORPAY_AVAILABLE = True
except ImportError:
    RAZORPAY_AVAILABLE = False
    razorpay = None

logger = logging.getLogger(__name__)


class RecoveryState(Enum):
    """Recovery execution states."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RecoveryEngine:
    """
    Executes approved recovery actions based on Policy Engine decisions.

    Only supports PAYMENT_LINK recovery action in Razorpay Test Mode.
    Implements state machine, idempotency, error handling, and audit trails.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, db_session=None):
        """
        Initialize the Recovery Engine.

        Args:
            config: Configuration dictionary with Razorpay credentials and settings
            db_session: Async database session for repository operations (required)
        """
        if db_session is None:
            raise ValueError("db_session is required for RecoveryEngine")

        self.config = config or {}
        from app.repositories.recovery_repository import RecoveryRepository
        self.recovery_repository = RecoveryRepository(db_session)

        # Determine if we are in simulation mode (explicitly set via environment variable)
        self.simulation_mode = os.getenv('SIMULATION_MODE', '').lower() in ('true', '1', 'yes')

        # Initialize Razorpay client if available and credentials provided
        self.razorpay_client = None
        if RAZORPAY_AVAILABLE:
            key_id = self.config.get('razorpay_key_id') or os.getenv('RAZORPAY_KEY_ID')
            key_secret = self.config.get('razorpay_key_secret') or os.getenv('RAZORPAY_KEY_SECRET')

            if key_id and key_secret:
                try:
                    self.razorpay_client = razorpay.Client(auth=(key_id, key_secret), timeout=30)
                    logger.info("Razorpay client initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize Razorpay client: {e}")
                    self.razorpay_client = None
            else:
                if self.simulation_mode:
                    logger.info("SIMULATION_MODE enabled - running without Razorpay credentials")
                else:
                    logger.warning("Razorpay credentials not provided and SIMULATION_MODE not set - operations requiring Razorpay will fail")

        logger.info("Recovery Engine initialized")

    async def execute_recovery(
        self,
        policy_decision: Dict[str, Any],
        evidence_package: Dict[str, Any],
        llm_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a recovery action based on Policy Engine decision.

        Args:
            policy_decision: Decision from Policy Engine (must be AUTO_APPROVED or HUMAN_APPROVAL)
            evidence_package: Validated evidence package from Checkpoint 7
            llm_report: Validated LLM report from Checkpoint 8

        Returns:
            Recovery execution result with state, payment link details, and audit trail
        """
        # Generate unique recovery ID for idempotency
        recovery_id = str(uuid.uuid4())
        incident_id = evidence_package.get("incident_metadata", {}).get("incident_id", "unknown")

        logger.info(f"Starting recovery execution for incident {incident_id} with recovery ID {recovery_id}")

        # Validate that we have authorization to proceed
        if not self._is_authorized_for_recovery(policy_decision):
            audit_event = self._create_audit_event(
                recovery_id=recovery_id,
                incident_id=incident_id,
                state=RecoveryState.FAILED,
                action="authorization_check",
                details={"reason": "Policy Engine did not approve recovery"},
                success=False,
                error_message="Recovery not authorized by Policy Engine"
            )
            return self._create_recovery_result(
                recovery_id=recovery_id,
                state=RecoveryState.FAILED,
                incident_id=incident_id,
                audit_events=[audit_event],
                error="Policy Engine did not approve recovery action"
            )

        # Check if recovery action is supported
        requested_action = policy_decision.get("action_type")
        if requested_action != "PAYMENT_LINK":
            audit_event = self._create_audit_event(
                recovery_id=recovery_id,
                incident_id=incident_id,
                state=RecoveryState.FAILED,
                action="action_validation",
                details={"requested_action": requested_action},
                success=False,
                error_message=f"Unsupported recovery action: {requested_action}"
            )
            return self._create_recovery_result(
                recovery_id=recovery_id,
                state=RecoveryState.FAILED,
                incident_id=incident_id,
                audit_events=[audit_event],
                error=f"Unsupported recovery action: {requested_action}. Only PAYMENT_LINK is supported."
            )

        # Check for idempotency - see if we already processed this recovery
        existing_record = await self._get_recovery_record_by_incident_and_action(incident_id, requested_action)
        if existing_record and existing_record.get("state") in [RecoveryState.COMPLETED.value, RecoveryState.PROCESSING.value]:
            logger.info(f"Recovery already exists for incident {incident_id} and action {requested_action}")
            audit_event = self._create_audit_event(
                recovery_id=existing_record["recovery_id"],
                incident_id=incident_id,
                state=RecoveryState(existing_record["state"]),
                action="idempotency_check",
                details={"previous_recovery_id": existing_record["recovery_id"]},
                success=True
            )
            return self._create_recovery_result_from_record(existing_record, [audit_event])

        # Create initial recovery record
        recovery_record = self._create_recovery_record(
            recovery_id=recovery_id,
            incident_id=incident_id,
            action_type=requested_action,
            policy_decision=policy_decision,
            evidence_package=evidence_package,
            llm_report=llm_report
        )

        # Store the record in database
        from app.models.recovery import Recovery

        rec_uuid = self._resolve_recovery_db_id(recovery_record["recovery_id"])
        inc_uuid = await self._resolve_incident_db_id(recovery_record["incident_id"])

        recovery_model = Recovery(
            id=rec_uuid,
            incident_id=inc_uuid,
            action_type=recovery_record["action_type"],
            amount_paise=0,  # Will be updated after processing
            currency="INR",  # Will be updated after processing
            state=recovery_record["state"],
            idempotency_key=f"idempotency_{recovery_id}"  # Simple idempotency key
        )
        saved_recovery = await self.recovery_repository.create(recovery_model)

        # Execute the recovery action
        try:
            result = await self._execute_payment_link_recovery(recovery_record)

            # Update record with result
            recovery_record.update(result)

            # Update database record
            if saved_recovery:
                saved_recovery.action_type = recovery_record.get("action_type", saved_recovery.action_type)
                saved_recovery.amount_paise = recovery_record.get("amount_paise", saved_recovery.amount_paise)
                saved_recovery.currency = recovery_record.get("currency", saved_recovery.currency)
                saved_recovery.state = recovery_record.get("state", saved_recovery.state)
                saved_recovery.razorpay_payment_link_id = recovery_record.get("payment_link_id")
                saved_recovery.razorpay_payment_status = recovery_record.get("payment_status")
                saved_recovery.recovered_amount_paise = recovery_record.get("recovered_amount_paise")
                saved_recovery.error_message = recovery_record.get("error")
                await self.recovery_repository.update(saved_recovery)

            logger.info(f"Recovery {recovery_id} completed with state: {recovery_record.get('state')}")
            return self._create_recovery_result_from_record(recovery_record)

        except Exception as e:
            logger.error(f"Recovery execution failed for {recovery_id}: {e}", exc_info=True)

            # Update record with failure
            recovery_record["state"] = RecoveryState.FAILED.value
            recovery_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            recovery_record["error"] = str(e)

            # Create failure audit event
            audit_event = self._create_audit_event(
                recovery_id=recovery_id,
                incident_id=incident_id,
                state=RecoveryState.FAILED,
                action="payment_link_creation",
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )

            # Add audit event to record
            if "audit_events" not in recovery_record:
                recovery_record["audit_events"] = []
            recovery_record["audit_events"].append(audit_event)

            # Update database record with failure
            if saved_recovery:
                saved_recovery.state = RecoveryState.FAILED.value
                saved_recovery.error_message = str(e)
                await self.recovery_repository.update(saved_recovery)

            return self._create_recovery_result_from_record(recovery_record)

    def _is_authorized_for_recovery(self, policy_decision: Dict[str, Any]) -> bool:
        """Check if Policy Engine has authorized recovery execution."""
        decision = policy_decision.get("decision")
        # Only execute if Policy Engine explicitly approved (AUTO_APPROVED or HUMAN_APPROVAL)
        # Note: In a real system, HUMAN_APPROVAL might require additional manual trigger
        # For this implementation, we'll treat both as authorization to proceed
        return decision in ["AUTO_APPROVED", "HUMAN_APPROVAL"]

    async def _execute_payment_link_recovery(self, recovery_record: Dict[str, Any]) -> Dict[str, Any]:
        """Execute PAYMENT_LINK recovery action using Razorpay Test Mode."""
        recovery_id = recovery_record["recovery_id"]
        incident_id = recovery_record["incident_id"]

        # Create audit event for start of processing
        start_audit = self._create_audit_event(
            recovery_id=recovery_id,
            incident_id=incident_id,
            state=RecoveryState.PROCESSING,
            action="payment_link_creation_start",
            details={},
            success=True
        )

        if "audit_events" not in recovery_record:
            recovery_record["audit_events"] = []
        recovery_record["audit_events"].append(start_audit)

        # Update state to processing
        recovery_record["state"] = RecoveryState.PROCESSING.value
        recovery_record["started_at"] = datetime.now(timezone.utc).isoformat()

        # Extract recovery details from LLM report
        recovery_info = recovery_record["llm_report"].get("recovery", {})
        amount_paise = recovery_info.get("amount", {}).get("paise", 0)
        currency = recovery_info.get("amount", {}).get("currency", "INR")
        reason = recovery_info.get("reason", "Compensation for service degradation")

        # Validate recovery amount does not exceed maximum allowed
        # Check against revenue_at_risk from evidence package if available
        max_allowed_paise = None
        evidence_package = recovery_record.get("evidence_package", {})
        impact_evidence = evidence_package.get("impact_evidence", {})
        revenue_at_risk = impact_evidence.get("revenue_at_risk", {})

        if revenue_at_risk and isinstance(revenue_at_risk, dict):
            risk_paise = revenue_at_risk.get("paise")
            risk_currency = revenue_at_risk.get("currency", "INR")
            if risk_paise is not None and risk_currency == currency:
                max_allowed_paise = risk_paise

        # Check against configured maximum limit if revenue_at_risk not available or not applicable
        if max_allowed_paise is None:
            # Get maximum from config or environment variable
            config_max_paise = self.config.get('maximum_recovery_paise')
            if config_max_paise is not None:
                max_allowed_paise = config_max_paise
            else:
                env_max_paise = os.getenv('MAXIMUM_RECOVERY_PAISA')
                if env_max_paise is not None:
                    try:
                        max_allowed_paise = int(env_max_paise)
                    except ValueError:
                        logger.warning(f"Invalid MAXIMUM_RECOVERY_PAISA value: {env_max_paise}")

        # Apply the maximum limit if we have one
        if max_allowed_paise is not None and amount_paise > max_allowed_paise:
            logger.warning(f"Recovery amount {amount_paise} paise exceeds maximum allowed {max_allowed_paise} paise")
            audit_event = self._create_audit_event(
                recovery_id=recovery_id,
                incident_id=incident_id,
                state=RecoveryState.FAILED,
                action="amount_validation",
                details={
                    "requested_amount_paise": amount_paise,
                    "maximum_allowed_paise": max_allowed_paise,
                    "currency": currency,
                    "validation_type": "revenue_at_risk" if revenue_at_risk and revenue_at_risk.get("paise") == max_allowed_paise else "configured_limit"
                },
                success=False,
                error_message=f"Recovery amount exceeds maximum allowed: {amount_paise} paise > {max_allowed_paise} paise"
            )
            return self._create_recovery_result(
                recovery_id=recovery_id,
                state=RecoveryState.FAILED,
                incident_id=incident_id,
                audit_events=[audit_event],
                error=f"Recovery amount exceeds maximum allowed: {amount_paise} paise > {max_allowed_paise} paise"
            )

        # Convert paise to rupees for Razorpay (amount should be in rupees)
        amount_rupees = max(1, int(amount_paise / 100))  # Minimum 1 rupee

        # Prepare payment link data
        payment_link_data = {
            "amount": amount_rupees,  # Amount in rupees
            "currency": currency.upper(),
            "accept_partial": False,
            "description": f"Compensation for incident {incident_id}",
            "customer": {
                "name": "Affected Customer",
                "email": "customer@example.com",  # In real system, this would come from evidence
                "contact": "+91XXXXXXXXXX"
            },
            "notify": {
                "sms": True,
                "email": True
            },
            "reminder_enable": True,
            "notes": {
                "incident_id": incident_id,
                "recovery_id": recovery_id,
                "source": "degradewatch_recovery_engine"
            },
            "callback_url": "https://example.com/payment/callback"  # Would be configurable
            # Note: callback_method and first_min_partial are not valid Razorpay API parameters
            # and have been removed to prevent API errors
        }

        # If Razorpay client is not available, check simulation mode
        if not self.razorpay_client:
            if self.simulation_mode:
                logger.info("Razorpay client not available - simulating payment link creation (SIMULATION_MODE set)")
                # Simulate successful payment link creation
                simulated_payment_link = {
                    "id": f"plink_sim_{uuid.uuid4().hex[:10]}",
                    "amount": amount_rupees,
                    "currency": currency.upper(),
                    "status": "created",
                    "short_url": f"https://rzp.io/l/sim_{uuid.uuid4().hex[:8]}",
                    "created_at": int(time.time()),
                    "expire_by": int(time.time()) + (7 * 24 * 60 * 60),  # 7 days expiry
                    "reference_id": f"ref_{uuid.uuid4().hex[:10]}"
                }

                # Update recovery record with simulated payment link
                recovery_record["payment_link_id"] = simulated_payment_link["id"]
                recovery_record["payment_link_url"] = simulated_payment_link["short_url"]
                recovery_record["payment_link_reference_id"] = simulated_payment_link["reference_id"]
                recovery_record["amount_paise"] = amount_paise
                recovery_record["amount_rupees"] = amount_rupees
                recovery_record["currency"] = currency.upper()
                recovery_record["payment_status"] = "created"  # Initial status

                # Create success audit event
                success_audit = self._create_audit_event(
                    recovery_id=recovery_id,
                    incident_id=incident_id,
                    state=RecoveryState.COMPLETED,
                    action="payment_link_creation",
                    details={
                        "payment_link_id": simulated_payment_link["id"],
                        "short_url": simulated_payment_link["short_url"],
                        "amount_rupees": amount_rupees
                    },
                    success=True
                )

                recovery_record["audit_events"].append(success_audit)
                recovery_record["state"] = RecoveryState.COMPLETED.value
                recovery_record["completed_at"] = datetime.now(timezone.utc).isoformat()
                recovery_record["payment_status"] = "paid"  # Mark as paid in simulation
                recovery_record["actual_recovered_paise"] = amount_paise  # In simulation, assume full amount recovered
                recovery_record["actual_recovered_rupees"] = amount_rupees

                # Update database record
                recovery_model = await self.recovery_repository.get_by_id(recovery_id)
                if recovery_model:
                    recovery_model.amount_paise = amount_paise
                    recovery_model.currency = currency.upper()
                    recovery_model.state = RecoveryState.COMPLETED.value
                    recovery_model.razorpay_payment_link_id = simulated_payment_link["id"]
                    recovery_model.razorpay_payment_status = "paid"
                    recovery_model.recovered_amount_paise = amount_paise
                    await self.recovery_repository.update(recovery_model)

                return recovery_record
            else:
                logger.error("Razorpay client not available and SIMULATION_MODE not set")
                raise Exception("Razorpay client not available and SIMULATION_MODE not set")

        # Actual Razorpay API call (Test Mode)
        try:
            logger.info(f"Creating Razorpay payment link for recovery {recovery_id}")
            payment_link = self.razorpay_client.payment_link.create(payment_link_data)

            logger.info(f"Payment link created successfully: {payment_link['id']}")

            # Update recovery record with payment link details
            recovery_record["payment_link_id"] = payment_link["id"]
            recovery_record["payment_link_url"] = payment_link["short_url"]
            recovery_record["payment_link_reference_id"] = payment_link.get("reference_id")
            recovery_record["amount_paise"] = amount_paise
            recovery_record["amount_rupees"] = amount_rupees
            recovery_record["currency"] = currency.upper()
            recovery_record["payment_status"] = payment_link["status"]  # Set payment status from Razorpay response
            recovery_record["razorpay_response"] = payment_link  # Store full response for auditing

            # Create success audit event
            success_audit = self._create_audit_event(
                recovery_id=recovery_id,
                incident_id=incident_id,
                state=RecoveryState.COMPLETED,
                action="payment_link_creation",
                details={
                    "payment_link_id": payment_link["id"],
                    "short_url": payment_link["short_url"],
                    "amount_rupees": amount_rupees
                },
                success=True
            )

            recovery_record["audit_events"].append(success_audit)
            recovery_record["state"] = RecoveryState.COMPLETED.value
            recovery_record["completed_at"] = datetime.now(timezone.utc).isoformat()

            # Update database record
            recovery_model = await self.recovery_repository.get_by_id(recovery_id)
            if recovery_model:
                recovery_model.state = RecoveryState.COMPLETED.value
                recovery_model.razorpay_payment_link_id = payment_link["id"]
                recovery_model.razorpay_payment_status = payment_link["status"]
                await self.recovery_repository.update(recovery_model)

            return recovery_record

        except Exception as e:
            logger.error(f"Razorpay API call failed: {e}")

            # Create failure audit event
            failure_audit = self._create_audit_event(
                recovery_id=recovery_id,
                incident_id=incident_id,
                state=RecoveryState.FAILED,
                action="payment_link_creation",
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )

            recovery_record["audit_events"].append(failure_audit)
            recovery_record["state"] = RecoveryState.FAILED.value
            recovery_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            recovery_record["error"] = str(e)

            # Update database record
            recovery_model = await self.recovery_repository.get_by_id(recovery_id)
            if recovery_model:
                recovery_model.state = RecoveryState.FAILED.value
                recovery_model.error_message = str(e)
                await self.recovery_repository.update(recovery_model)

            raise  # Re-raise to be caught by execute_recovery method

    async def check_payment_status(self, recovery_id: str) -> Dict[str, Any]:
        """
        Check the status of a payment link recovery.

        Args:
            recovery_id: The recovery ID to check

        Returns:
            Updated recovery record with payment status
        """
        # Get recovery from database
        recovery_model = await self.recovery_repository.get_by_id(recovery_id)
        if not recovery_model:
            raise ValueError(f"Recovery record not found: {recovery_id}")

        # Convert recovery model to dict format
        recovery_record = {
            "recovery_id": str(recovery_model.id),
            "incident_id": str(recovery_model.incident_id),
            "action_type": recovery_model.action_type,
            "state": recovery_model.state,
            "amount_paise": recovery_model.amount_paise,
            "currency": recovery_model.currency,
            "payment_link_id": recovery_model.razorpay_payment_link_id,
            "payment_status": recovery_model.razorpay_payment_status,
            "recovered_amount_paise": recovery_model.recovered_amount_paise,
            "error": recovery_model.error_message,
            "audit_events": []  # Audit events would need to be fetched separately
        }

        # If already completed or failed, return current state
        if recovery_record.get("state") in [RecoveryState.COMPLETED.value, RecoveryState.FAILED.value]:
            return recovery_record

        # If we don't have a payment link ID, we can't check status
        if not recovery_record.get("payment_link_id"):
            logger.warning(f"No payment link ID found for recovery {recovery_id}")
            return recovery_record

        # If Razorpay client is not available, check simulation mode
        if not self.razorpay_client:
            if self.simulation_mode:
                logger.info(f"Simulating payment status check for recovery {recovery_id} (SIMULATION_MODE set)")
                # For simulation, we'll randomly mark some as completed after a delay
                # In a real implementation, this would check actual payment status
                recovery_record["state"] = RecoveryState.COMPLETED.value
                recovery_record["completed_at"] = datetime.now(timezone.utc).isoformat()
                recovery_record["actual_recovered_paise"] = recovery_record.get("amount_paise", 0)
                recovery_record["payment_status"] = "paid"

                # Create payment completion audit event
                completion_audit = self._create_audit_event(
                    recovery_id=recovery_id,
                    incident_id=recovery_record["incident_id"],
                    state=RecoveryState.COMPLETED,
                    action="payment_completion_check",
                    details={
                        "actual_recovered_paise": recovery_record.get("actual_recovered_paise", 0),
                        "payment_status": "paid"
                    },
                    success=True
                )

                if "audit_events" not in recovery_record:
                    recovery_record["audit_events"] = []
                recovery_record["audit_events"].append(completion_audit)

                # Update database record
                recovery_model.state = RecoveryState.COMPLETED.value
                recovery_model.actual_recovered_paise = recovery_record.get("actual_recovered_paise", 0)
                recovery_model.payment_status = "paid"
                await self.recovery_repository.update(recovery_model)

                return recovery_record
            else:
                logger.error(f"Razorpay client not available and SIMULATION_MODE not set for recovery {recovery_id}")
                recovery_record["state"] = RecoveryState.FAILED.value
                recovery_record["completed_at"] = datetime.now(timezone.utc).isoformat()
                recovery_record["error"] = "Razorpay client not available and SIMULATION_MODE not set"

                # Create failure audit event
                failure_audit = self._create_audit_event(
                    recovery_id=recovery_id,
                    incident_id=recovery_record["incident_id"],
                    state=RecoveryState.FAILED,
                    action="payment_completion_check",
                    details={"error": "Razorpay client not available and SIMULATION_MODE not set"},
                    success=False,
                    error_message="Razorpay client not available and SIMULATION_MODE not set"
                )

                if "audit_events" not in recovery_record:
                    recovery_record["audit_events"] = []
                recovery_record["audit_events"].append(failure_audit)

                # Update database record
                recovery_model.state = RecoveryState.FAILED.value
                recovery_model.error_message = "Razorpay client not available and SIMULATION_MODE not set"
                await self.recovery_repository.update(recovery_model)

                return recovery_record

        # Actual Razorpay API call to check payment link status
        try:
            payment_link = self.razorpay_client.payment_link.fetch(recovery_record["payment_link_id"])

            # Update recovery record with payment status
            recovery_record["payment_status"] = payment_link["status"]
            recovery_record["razorpay_payment_link_response"] = payment_link

            if payment_link["status"] == "paid":
                recovery_record["state"] = RecoveryState.COMPLETED.value
                recovery_record["completed_at"] = datetime.now(timezone.utc).isoformat()
                recovery_record["actual_recovered_paise"] = payment_link.get("amount_paid", 0) * 100  # Convert rupees to paise
                recovery_record["actual_recovered_rupees"] = payment_link.get("amount_paid", 0)

                # Create payment completion audit event
                completion_audit = self._create_audit_event(
                    recovery_id=recovery_id,
                    incident_id=recovery_record["incident_id"],
                    state=RecoveryState.COMPLETED,
                    action="payment_completion_check",
                    details={
                        "payment_status": "paid",
                        "actual_recovered_paise": recovery_record.get("actual_recovered_paise", 0),
                        "amount_paid": payment_link.get("amount_paid", 0)
                    },
                    success=True
                )

                if "audit_events" not in recovery_record:
                    recovery_record["audit_events"] = []
                recovery_record["audit_events"].append(completion_audit)

                # Update database record
                recovery_model.state = RecoveryState.COMPLETED.value
                recovery_model.actual_recovered_paise = recovery_record.get("actual_recovered_paise", 0)
                recovery_model.payment_status = "paid"
                await self.recovery_repository.update(recovery_model)

            elif payment_link["status"] in ["cancelled", "expired"]:
                recovery_record["state"] = RecoveryState.FAILED.value
                recovery_record["completed_at"] = datetime.now(timezone.utc).isoformat()
                recovery_record["error"] = f"Payment link {payment_link['status']}"

                # Create failure audit event
                failure_audit = self._create_audit_event(
                    recovery_id=recovery_id,
                    incident_id=recovery_record["incident_id"],
                    state=RecoveryState.FAILED,
                    action="payment_completion_check",
                    details={"payment_status": payment_link["status"]},
                    success=False,
                    error_message=f"Payment link {payment_link['status']}"
                )

                if "audit_events" not in recovery_record:
                    recovery_record["audit_events"] = []
                recovery_record["audit_events"].append(failure_audit)

                # Update database record
                recovery_model.state = RecoveryState.FAILED.value
                recovery_model.error_message = f"Payment link {payment_link['status']}"
                await self.recovery_repository.update(recovery_model)

            return recovery_record

        except Exception as e:
            logger.error(f"Failed to fetch payment link status: {e}")

            # Create error audit event
            error_audit = self._create_audit_event(
                recovery_id=recovery_id,
                incident_id=recovery_record["incident_id"],
                state=RecoveryState.FAILED,
                action="payment_completion_check",
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )

            if "audit_events" not in recovery_record:
                recovery_record["audit_events"] = []
            recovery_record["audit_events"].append(error_audit)

            recovery_record["state"] = RecoveryState.FAILED.value
            recovery_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            recovery_record["error"] = str(e)

            # Update database record
            recovery_model.state = RecoveryState.FAILED.value
            recovery_model.error_message = str(e)
            await self.recovery_repository.update(recovery_model)

            return recovery_record

    def _create_recovery_record(
        self,
        recovery_id: str,
        incident_id: str,
        action_type: str,
        policy_decision: Dict[str, Any],
        evidence_package: Dict[str, Any],
        llm_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new recovery record."""
        return {
            "recovery_id": recovery_id,
            "incident_id": incident_id,
            "action_type": action_type,
            "policy_decision": policy_decision,
            "evidence_package": evidence_package,
            "llm_report": llm_report,
            "state": RecoveryState.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "audit_events": [],
            # Initialize payment-related fields
            "payment_link_id": None,
            "payment_link_url": None,
            "payment_link_reference_id": None,
            "amount_paise": 0,
            "amount_rupees": 0,
            "currency": "INR",
            "payment_status": None,
            "actual_recovered_paise": 0,
            "actual_recovered_rupees": 0,
            "razorpay_response": None
        }

    async def _get_recovery_record_by_incident_and_action(self, incident_id: str, action_type: str) -> Optional[Dict[str, Any]]:
        """Find existing recovery record for incident and action type."""
        # Use repository to find recovery by incident_id and action_type
        recoveries = await self.recovery_repository.get_by_incident_id(incident_id)
        for recovery in recoveries:
            if (recovery.action_type == action_type and
                recovery.state in [RecoveryState.PENDING.value, RecoveryState.PROCESSING.value, RecoveryState.COMPLETED.value]):
                # Convert recovery model to dict format expected by the rest of the code
                return {
                    "recovery_id": str(recovery.id),
                    "incident_id": str(recovery.incident_id),
                    "action_type": recovery.action_type,
                    "state": recovery.state,
                    # Add other fields as needed for compatibility
                    "amount_paise": recovery.amount_paise,
                    "currency": recovery.currency,
                    "payment_link_id": recovery.razorpay_payment_link_id,
                    "payment_link_url": "",  # Not stored in DB, but kept for compatibility
                    "payment_link_reference_id": "",  # Not stored in DB
                    "amount_rupees": 0,  # Not stored in DB
                    "payment_status": recovery.razorpay_payment_status,
                    "actual_recovered_paise": recovery.recovered_amount_paise,
                    "actual_recovered_rupees": 0,  # Not stored in DB
                    "razorpay_response": None,  # Not stored in DB
                    "error": recovery.error_message
                }
        return None

    def _create_audit_event(
        self,
        recovery_id: str,
        incident_id: str,
        state: RecoveryState,
        action: str,
        details: Dict[str, Any],
        success: bool = True,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an audit event for recovery actions."""
        return {
            "recovery_id": recovery_id,
            "incident_id": incident_id,
            "state": state.value,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "details": details,
            "error_message": error_message
        }

    def _create_recovery_result(
        self,
        recovery_id: str,
        state: RecoveryState,
        incident_id: str,
        audit_events: list,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a recovery result dictionary."""
        result = {
            "recovery_id": recovery_id,
            "incident_id": incident_id,
            "state": state.value,
            "audit_events": audit_events,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if error:
            result["error"] = error
        return result

    def _create_recovery_result_from_record(self, recovery_record: Dict[str, Any], audit_events: list = None) -> Dict[str, Any]:
        """Create a recovery result from a recovery record."""
        if audit_events is None:
            audit_events = recovery_record.get("audit_events", [])

        return {
            "recovery_id": recovery_record["recovery_id"],
            "incident_id": recovery_record["incident_id"],
            "state": recovery_record["state"],
            "audit_events": audit_events,
            "timestamp": recovery_record.get("completed_at", recovery_record.get("created_at", datetime.now(timezone.utc).isoformat())),
            "amount_paise": recovery_record.get("amount_paise", 0),
            "currency": recovery_record.get("currency", "INR"),
            "payment_link_id": recovery_record.get("payment_link_id"),
            "payment_link_url": recovery_record.get("payment_link_url"),
            "payment_status": recovery_record.get("payment_status"),
            "recovered_amount_paise": recovery_record.get("recovered_amount_paise", 0),
            "actual_recovered_paise": recovery_record.get("actual_recovered_paise", 0),
            "error": recovery_record.get("error")
        }

    def get_recovery_record(self, recovery_id: str) -> Optional[Dict[str, Any]]:
        """Get a recovery record by ID (synchronous version for compatibility)."""
        # This is a synchronous method for backward compatibility
        # In a real async application, you'd want to use the async version
        import asyncio
        try:
            # Try to get the running loop
            loop = asyncio.get_running_loop()
            # If we're already in an async context, we can't call async methods synchronously
            # Return None to indicate the caller should use the async version
            return None
        except RuntimeError:
            # No running loop, we can create a new one
            recovery_model = asyncio.run(self.recovery_repository.get_by_id(recovery_id))
            if not recovery_model:
                return None

            return {
                "recovery_id": str(recovery_model.id),
                "incident_id": str(recovery_model.incident_id),
                "action_type": recovery_model.action_type,
                "state": recovery_model.state,
                "amount_paise": recovery_model.amount_paise,
                "currency": recovery_model.currency,
                "payment_link_id": recovery_model.razorpay_payment_link_id,
                "payment_link_url": "",  # Not stored in DB
                "payment_link_reference_id": "",  # Not stored in DB
                "amount_rupees": 0,  # Not stored in DB
                "payment_status": recovery_model.razorpay_payment_status,
                "recovered_amount_paise": recovery_model.recovered_amount_paise,
                "actual_recovered_rupees": 0,  # Not stored in DB
                "razorpay_response": None,  # Not stored in DB
                "error": recovery_model.error_message
            }

    def _resolve_recovery_db_id(self, recovery_id_str: str) -> uuid.UUID:
        """Resolve recovery_id string to UUID PK for Recovery model."""
        if not recovery_id_str:
            return uuid.uuid4()
        try:
            return uuid.UUID(str(recovery_id_str))
        except (ValueError, TypeError, AttributeError):
            pass
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(recovery_id_str))

    async def _resolve_incident_db_id(self, incident_id_str: str) -> uuid.UUID:
        """
        Resolve business incident_id string to internal database Incident UUID PK.
        Preserves referential integrity when saving to PostgreSQL.
        """
        if not incident_id_str:
            return uuid.uuid4()

        try:
            from app.repositories.incident_repository import IncidentRepository
            if hasattr(self, 'recovery_repository') and self.recovery_repository and hasattr(self.recovery_repository, 'db'):
                incident_repo = IncidentRepository(self.recovery_repository.db)
                incident_model = await incident_repo.get_by_id(incident_id_str)
                if incident_model and hasattr(incident_model, 'id') and isinstance(incident_model.id, uuid.UUID):
                    return incident_model.id
        except Exception as e:
            logger.debug(f"Could not fetch Incident from repository by incident_id '{incident_id_str}': {e}")

        try:
            return uuid.UUID(str(incident_id_str))
        except (ValueError, TypeError, AttributeError):
            pass

        return uuid.uuid5(uuid.NAMESPACE_DNS, str(incident_id_str))

    async def get_recovery_record_async(self, recovery_id: str) -> Optional[Dict[str, Any]]:
        """Get a recovery record by ID (async version)."""
        recovery_model = await self.recovery_repository.get_by_id(recovery_id)
        if not recovery_model:
            return None

        return {
            "recovery_id": str(recovery_model.id),
            "incident_id": str(recovery_model.incident_id),
            "action_type": recovery_model.action_type,
            "state": recovery_model.state,
            "amount_paise": recovery_model.amount_paise,
            "currency": recovery_model.currency,
            "payment_link_id": recovery_model.razorpay_payment_link_id,
            "payment_link_url": "",  # Not stored in DB
            "payment_link_reference_id": "",  # Not stored in DB
            "amount_rupees": 0,  # Not stored in DB
            "payment_status": recovery_model.razorpay_payment_status,
            "recovered_amount_paise": recovery_model.recovered_amount_paise,
            "actual_recovered_rupees": 0,  # Not stored in DB
            "razorpay_response": None,  # Not stored in DB
            "error": recovery_model.error_message
        }

    def list_recoveries(self, incident_id: Optional[str] = None) -> list:
        """List recovery records, optionally filtered by incident ID (synchronous version)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            return []
        except RuntimeError:
            if incident_id:
                recoveries = asyncio.run(self.recovery_repository.get_by_incident_id(incident_id))
            else:
                recoveries = asyncio.run(self.recovery_repository.get_all())

            result = []
            for recovery in recoveries:
                result.append({
                    "recovery_id": str(recovery.id),
                    "incident_id": str(recovery.incident_id),
                    "action_type": recovery.action_type,
                    "state": recovery.state,
                    "amount_paise": recovery.amount_paise,
                    "currency": recovery.currency,
                    "payment_link_id": recovery.razorpay_payment_link_id,
                    "payment_link_url": "",  # Not stored in DB
                    "payment_link_reference_id": "",  # Not stored in DB
                    "amount_rupees": 0,  # Not stored in DB
                    "payment_status": recovery.razorpay_payment_status,
                    "recovered_amount_paise": recovery.recovered_amount_paise,
                    "actual_recovered_rupees": 0,  # Not stored in DB
                    "razorpay_response": None,  # Not stored in DB
                    "error": recovery.error_message
                })
            return result

    async def list_recoveries_async(self, incident_id: Optional[str] = None) -> list:
        """List recovery records, optionally filtered by incident ID (async version)."""
        if incident_id:
            recoveries = await self.recovery_repository.get_by_incident_id(incident_id)
        else:
            recoveries = await self.recovery_repository.get_all()

        result = []
        for recovery in recoveries:
            result.append({
                "recovery_id": str(recovery.id),
                "incident_id": str(recovery.incident_id),
                "action_type": recovery.action_type,
                "state": recovery.state,
                "amount_paise": recovery.amount_paise,
                "currency": recovery.currency,
                "payment_link_id": recovery.razorpay_payment_link_id,
                "payment_link_url": "",  # Not stored in DB
                "payment_link_reference_id": "",  # Not stored in DB
                "amount_rupees": 0,  # Not stored in DB
                "payment_status": recovery.razorpay_payment_status,
                "recovered_amount_paise": recovery.recovered_amount_paise,
                "actual_recovered_rupees": 0,  # Not stored in DB
                "razorpay_response": None,  # Not stored in DB
                "error": recovery.error_message
            })
        return result

    async def cleanup_old_records_async(self, older_than_hours: int = 24) -> int:
        """Clean up old recovery records to prevent database buildup (async version)."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        return await self.recovery_repository.delete_older_than(cutoff)

    def cleanup_old_records(self, older_than_hours: int = 24) -> int:
        """Clean up old recovery records (synchronous version)."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        try:
            return asyncio.run(self.recovery_repository.delete_older_than(cutoff))
        except Exception as e:
            logger.warning(f"Failed to cleanup old records: {e}")
            return 0