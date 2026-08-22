"""
Main entry point for the DegradeWatch backend API.
Provides REST endpoints for the frontend application.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

# Import existing components
from app.evidence_package import EvidencePackageBuilder
from app.llm_report_generator import LLMReportGenerator
from app.policy_engine import PolicyEngine
from app.recovery_engine import RecoveryEngine

app = FastAPI(
    title="DegradeWatch API",
    description="Backend API for DegradeWatch frontend application",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores (in production, these would be databases)
_incidents_store: Dict[str, Dict[str, Any]] = {}
_evidence_store: Dict[str, Dict[str, Any]] = {}
_llm_reports_store: Dict[str, Dict[str, Any]] = {}
_policy_decisions_store: Dict[str, Dict[str, Any]] = {}
_recovery_store: Dict[str, Dict[str, Any]] = {}
_approvals_store: Dict[str, Dict[str, Any]] = {}

# Initialize components
evidence_builder = EvidencePackageBuilder()
llm_generator = LLMReportGenerator()
policy_engine = PolicyEngine()
recovery_engine = RecoveryEngine()

# Pydantic models for request/response validation
class IncidentBase(BaseModel):
    incident_id: str
    merchant_id: str
    detection_timestamp: str
    severity: str
    classification: str
    affected_segment: Dict[str, Any]
    impact_evidence: Dict[str, Any]

class IncidentDetail(IncidentBase):
    success_rate_evidence: Dict[str, Any]
    error_evidence: Dict[str, Any]
    localization_evidence: Dict[str, Any]
    temporal_evidence: Dict[str, Any]
    volume_evidence: Dict[str, Any]
    latency_evidence: Dict[str, Any]
    investigation_checklist: List[Dict[str, Any]]
    sample_payments: List[Dict[str, Any]]
    hypothesis_evidence: Dict[str, Any]

class RecoveryBase(BaseModel):
    recovery_id: str
    incident_id: str
    action_type: str
    state: str
    amount_paise: int
    currency: str
    created_at: str
    completed_at: Optional[str] = None

class ApprovalBase(BaseModel):
    approval_id: str
    incident_id: str
    merchant_id: str
    severity: str
    revenue_at_risk_paise: int
    proposed_action: str
    policy_reason_codes: List[str]
    confidence: float
    status: str  # PENDING, APPROVED, REJECTED
    created_at: str

# Helper functions to generate demo data
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
                "Error analysis shows USER_CANCELLED as primary failure reason",
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

def initialize_demo_data():
    """Initialize demo data for the application"""
    # Create Scenario A incident
    scenario_a_evidence = create_scenario_a_evidence()
    scenario_a_llm_report = create_scenario_a_llm_report(scenario_a_evidence)

    # Store evidence and LLM report
    _evidence_store[scenario_a_evidence["incident_metadata"]["incident_id"]] = scenario_a_evidence
    _llm_reports_store[scenario_a_llm_report["incident_id"]] = scenario_a_llm_report

    # Create policy decision for Scenario A
    policy_decision_a = policy_engine.make_decision(scenario_a_evidence, scenario_a_llm_report)
    policy_decision_a["policy_id"] = str(uuid4())
    _policy_decisions_store[policy_decision_a["policy_id"]] = policy_decision_a

    # Create incident record
    incident_a = {
        "incident_id": scenario_a_evidence["incident_metadata"]["incident_id"],
        "merchant_id": scenario_a_evidence["incident_metadata"]["merchant_id"],
        "detection_timestamp": scenario_a_evidence["incident_metadata"]["detection_timestamp"],
        "severity": scenario_a_evidence["incident_metadata"]["severity"],
        "classification": scenario_a_evidence["incident_metadata"]["detector_classification"],
        "affected_segment": scenario_a_evidence["affected_segment"],
        "impact_evidence": scenario_a_evidence["impact_evidence"],
        "success_rate_evidence": scenario_a_evidence["success_rate_evidence"],
        "error_evidence": scenario_a_evidence["error_evidence"],
        "localization_evidence": scenario_a_evidence["localization_evidence"],
        "temporal_evidence": scenario_a_evidence["temporal_evidence"],
        "volume_evidence": scenario_a_evidence["volume_evidence"],
        "latency_evidence": scenario_a_evidence["latency_evidence"],
        "investigation_checklist": scenario_a_evidence["investigation_checklist"],
        "sample_payments": scenario_a_evidence["sample_payments"],
        "hypothesis_evidence": scenario_a_evidence["hypothesis_evidence"]
    }
    _incidents_store[incident_a["incident_id"]] = incident_a

    # If policy decision is AUTO_APPROVED or HUMAN_APPROVAL, create recovery record
    if policy_decision_a["decision"] in ["AUTO_APPROVED", "HUMAN_APPROVAL"]:
        recovery_result = recovery_engine.execute_recovery(
            policy_decision=policy_decision_a,
            evidence_package=scenario_a_evidence,
            llm_report=scenario_a_llm_report
        )
        _recovery_store[recovery_result["recovery_id"]] = recovery_result

        # If HUMAN_APPROVAL, create approval record
        if policy_decision_a["decision"] == "HUMAN_APPROVAL":
            approval_record = {
                "approval_id": str(uuid4()),
                "incident_id": incident_a["incident_id"],
                "merchant_id": incident_a["merchant_id"],
                "severity": incident_a["severity"],
                "revenue_at_risk_paise": incident_a["impact_evidence"]["revenue_at_risk"]["paise"],
                "proposed_action": "PAYMENT_LINK",
                "policy_reason_codes": policy_decision_a["reason_codes"],
                "confidence": scenario_a_llm_report["summary"]["confidence"],
                "status": "PENDING",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            _approvals_store[approval_record["approval_id"]] = approval_record

    # Create Scenario E incident (customer-caused, should be blocked)
    scenario_e_evidence = create_scenario_e_evidence()
    scenario_e_llm_report = create_scenario_e_llm_report(scenario_e_evidence)

    # Store evidence and LLM report
    _evidence_store[scenario_e_evidence["incident_metadata"]["incident_id"]] = scenario_e_evidence
    _llm_reports_store[scenario_e_llm_report["incident_id"]] = scenario_e_llm_report

    # Create policy decision for Scenario E
    policy_decision_e = policy_engine.make_decision(scenario_e_evidence, scenario_e_llm_report)
    policy_decision_e["policy_id"] = str(uuid4())
    _policy_decisions_store[policy_decision_e["policy_id"]] = policy_decision_e

    # Create incident record
    incident_e = {
        "incident_id": scenario_e_evidence["incident_metadata"]["incident_id"],
        "merchant_id": scenario_e_evidence["incident_metadata"]["merchant_id"],
        "detection_timestamp": scenario_e_evidence["incident_metadata"]["detection_timestamp"],
        "severity": scenario_e_evidence["incident_metadata"]["severity"],
        "classification": scenario_e_evidence["incident_metadata"]["detector_classification"],
        "affected_segment": scenario_e_evidence["affected_segment"],
        "impact_evidence": scenario_e_evidence["impact_evidence"],
        "success_rate_evidence": scenario_e_evidence["success_rate_evidence"],
        "error_evidence": scenario_e_evidence["error_evidence"],
        "localization_evidence": scenario_e_evidence["localization_evidence"],
        "temporal_evidence": scenario_e_evidence["temporal_evidence"],
        "volume_evidence": scenario_e_evidence["volume_evidence"],
        "latency_evidence": scenario_e_evidence["latency_evidence"],
        "investigation_checklist": scenario_e_evidence["investigation_checklist"],
        "sample_payments": scenario_e_evidence["sample_payments"],
        "hypothesis_evidence": scenario_e_evidence["hypothesis_evidence"]
    }
    _incidents_store[incident_e["incident_id"]] = incident_e

    # Scenario E should not create recovery or approval (customer-caused, blocked)
    # But we can still create a recovery record in FAILED state to show it was attempted and blocked
    if policy_decision_e["decision"] == "BLOCKED":
        # Create a recovery record showing it was blocked
        recovery_blocked = {
            "recovery_id": str(uuid4()),
            "incident_id": incident_e["incident_id"],
            "action_type": "BLOCKED",
            "state": "NOT_AUTHORIZED",
            "amount_paise": 0,
            "currency": "INR",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": "Recovery blocked by policy engine - customer-caused issue"
        }
        _recovery_store[recovery_blocked["recovery_id"]] = recovery_blocked

# Initialize demo data on startup
initialize_demo_data()

# API Endpoints

# Merchant endpoints
@app.get("/api/merchant/overview")
async def get_merchant_overview():
    """Get overview of merchant's payment health"""
    # In a real app, we would filter by merchant_id from auth token
    # For demo, we'll return aggregate data from all incidents

    total_incidents = len(_incidents_store)
    active_incidents = len([inc for inc in _incidents_store.values() if inc["classification"] == "INCIDENT"])
    total_revenue_at_risk = sum(
        inc["impact_evidence"]["revenue_at_risk"]["paise"]
        for inc in _incidents_store.values()
    )

    # Calculate overall success rate (simplified)
    baseline_success_rates = [
        inc["success_rate_evidence"]["baseline_success_rate"]
        for inc in _incidents_store.values()
    ]
    current_success_rates = [
        inc["success_rate_evidence"]["current_success_rate"]
        for inc in _incidents_store.values()
    ]

    avg_baseline = sum(baseline_success_rates) / len(baseline_success_rates) if baseline_success_rates else 0
    avg_current = sum(current_success_rates) / len(current_success_rates) if current_success_rates else 0
    overall_success_change = avg_current - avg_baseline

    return {
        "total_incidents": total_incidents,
        "active_incidents": active_incidents,
        "overall_success_rate_change": round(overall_success_change, 4),
        "total_revenue_at_risk_paise": total_revenue_at_risk,
        "recent_incidents": list(_incidents_store.values())[:5]  # Most recent 5
    }

@app.get("/api/merchant/incidents")
async def get_merchant_incidents():
    """Get list of incidents for the merchant"""
    # In a real app, filter by merchant_id from auth token
    return list(_incidents_store.values())

@app.get("/api/merchant/incidents/{incident_id}")
async def get_merchant_incident_detail(incident_id: str):
    """Get detailed incident information for merchant view"""
    if incident_id not in _incidents_store:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident = _incidents_store[incident_id]
    evidence = _evidence_store.get(incident_id, {})
    llm_report = _llm_reports_store.get(incident_id, {})
    policy_decision = {}

    # Find policy decision for this incident
    for policy in _policy_decisions_store.values():
        if policy.get("incident_id") == incident_id:
            policy_decision = policy
            break

    recovery = {}
    for rec in _recovery_store.values():
        if rec.get("incident_id") == incident_id:
            recovery = rec
            break

    return {
        "incident": incident,
        "evidence": evidence,
        "llm_report": llm_report,
        "policy_decision": policy_decision,
        "recovery": recovery
    }

@app.get("/api/merchant/recoveries")
async def get_merchant_recoveries():
    """Get list of recoveries for the merchant"""
    # In a real app, filter by merchant_id from auth token
    return list(_recovery_store.values())

# Support endpoints
@app.get("/api/support/incidents")
async def get_support_incidents():
    """Get list of incidents for support/operations console"""
    incidents_with_status = []
    for incident in _incidents_store.values():
        # Get latest policy decision and recovery status for this incident
        policy_decision = {}
        recovery_state = "UNKNOWN"

        for policy in _policy_decisions_store.values():
            if policy.get("incident_id") == incident["incident_id"]:
                policy_decision = policy
                break

        for recovery in _recovery_store.values():
            if recovery.get("incident_id") == incident["incident_id"]:
                recovery_state = recovery.get("state", "UNKNOWN")
                break

        incident_with_status = incident.copy()
        incident_with_status["policy_status"] = policy_decision.get("decision", "UNKNOWN")
        incident_with_status["recovery_status"] = recovery_state
        incidents_with_status.append(incident_with_status)

    return incidents_with_status

@app.get("/api/support/incidents/{incident_id}")
async def get_support_incident_detail(incident_id: str):
    """Get detailed incident information for support/forensic view"""
    if incident_id not in _incidents_store:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident = _incidents_store[incident_id]
    evidence = _evidence_store.get(incident_id, {})
    llm_report = _llm_reports_store.get(incident_id, {})
    policy_decision = {}

    # Find policy decision for this incident
    for policy in _policy_decisions_store.values():
        if policy.get("incident_id") == incident_id:
            policy_decision = policy
            break

    recovery = {}
    for rec in _recovery_store.values():
        if rec.get("incident_id") == incident_id:
            recovery = rec
            break

    audit_events = []
    if recovery:
        audit_events = recovery.get("audit_events", [])

    return {
        "incident": incident,
        "evidence": evidence,
        "llm_report": llm_report,
        "policy_decision": policy_decision,
        "recovery": recovery,
        "audit_trail": audit_events
    }

@app.get("/api/support/evidence/{incident_id}")
async def get_support_evidence(incident_id: str):
    """Get evidence package for incident"""
    if incident_id not in _evidence_store:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return _evidence_store[incident_id]

@app.get("/api/support/audit/{incident_id}")
async def get_support_audit(incident_id: str):
    """Get audit trail for incident"""
    # Find recovery record for this incident to get audit events
    audit_events = []
    for recovery in _recovery_store.values():
        if recovery.get("incident_id") == incident_id:
            audit_events = recovery.get("audit_events", [])
            break

    if not audit_events:
        raise HTTPException(status_code=404, detail="Audit trail not found")

    return {"audit_trail": audit_events}

# Approval endpoints
@app.get("/api/approvals")
async def get_approvals():
    """Get list of pending approvals"""
    # Return only pending approvals for the approval queue
    pending_approvals = [
        approval for approval in _approvals_store.values()
        if approval["status"] == "PENDING"
    ]
    return pending_approvals

@app.get("/api/approvals/{approval_id}")
async def get_approval_detail(approval_id: str):
    """Get detailed approval information"""
    if approval_id not in _approvals_store:
        raise HTTPException(status_code=404, detail="Approval not found")

    approval = _approvals_store[approval_id]

    # Get related incident, evidence, LLM report, policy decision
    incident = _incidents_store.get(approval["incident_id"], {})
    evidence = _evidence_store.get(approval["incident_id"], {})
    llm_report = _llm_reports_store.get(approval["incident_id"], {})
    policy_decision = {}

    # Find policy decision for this incident
    for policy in _policy_decisions_store.values():
        if policy.get("incident_id") == approval["incident_id"]:
            policy_decision = policy
            break

    return {
        "approval": approval,
        "incident": incident,
        "evidence": evidence,
        "llm_report": llm_report,
        "policy_decision": policy_decision
    }

@app.post("/api/approvals/{approval_id}/approve")
async def approve_approval(approval_id: str):
    """Approve a pending recovery action"""
    if approval_id not in _approvals_store:
        raise HTTPException(status_code=404, detail="Approval not found")

    approval = _approvals_store[approval_id]
    if approval["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Approval is not pending")

    # Get the related incident and LLM report
    incident = _incidents_store.get(approval["incident_id"], {})
    llm_report = _llm_reports_store.get(approval["incident_id"], {})
    if not incident or not llm_report:
        raise HTTPException(status_code=404, detail="Related incident or LLM report not found")

    # Find the policy decision for this incident
    policy_decision = {}
    for policy in _policy_decisions_store.values():
        if policy.get("incident_id") == approval["incident_id"]:
            policy_decision = policy
            break

    if not policy_decision:
        raise HTTPException(status_code=404, detail="Policy decision not found")

    # Update the approval status
    approval["status"] = "APPROVED"
    approval["updated_at"] = datetime.now(timezone.utc).isoformat()
    _approvals_store[approval_id] = approval

    # Execute the recovery (since now approved)
    recovery_result = recovery_engine.execute_recovery(
        policy_decision=policy_decision,
        evidence_package=incident,
        llm_report=llm_report
    )

    # Store the recovery record
    _recovery_store[recovery_result["recovery_id"]] = recovery_result

    return {"message": "Recovery approved and executed", "recovery_id": recovery_result["recovery_id"]}

@app.post("/api/approvals/{approval_id}/reject")
async def reject_approval(approval_id: str):
    """Reject a pending recovery action"""
    if approval_id not in _approvals_store:
        raise HTTPException(status_code=404, detail="Approval not found")

    approval = _approvals_store[approval_id]
    if approval["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Approval is not pending")

    # Update the approval status
    approval["status"] = "REJECTED"
    approval["updated_at"] = datetime.now(timezone.utc).isoformat()
    _approvals_store[approval_id] = approval

    # Create a recovery record showing it was rejected
    recovery_rejected = {
        "recovery_id": str(uuid4()),
        "incident_id": approval["incident_id"],
        "action_type": "PAYMENT_LINK",
        "state": "CANCELLED",
        "amount_paise": 0,
        "currency": "INR",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "error": "Recovery rejected by authorized operator"
    }
    _recovery_store[recovery_rejected["recovery_id"]] = recovery_rejected

    return {"message": "Recovery rejected", "recovery_id": recovery_rejected["recovery_id"]}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)