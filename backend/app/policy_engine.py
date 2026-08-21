#!/usr/bin/env python3
"""
Policy Engine for DegradeWatch Checkpoint 9.

Implements a deterministic policy that decides whether to approve a recovery action
based on the validated Evidence Package and the LLM's Forensic Report.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class PolicyConfig:
    """
    Configuration for the Policy Engine.
    All thresholds and rules are defined here.
    """

    # Recovery action types we support
    SUPPORTED_ACTIONS = ["PAYMENT_LINK"]

    # Confidence threshold for automatic approval (from LLM report, but note:
    # we must not use LLM confidence to override backend-owned severity, but we
    # can use it as a factor in the decision).
    # We'll set a high threshold for auto-approval.
    AUTO_APPROVAL_CONFIDENCE_THRESHOLD = 0.85

    # Revenue at risk threshold for automatic approval (in paise)
    # We'll set a conservative limit: 1,000,000 paise (which is 10,000 INR)
    # This is just an example; in reality, this should be configurable.
    AUTO_APPROVAL_REVENUE_RISK_LIMIT_PAISE = 1_000_000

    # Sample sufficiency: we'll look at the affected segment's baseline_attempts
    # and current_attempts. We'll consider the sample sufficient if the
    # baseline_attempts is above a threshold (to ensure we have enough baseline
    # to make a statistically significant decision).
    # We'll set a minimum baseline_attempts of 100.
    MIN_BASELINE_ATTEMPTS_FOR_SUFFICIENT_SAMPLE = 100

    # We'll define a list of reason codes for the decision.
    REASON_CODES = {
        # Positive reasons (supporting auto-approval)
        "INCIDENT_CONFIRMED": "Detector classification is INCIDENT",
        "HIGH_CONFIDENCE": "LLM confidence meets or exceeds threshold for auto-approval",
        "SUFFICIENT_SAMPLE": "Baseline sample size is sufficient for statistical decisions",
        "TECHNICAL_EVIDENCE_PRESENT": "Technical error evidence supports the incident",
        "LOW_REVENUE_RISK": "Revenue at risk is within the approved limit for auto-approval",
        "NOT_PRIMARILY_CUSTOMER_CAUSED": "Evidence indicates the incident is not primarily customer-caused",
        "LOCALIZED_INCIDENT": "Incident is localized to a specific segment",
        "NO_CONTRADICTORY_EVIDENCE": "No contradictory evidence found in the investigation checklist",
        # Negative reasons (leading to human approval or block)
        "NORMAL_CLASSIFICATION": "Detector classification is NORMAL, not an incident",
        "LOW_CONFIDENCE": "LLM confidence is below threshold for auto-approval",
        "INSUFFICIENT_SAMPLE": "Baseline sample size is insufficient",
        "HIGH_REVENUE_RISK": "Revenue at risk exceeds the limit for auto-approval",
        "PRIMARILY_CUSTOMER_CAUSED": "Evidence indicates the incident is primarily customer-caused",
        "MULTI_DIMENSIONAL": "Incident affects multiple dimensions (not localized)",
        "CONTRADICTORY_EVIDENCE": "Investigation checklist contains contradictory evidence",
        "UNSUPPORTED_ACTION": "Requested recovery action is not supported",
        "MISSING_EVIDENCE": "Required evidence is missing for decision",
        "POLICY_LIMIT_EXCEEDED": "Policy limit exceeded (general)",
        "ALTERNATIVE_HYPOTHESIS": "Alternative hypotheses create material uncertainty",
    }


class PolicyEngine:
    """
    The Policy Engine makes deterministic decisions about recovery actions.
    """

    def __init__(self, config: Optional[PolicyConfig] = None):
        """
        Initialize the Policy Engine with a configuration.
        If no config is provided, use the default PolicyConfig.
        """
        self.config = config or PolicyConfig()

    def make_decision(
        self,
        evidence_package: Dict[str, Any],
        llm_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make a policy decision based on the evidence package and LLM report.

        Args:
            evidence_package: The validated evidence package from Checkpoint 7.
            llm_report: The validated LLM report from Checkpoint 8.

        Returns:
            A dictionary representing the policy decision.
        """
        # We'll extract the backend-owned fields from the evidence package.
        # We will not trust the LLM report for these fields.

        incident_id = evidence_package.get("incident_metadata", {}).get("incident_id")
        if not incident_id:
            # This should not happen if the evidence package is validated, but we guard.
            return self._make_blocked_decision(
                reason_code="MISSING_EVIDENCE",
                reason="Incident ID is missing in the evidence package",
                evidence_package=evidence_package,
                llm_report=llm_report
            )

        # Extract the LLM's requested recovery action.
        # We are only interested in the recovery recommendation.
        llm_recovery = llm_report.get("recovery", {})
        requested_action = llm_recovery.get("recommendation")
        # We only support PAYMENT_LINK. Any other action (including null) is treated as no action requested.
        # But note: the LLM might recommend null or a string that is not PAYMENT_LINK.
        # We'll treat any action that is not PAYMENT_LINK as unsupported.

        # We'll also extract the LLM's confidence for informational purposes (but we won't use it to override
        # backend-owned severity). We'll use it as a factor in the decision.
        llm_confidence = llm_report.get("summary", {}).get("confidence", 0.0)

        # Now, we'll evaluate the policy.

        # We'll start by assuming we want to block, and then we'll see if we can approve.

        # We'll collect reason codes for the decision.
        reason_codes = []
        # We'll also collect human readable explanations.

        # We'll make a decision in steps.

        # Step 1: Check the detector classification.
        classification = evidence_package.get("incident_metadata", {}).get("detector_classification")
        if classification != "INCIDENT":
            reason_codes.append("NORMAL_CLASSIFICATION")
            return self._make_blocked_decision(
                reason_code="NORMAL_CLASSIFICATION",
                reason="Detector classification is NORMAL, not an incident",
                evidence_package=evidence_package,
                llm_report=llm_report
            )

        # Step 2: Check the sample sufficiency.
        affected_segment = evidence_package.get("affected_segment", {})
        baseline_attempts = affected_segment.get("baseline_attempts", 0)
        if baseline_attempts < self.config.MIN_BASELINE_ATTEMPTS_FOR_SUFFICIENT_SAMPLE:
            reason_codes.append("INSUFFICIENT_SAMPLE")
            # According to the policy, insufficient sample should lead to BLOCKED.
            return self._make_blocked_decision(
                reason_code="INSUFFICIENT_SAMPLE",
                reason="Baseline sample size is insufficient",
                evidence_package=evidence_package,
                llm_report=llm_report
            )

        # Step 3: Check if the incident is primarily customer-caused.
        # We'll look at the error_evidence changes.
        error_evidence = evidence_package.get("error_evidence", {})
        changes = error_evidence.get("changes", {})
        customer_change = changes.get("customer_error_rate_change", 0.0)
        technical_change = changes.get("technical_error_rate_change", 0.0)

        # We'll also check the investigation checklist for a check on
        # primarily_customer_caused.

        # We'll initialize a flag.
        is_primarily_customer_caused = False

        # Check the investigation checklist first.
        investigation_checklist = evidence_package.get("investigation_checklist", [])
        for check in investigation_checklist:
            if check.get("check") == "primarily_customer_caused" and check.get("result") == "PASS":
                # If the check "primarily_customer_caused" passes, it means it's NOT primarily customer-caused
                is_primarily_customer_caused = False
                break
            elif check.get("check") == "primarily_customer_caused" and check.get("result") == "FAIL":
                # If the check "primarily_customer_caused" fails, it means it IS primarily customer-caused
                is_primarily_customer_caused = True
                break

        # If we didn't find it in the checklist, we'll use the changes.
        if not is_primarily_customer_caused:
            # We'll consider it primarily customer-caused if the customer change is
            # greater than the technical change (and note: we are looking for increases).
            if customer_change > technical_change:
                is_primarily_customer_caused = True

        if is_primarily_customer_caused:
            reason_codes.append("PRIMARILY_CUSTOMER_CAUSED")
            # According to the policy, we should block automated recovery for Scenario E.
            return self._make_blocked_decision(
                reason_code="PRIMARILY_CUSTOMER_CAUSED",
                reason="Evidence indicates the incident is primarily customer-caused",
                evidence_package=evidence_package,
                llm_report=llm_report
            )

        # Step 4: Check the LLM confidence.
        if llm_confidence < self.config.AUTO_APPROVAL_CONFIDENCE_THRESHOLD:
            reason_codes.append("LOW_CONFIDENCE")
            auto_approval_eligible = False
        else:
            reason_codes.append("HIGH_CONFIDENCE")
            auto_approval_eligible = True

        # Step 5: Check the revenue at risk.
        impact_evidence = evidence_package.get("impact_evidence", {})
        revenue_at_risk = impact_evidence.get("revenue_at_risk", {})
        revenue_paise = revenue_at_risk.get("paise", 0)
        if revenue_paise > self.config.AUTO_APPROVAL_REVENUE_RISK_LIMIT_PAISE:
            reason_codes.append("HIGH_REVENUE_RISK")
            auto_approval_eligible = False
        else:
            reason_codes.append("LOW_REVENUE_RISK")

        # Step 6: Check the localization status.
        localization_evidence = evidence_package.get("localization_evidence", {})
        localization_status = localization_evidence.get("localization_status")
        if localization_status == "LOCALIZED":
            reason_codes.append("LOCALIZED_INCIDENT")
        else:
            # If it's not localized, we consider it multi-dimensional.
            reason_codes.append("MULTI_DIMENSIONAL")
            # Multi-dimensional incidents require human approval.
            auto_approval_eligible = False

        # Step 7: Check for contradictory evidence in the investigation checklist.
        # We'll look for any check that has a result of "FAIL".
        has_contradictory_evidence = False
        for check in investigation_checklist:
            if check.get("result") == "FAIL":
                has_contradictory_evidence = True
                break
        if has_contradictory_evidence:
            reason_codes.append("CONTRADICTORY_EVIDENCE")
            auto_approval_eligible = False
        else:
            reason_codes.append("NO_CONTRADICTORY_EVIDENCE")

        # Step 8: Check the requested recovery action.
        if requested_action not in self.config.SUPPORTED_ACTIONS:
            reason_codes.append("UNSUPPORTED_ACTION")
            # Unsupported action leads to BLOCKED.
            return self._make_blocked_decision(
                reason_code="UNSUPPORTED_ACTION",
                reason="Requested recovery action is not supported",
                evidence_package=evidence_package,
                llm_report=llm_report
            )

        # Step 9: Check for alternative hypotheses that create material uncertainty.
        alternative_hypotheses = llm_report.get("alternative_hypotheses", [])
        has_supporting_alternative = False
        for hypo in alternative_hypotheses:
            assessment = hypo.get("assessment")
            if assessment in ["SUPPORTED", "PARTIALLY_SUPPORTED"]:
                has_supporting_alternative = True
                break
        if has_supporting_alternative:
            reason_codes.append("ALTERNATIVE_HYPOTHESIS")
            auto_approval_eligible = False

        # Step 10: Check the success rate evidence for statistical significance.
        success_rate_evidence = evidence_package.get("success_rate_evidence", {})
        stat_sign = success_rate_evidence.get("statistical_significance", {})
        if not stat_sign.get("statistically_significant", False):
            reason_codes.append("MISSING_EVIDENCE")
            auto_approval_eligible = False

        # Now, we have collected reason codes and we have a flag for auto_approval_eligible.

        # We'll also add the INCIDENT_CONFIRMED reason code (we already checked classification is INCIDENT).
        reason_codes.append("INCIDENT_CONFIRMED")

        # We'll also add a reason for sufficient sample if we passed that check.
        if baseline_attempts >= self.config.MIN_BASELINE_ATTEMPTS_FOR_SUFFICIENT_SAMPLE:
            reason_codes.append("SUFFICIENT_SAMPLE")

        # We'll also add a reason for technical evidence present if we have technical error evidence.
        technical_error_count = error_evidence.get("current", {}).get("failure_breakdown", {}).get("technical", 0)
        if technical_error_count > 0:
            reason_codes.append("TECHNICAL_EVIDENCE_PRESENT")

        # Now, we decide:
        # If auto_approval_eligible is True, then we can auto-approve.
        # Otherwise, we check if we can at least get human approval.

        # We define that we can get human approval if we have not returned blocked yet.
        # The conditions that lead to blocked return are:
        #   - NORMAL_CLASSIFICATION
        #   - INSUFFICIENT_SAMPLE
        #   - PRIMARILY_CUSTOMER_CAUSED
        #   - UNSUPPORTED_ACTION
        # If we reach this point, we have not been blocked by those conditions.

        if auto_approval_eligible:
            decision = "AUTO_APPROVED"
            action_type = requested_action
        else:
            decision = "HUMAN_APPROVAL"
            action_type = requested_action  # We still recommend the action, but it needs human approval.

        # We'll create the decision dictionary.
        return self._make_decision_dict(
            decision=decision,
            action_type=action_type,
            reason_codes=reason_codes,
            evidence_package=evidence_package,
            llm_report=llm_report
        )

    def _make_blocked_decision(
        self,
        reason_code: str,
        reason: str,
        evidence_package: Dict[str, Any],
        llm_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Helper to make a blocked decision with a single reason code.
        """
        reason_codes = [reason_code]
        # We'll also add the INCIDENT_CONFIRMED if applicable? But if we are blocked
        # due to normal classification, then it's not an incident.
        # We'll let the caller decide what reason codes to include.
        # We'll just use the provided reason_code.
        return self._make_decision_dict(
            decision="BLOCKED",
            action_type=None,
            reason_codes=reason_codes,
            evidence_package=evidence_package,
            llm_report=llm_report
        )

    def _make_decision_dict(
        self,
        decision: str,
        action_type: Optional[str],
        reason_codes: List[str],
        evidence_package: Dict[str, Any],
        llm_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create the decision dictionary.
        """
        # We'll remove duplicates from reason_codes while preserving order.
        seen = set()
        unique_reason_codes = []
        for code in reason_codes:
            if code not in seen:
                seen.add(code)
                unique_reason_codes.append(code)

        # We'll create a human readable reason from the reason codes.
        # We'll map each reason code to a human readable string.
        # We'll use the PolicyConfig.REASON_CODES for the explanation.
        # We'll join them into a sentence.
        reason_explanations = []
        for code in unique_reason_codes:
            explanation = self.config.REASON_CODES.get(code, f"Unknown reason code: {code}")
            reason_explanations.append(explanation)

        human_readable_reason = "Decision is based on the following factors: " + "; ".join(reason_explanations) + "."

        # We'll also include evidence references for traceability.
        # We'll include a few key evidence references that were used in the decision.
        # We'll leave this as an empty list for now, but we can add them later.
        evidence_refs = []

        # We'll also include the timestamp.
        evaluated_at = datetime.now(timezone.utc).isoformat()

        # We'll include the policy version.
        policy_version = "v1"

        # We'll include the incident_id from the evidence package.
        incident_id = evidence_package.get("incident_metadata", {}).get("incident_id", "unknown")

        # We'll create the decision dictionary.
        decision_dict = {
            "incident_id": incident_id,
            "decision": decision,
            "action_type": action_type,
            "reason_codes": unique_reason_codes,
            "human_readable_reason": human_readable_reason,
            "policy_version": policy_version,
            "evaluated_at": evaluated_at,
            "evidence_refs": evidence_refs
        }

        return decision_dict