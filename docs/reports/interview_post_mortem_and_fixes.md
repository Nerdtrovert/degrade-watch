# 🧠 Razorpay Interview Cheat Sheet: The Post-Mortem & Fixes

When talking to a hiring manager or tech lead at a high-volume payment processor (like Razorpay), they want to see rigorous monitoring, segment-level granularity, failure classification safety, and clean statistical math.

Use the following 4 structured points to sell the engineering complexity of this project:

### 1. The Core Project: Automated Anomaly Detection & Self-Healing

* **What you built**: An automated payment link monitoring and self-healing engine (DegradeWatch) that detects payment infrastructure degradation, analyzes the root cause via deterministic statistical evidence, and triggers automated payouts.
* **Why it matters**: In high-scale payment processing, top-level transaction success rates (SR) are a lagging indicator. Localized gateway failures (e.g., *UPI + BANK_X + Android*) get masked by overall high success rates, causing undetected customer churn.

### 2. High-Impact Technical Problems & Solutions

#### 🔴 Bug 1: Top-Level Metrics Masking Localized Outages (The Aggregation Masking Problem)

* **The Problem**: A localized payment failure (like a BANK_X UPI gateway issue) represented only a small percentage of total merchant traffic. The merchant-wide success rate changed by only ~1.68%, which was too small to trigger top-level alerts.
* **The Solution**: Refactored the anomaly detector to analyze payment traffic on a granular, multi-dimensional basis (Method, Bank, Device, UPI App) using bottom-up hierarchical aggregation, making localized failures a first-class detection signal.

#### 🔴 Bug 2: Window-Duration Normalization Mismatch (The ₹31 Lakh Math Bug)

* **The Problem**: The impact assessment builder calculated revenue at risk by comparing raw transaction numbers from a 14-day baseline period against a 90-minute analysis window, inflating the revenue at risk from ₹99,000 to ₹31 Lakhs and triggering false emergency halts.
* **The Solution**: Normalized the baseline attempt numbers to the window duration dynamically using baseline metadata period durations, keeping monetary arithmetic strict in integer paise.

#### 🔴 Bug 3: Distinguishing Platform Failures from Customer Actions (The Safety Guardrail)

* **The Problem**: A spike in user-side errors (e.g., users entering wrong PINs or having insufficient funds) caused a success rate drop that the detector misclassified as an infrastructure outage.
* **The Solution**: Formulated a strict error-type boundary check (`is_customer_caused`) to isolate customer cancellations from platform technical failures, preventing incorrect automated payouts.

### 3. Safety Boundary Architecture (Policy & Recovery)

* **The Rule**: Enforced a strict boundary separating automatic remediation from manual trigger:
  * `AUTO_APPROVED` ➡️ Executes payment link creation automatically.
  * `HUMAN_APPROVAL` ➡️ Stops automatic recovery (held for human audit due to high revenue or non-standard anomalies like intermittent/unstable signals).
  * `BLOCKED` ➡️ Halts execution (e.g., when the event is customer-caused).
* **The LLM boundary**: Constrained the LLM Report Generator to only explaining forensic evidence. Crucial fields like `severity`, `incident_id`, and `affected_segment` are backend-owned and cannot be overridden by LLM output.

### 4. Rigorous QA & Scenario Simulation

* **What you did**: Designed a five-scenario degradation simulator injecting distinct gateway outages, customer-caused spikes, and method outages.
* **Result**: Initially, the detector failed 3 out of 5 simulation scenarios. Through rigorous refactoring of the nested loops, scope variable shadowing fixes, and signal mapping, achieved 100% correctness (5/5 scenarios) and scaled unit/integration test coverage to 119 passing tests.



Problem:

RecoveryEngine currently assumes incident_id is always a UUID and calls

uuid.UUID(incident_id), but DegradeWatch uses business/string incident IDs

such as:

scenario_a_merchant_20260822_100000

scenario_e_merchant_20260822_110000

This causes:

ValueError: badly formed hexadecimal UUID string

during recovery execution/audit event creation.