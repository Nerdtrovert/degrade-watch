# Human Approval Scenario for DegradeWatch Demo

This document describes a legitimate scenario that results in HUMAN_APPROVAL according to the existing policy engine rules, suitable for demonstrating the complete safety workflow in the final project demonstration.

## Scenario Overview

**Scenario H: Localized Technical Issue with Low LLM Confidence**
- Incident ID: `scenario_h_merchant_20260822_120000`
- Merchant ID: `scenario_h_merchant`
- Classification: INCIDENT (detector confirmed incident)
- Severity: MEDIUM
- Technical Details: UPI payment gateway timeout issue with BANK_H on Android Paytm
- Impact: 15% drop in success rate (95% → 80%), affecting 75 users and 50 transactions
- Revenue at Risk: 75,000 paise (750 INR) - well within auto-approval limit

## Why This Results in HUMAN_APPROVAL

According to the policy engine in `/backend/app/policy_engine.py`, this scenario triggers the **LOW_CONFIDENCE** reason code:

1. **Detector Classification**: INCIDENT ✓ (passes initial check)
2. **Sample Sufficiency**: Baseline attempts = 1000 (> 100 threshold) ✓
3. **Customer Causation**: Not primarily customer-caused (investigation checklist PASS) ✓
4. **LLM Confidence**: 0.75 (< 0.85 AUTO_APPROVAL_CONFIDENCE_THRESHOLD) → **LOW_CONFIDENCE** ✓
5. **Revenue at Risk**: 75,000 paise (< 1,000,000 paise limit) → LOW_REVENUE_RISK ✓
6. **Localization**: LOCALIZED → LOCALIZED_INCIDENT ✓
7. **Contradictory Evidence**: All investigation checklist checks PASS → NO_CONTRADICTORY_EVIDENCE ✓
8. **Requested Action**: PAYMENT_LINK (supported action) ✓
9. **Alternative Hypotheses**: Both contradicted → no supporting alternatives ✓
10. **Statistical Significance**: Statistically significant (p=0.001) ✓

Since the LLM confidence (0.75) is below the auto-approval threshold (0.85), `auto_approval_eligible` is set to False, resulting in a **HUMAN_APPROVAL** decision while avoiding all blocked conditions (NORMAL_CLASSIFICATION, INSUFFICIENT_SAMPLE, PRIMARILY_CUSTOMER_CAUSED, UNSUPPORTED_ACTION).

## Files Created

1. **`create_human_approval_scenario.py`** - Script to seed Scenario H into the database
2. **`verify_approval_scenario.py`** - Verification script showing the policy decision
3. **`README_HUMAN_APPROVAL.md`** - This documentation

## How to Use for Demo

1. **Ensure Docker services are running** (database, backend, etc.)
2. **Run the seeding script**:
   ```bash
   python3 create_human_approval_scenario.py
   ```
3. **Verify the scenario exists** by checking the approval queue in the Support Console
4. **Demonstrate the workflow**:
   - Incident appears in Support Console with policy decision "HUMAN_APPROVAL"
   - Approval Queue shows 1 pending request
   - Approver can view details and click "Approve" or "Reject"
   - Approving triggers the recovery workflow (PAYMENT_LINK execution)
   - Recovery state transitions from PENDING → PROCESSING → COMPLETED
   - Audit trail shows the complete workflow

## Verification that Existing Scenarios Remain Unchanged

- **Scenario A** (`scenario_a_merchant_20260822_100000`) remains **AUTO_APPROVED**
- **Scenario E** (`scenario_e_merchant_20260822_110000`) remains **BLOCKED** (NORMAL_CLASSIFICATION)

## Demo Flow Verification

After seeding Scenario H:
1. Approval Queue shows 1 pending request (Scenario H)
2. Clicking the approval shows:
   - Incident details matching Scenario H
   - Policy decision: HUMAN_APPROVAL
   - Reason codes including LOW_CONFIDENCE
   - Suggested recovery: PAYMENT_LINK for 15,000 paise
3. Clicking "Approve" (as user with "approver" role):
   - Changes recovery state from PENDING → PROCESSING → COMPLETED
   - Creates RECOVERY_APPROVED audit event
   - Approval disappears from queue
4. Clicking "Reject":
   - Changes recovery state from PENDING → CANCELLED
   - Creates RECOVERY_REJECTED audit event
   - Approval disappears from queue

This provides both paths needed for the demo:
1. **Automatic recovery path**: Scenario A (AUTO_APPROVED)
2. **Human approval path**: Scenario H (HUMAN_APPROVAL → manual approve/reject)

All existing authentication, authorization, and validation logic remains intact - no security controls are weakened or bypassed.
