# Verification Steps for Three Demo Paths

## Prerequisites
1. Ensure Docker containers are running:
   ```bash
   docker compose up -d
   ```
2. Wait for health check:
   ```bash
   curl -s http://localhost:8000/health  # Should return {"status":"healthy"}
   ```

## Path A: INCIDENT → AUTO_APPROVED → recovery
*(Scenario A: Technically severe issue requiring automatic recovery)*

### Step 1: Verify Incident Classification
```bash
curl -s http://localhost:8000/api/support/incidents | \
  jq -r '.items[] | select(.incident_id=="scenario_a_merchant_20260822_100000") | 
  {incident_id, policy_status, recovery_status, severity}'
```
**Expected Output:**
```json
{
  "incident_id": "scenario_a_merchant_20260822_100000",
  "policy_status": "AUTO_APPROVED",
  "recovery_status": "PENDING",
  "severity": "MEDIUM"
}
```

### Step 2: Check Recovery Details
```bash
curl -s http://localhost:8000/api/support/incidents/scenario_a_merchant_20260822_100000 | \
  jq '.recovery | {recovery_id, state, action_type, amount_paise}'
```
**Expected Output:**
```json
{
  "recovery_id": "895edea3-3a89-4713-aac0-03a4a2b2cd0b",
  "state": "PENDING",
  "action_type": "PAYMENT_LINK",
  "amount_paise": 15000
}
```

### Step 3: Verify Evidence (Optional)
```bash
curl -s http://localhost:8000/api/support/incidents/scenario_a_merchant_20260822_100000/evidence | \
  jq '.success_rate_evidence.statistical_significance.statistically_significant'
```
**Expected:** `true`

## Path H: INCIDENT → LOW_CONFIDENCE → HUMAN_APPROVAL → approve → recovery
*(Scenario H: Technically severe issue but low LLM confidence requiring human approval)*

### Step 1: Seed the Scenario (if not already present)
```bash
docker compose exec backend python /app/create_human_approval_scenario.py
```
**Expected Output:**
```
Created Scenario H incident: scenario_h_merchant_20260822_120000
Policy Decision: HUMAN_APPROVAL
Reason Codes: ['LOW_CONFIDENCE', ...]
LLM Confidence: 0.75 (threshold: 0.85)
```

### Step 2: Verify Incident Requires Human Approval
```bash
curl -s http://localhost:8000/api/support/incidents | \
  jq -r '.items[] | select(.incident_id=="scenario_h_merchant_20260822_120000") | 
  {incident_id, policy_status, recovery_status}'
```
**Expected Output:**
```json
{
  "incident_id": "scenario_h_merchant_20260822_120000",
  "policy_status": "HUMAN_APPROVAL",
  "recovery_status": "PENDING"
}
```

### Step 3: Get Authentication Token
```bash
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"approver_user","password":"password123"}')
TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
```

### Step 4: Get Approval ID
```bash
APPROVAL_ID=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/approvals | \
  jq -r '.items[0].approval_id')
echo "Approval ID: $APPROVAL_ID"
```

### Step 5: Approve the Recovery
```bash
curl -s -X POST "http://localhost:8000/api/approvals/$APPROVAL_ID/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | \
  jq .
```
**Expected Output:**
```json
{
  "message": "Recovery approved and executed",
  "recovery_id": "27ff1b2d-4953-4c7a-b94f-cc7285f75682"
}
```

### Step 6: Verify Recovery Completion
```bash
sleep 3  # Allow processing time
curl -s http://localhost:8000/api/support/incidents/scenario_h_merchant_20260822_120000 | \
  jq '.recovery | {recovery_id, state, action_type, amount_paise, error_message}'
```
**Expected Output (after fix):**
```json
{
  "recovery_id": "27ff1b2d-4953-4c7a-b94f-cc7285f75682",
  "state": "COMPLETED",
  "action_type": "PAYMENT_LINK",
  "amount_paise": 15000,
  "error_message": null
}
```

### Current Status (Known Issue):
As of this verification, Step 6 shows:
```json
{
  "recovery_id": "27ff1b2d-4953-4c7a-b94f-cc7285f75682",
  "state": "FAILED",
  "action_type": "NONE",
  "amount_paise": 0,
  "error_message": "Unsupported recovery action: None. Only PAYMENT_LINK is supported."
}
```
**This indicates a bug in the approval flow where the action_type is not being properly set.**

## Path E: NORMAL / BLOCKED (no action required)
*(Scenario E: Customer-caused issue - no recovery action needed)*

### Step 1: Verify Incident Classification
```bash
curl -s http://localhost:8000/api/support/incidents | \
  jq -r '.items[] | select(.incident_id=="scenario_e_merchant_20260822_110000") | 
  {incident_id, policy_status, recovery_status, severity, classification}'
```
**Expected Output:**
```json
{
  "incident_id": "scenario_e_merchant_20260822_110000",
  "policy_status": "BLOCKED",
  "recovery_status": "NOT_AUTHORIZED",
  "severity": "LOW",
  "classification": "NORMAL"
}
```

### Step 2: Check Recovery Details
```bash
curl -s http://localhost:8000/api/support/incidents/scenario_e_merchant_20260822_110000 | \
  jq '.recovery | {recovery_id, state, action_type, error_message}'
```
**Expected Output:**
```json
{
  "recovery_id": "916084da-c9a7-4d46-b4a3-bf4f172609fa",
  "state": "NOT_AUTHORIZED",
  "action_type": "NONE",
  "error_message": "Recovery blocked by policy engine - customer-caused issue"
}
```

### Step 3: Verify Evidence Shows Customer Cause
```bash
curl -s http://localhost:8000/api/support/incidents/scenario_e_merchant_20260822_110000/evidence | \
  jq '.error_evidence.failure_breakdown.customer_caused'
```
**Expected:** `63` (significantly higher than technical causes)

## Verification Summary
Run this quick summary to see all three paths:
```bash
echo "=== PATH SUMMARY ==="
echo "Path A (Auto-approved):"
curl -s http://localhost:8000/api/support/incidents | \
  jq -r '.items[] | select(.incident_id=="scenario_a_merchant_20260822_100000") | 
  "A: \(.policy_status) → \(.recovery_status)"'

echo "Path B (Human approval):"  
curl -s http://localhost:8000/api/support/incidents | \
  jq -r '.items[] | select(.incident_id=="scenario_h_merchant_20260822_120000") | 
  "H: \(.policy_status) → \(.recovery_status)"'

echo "Path E (Normal/Blocked):"
curl -s http://localhost:8000/api/support/incidents | \
  jq -r '.items[] | select(.incident_id=="scenario_e_merchant_20260822_110000") | 
  "E: \(.policy_status) → \(.recovery_status)"'
```