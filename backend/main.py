"""
Main entry point for the DegradeWatch backend API.
Provides REST endpoints for the frontend application.
"""
import logging
from typing import Optional, List
from fastapi import FastAPI, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import uuid

# Import existing components
from app.evidence_package import EvidencePackageBuilder
from app.llm_report_generator import LLMReportGenerator
from app.policy_engine import PolicyEngine
from app.recovery_engine import RecoveryEngine
from app.auth import get_current_active_user, get_current_merchant_id, require_role

# Import database and services
from app.database import get_async_db, AsyncSession, SyncSessionLocal, sync_engine
from app.models import Base, AuditEvent, User
from app.services.incident_service import IncidentService
from app.services.evidence_package_service import EvidencePackageService
from app.services.forensic_report_service import ForensicReportService
from app.services.policy_decision_service import PolicyDecisionService
from app.services.recovery_service import RecoveryService
from app.services.audit_event_service import AuditEventService

# Import centralized exception handling
from app.exceptions import (
    DegradeWatchException,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
    NotFoundException,
    ConflictException,
    RateLimitException,
    ServiceUnavailableException,
    PaymentProcessingException,
    ConfigurationException,
    setup_exception_handlers
)

# Create database tables using synchronous engine (for Alembic compatibility)
Base.metadata.create_all(bind=sync_engine)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Setup centralized exception handling
setup_exception_handlers(app)

# Initialize components
evidence_builder = EvidencePackageBuilder()
llm_generator = LLMReportGenerator()
policy_engine = PolicyEngine()

# Pydantic models for request/response validation
from app.database import get_sync_db
from sqlalchemy.orm import Session
from app.auth import authenticate_user, create_access_token
from app.exceptions import AuthenticationException

class LoginRequest(BaseModel):
    user_id: str
    password: str

@app.post("/api/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_sync_db)):
    user = authenticate_user(db, request.user_id, request.password)
    if not user:
        raise AuthenticationException("Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.user_id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "roles": user.role_list,
        "merchant_id": str(user.merchant_id) if user.merchant_id else None
    }


class IncidentBase(BaseModel):
    incident_id: str
    merchant_id: str
    detection_timestamp: str
    severity: str
    classification: str
    affected_segment: dict
    impact_evidence: dict

class IncidentDetail(IncidentBase):
    success_rate_evidence: dict
    error_evidence: dict
    localization_evidence: dict
    temporal_evidence: dict
    volume_evidence: dict
    latency_evidence: dict
    investigation_checklist: List[dict]
    sample_payments: List[dict]
    hypothesis_evidence: dict

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

# Helper functions to create demo data (for seeding only, not for auto-initialization)
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

# API Endpoints

# Merchant endpoints
@app.get("/api/merchant/overview")
async def get_merchant_overview(
    merchant_id: str = Depends(get_current_merchant_id),
    db: AsyncSession = Depends(get_async_db)
):
    """Get overview of merchant's payment health with optimized SQL queries"""
    try:
        incident_service = IncidentService(db)

        # Get aggregated stats directly from database
        stats = await incident_service.get_merchant_overview_stats(merchant_id)

        # Get recent incidents (limited to 5 for display)
        recent_incidents = await incident_service.get_recent_incidents(merchant_id, limit=5)

        # Calculate overall success rate change
        avg_baseline = stats['avg_baseline_success_rate']
        avg_current = stats['avg_current_success_rate']
        overall_success_change = avg_current - avg_baseline

        return {
            "total_incidents": stats['total_incidents'],
            "active_incidents": stats['active_incidents'],
            "overall_success_rate_change": round(overall_success_change * 100, 4),
            "total_revenue_at_risk_paise": stats['total_revenue_at_risk_paise'],
            "recent_incidents": [
                {
                    "incident_id": inc.incident_id,
                    "merchant_id": inc.merchant.merchant_id if inc.merchant else str(inc.merchant_id),
                    "detection_timestamp": inc.detection_timestamp.isoformat(),
                    "severity": inc.severity,
                    "classification": inc.classification,
                    "affected_segment": inc.affected_segment,
                    "impact_evidence": inc.evidence_package.evidence_package.get("impact_evidence", {}) if inc.evidence_package else {},
                    "success_rate_evidence": inc.evidence_package.evidence_package.get("success_rate_evidence", {}) if inc.evidence_package else {}
                }
                for inc in recent_incidents
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_merchant_overview: {e}")
        raise  # Let the exception handlers deal with it

@app.get("/api/merchant/incidents")
async def get_merchant_incidents(
    merchant_id: str = Depends(get_current_merchant_id),
    db: AsyncSession = Depends(get_async_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return")
):
    """Get list of incidents for the merchant with pagination"""
    try:
        incident_service = IncidentService(db)
        incidents = await incident_service.get_by_merchant_id(merchant_id, skip=skip, limit=limit)
        total = await incident_service.repository.get_count_by_merchant_id(merchant_id)

        return {
            "items": [
                {
                    "incident_id": inc.incident_id,
                    "merchant_id": inc.merchant.merchant_id if inc.merchant else str(inc.merchant_id),
                    "detection_timestamp": inc.detection_timestamp.isoformat(),
                    "severity": inc.severity,
                    "classification": inc.classification,
                    "affected_segment": inc.affected_segment,
                    "impact_evidence": inc.evidence_package.evidence_package.get("impact_evidence", {}) if inc.evidence_package else {},
                    "success_rate_evidence": inc.evidence_package.evidence_package.get("success_rate_evidence", {}) if inc.evidence_package else {}
                }
                for inc in incidents
            ],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error in get_merchant_incidents: {e}")
        raise

@app.get("/api/merchant/incidents/{incident_id}")
async def get_merchant_incident_detail(
    incident_id: str,
    merchant_id: str = Depends(get_current_merchant_id),
    db: AsyncSession = Depends(get_async_db)
):
    """Get detailed incident information for merchant view"""
    try:
        incident_service = IncidentService(db)
        incident = await incident_service.get_by_id(incident_id)
        if not incident:
            raise NotFoundException(f"Incident not found: {incident_id}")

        # Verify that the incident belongs to the current merchant
        if incident.merchant and incident.merchant.merchant_id != merchant_id:
            raise AuthorizationException("Access denied: Incident does not belong to your merchant")

        ev_pkg = incident.evidence_package.evidence_package if incident.evidence_package else {}
        report = incident.forensic_report.report if incident.forensic_report else {}
        pol = incident.policy_decision
        rec = incident.recoveries[0] if incident.recoveries else None

        return {
            "incident": {
                "incident_id": incident.incident_id,
                "merchant_id": incident.merchant.merchant_id if incident.merchant else str(incident.merchant_id),
                "detection_timestamp": incident.detection_timestamp.isoformat(),
                "severity": incident.severity,
                "classification": incident.classification,
                "affected_segment": incident.affected_segment,
                "impact_evidence": ev_pkg.get("impact_evidence", {})
            },
            "evidence": ev_pkg,
            "llm_report": report,
            "policy_decision": {
                "decision": pol.decision if pol else None,
                "reason_codes": pol.reason_codes if pol else [],
                "human_readable_reason": pol.human_readable_reason if pol else "",
                "requested_recovery_action": pol.requested_recovery_action if pol else None
            } if pol else {},
            "recovery": {
                "recovery_id": str(rec.id) if rec else None,
                "incident_id": incident.incident_id,
                "action_type": rec.action_type if rec else None,
                "amount_paise": rec.amount_paise if rec else 0,
                "currency": rec.currency if rec else "INR",
                "state": rec.state if rec else None,
                "razorpay_payment_link_id": rec.razorpay_payment_link_id if rec else None,
                "razorpay_payment_status": rec.razorpay_payment_status if rec else None,
                "recovered_amount_paise": rec.recovered_amount_paise if rec else None,
                "created_at": rec.created_at.isoformat() if rec and hasattr(rec, 'created_at') and rec.created_at else (incident.detection_timestamp.isoformat() if rec else None),
                "completed_at": rec.completed_at.isoformat() if rec and getattr(rec, 'completed_at', None) else None,
                "error_message": rec.error_message if rec else None
            } if rec else {}
        }
    except Exception as e:
        logger.error(f"Error in get_merchant_incident_detail: {e}")
        raise

@app.get("/api/merchant/recoveries")
async def get_merchant_recoveries(
    merchant_id: str = Depends(get_current_merchant_id),
    db: AsyncSession = Depends(get_async_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return")
):
    """Get list of recoveries for the merchant with pagination"""
    try:
        recovery_service = RecoveryService(db)
        recoveries = await recovery_service.get_by_merchant_id(merchant_id, skip=skip, limit=limit)
        total = await recovery_service.repository.get_count_by_merchant_id(merchant_id)

        return {
            "items": [
                {
                    "recovery_id": str(rec.id),
                    "incident_id": rec.incident.incident_id if rec.incident else str(rec.incident_id),
                    "action_type": rec.action_type,
                    "amount_paise": rec.amount_paise,
                    "currency": rec.currency,
                    "state": rec.state,
                    "razorpay_payment_link_id": rec.razorpay_payment_link_id,
                    "razorpay_payment_status": rec.razorpay_payment_status,
                    "recovered_amount_paise": rec.recovered_amount_paise,
                    "created_at": rec.created_at.isoformat() if hasattr(rec, 'created_at') and rec.created_at else None,
                    "completed_at": rec.completed_at.isoformat() if getattr(rec, 'completed_at', None) else None,
                    "error_message": rec.error_message
                }
                for rec in recoveries
            ],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error in get_merchant_recoveries: {e}")
        raise

# Support endpoints
@app.get("/api/support/incidents")
async def get_support_incidents(
    db: AsyncSession = Depends(get_async_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return")
):
    """Get list of incidents for support/operations console with pagination"""
    try:
        incident_service = IncidentService(db)
        incidents = await incident_service.get_all(skip=skip, limit=limit)
        total = await incident_service.repository.get_count()

        incidents_with_status = []
        for incident in incidents:
            ev_pkg = incident.evidence_package.evidence_package if incident.evidence_package else {}
            pol = incident.policy_decision
            rec = incident.recoveries[0] if incident.recoveries else None

            incidents_with_status.append({
                "incident_id": incident.incident_id,
                "merchant_id": incident.merchant.merchant_id if incident.merchant else str(incident.merchant_id),
                "detection_timestamp": incident.detection_timestamp.isoformat(),
                "severity": incident.severity,
                "classification": incident.classification,
                "affected_segment": incident.affected_segment,
                "impact_evidence": ev_pkg.get("impact_evidence", {}),
                "success_rate_evidence": ev_pkg.get("success_rate_evidence", {}),
                "policy_status": pol.decision if pol else "UNKNOWN",
                "recovery_status": rec.state if rec else "UNKNOWN"
            })

        return {
            "items": incidents_with_status,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error in get_support_incidents: {e}")
        raise

@app.get("/api/support/incidents/{incident_id}")
async def get_support_incident_detail(incident_id: str, db: AsyncSession = Depends(get_async_db)):
    """Get detailed incident information for support/forensic view"""
    try:
        incident_service = IncidentService(db)
        incident = await incident_service.get_by_id(incident_id)
        if not incident:
            raise NotFoundException(f"Incident not found: {incident_id}")

        ev_pkg = incident.evidence_package.evidence_package if incident.evidence_package else {}
        report = incident.forensic_report.report if incident.forensic_report else {}
        pol = incident.policy_decision
        rec = incident.recoveries[0] if incident.recoveries else None
        audit_events = incident.audit_events or []

        return {
            "incident": {
                "incident_id": incident.incident_id,
                "merchant_id": incident.merchant.merchant_id if incident.merchant else str(incident.merchant_id),
                "detection_timestamp": incident.detection_timestamp.isoformat(),
                "severity": incident.severity,
                "classification": incident.classification,
                "affected_segment": incident.affected_segment,
                "impact_evidence": ev_pkg.get("impact_evidence", {}),
                "success_rate_evidence": ev_pkg.get("success_rate_evidence", {}),
                "error_evidence": ev_pkg.get("error_evidence", {}),
                "localization_evidence": ev_pkg.get("localization_evidence", {}),
                "temporal_evidence": ev_pkg.get("temporal_evidence", {}),
                "volume_evidence": ev_pkg.get("volume_evidence", {}),
                "latency_evidence": ev_pkg.get("latency_evidence", {}),
                "investigation_checklist": ev_pkg.get("investigation_checklist", []),
                "sample_payments": ev_pkg.get("sample_payments", []),
                "hypothesis_evidence": ev_pkg.get("hypothesis_evidence", {})
            },
            "evidence": ev_pkg,
            "llm_report": report,
            "policy_decision": {
                "decision": pol.decision if pol else None,
                "reason_codes": pol.reason_codes if pol else [],
                "human_readable_reason": pol.human_readable_reason if pol else "",
                "requested_recovery_action": pol.requested_recovery_action if pol else None,
                "policy_inputs": pol.policy_inputs if pol else {}
            } if pol else {},
            "recovery": {
                "recovery_id": str(rec.id) if rec else None,
                "incident_id": incident.incident_id,
                "action_type": rec.action_type if rec else None,
                "amount_paise": rec.amount_paise if rec else 0,
                "currency": rec.currency if rec else "INR",
                "state": rec.state if rec else None,
                "razorpay_payment_link_id": rec.razorpay_payment_link_id if rec else None,
                "razorpay_payment_status": rec.razorpay_payment_status if rec else None,
                "recovered_amount_paise": rec.recovered_amount_paise if rec else None,
                "created_at": rec.created_at.isoformat() if rec and hasattr(rec, 'created_at') and rec.created_at else (incident.detection_timestamp.isoformat() if rec else None),
                "completed_at": rec.completed_at.isoformat() if rec and getattr(rec, 'completed_at', None) else None,
                "error_message": rec.error_message if rec else None
            } if rec else {},
            "audit_trail": [
                {
                    "event_id": str(event.id),
                    "incident_id": incident.incident_id,
                    "recovery_id": str(event.recovery_id) if event.recovery_id else None,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp.isoformat(),
                    "actor": event.actor,
                    "outcome": event.outcome,
                    "details": event.details
                }
                for event in audit_events
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_support_incident_detail: {e}")
        raise

@app.get("/api/support/evidence/{incident_id}")
async def get_support_evidence(incident_id: str, db: AsyncSession = Depends(get_async_db)):
    """Get evidence package for incident"""
    try:
        incident_service = IncidentService(db)
        incident = await incident_service.get_by_id(incident_id)
        if not incident or not incident.evidence_package:
            raise NotFoundException(f"Evidence not found for incident: {incident_id}")
        return incident.evidence_package.evidence_package
    except Exception as e:
        logger.error(f"Error in get_support_evidence: {e}")
        raise

@app.get("/api/support/audit/{incident_id}")
async def get_support_audit(incident_id: str, db: AsyncSession = Depends(get_async_db)):
    """Get audit trail for incident"""
    try:
        incident_service = IncidentService(db)
        incident = await incident_service.get_by_id(incident_id)
        if not incident:
            raise NotFoundException(f"Incident not found: {incident_id}")

        return {
            "audit_trail": [
                {
                    "event_id": str(event.id),
                    "incident_id": incident.incident_id,
                    "recovery_id": str(event.recovery_id) if event.recovery_id else None,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp.isoformat(),
                    "actor": event.actor,
                    "outcome": event.outcome,
                    "details": event.details
                }
                for event in (incident.audit_events or [])
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_support_audit: {e}")
        raise

# Approval endpoints
@app.get("/api/approvals")
async def get_approvals(
    current_user: User = Depends(get_current_active_user),
    merchant_id: str = Depends(get_current_merchant_id),
    db: AsyncSession = Depends(get_async_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return")
):
    """Get list of pending approvals for the current merchant with pagination"""
    try:
        incident_service = IncidentService(db)
        incidents = await incident_service.get_by_merchant_id(merchant_id, skip=skip, limit=limit)
        total = await incident_service.repository.get_count_by_merchant_id(merchant_id)
        approvals = []

        for incident in incidents:
            pol = incident.policy_decision
            rec = incident.recoveries[0] if incident.recoveries else None

            if pol and pol.decision == "HUMAN_APPROVAL" and rec and rec.state == "PENDING":
                ev_pkg = incident.evidence_package.evidence_package if incident.evidence_package else {}
                impact = ev_pkg.get("impact_evidence", {})
                rev_paise = impact.get("revenue_at_risk", {}).get("paise", 0)
                
                llm_rep = incident.forensic_report.report if incident.forensic_report else {}
                confidence = llm_rep.get("summary", {}).get("confidence", 0.9)

                approvals.append({
                    "approval_id": f"{incident.incident_id}_approval",
                    "incident_id": incident.incident_id,
                    "merchant_id": incident.merchant.merchant_id if incident.merchant else str(incident.merchant_id),
                    "severity": incident.severity,
                    "revenue_at_risk_paise": rev_paise,
                    "proposed_action": pol.requested_recovery_action or "PAYMENT_LINK",
                    "policy_reason_codes": pol.reason_codes or [],
                    "confidence": confidence,
                    "status": "PENDING",
                    "created_at": rec.created_at.isoformat() if hasattr(rec, "created_at") and rec.created_at else incident.detection_timestamp.isoformat()
                })

        return {
            "items": approvals,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error in get_approvals: {e}")
        raise

@app.get("/api/approvals/{approval_id}")
async def get_approval_detail(
    approval_id: str,
    current_user: User = Depends(get_current_active_user),
    merchant_id: str = Depends(get_current_merchant_id),
    db: AsyncSession = Depends(get_async_db)
):
    """Get detailed approval information"""
    try:
        if not approval_id.endswith("_approval"):
            raise ValidationException("Invalid approval ID format")

        incident_id = approval_id.replace("_approval", "")
        incident_service = IncidentService(db)
        incident = await incident_service.get_by_id(incident_id)

        if not incident:
            raise NotFoundException(f"Approval not found: {approval_id}")

        # Verify that the incident belongs to the current merchant
        if incident.merchant_id != current_user.merchant_id:
            raise AuthorizationException(f"Access denied: Approval does not belong to your merchant")

        pol = incident.policy_decision
        rec = incident.recoveries[0] if incident.recoveries else None
        ev_pkg = incident.evidence_package.evidence_package if incident.evidence_package else {}
        report = incident.forensic_report.report if incident.forensic_report else {}

        if not pol or pol.decision != "HUMAN_APPROVAL":
            raise NotFoundException(f"Approval not found or not pending: {approval_id}")

        if not rec or rec.state != "PENDING":
            raise NotFoundException(f"Approval not found or not pending: {approval_id}")

        impact = ev_pkg.get("impact_evidence", {})
        rev_paise = impact.get("revenue_at_risk", {}).get("paise", 0)

        return {
            "approval": {
                "approval_id": approval_id,
                "incident_id": incident.incident_id,
                "merchant_id": incident.merchant.merchant_id if incident.merchant else str(incident.merchant_id),
                "severity": incident.severity,
                "revenue_at_risk_paise": rev_paise,
                "proposed_action": pol.requested_recovery_action or "PAYMENT_LINK",
                "policy_reason_codes": pol.reason_codes or [],
                "confidence": 0.9,
                "status": "PENDING",
                "created_at": rec.created_at.isoformat() if hasattr(rec, 'created_at') and rec.created_at else incident.detection_timestamp.isoformat()
            },
            "incident": {
                "incident_id": incident.incident_id,
                "merchant_id": incident.merchant.merchant_id if incident.merchant else str(incident.merchant_id),
                "detection_timestamp": incident.detection_timestamp.isoformat(),
                "severity": incident.severity,
                "classification": incident.classification,
                "affected_segment": incident.affected_segment,
                "impact_evidence": ev_pkg.get("impact_evidence", {}),
                "success_rate_evidence": ev_pkg.get("success_rate_evidence", {}),
                "error_evidence": ev_pkg.get("error_evidence", {}),
                "localization_evidence": ev_pkg.get("localization_evidence", {}),
                "temporal_evidence": ev_pkg.get("temporal_evidence", {}),
                "volume_evidence": ev_pkg.get("volume_evidence", {}),
                "latency_evidence": ev_pkg.get("latency_evidence", {}),
                "investigation_checklist": ev_pkg.get("investigation_checklist", []),
                "sample_payments": ev_pkg.get("sample_payments", []),
                "hypothesis_evidence": ev_pkg.get("hypothesis_evidence", {})
            },
            "evidence": ev_pkg,
            "llm_report": report,
            "policy_decision": {
                "decision": pol.decision,
                "reason_codes": pol.reason_codes,
                "human_readable_reason": pol.human_readable_reason,
                "requested_recovery_action": pol.requested_recovery_action,
                "policy_inputs": pol.policy_inputs
            } if pol else {}
        }
    except Exception as e:
        logger.error(f"Error in get_approval_detail: {e}")
        raise

@app.post("/api/approvals/{approval_id}/approve")
async def approve_approval(
    approval_id: str,
    current_user: User = Depends(require_role("approver")),
    merchant_id: str = Depends(get_current_merchant_id),
    db: AsyncSession = Depends(get_async_db)
):
    """Approve a pending recovery action"""
    try:
        if not approval_id.endswith("_approval"):
            raise ValidationException("Invalid approval ID format")

        incident_id = approval_id.replace("_approval", "")
        incident_service = IncidentService(db)
        incident = await incident_service.get_by_id(incident_id)

        if not incident:
            raise NotFoundException(f"Approval not found: {approval_id}")

        # Verify that the incident belongs to the current merchant
        if incident.merchant_id != current_user.merchant_id:
            raise AuthorizationException(f"Access denied: Approval does not belong to your merchant")

        policy_decision = incident.policy_decision
        if not policy_decision or policy_decision.decision != "HUMAN_APPROVAL":
            raise ValidationException("Approval is not pending or not a human approval")

        # Lock the recovery record for update to prevent race conditions
        from app.models.recovery import Recovery

        if not incident.recoveries:
            raise NotFoundException("Recovery record not found")

        recovery_id = incident.recoveries[0].id
        # Use with_for_update for locking in async session
        from sqlalchemy import select
        result = await db.execute(
            select(Recovery).filter(Recovery.id == recovery_id).with_for_update()
        )
        recovery = result.scalars().first()

        if not recovery:
            raise NotFoundException("Recovery record not found")

        # Idempotency check: if operator double-clicks approve, safely return existing state
        if recovery.state in ["COMPLETED", "PROCESSING"]:
            return {"message": "Recovery already approved and executed", "recovery_id": str(recovery.id)}

        if recovery.state != "PENDING":
            raise ValidationException("Approval is not pending")

        # Mark recovery as processing immediately to prevent concurrent approvals
        # recovery.state = "PROCESSING"

        forensic_service = ForensicReportService(db)
        llm_report = await forensic_service.get_by_incident_id(incident_id)

        ev_pkg = incident.evidence_package.evidence_package if incident.evidence_package else {}
        report_dict = llm_report.report if llm_report else {}
        pol_dict = {
            "decision": policy_decision.decision,
            "reason_codes": policy_decision.reason_codes,
            "human_readable_reason": policy_decision.human_readable_reason,
            "action_type": policy_decision.requested_recovery_action,
            "policy_inputs": policy_decision.policy_inputs
        }

        # Initialize recovery engine with db session
        recovery_engine = RecoveryEngine(db_session=db)
        recovery_result = await recovery_engine.execute_recovery(
            policy_decision=pol_dict,
            evidence_package=ev_pkg,
            llm_report=report_dict
        )

        recovery.razorpay_payment_link_id = recovery_result.get("payment_link_id")
        recovery.razorpay_payment_status = recovery_result.get("payment_status")
        recovery.amount_paise = recovery_result.get("amount_paise", 0)
        recovery.currency = recovery_result.get("currency", "INR")
        recovery.state = recovery_result.get("state", "COMPLETED")
        recovery.recovered_amount_paise = recovery_result.get("recovered_amount_paise", 0)
        recovery.error_message = recovery_result.get("error")
        recovery.completed_at = datetime.now(timezone.utc)

        # Atomic Commit: Add audit event & commit state change together in one transaction
        audit_event = AuditEvent(
            incident_id=incident.id,
            recovery_id=recovery.id,
            event_type="RECOVERY_APPROVED",
            timestamp=datetime.now(timezone.utc),
            actor=current_user.user_id,
            outcome="SUCCESS",
            details={
                "approval_id": approval_id,
                "action_type": recovery.action_type,
                "amount_paise": recovery.amount_paise
            }
        )
        db.add(audit_event)
        await db.commit()
        await db.refresh(recovery)

        return {"message": "Recovery approved and executed", "recovery_id": str(recovery.id)}
    except Exception as e:
        logger.error(f"Error in approve_approval: {e}")
        raise

@app.post("/api/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    current_user: User = Depends(require_role("approver")),
    merchant_id: str = Depends(get_current_merchant_id),
    db: AsyncSession = Depends(get_async_db)
):
    """Reject a pending recovery action"""
    try:
        if not approval_id.endswith("_approval"):
            raise ValidationException("Invalid approval ID format")

        incident_id = approval_id.replace("_approval", "")
        incident_service = IncidentService(db)
        incident = await incident_service.get_by_id(incident_id)

        if not incident:
            raise NotFoundException(f"Approval not found: {approval_id}")

        # Verify that the incident belongs to the current merchant
        if incident.merchant_id != current_user.merchant_id:
            raise AuthorizationException(f"Access denied: Approval does not belong to your merchant")

        policy_decision = incident.policy_decision
        if not policy_decision or policy_decision.decision != "HUMAN_APPROVAL":
            raise ValidationException("Approval is not pending or not a human approval")

        # Lock the recovery record for update to prevent race conditions
        from app.models.recovery import Recovery

        if not incident.recoveries:
            raise NotFoundException("Recovery record not found")

        recovery_id = incident.recoveries[0].id
        # Use with_for_update for locking in async session
        from sqlalchemy import select
        result = await db.execute(
            select(Recovery).filter(Recovery.id == recovery_id).with_for_update()
        )
        recovery = result.scalars().first()

        if not recovery:
            raise NotFoundException("Recovery record not found")

        # Idempotency check: if already cancelled, return cleanly
        if recovery.state == "CANCELLED":
            return {"message": "Recovery already rejected", "recovery_id": str(recovery.id)}

        if recovery.state != "PENDING":
            raise ValidationException("Approval is not pending")

        # Mark recovery as cancelled immediately to prevent concurrent rejections
        recovery.state = "CANCELLED"
        recovery.completed_at = datetime.now(timezone.utc)
        recovery.error_message = "Recovery rejected by authorized operator"

        # Atomic Commit: Add audit event & commit state change together in one transaction
        audit_event = AuditEvent(
            incident_id=incident.id,
            recovery_id=recovery.id,
            event_type="RECOVERY_REJECTED",
            timestamp=datetime.now(timezone.utc),
            actor=current_user.user_id,
            outcome="SUCCESS",
            details={
                "approval_id": approval_id,
                "action_type": recovery.action_type,
                "amount_paise": recovery.amount_paise
            }
        )
        db.add(audit_event)
        await db.commit()
        await db.refresh(recovery)

        return {"message": "Recovery rejected", "recovery_id": str(recovery.id)}
    except Exception as e:
        logger.error(f"Error in reject_approval: {e}")
        raise

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Readiness endpoint
@app.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_async_db)):
    """Readiness endpoint - checks if we can connect to the database"""
    try:
        # Try to execute a simple query
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1"))
        return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise ServiceUnavailableException("Database connection failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)