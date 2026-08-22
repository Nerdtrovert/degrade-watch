#!/usr/bin/env python3
"""
End-to-End Integration Runner for DegradeWatch Checkpoint 11.

This script executes the full hero flow:
Scenario A → detector → evidence package → LLM report → policy decision →
recovery authorization → recovery execution → recovery status → audit trail

It produces a concise final summary containing:
- incident ID
- detector classification/severity
- affected segment
- key evidence
- LLM likely cause
- policy decision
- authorized recovery action
- recovery state
- payment link/recovery ID if applicable
- recovered amount
- audit trail summary

Do NOT duplicate logic from existing modules.
Call existing components through their public interfaces.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

# Load environment variables from backend/.env if it exists
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    with open(backend_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

# Import all the components through their public interfaces
from scripts.detect_anomalies import AnomalyDetector
from backend.app.evidence_package import EvidencePackageBuilder
from backend.app.llm_report_generator import LLMReportGenerator
from backend.app.policy_engine import PolicyEngine
from backend.app.recovery_engine import RecoveryEngine
from app.database import SessionLocal


class EndToEndRunner:
    """Orchestrates the full DegradeWatch pipeline from detection to recovery."""

    def __init__(self, data_dir: Path = None):
        """
        Initialize the end-to-end runner.

        Args:
            data_dir: Directory containing generated data (defaults to data/generated)
        """
        self.data_dir = data_dir or (project_root / "data" / "generated")
        self.baselines_dir = project_root / "data" / "generated" / "baselines"

        # Initialize all components except LLMReportGenerator (created per run based on use_real_llm flag)
        self.detector = AnomalyDetector()
        self.evidence_builder = EvidencePackageBuilder()
        self.policy_engine = PolicyEngine()
        # Create a database session for components that need it
        self.db = SessionLocal()
        self.recovery_engine = RecoveryEngine(db_session=self.db)

        import logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("End-to-End Runner initialized")

    def cleanup(self):
        """Clean up resources, including database session."""
        if hasattr(self, 'db'):
            self.db.close()

    def run_hero_flow(
        self,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime,
        use_real_llm: bool = False,
        use_real_razorpay: bool = False
    ) -> Dict[str, Any]:
        """
        Execute the full hero flow.

        Args:
            merchant_id: Merchant identifier to analyze
            window_start: Start of analysis window
            window_end: End of analysis window
            use_real_llm: Whether to use real LLM API (if credentials available)
            use_real_razorpay: Whether to use real Razorpay API (if credentials available)

        Returns:
            Complete execution summary
        """
        execution_id = f"exec_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"Starting hero flow execution {execution_id}")
        self.logger.info(f"Merchant: {merchant_id}, Window: {window_start} to {window_end}")

        # Initialize result structure
        result = {
            "execution_id": execution_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "merchant_id": merchant_id,
            "window": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat()
            },
            "stages": {},
            "summary": {},
            "success": False
        }

        try:
            # Stage 1: Detection
            self.logger.info("Stage 1: Running anomaly detector")
            detector_result = self.detector.detect(
                merchant_id=merchant_id,
                window_start=window_start,
                window_end=window_end,
                generated_data_dir=self.data_dir
            )
            result["stages"]["detection"] = detector_result

            # Stage 2: Evidence Package Generation
            self.logger.info("Stage 2: Building evidence package")
            evidence_package = self.evidence_builder.build_evidence_package(
                merchant_id=merchant_id,
                window_start=window_start,
                window_end=window_end,
                generated_data_dir=self.data_dir
            )
            result["stages"]["evidence_package"] = evidence_package

            # Stage 3: LLM Report Generation
            self.logger.info("Stage 3: Generating LLM forensic report")
            if use_real_llm:
                # Use real LLM API
                # Create LLMReportGenerator instance for this run
                # It will use the provider specified in DEGRADEWATCH_LLM_PROVIDER env var
                # Defaults to openai, but can be set to groq, anthropic, etc.
                llm_generator = LLMReportGenerator()
                # Verify that the client is initialized (API key available)
                provider = llm_generator.provider
                client_initialized = False
                if provider == "openai":
                    client_initialized = llm_generator.openai_client is not None
                elif provider == "anthropic":
                    client_initialized = llm_generator.anthropic_client is not None
                elif provider == "groq":
                    client_initialized = llm_generator.groq_client is not None

                if not client_initialized:
                    self.logger.warning(f"Real LLM requested but {provider.upper()} API key not available. Falling back to simulation mode.")
                    # Fall back to simulation mode when API key is not available
                    llm_report = self._generate_mock_llm_report(evidence_package)
                else:
                    self.logger.info(f"Using real {provider.upper()} LLM API")
                    llm_report = llm_generator.generate_report(
                        evidence_package=evidence_package
                    )
            else:
                # Use simulation mode - generate mock report without calling LLM API
                llm_report = self._generate_mock_llm_report(evidence_package)
            result["stages"]["llm_report"] = llm_report

            # Stage 4: Policy Engine Decision
            self.logger.info("Stage 4: Making policy decision")
            policy_decision = self.policy_engine.make_decision(
                evidence_package=evidence_package,
                llm_report=llm_report
            )
            result["stages"]["policy_decision"] = policy_decision

            # Stage 5: Recovery Engine Execution (if authorized)
            if self._is_recovery_authorized(policy_decision):
                self.logger.info("Stage 5: Executing recovery (authorized)")
                recovery_result = self.recovery_engine.execute_recovery(
                    policy_decision=policy_decision,
                    evidence_package=evidence_package,
                    llm_report=llm_report
                )
                result["stages"]["recovery_execution"] = recovery_result

                # Check payment status if we have a recovery ID
                if recovery_result.get("recovery_id"):
                    self.logger.info("Stage 5b: Checking payment status")
                    payment_status = self.recovery_engine.check_payment_status(
                        recovery_result["recovery_id"]
                    )
                    result["stages"]["payment_status_check"] = payment_status
                    # Merge payment status into recovery result for summary
                    recovery_result.update(payment_status)
            else:
                self.logger.info("Stage 5: Recovery not authorized by Policy Engine")
                result["stages"]["recovery_execution"] = {
                    "state": "NOT_AUTHORIZED",
                    "reason": "Policy Engine did not authorize recovery action"
                }

            # Generate final summary
            result["summary"] = self._generate_summary(result["stages"])
            result["success"] = True

            self.logger.info(f"Hero flow execution {execution_id} completed successfully")

        except Exception as e:
            self.logger.error(f"Hero flow execution failed: {e}", exc_info=True)
            result["error"] = str(e)
            result["success"] = False

        return result

    def _is_recovery_authorized(self, policy_decision: Dict[str, Any]) -> bool:
        """Check if recovery is authorized by Policy Engine."""
        decision = policy_decision.get("decision")
        # Automatic recovery only executes if the decision is AUTO_APPROVED.
        # HUMAN_APPROVAL requires manual intervention, so automatic recovery does not execute.
        return decision == "AUTO_APPROVED"

    def _generate_summary(self, stages: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a concise final summary from all stages."""
        summary = {
            "incident_id": "unknown",
            "detector_classification": "unknown",
            "detector_severity": "unknown",
            "affected_segment": {},
            "key_evidence": [],
            "llm_likely_cause": "unknown",
            "llm_confidence": 0.0,
            "policy_decision": "unknown",
            "authorized_recovery_action": "none",
            "recovery_state": "not_attempted",
            "recovery_id": None,
            "payment_link_id": None,
            "recovered_amount_paise": 0,
            "recovered_amount_rupees": 0.0,
            "audit_trail_events": 0,
            "audit_trail_summary": []
        }

        # Extract from detection stage
        if "detection" in stages:
            det = stages["detection"]
            summary["incident_id"] = det.get("merchant_id", "unknown")
            summary["detector_classification"] = det.get("classification", "unknown")
            summary["detector_severity"] = det.get("severity", "unknown")

            # Extract affected segment
            candidate_seg = det.get("candidate_segment", {})
            if isinstance(candidate_seg, dict):
                summary["affected_segment"] = {
                    "payment_method": candidate_seg.get("payment_method"),
                    "bank": candidate_seg.get("bank"),
                    "device": candidate_seg.get("device"),
                    "upi_app": candidate_seg.get("upi_app"),
                    "attempts": candidate_seg.get("attempts", 0),
                    "success_rate": candidate_seg.get("success_rate", 0.0)
                }

            # Extract key evidence
            evidence_list = det.get("evidence", [])
            summary["key_evidence"] = evidence_list[:3]  # Top 3 evidence items

        # Extract from LLM report stage
        if "llm_report" in stages:
            llm = stages["llm_report"]
            summary["llm_likely_cause"] = llm.get("likely_cause", {}).get("primary", "unknown")
            summary["llm_confidence"] = llm.get("summary", {}).get("confidence", 0.0)

        # Extract from policy decision stage
        if "policy_decision" in stages:
            policy = stages["policy_decision"]
            summary["policy_decision"] = policy.get("decision", "unknown")
            summary["authorized_recovery_action"] = policy.get("action_type", "none")

        # Extract from recovery execution stage
        if "recovery_execution" in stages:
            recovery = stages["recovery_execution"]
            summary["recovery_state"] = recovery.get("state", "unknown")
            summary["recovery_id"] = recovery.get("recovery_id")
            summary["payment_link_id"] = recovery.get("payment_link_id")
            summary["recovered_amount_paise"] = recovery.get("amount_paise", 0)
            summary["recovered_amount_rupees"] = recovery.get("amount_rupees", 0.0)

            # Extract audit trail
            audit_events = recovery.get("audit_events", [])
            summary["audit_trail_events"] = len(audit_events)
            summary["audit_trail_summary"] = [
                {
                    "timestamp": event.get("timestamp"),
                    "action": event.get("action"),
                    "state": event.get("state"),
                    "success": event.get("success")
                }
                for event in audit_events[-5:]  # Last 5 audit events
            ]

        # Extract from payment status check stage (if available)
        if "payment_status_check" in stages:
            payment = stages["payment_status_check"]
            # Override recovery amounts with actual recovered if available
            if payment.get("actual_recovered_paise") is not None:
                summary["recovered_amount_paise"] = payment.get("actual_recovered_paise", 0)
                summary["recovered_amount_rupees"] = payment.get("actual_recovered_rupees", 0.0)

        return summary

    def print_summary(self, result: Dict[str, Any]):
        """Print a human-readable summary of the execution."""
        print("\n" + "="*80)
        print("DEGRADEWATCH END-TO-END HERO FLOW EXECUTION SUMMARY")
        print("="*80)

        if not result.get("success", False):
            print(f"EXECUTION FAILED: {result.get('error', 'Unknown error')}")
            print("="*80)
            return

        summary = result["summary"]

        print(f"Incident ID: {summary['incident_id']}")
        print(f"Detector Classification: {summary['detector_classification']}")
        print(f"Detector Severity: {summary['detector_severity']}")

        seg = summary["affected_segment"]
        if seg and isinstance(seg, dict):
            print(f"Affected Segment: {seg.get('payment_method', 'unknown')}")
            if seg.get('bank'):
                print(f"   Bank: {seg['bank']}")
            if seg.get('device'):
                print(f"   Device: {seg['device']}")
            if seg.get('upi_app'):
                print(f"   UPI App: {seg['upi_app']}")
            print(f"   Attempts: {seg.get('attempts', 0)}")
            print(f"   Success Rate: {seg.get('success_rate', 0):.1%}")

        print(f"\nKey Evidence:")
        for i, evidence in enumerate(summary["key_evidence"], 1):
            print(f"   {i}. {evidence}")

        print(f"\nLLM Analysis:")
        print(f"   Likely Cause: {summary['llm_likely_cause']}")
        print(f"   Confidence: {summary['llm_confidence']:.1%}")

        print(f"\nPolicy Decision:")
        print(f"   Decision: {summary['policy_decision']}")
        print(f"   Action: {summary['authorized_recovery_action']}")

        print(f"\nRecovery Execution:")
        print(f"   State: {summary['recovery_state']}")
        if summary['recovery_id']:
            print(f"   Recovery ID: {summary['recovery_id']}")
        if summary['payment_link_id']:
            print(f"   Payment Link ID: {summary['payment_link_id']}")
        print(f"   Recovered Amount: {summary['recovered_amount_paise']} paise "
              f"({summary['recovered_amount_rupees']:.2f} INR)")

        print(f"\nAudit Trail:")
        print(f"   Total Events: {summary['audit_trail_events']}")
        for i, event in enumerate(summary["audit_trail_summary"], 1):
            status = "SUCCESS" if event.get("success") else "FAILED"
            print(f"   {i}. {status} {event.get('action')} [{event.get('state')}] "
                  f"at {event.get('timestamp', '').split('T')[1][:8] if event.get('timestamp') else 'unknown'}")

        # Overall assessment
        print(f"\nOVERALL ASSESSMENT:")
        if summary["detector_classification"] == "INCIDENT" and \
           summary["policy_decision"] == "AUTO_APPROVED" and \
           summary["recovery_state"] == "COMPLETED":
            print("   SUCCESS: Full hero flow completed successfully!")
            print("   Revenue recovered and audit trail complete")
        elif summary["detector_classification"] == "INCIDENT" and \
             summary["policy_decision"] in ["AUTO_APPROVED", "HUMAN_APPROVAL"] and \
             summary["recovery_state"] == "NOT_AUTHORIZED":
            print("   PARTIAL: Incident detected and policy authorized, but recovery not executed")
            print("   This may be expected for HUMAN_APPROVAL requiring manual trigger")
        elif summary["detector_classification"] == "NORMAL":
            print("   HEALTHY: No incident detected - correct behavior")
        else:
            print("   INCOMPLETE: Pipeline did not complete as expected")

        print("="*80)


    def _generate_mock_llm_report(self, evidence_package: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a mock LLM report for simulation mode.

        Args:
            evidence_package: The evidence package from the detector

        Returns:
            A mock LLM report with the expected structure
        """
        # Extract key information from evidence package
        incident_id = evidence_package.get("incident_metadata", {}).get("incident_id", "unknown")
        severity = evidence_package.get("incident_metadata", {}).get("severity", "MEDIUM")
        detector_classification = evidence_package.get("incident_metadata", {}).get("detector_classification", "UNKNOWN")

        # Determine if this should be an action-required or no-action scenario
        # For simulation, we'll base it on the detector classification
        if detector_classification == "NORMAL":
            status = "NO_ACTION"
            likely_cause_primary = "No significant degradation detected - normal payment processing variability"
            recovery_eligible = False
            recovery_reason = "No action warranted based on evidence analysis"
            confidence = 0.95
        else:
            status = "ACTION_PROPOSED"
            likely_cause_primary = "Technical infrastructure issue detected in payment processing - elevated error rates and decreased success rate"
            recovery_eligible = True
            recovery_reason = "To compensate affected users for service degradation"
            confidence = 0.85

        # Extract affected segment details
        affected_segment = evidence_package.get("affected_segment", {})

        # Build the mock report
        mock_report = {
            "incident_id": incident_id,
            "severity": severity,
            "status": status,
            "summary": {
                "title": f"Payment Processing Degradation Detected - {detector_classification}",
                "what_happened": f"Payment success rate showed {detector_classification.lower()} pattern with elevated error rates",
                "where": {
                    "payment_method": affected_segment.get("payment_method", "unknown"),
                    "bank": affected_segment.get("bank", "unknown"),
                    "device": affected_segment.get("device", "unknown"),
                    "upi_app": affected_segment.get("upi_app", "unknown")
                },
                "confidence": confidence,
                "confidence_level": "HIGH" if confidence > 0.8 else "MEDIUM" if confidence > 0.5 else "LOW",
                "confidence_explanation": "Based on analysis of success rate trends, error patterns, and statistical significance",
                "evidence_summary": [
                    f"Success rate changed from {affected_segment.get('baseline_success_rate', 0):.1%} to {affected_segment.get('current_success_rate', 0):.1%}",
                    f"Technical error rate changed from {evidence_package.get('error_evidence', {}).get('baseline', {}).get('technical_error_rate', 0):.1%} to {evidence_package.get('error_evidence', {}).get('current', {}).get('technical_error_rate', 0):.1%}",
                    f"Issue localized to {affected_segment.get('payment_method', 'unknown')} segment"
                ]
            },
            "likely_cause": {
                "primary": likely_cause_primary,
                "confidence": confidence * 0.9,  # Slightly lower than overall confidence
                "evidence_refs": [
                    "success_rate_evidence.relative_change",
                    "error_evidence.changes.technical_error_rate_change"
                ]
            },
            "alternative_hypotheses": [
                {
                    "hypothesis": "Customer-side payment issues",
                    "assessment": "CONTRADICTED" if detector_classification != "NORMAL" else "SUPPORTED",
                    "explanation": "Customer error rates did not show significant increase",
                    "evidence_refs": ["error_evidence.changes.customer_error_rate_change"]
                }
            ] if detector_classification != "NORMAL" else [
                {
                    "hypothesis": "Customer-side payment issues",
                    "assessment": "SUPPORTED",
                    "explanation": "Customer error rates increased while technical rates remained normal",
                    "evidence_refs": ["error_evidence.changes.customer_error_rate_change",
                                   "error_evidence.changes.technical_error_rate_change"]
                }
            ],
            "recommended_next_steps": [
                "Monitor payment success rate for the next 15-20 minutes",
                "Check with payment gateway for any known issues",
                "Prepare customer communication if issue persists"
            ] if detector_classification != "NORMAL" else [
                "Consider informing customers about payment method alternatives",
                "Monitor for recurrence to determine if intervention is needed"
            ],
            "recovery": {
                "eligible": recovery_eligible,
                "recommendation": "PAYMENT_LINK" if recovery_eligible else "NONE",
                "reason": recovery_reason
            },
            "timeline": [
                {
                    "time": evidence_package.get("incident_metadata", {}).get("detection_timestamp", ""),
                    "event": "Incident detected by automated monitoring"
                },
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": "Forensic analysis completed"
                }
            ]
        }

        return mock_report

def main():
    """Main function for command-line usage."""
    import argparse
    import logging

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    global logger
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(
        description="Run DegradeWatch end-to-end hero flow"
    )
    parser.add_argument(
        "--merchant-id",
        default="merch_upi_smb",
        help="Merchant ID to analyze (default: merch_upi_smb)"
    )
    parser.add_argument(
        "--window-start",
        required=True,
        help="Window start time (ISO format)"
    )
    parser.add_argument(
        "--window-end",
        required=True,
        help="Window end time (ISO format)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        help="Directory containing generated data"
    )
    parser.add_argument(
        "--use-real-llm",
        action="store_true",
        help="Use real LLM API if credentials are available"
    )
    parser.add_argument(
        "--use-real-razorpay",
        action="store_true",
        help="Use real Razorpay API if credentials are available"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for JSON result (default: stdout)"
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress verbose logging"
    )

    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # Parse timestamps
    try:
        window_start = datetime.fromisoformat(args.window_start.replace("Z", "+00:00"))
        window_end = datetime.fromisoformat(args.window_end.replace("Z", "+00:00"))
    except ValueError as e:
        print(f"Error parsing timestamps: {e}")
        sys.exit(1)

    # Validate window
    if window_start >= window_end:
        print("Error: Window start must be before window end")
        sys.exit(1)

    # Create runner and execute
    data_dir = Path(args.data_dir) if args.data_dir else None
    runner = EndToEndRunner(data_dir=data_dir)

    result = runner.run_hero_flow(
        merchant_id=args.merchant_id,
        window_start=window_start,
        window_end=window_end,
        use_real_llm=args.use_real_llm,
        use_real_razorpay=args.use_real_razorpay
    )

    # Print summary
    runner.print_summary(result)

    # Output JSON if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nFull results written to {args.output}")

    # Exit with appropriate code
    if result.get("success", False):
        # Consider success if we got a meaningful result, even if no recovery was needed
        summary = result.get("summary", {})
        if summary.get("detector_classification") in ["NORMAL", "INCIDENT"]:
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()