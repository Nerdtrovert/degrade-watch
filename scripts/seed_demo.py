#!/usr/bin/env python3
"""
Seed script for DegradeWatch demo data.
Creates Scenario A and Scenario E incidents with evidence, LLM reports, policy decisions, recoveries, and audit events.
"""
import sys
import os
from datetime import datetime, timezone
import uuid

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend'))

from app.database import SessionLocal
from app.models.merchant import Merchant
from app.models.incident import Incident
from app.models.evidence_package import EvidencePackage
from app.models.forensic_report import ForensicReport
from app.models.policy_decision import PolicyDecision
from app.models.recovery import Recovery
from app.models.audit_event import AuditEvent
from app.services.incident_service import IncidentService
from app.services.evidence_package_service import EvidencePackageService
from app.services.forensic_report_service import ForensicReportService
from app.services.policy_decision_service import PolicyDecisionService
from app.services.recovery_service import RecoveryService
from app.services.audit_event_service import AuditEventService
from app.evidence_package import EvidencePackageBuilder
from app.llm_report_generator import LLMReportGenerator
from app.policy_engine import PolicyEngine
from app.recovery_engine import RecoveryEngine

def get_or_create_merchant(db, merchant_id: str, name: str = None, description: str = None):
    """Get or create a merchant."""
    merchant = db.query(Merchant).filter(Merchant.merchant_id == merchant_id).first()
    if not merchant:
        merchant = Merchant(
            merchant_id=merchant_id,
            name=name or merchant_id,
            description=description
        )
        db.add(merchant)
        db.commit()
        db.refresh(merchant)
    return merchant

def create_scenario_a_evidence():
    """Create evidence package representing Scenario A: Localized technical issue"""
    evidence_package = {
        "incident_metadata": {
            "incident_id": "scenario_a_merchant_20260822_100000",
            "merchant_id": "scenario_a_merchant",
            "detection_timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis_window": {
                "start": "2026-08-22T09:30:00Z",
                "end": "2026-08-22T10:00:00Z",
                "duration_minutes": 30
            },
            "severity": "MEDIUM",
            "detector_classification": "INCIDENT",
            "detector_confidence": "HIGH"
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
                "customer_error_rate": 0.020,
                "technical_error_rate": 0.175,
                "other_error_rate": 0.00,
                "failure_rate": 0.195,
                "failure_breakdown": {
                    "customer_caused": 16,
                    "technical": 140,
                    "other": 0
                }
            },
            "changes": {
                "customer_error_rate_change": 0.000,
                "technical_error_rate_change": 0.145,
                "other_error_rate_change": 0.0,
                "customer_error_relative_change": 0.0,
                "technical_error_relative_change": 3.833
            },
            "error_code_distribution": {
                "GATEWAY_TIMEOUT": 100,
                "NETWORK_ERROR": 40
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
                "paise": 75000,
                "currency": "INR",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "affected_users": 75,
            "affected_transactions": 50
        },
        "investigation_checklist": [
            {
                "check": "primarily_customer_caused",
                "result": "PASS",
                "details": "Technical error rate increased significantly while customer error rate unchanged"
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
        "sample_payments": [
            {
                "payment_id": "pay_sample_001",
                "timestamp": "2026-08-22T09:45:00Z",
                "amount": {"paise": 15000, "currency": "INR"},
                "status": "FAILED",
                "failure_reason": "GATEWAY_TIMEOUT"
            }
        ],
        "hypothesis_evidence": {}
    }
    return evidence_package

def create_scenario_a_llm_report(evidence_package):
    """Create a realistic LLM report for Scenario A"""
    return {
        "incident_id": evidence_package["incident_metadata"]["incident_id"],
        "severity": evidence_package["incident_metadata"]["severity"],
        "status": "ACTION_REQUIRED",
        "summary": {
            "title": "UPI Payment Gateway Timeout - Localized Issue",
            "what_happened": "Payment success rate dropped from 95% to 80% for UPI transactions with BANK_X on Android PhonePe due to gateway timeouts",
            "where": {
                "payment_method": "UPI",
                "bank": "BANK_X",
                "device": "ANDROID",
                "upi_app": "PHONEPE"
            },
            "confidence": 0.92,
            "confidence_level": "HIGH",
            "confidence_explanation": "High confidence based on clear technical error pattern, localization to specific segment, and statistical significance",
            "evidence_summary": [
                "Success rate dropped 15 percentage points (95% → 80%)",
                "Technical error rate increased from 3% to 17.5%",
                "Error analysis shows GATEWAY_TIMEOUT as primary failure reason",
                "Issue is localized to UPI|BANK_X|ANDROID|PHONEPE segment",
                "Control segments show normal behavior"
            ]
        },
        "likely_cause": {
            "primary": "Payment gateway timeout issue with BANK_X UPI integration",
            "confidence": 0.88,
            "evidence_refs": [
                "error_evidence.error_code_distribution.GATEWAY_TIMEOUT",
                "error_evidence.changes.technical_error_rate_change"
            ]
        },
        "alternative_hypotheses": [
            {
                "hypothesis": "Customer network connectivity issues",
                "evidence_refs": ["error_evidence.changes.customer_error_rate_change"],
                "assessment": "CONTRADICTED"
            },
            {
                "hypothesis": "Bank server overload",
                "evidence_refs": ["error_evidence.error_code_distribution.NETWORK_ERROR"],
                "assessment": "CONTRADICTED"
            }
        ],
        "recommended_next_steps": [
            "Monitor payment success rate for the next 15 minutes",
            "Check BANK_X gateway status and logs",
            "Prepare customer communication if issue persists",
            "Have fallback routing options ready"
        ],
        "recovery": {
            "eligible": True,
            "recommendation": "PAYMENT_LINK",
            "amount": {"paise": 15000, "currency": "INR"},
            "reason": "To compensate affected users for failed transactions due to gateway timeout"
        },
        "timeline": [
            {
                "time": evidence_package["incident_metadata"]["detection_timestamp"],
                "event": "Incident detected by automated monitoring"
            },
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "event": "Forensic analysis completed"
            }
        ]
    }

def create_scenario_e_evidence():
    """Create evidence package representing Scenario E: Customer-caused issue"""
    evidence_package = {
        "incident_metadata": {
            "incident_id": "scenario_e_merchant_20260822_110000",
            "merchant_id": "scenario_e_merchant",
            "detection_timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis_window": {
                "start": "2026-08-22T10:30:00Z",
                "end": "2026-08-22T11:00:00Z",
                "duration_minutes": 30
            },
            "severity": "LOW",
            "detector_classification": "NORMAL",  # Not an incident
            "detector_confidence": "MEDIUM"
        },
        "affected_segment": {
            "payment_method": "UPI",
            "bank": "BANK_Y",
            "device": "IOS",
            "upi_app": "GOOGLE_PAY",
            "hierarchy_level": "FULL_SEGMENT",
            "baseline_attempts": 1000,
            "baseline_success_rate": 0.96,
            "current_attempts": 900,
            "current_success_rate": 0.90,
            "segment_key": "UPI|BANK_Y|IOS|GOOGLE_PAY"
        },
        "success_rate_evidence": {
            "baseline_success_rate": 0.96,
            "current_success_rate": 0.90,
            "absolute_change": -0.06,
            "absolute_percentage_point_change": -6.0,
            "relative_change": -0.0625,
            "baseline_attempts": 1000,
            "current_attempts": 900,
            "statistical_significance": {
                "statistically_significant": False,  # Not significant due to sample size
                "p_value": 0.12,
                "z_score": -1.55,
                "confidence_level": 0.95
            },
            "test_type": "two_proportion_z_test",
            "interpretation": "Not statistically significant"
        },
        "error_evidence": {
            "baseline": {
                "customer_error_rate": 0.01,
                "technical_error_rate": 0.02,
                "other_error_rate": 0.00,
                "failure_rate": 0.03,
                "failure_breakdown": {
                    "customer_caused": 10,
                    "technical": 20,
                    "other": 0
                }
            },
            "current": {
                "customer_error_rate": 0.07,  # Significant increase in customer-caused
                "technical_error_rate": 0.02,
                "other_error_rate": 0.00,
                "failure_rate": 0.09,
                "failure_breakdown": {
                    "customer_caused": 63,
                    "technical": 18,
                    "other": 0
                }
            },
            "changes": {
                "customer_error_rate_change": 0.06,  # Customer-caused increase
                "technical_error_rate_change": 0.00,
                "other_error_rate_change": 0.0,
                "customer_error_relative_change": 5.0,
                "technical_error_relative_change": 0.0
            },
            "error_code_distribution": {
                "USER_CANCELLED": 50,
                "NETWORK_ERROR": 13
            },
            "error_code_shifts": {}
        },
        "localization_evidence": {
            "affected_segment": {
                "payment_method": "UPI",
                "bank": "BANK_Y",
                "device": "IOS",
                "upi_app": "GOOGLE_PAY",
                "success_rate": 0.90,
                "attempts": 900
            },
            "localization_status": "LOCALIZED",
            "control_analysis": {
                "status": "LOCALIZED",
                "message": "Control segments remain healthy",
                "control_segments": {
                    "Other banks (same device=IOS, upi_app=GOOGLE_PAY)": {
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
                "paise": 30000,
                "currency": "INR",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "affected_users": 30,
            "affected_transactions": 20
        },
        "investigation_checklist": [
            {
                "check": "primarily_customer_caused",
                "result": "FAIL",  # Primarily customer-caused
                "details": "Customer error rate increased significantly while technical error rate unchanged"
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
        "sample_payments": [
            {
                "payment_id": "pay_sample_002",
                "timestamp": "2026-08-22T10:45:00Z",
                "amount": {"paise": 20000, "currency": "INR"},
                "status": "FAILED",
                "failure_reason": "USER_CANCELLED"
            }
        ],
        "hypothesis_evidence": {}
    }
    return evidence_package

def create_scenario_e_llm_report(evidence_package):
    """Create a realistic LLM report for Scenario E"""
    return {
        "incident_id": evidence_package["incident_metadata"]["incident_id"],
        "severity": evidence_package["incident_metadata"]["severity"],
        "status": "NO_ACTION_REQUIRED",
        "summary": {
            "title": "User Initiated Payment Cancellations - Customer Behavior",
            "what_happened": "Payment success rate dropped from 96% to 90% for UPI transactions with BANK_Y on iOS Google Pay due to increased user cancellations",
            "where": {
                "payment_method": "UPI",
                "bank": "BANK_Y",
                "device": "IOS",
                "upi_app": "GOOGLE_PAY"
            },
            "confidence": 0.75,
            "confidence_level": "MEDIUM",
            "confidence_explanation": "Medium confidence based on clear customer-caused pattern, but lack of statistical significance",
            "evidence_summary": [
                "Success rate dropped 6 percentage points (96% → 90%)",
                "Customer error rate increased from 1% to 7%",
                "Technical error rate remained stable at 2%",
                "Error analysis shows USER_CANCELLET as primary failure reason",
                "Issue is localized to UPI|BANK_Y|IOS|GOOGLE_PAY segment",
                "Control segments show normal behavior"
            ]
        },
        "likely_cause": {
            "primary": "Increased user-initiated payment cancellations, possibly due to app usability issues or changing user preferences",
            "confidence": 0.70,
            "evidence_refs": [
                "error_evidence.changes.customer_error_rate_change",
                "error_evidence.error_code_distribution.USER_CANCELLED"
            ]
        },
        "alternative_hypotheses": [
            {
                "hypothesis": "Technical gateway issues",
                "evidence_refs": ["error_evidence.changes.technical_error_rate_change"],
                "assessment": "CONTRADICTED"  # Technical errors didn't increase
            },
            {
                "hypothesis": "Bank server issues",
                "evidence_refs": ["error_evidence.error_code_distribution.NETWORK_ERROR"],
                "assessment": "CONTRADICTED"  # No significant NETWORK_ERROR evidence beyond baseline
            }
        ],
        "recommended_next_steps": [
            "Analyze user flow in the Google Pay app for potential usability issues",
            "Monitor cancellation rates for the next 24 hours",
            "Consider A/B testing of payment confirmation dialogs",
            "Review recent app updates that might affect user behavior"
        ],
        "recovery": {
            "eligible": False,
            "recommendation": "NONE",
            "amount": {"paise": 0, "currency": "INR"},
            "reason": "Customer-caused issue - recovery not appropriate"
        },
        "timeline": [
            {
                "time": evidence_package["incident_metadata"]["detection_timestamp"],
                "event": "Incident detected by automated monitoring"
            },
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "event": "Forensic analysis completed"
            }
        ]
    }

def main():
    db = SessionLocal()
    try:
        # Get or create merchants
        merchant_a = get_or_create_merchant(db, "scenario_a_merchant", "Scenario A Merchant", "Merchant experiencing localized technical issue")
        merchant_e = get_or_create_merchant(db, "scenario_e_merchant", "Scenario E Merchant", "Merchant experiencing customer-caused issue")

        # Check if Scenario A incident already exists
        incident_a = db.query(Incident).filter(Incident.incident_id == "scenario_a_merchant_20260822_100000").first()
        if not incident_a:
            # Create Scenario A evidence package
            evidence_a = create_scenario_a_evidence()
            llm_report_a = create_scenario_a_llm_report(evidence_a)

            # Create incident first
            incident_obj = Incident(
                incident_id=evidence_a["incident_metadata"]["incident_id"],
                merchant_id=merchant_a.id,
                classification=evidence_a["incident_metadata"]["detector_classification"],
                severity=evidence_a["incident_metadata"]["severity"],
                status=evidence_a["incident_metadata"]["detector_classification"],  # status same as classification for now
                affected_segment=evidence_a["affected_segment"],
                detection_timestamp=datetime.fromisoformat(evidence_a["incident_metadata"]["detection_timestamp"].replace('Z', '+00:00'))
            )
            db.add(incident_obj)
            db.flush()  # Get incident ID

            # Persist evidence package
            evidence_package_obj = EvidencePackage(
                incident_id=incident_obj.id,
                schema_version="1.0",
                evidence_package=evidence_a,
                generated_at=datetime.now(timezone.utc)
            )
            db.add(evidence_package_obj)

            # Persist LLM report
            forensic_report_obj = ForensicReport(
                incident_id=incident_obj.id,
                report_status=llm_report_a["status"],
                report=llm_report_a,
                generated_at=datetime.now(timezone.utc),
                provider="groq",
                model="mixtral-8x7b-32768"
            )
            db.add(forensic_report_obj)
            db.flush()  # Get IDs for evidence_package and forensic_report

            # Link evidence and report to incident (already set via incident_id)

            # Create policy decision
            policy_engine = PolicyEngine()
            policy_decision_dict = policy_engine.make_decision(evidence_a, llm_report_a)
            policy_decision_obj = PolicyDecision(
                incident_id=incident_obj.id,
                decision=policy_decision_dict["decision"],
                reason_codes=policy_decision_dict["reason_codes"],
                human_readable_reason=policy_decision_dict["human_readable_reason"],
                requested_recovery_action=policy_decision_dict.get("requested_recovery_action"),
                policy_inputs=policy_decision_dict.get("policy_inputs"),
                decision_timestamp=datetime.now(timezone.utc)
            )
            db.add(policy_decision_obj)
            db.flush()

            # If policy decision is AUTO_APPROVED or HUMAN_APPROVAL, create recovery
            if policy_decision_dict["decision"] in ["AUTO_APPROVED", "HUMAN_APPROVAL"]:
                recovery_engine = RecoveryEngine(db_session=db)
                # For seeding, we'll simulate recovery without calling Razorpay
                recovery_result = {
                    "id": uuid.uuid4(),
                    "incident_id": incident_obj.id,
                    "action_type": "PAYMENT_LINK",
                    "amount_paise": llm_report_a["recovery"]["amount"]["paise"],
                    "currency": llm_report_a["recovery"]["amount"]["currency"],
                    "state": "PENDING",  # start as pending, will be updated when approved
                    "razorpay_payment_link_id": None,
                    "razorpay_payment_status": None,
                    "recovered_amount_paise": 0,
                    "created_at": datetime.now(timezone.utc),
                    "error_message": None,
                    "idempotency_key": f"idempotency_{incident_obj.incident_id}"
                }
                recovery_obj = Recovery(**recovery_result)
                db.add(recovery_obj)
                db.flush()

                # If HUMAN_APPROVAL, we leave recovery as PENDING for approval
                if policy_decision_dict["decision"] == "HUMAN_APPROVAL":
                    # Create audit event for recovery requested (but not yet approved)
                    audit_event = AuditEvent(
                        incident_id=incident_obj.id,
                        recovery_id=recovery_obj.id,
                        event_type="RECOVERY_REQUESTED",
                        timestamp=datetime.now(timezone.utc),
                        actor="system",
                        outcome="SUCCESS",
                        details={"action_type": "PAYMENT_LINK", "amount_paise": recovery_result["amount_paise"]}
                    )
                    db.add(audit_event)
                else:  # AUTO_APPROVED
                    # For auto-approved, we can immediately mark as processing? But let's leave as pending for demo.
                    # Actually, in the flow, auto-approved would execute recovery immediately.
                    # For seeding, we'll leave as pending to show it can be approved.
                    pass

            # Create audit events for incident creation, evidence generation, etc.
            audit_events = [
                AuditEvent(
                    incident_id=incident_obj.id,
                    event_type="INCIDENT_CREATED",
                    timestamp=incident_obj.detection_timestamp,
                    actor="detector",
                    outcome="SUCCESS",
                    details={"classification": incident_obj.classification, "severity": incident_obj.severity}
                ),
                AuditEvent(
                    incident_id=incident_obj.id,
                    event_type="EVIDENCE_GENERATED",
                    timestamp=evidence_package_obj.generated_at,
                    actor="evidence_package_builder",
                    outcome="SUCCESS",
                    details={"schema_version": evidence_package_obj.schema_version}
                ),
                AuditEvent(
                    incident_id=incident_obj.id,
                    event_type="FORENSIC_REPORT_GENERATED",
                    timestamp=forensic_report_obj.generated_at,
                    actor="llm_report_generator",
                    outcome="SUCCESS",
                    details={"status": forensic_report_obj.report_status, "provider": forensic_report_obj.provider}
                ),
                AuditEvent(
                    incident_id=incident_obj.id,
                    event_type="POLICY_EVALUATED",
                    timestamp=policy_decision_obj.decision_timestamp,
                    actor="policy_engine",
                    outcome="SUCCESS",
                    details={"decision": policy_decision_obj.decision, "reason_codes": policy_decision_obj.reason_codes}
                )
            ]
            for audit in audit_events:
                db.add(audit)

            print(f"Created Scenario A incident: {incident_obj.incident_id}")
        else:
            print(f"Scenario A incident already exists: {incident_a.incident_id}")

        # Check if Scenario E incident already exists
        incident_e = db.query(Incident).filter(Incident.incident_id == "scenario_e_merchant_20260822_110000").first()
        if not incident_e:
            # Create Scenario E evidence package
            evidence_e = create_scenario_e_evidence()
            llm_report_e = create_scenario_e_llm_report(evidence_e)

            # Create incident first
            incident_obj = Incident(
                incident_id=evidence_e["incident_metadata"]["incident_id"],
                merchant_id=merchant_e.id,
                classification=evidence_e["incident_metadata"]["detector_classification"],
                severity=evidence_e["incident_metadata"]["severity"],
                status=evidence_e["incident_metadata"]["detector_classification"],
                affected_segment=evidence_e["affected_segment"],
                detection_timestamp=datetime.fromisoformat(evidence_e["incident_metadata"]["detection_timestamp"].replace('Z', '+00:00'))
            )
            db.add(incident_obj)
            db.flush()  # Get incident ID

            # Persist evidence package
            evidence_package_obj = EvidencePackage(
                incident_id=incident_obj.id,
                schema_version="1.0",
                evidence_package=evidence_e,
                generated_at=datetime.now(timezone.utc)
            )
            db.add(evidence_package_obj)

            # Persist LLM report
            forensic_report_obj = ForensicReport(
                incident_id=incident_obj.id,
                report_status=llm_report_e["status"],
                report=llm_report_e,
                generated_at=datetime.now(timezone.utc),
                provider="groq",
                model="mixtral-8x7b-32768"
            )
            db.add(forensic_report_obj)
            db.flush()  # Get IDs for evidence_package and forensic_report

            # Link evidence and report to incident (already set via incident_id)

            # Create policy decision
            policy_engine = PolicyEngine()
            policy_decision_dict = policy_engine.make_decision(evidence_e, llm_report_e)
            policy_decision_obj = PolicyDecision(
                incident_id=incident_obj.id,
                decision=policy_decision_dict["decision"],
                reason_codes=policy_decision_dict["reason_codes"],
                human_readable_reason=policy_decision_dict["human_readable_reason"],
                requested_recovery_action=policy_decision_dict.get("requested_recovery_action"),
                policy_inputs=policy_decision_dict.get("policy_inputs"),
                decision_timestamp=datetime.now(timezone.utc)
            )
            db.add(policy_decision_obj)
            db.flush()

            # Scenario E should not create recovery (blocked), but we can create a recovery record in NOT_AUTHORIZED state
            if policy_decision_dict["decision"] == "BLOCKED":
                recovery_result = {
                    "id": uuid.uuid4(),
                    "incident_id": incident_obj.id,
                    "action_type": "NONE",
                    "amount_paise": 0,
                    "currency": "INR",
                    "state": "NOT_AUTHORIZED",
                    "razorpay_payment_link_id": None,
                    "razorpay_payment_status": None,
                    "recovered_amount_paise": 0,
                    "created_at": datetime.now(timezone.utc),
                    "error_message": "Recovery blocked by policy engine - customer-caused issue",
                    "idempotency_key": f"idempotency_{incident_obj.incident_id}"
                }
                recovery_obj = Recovery(**recovery_result)
                db.add(recovery_obj)
                db.flush()

            # Create audit events
            audit_events = [
                AuditEvent(
                    incident_id=incident_obj.id,
                    event_type="INCIDENT_CREATED",
                    timestamp=incident_obj.detection_timestamp,
                    actor="detector",
                    outcome="SUCCESS",
                    details={"classification": incident_obj.classification, "severity": incident_obj.severity}
                ),
                AuditEvent(
                    incident_id=incident_obj.id,
                    event_type="EVIDENCE_GENERATED",
                    timestamp=evidence_package_obj.generated_at,
                    actor="evidence_package_builder",
                    outcome="SUCCESS",
                    details={"schema_version": evidence_package_obj.schema_version}
                ),
                AuditEvent(
                    incident_id=incident_obj.id,
                    event_type="FORENSIC_REPORT_GENERATED",
                    timestamp=forensic_report_obj.generated_at,
                    actor="llm_report_generator",
                    outcome="SUCCESS",
                    details={"status": forensic_report_obj.report_status, "provider": forensic_report_obj.provider}
                ),
                AuditEvent(
                    incident_id=incident_obj.id,
                    event_type="POLICY_EVALUATED",
                    timestamp=policy_decision_obj.decision_timestamp,
                    actor="policy_engine",
                    outcome="SUCCESS",
                    details={"decision": policy_decision_obj.decision, "reason_codes": policy_decision_obj.reason_codes}
                )
            ]
            for audit in audit_events:
                db.add(audit)

            print(f"Created Scenario E incident: {incident_obj.incident_id}")
        else:
            print(f"Scenario E incident already exists: {incident_e.incident_id}")

        db.commit()
        print("Demo data seeding completed.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding demo data: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()