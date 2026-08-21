#!/usr/bin/env python3
"""
Scenario injection system for DegradeWatch Checkpoint 6.
Creates controlled degradation scenarios from healthy payment data.
"""

import json
import jsonlines
import argparse
import sys
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import random
import copy

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.analyze_baselines import (
    load_merchant_profile,
    parse_timestamp,
    categorize_failure
)

def load_healthy_payments(merchant_id: str, generated_dir: Path) -> List[Dict[str, Any]]:
    """Load healthy payments for a merchant from JSONL file."""
    payments_file = generated_dir / f"{merchant_id}.jsonl"
    payments = []

    if payments_file.exists():
        with jsonlines.open(payments_file, mode='r') as reader:
            for payment in reader:
                payments.append(payment)

    return payments

def save_payments(payments: List[Dict[str, Any]], merchant_id: str, output_dir: Path):
    """Save payments to JSONL file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payments_file = output_dir / f"{merchant_id}.jsonl"
    with jsonlines.open(payments_file, mode='w') as writer:
        for payment in payments:
            writer.write(payment)

def copy_baseline(baseline_dir: Path, output_dir: Path):
    """Copy baseline data to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for baseline_file in baseline_dir.glob("*.json"):
        import shutil
        shutil.copy2(baseline_file, output_dir / baseline_file.name)

def create_ground_truth(scenario_id: str, scenario_name: str, merchant_id: str,
                       affected_segment: Dict[str, Any], window: Dict[str, str],
                       expected_classification: str, expected_severity: str,
                       expected_behavior: Dict[str, Any], output_dir: Path,
                       true_cause: str):
    """Create ground truth JSON file."""
    ground_truth = {
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "merchant_id": merchant_id,
        "true_cause": true_cause,
        "affected_segment": affected_segment,
        "window": window,
        "expected_classification": expected_classification,
        "expected_severity": expected_severity,
        "expected_behavior": expected_behavior
    }

    ground_truth_file = output_dir / "ground_truth.json"
    with open(ground_truth_file, 'w') as f:
        json.dump(ground_truth, f, indent=2)

def determine_scenario_window(merchant_id: str, payments: List[Dict[str, Any]],
                            scenario_hours: float = 1.5) -> Tuple[datetime, datetime]:
    """
    Determine a deterministic scenario window based on merchant data.
    Returns (start_datetime, end_datetime) for injection.
    """
    if not payments:
        # Default window if no payments
        start = datetime(2026, 8, 20, 10, 15, 0)
        end = start + timedelta(hours=scenario_hours)
        return start, end

    # Parse all timestamps
    timestamps = [parse_timestamp(p["timestamp"]) for p in payments]
    timestamps.sort()

    # Use middle 50% of data range to avoid edges
    start_idx = len(timestamps) // 4
    end_idx = 3 * len(timestamps) // 4
    usable_timestamps = timestamps[start_idx:end_idx]

    if not usable_timestamps:
        usable_timestamps = timestamps

    # Pick deterministic start based on hash of merchant_id + first timestamp
    hash_input = f"{merchant_id}_{usable_timestamps[0].isoformat()}"
    hash_int = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
    offset_ratio = (hash_int % 1000) / 1000.0  # 0.0 to 1.0

    time_range = usable_timestamps[-1] - usable_timestamps[0]
    start_offset = time_range * offset_ratio
    window_start = usable_timestamps[0] + start_offset
    window_end = window_start + timedelta(hours=scenario_hours)

    # Ensure window doesn't exceed data bounds
    if window_end > timestamps[-1]:
        window_end = timestamps[-1]
        window_start = window_end - timedelta(hours=scenario_hours)

    # Ensure window start is not before first timestamp
    if window_start < timestamps[0]:
        window_start = timestamps[0]
        window_end = window_start + timedelta(hours=scenario_hours)

    return window_start, window_end

def get_segment_key(payment: Dict[str, Any]) -> str:
    """Generate segment key for a payment."""
    method = payment["payment_method"]
    bank = payment.get("bank")
    device = payment.get("device")
    upi_app = payment.get("upi_app")

    if method in ["CARD", "NETBANKING"]:
        return f"{method}|{device}"
    else:  # UPI
        return f"{method}|{bank}|{device}|{upi_app}"

def is_in_target_segment(payment: Dict[str, Any], target_segment: Optional[Dict[str, Any]]) -> bool:
    """Check if payment belongs to target segment."""
    # If no target segment specified, all payments match
    if target_segment is None:
        return True

    method = payment["payment_method"]

    # Check payment method (only if specified in target segment)
    if target_segment.get("payment_method") is not None:
        if method != target_segment["payment_method"]:
            return False

    # Check bank if specified
    if target_segment.get("bank") is not None:
        if payment.get("bank") != target_segment["bank"]:
            return False

    # Check device if specified
    if target_segment.get("device") is not None:
        if payment.get("device") != target_segment["device"]:
            return False

    # Check UPI app if specified and payment is UPI
    if method == "UPI" and target_segment.get("upi_app") is not None:
        if payment.get("upi_app") != target_segment["upi_app"]:
            return False

    return True

def apply_scenario_a_injection(payments: List[Dict[str, Any]],
                              window_start: datetime, window_end: datetime,
                              merchant_profile: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply Scenario A: Bank + Device + Method degradation (HERO).
    Target: UPI + BANK_X + ANDROID
    """
    target_segment = {
        "payment_method": "UPI",
        "bank": "BANK_X",
        "device": "ANDROID",
        "upi_app": None  # Any UPI app
    }

    # Get baseline stats for target segment
    baseline_stats = calculate_segment_baseline(payments, window_start, window_end, target_segment, merchant_profile)

    # Calculate how many events to modify to achieve target success rate
    target_success_rate = 0.78  # Target 78% success rate
    current_success_rate = baseline_stats["success_rate"]
    total_attempts = baseline_stats["attempts"]

    if total_attempts == 0:
        return payments, {"modified": 0, "reason": "no_attempts_in_segment"}

    target_successes = round(total_attempts * target_success_rate)
    current_successes = baseline_stats["successes"]
    successes_to_convert = current_successes - target_successes

    if successes_to_convert <= 0:
        return payments, {"modified": 0, "reason": "already_below_target"}

    # Convert successful events to failures within the window and target segment
    modified_payments = copy.deepcopy(payments)
    modified_count = 0

    # Collect candidates for modification (successful payments in target segment & window)
    candidates = []
    for i, payment in enumerate(modified_payments):
        timestamp = parse_timestamp(payment["timestamp"])
        if (window_start <= timestamp < window_end and
            payment["status"] == "success" and
            is_in_target_segment(payment, target_segment)):
            candidates.append((i, payment))

    # Deterministic shuffle based on window start
    random.seed(int(window_start.timestamp()))
    random.shuffle(candidates)

    # Modify the required number of events
    for i in range(min(successes_to_convert, len(candidates))):
        idx, payment = candidates[i]
        modified_payments[idx]["status"] = "failed"
        modified_payments[idx]["error_code"] = get_deterministic_error_code(idx, ["BANK_TECHNICAL_ERROR", "UPI_TIMEOUT", "GATEWAY_ERROR", "NETWORK_ERROR"])
        # Increase latency for technical failures
        base_latency = payment["latency_ms"]
        modified_payments[idx]["latency_ms"] = int(base_latency * (1.5 + (random.random() * 2.0)))  # 1.5x to 3.5x
        modified_count += 1

    stats = {
        "modified": modified_count,
        "target_segment": target_segment,
        "window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat()
        },
        "baseline_success_rate": current_success_rate,
        "target_success_rate": target_success_rate,
        "total_attempts_in_segment": total_attempts
    }

    return modified_payments, stats

def apply_scenario_b_injection(payments: List[Dict[str, Any]],
                              window_start: datetime, window_end: datetime,
                              merchant_profile: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply Scenario B: Payment Method degradation.
    Target: UPI (all banks and devices)
    """
    target_segment = {
        "payment_method": "UPI",
        "bank": None,
        "device": None,
        "upi_app": None
    }

    # Get baseline stats for target segment
    baseline_stats = calculate_segment_baseline(payments, window_start, window_end, target_segment, merchant_profile)

    # Calculate how many events to modify to achieve target success rate
    target_success_rate = 0.80  # Target 80% success rate for method-level
    current_success_rate = baseline_stats["success_rate"]
    total_attempts = baseline_stats["attempts"]

    if total_attempts == 0:
        return payments, {"modified": 0, "reason": "no_attempts_in_segment"}

    target_successes = round(total_attempts * target_success_rate)
    current_successes = baseline_stats["successes"]
    successes_to_convert = current_successes - target_successes

    if successes_to_convert <= 0:
        return payments, {"modified": 0, "reason": "already_below_target"}

    # Convert successful events to failures within the window and target segment
    modified_payments = copy.deepcopy(payments)
    modified_count = 0

    # Collect candidates for modification (successful payments in target segment & window)
    candidates = []
    for i, payment in enumerate(modified_payments):
        timestamp = parse_timestamp(payment["timestamp"])
        if (window_start <= timestamp < window_end and
            payment["status"] == "success" and
            is_in_target_segment(payment, target_segment)):
            candidates.append((i, payment))

    # Deterministic shuffle based on window start
    random.seed(int(window_start.timestamp()) + 1000)  # Different seed from Scenario A
    random.shuffle(candidates)

    # Modify the required number of events
    for i in range(min(successes_to_convert, len(candidates))):
        idx, payment = candidates[i]
        modified_payments[idx]["status"] = "failed"
        # Distribute across different banks to simulate broad UPI issue
        error_codes = ["BANK_TECHNICAL_ERROR", "UPI_TIMEOUT", "GATEWAY_ERROR", "NETWORK_ERROR"]
        modified_payments[idx]["error_code"] = get_deterministic_error_code(idx, error_codes)
        # Increase latency for technical failures
        base_latency = payment["latency_ms"]
        modified_payments[idx]["latency_ms"] = int(base_latency * (1.3 + (random.random() * 1.5)))
        modified_count += 1

    stats = {
        "modified": modified_count,
        "target_segment": target_segment,
        "window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat()
        },
        "baseline_success_rate": current_success_rate,
        "target_success_rate": target_success_rate,
        "total_attempts_in_segment": total_attempts
    }

    return modified_payments, stats

def apply_scenario_c_injection(payments: List[Dict[str, Any]],
                              window_start: datetime, window_end: datetime,
                              merchant_profile: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply Scenario C: Merchant-wide degradation.
    Target: Multiple payment methods simultaneously
    """
    target_segments = [
        {"payment_method": "UPI", "bank": None, "device": None, "upi_app": None},
        {"payment_method": "CARD", "bank": None, "device": None},
        {"payment_method": "NETBANKING", "bank": None, "device": None}
    ]

    # Calculate baseline stats for all segments
    segment_stats = {}
    for segment in target_segments:
        segment_key = get_segment_key_from_dict(segment)
        stats = calculate_segment_baseline(payments, window_start, window_end, segment, merchant_profile)
        segment_stats[segment_key] = stats

    # Apply moderate degradation to all segments (more realistic for merchant-wide issue)
    target_success_rate = 0.85  # Target 85% success rate (less severe than single segment)
    modified_payments = copy.deepcopy(payments)
    total_modified = 0

    # Process each segment
    for segment in target_segments:
        segment_key = get_segment_key_from_dict(segment)
        baseline_stats = segment_stats[segment_key]
        total_attempts = baseline_stats["attempts"]

        if total_attempts == 0:
            continue

        current_success_rate = baseline_stats["success_rate"]
        target_successes = round(total_attempts * target_success_rate)
        current_successes = baseline_stats["successes"]
        successes_to_convert = max(0, current_successes - target_successes)

        if successes_to_convert <= 0:
            continue

        # Collect candidates for modification
        candidates = []
        for i, payment in enumerate(modified_payments):
            timestamp = parse_timestamp(payment["timestamp"])
            if (window_start <= timestamp < window_end and
                payment["status"] == "success" and
                is_in_target_segment(payment, segment)):
                candidates.append((i, payment))

        # Deterministic shuffle
        random.seed(int(window_start.timestamp()) + hash(segment_key))
        random.shuffle(candidates)

        # Modify events
        for i in range(min(successes_to_convert, len(candidates))):
            idx, payment = candidates[i]
            modified_payments[idx]["status"] = "failed"
            # Use appropriate error types for each payment method
            if segment["payment_method"] == "CARD":
                error_options = ["GATEWAY_ERROR", "INVALID_NUMBER", "EXPIRED_CARD"]
            elif segment["payment_method"] == "NETBANKING":
                error_options = ["BANK_TECHNICAL_ERROR", "NETWORK_ERROR", "GATEWAY_ERROR"]
            else:  # UPI
                error_options = ["BANK_TECHNICAL_ERROR", "UPI_TIMEOUT", "GATEWAY_ERROR", "NETWORK_ERROR"]

            modified_payments[idx]["error_code"] = get_deterministic_error_code(idx, error_options)
            base_latency = payment["latency_ms"]
            modified_payments[idx]["latency_ms"] = int(base_latency * (1.2 + (random.random() * 1.3)))
            total_modified += 1

    stats = {
        "modified": total_modified,
        "target_segments": target_segments,
        "window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat()
        },
        "segment_baseline_rates": {k: v["success_rate"] for k, v in segment_stats.items()},
        "target_success_rate": target_success_rate
    }

    return modified_payments, stats

def apply_scenario_d_injection(payments: List[Dict[str, Any]],
                              window_start: datetime, window_end: datetime,
                              merchant_profile: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply Scenario D: Device degradation.
    Target: ANDROID (across payment methods and banks)
    """
    target_segment = {
        "payment_method": None,  # Any method
        "bank": None,
        "device": "ANDROID",
        "upi_app": None
    }

    # Get baseline stats for target segment
    baseline_stats = calculate_segment_baseline(payments, window_start, window_end, target_segment, merchant_profile)

    # Calculate how many events to modify to achieve target success rate
    target_success_rate = 0.82  # Target 82% success rate
    current_success_rate = baseline_stats["success_rate"]
    total_attempts = baseline_stats["attempts"]

    if total_attempts == 0:
        return payments, {"modified": 0, "reason": "no_attempts_in_segment"}

    target_successes = round(total_attempts * target_success_rate)
    current_successes = baseline_stats["successes"]
    successes_to_convert = current_successes - target_successes

    if successes_to_convert <= 0:
        return payments, {"modified": 0, "reason": "already_below_target"}

    # Convert successful events to failures within the window and target segment
    modified_payments = copy.deepcopy(payments)
    modified_count = 0

    # Collect candidates for modification (successful payments in target segment & window)
    candidates = []
    for i, payment in enumerate(modified_payments):
        timestamp = parse_timestamp(payment["timestamp"])
        if (window_start <= timestamp < window_end and
            payment["status"] == "success" and
            is_in_target_segment(payment, target_segment)):
            candidates.append((i, payment))

    # Deterministic shuffle based on window start
    random.seed(int(window_start.timestamp()) + 2000)  # Different seed
    random.shuffle(candidates)

    # Modify the required number of events
    for i in range(min(successes_to_convert, len(candidates))):
        idx, payment = candidates[i]
        modified_payments[idx]["status"] = "failed"
        # Distribute error types based on payment method
        if payment["payment_method"] == "UPI":
            error_options = ["BANK_TECHNICAL_ERROR", "UPI_TIMEOUT", "GATEWAY_ERROR", "NETWORK_ERROR"]
        elif payment["payment_method"] == "CARD":
            error_options = ["GATEWAY_ERROR", "TECHNICAL_ERROR"]
        else:  # NETBANKING
            error_options = ["BANK_TECHNICAL_ERROR", "NETWORK_ERROR", "GATEWAY_ERROR"]

        modified_payments[idx]["error_code"] = get_deterministic_error_code(idx, error_options)
        # Increase latency for technical failures
        base_latency = payment["latency_ms"]
        modified_payments[idx]["latency_ms"] = int(base_latency * (1.4 + (random.random() * 1.6)))
        modified_count += 1

    stats = {
        "modified": modified_count,
        "target_segment": target_segment,
        "window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat()
        },
        "baseline_success_rate": current_success_rate,
        "target_success_rate": target_success_rate,
        "total_attempts_in_segment": total_attempts
    }

    return modified_payments, stats

def apply_scenario_e_injection(payments: List[Dict[str, Any]],
                              window_start: datetime, window_end: datetime,
                              merchant_profile: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply Scenario E: Customer-caused failure spike (NEGATIVE TEST).
    Target: Increase customer-caused errors without technical degradation
    """
    # We'll increase customer-caused errors across all segments
    target_segment = {
        "payment_method": None,
        "bank": None,
        "device": None,
        "upi_app": None
    }

    # Get baseline stats
    baseline_stats = calculate_segment_baseline(payments, window_start, window_end, target_segment, merchant_profile)

    # Increase customer-caused error rate significantly
    # Target: increase customer-caused errors by 3-4x while keeping technical errors normal
    baseline_customer_rate = baseline_stats["failure_breakdown"]["customer_caused"] / max(baseline_stats["attempts"], 1)
    baseline_technical_rate = baseline_stats["failure_breakdown"]["technical"] / max(baseline_stats["attempts"], 1)

    # Target customer-caused rate: 3x baseline
    target_customer_rate = min(0.25, baseline_customer_rate * 3.5)  # Cap at 25%
    current_customer_count = baseline_stats["failure_breakdown"]["customer_caused"]
    target_customer_count = int(baseline_stats["attempts"] * target_customer_rate)
    additional_customer_errors_needed = target_customer_count - current_customer_count

    if additional_customer_errors_needed <= 0:
        return payments, {"modified": 0, "reason": "already_at_target"}

    # Convert some successful payments and some technical failures to customer-caused failures
    modified_payments = copy.deepcopy(payments)
    modified_count = 0

    # Collect candidates: successful payments and technical failures in window
    candidates = []
    for i, payment in enumerate(modified_payments):
        timestamp = parse_timestamp(payment["timestamp"])
        if window_start <= timestamp < window_end:
            # Include successful payments and existing technical failures
            if (payment["status"] == "success" or
                (payment["status"] == "failed" and categorize_failure(payment.get("error_code")) == "technical")):
                candidates.append((i, payment))

    # Deterministic shuffle
    random.seed(int(window_start.timestamp()) + 3000)
    random.shuffle(candidates)

    # Modify events to be customer-caused failures
    for i in range(min(additional_customer_errors_needed, len(candidates))):
        idx, payment = candidates[i]
        modified_payments[idx]["status"] = "failed"
        modified_payments[idx]["error_code"] = get_deterministic_customer_error(idx)
        # Customer errors typically have normal latency
        modified_payments[idx]["latency_ms"] = int(payment["latency_ms"] * 0.9)  # Slightly faster or normal
        modified_count += 1

    stats = {
        "modified": modified_count,
        "target_segment": target_segment,
        "window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat()
        },
        "baseline_customer_rate": baseline_customer_rate,
        "target_customer_rate": target_customer_rate,
        "baseline_technical_rate": baseline_technical_rate,
        "total_attempts_in_window": len([p for p in payments if window_start <= parse_timestamp(p["timestamp"]) < window_end])
    }

    return modified_payments, stats

def calculate_segment_baseline(payments: List[Dict[str, Any]],
                              window_start: datetime, window_end: datetime,
                              target_segment: Dict[str, Any],
                              merchant_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate baseline statistics for a segment within a time window."""
    attempts = 0
    successes = 0
    failures = 0
    customer_caused = 0
    technical = 0
    other = 0
    latencies = []
    amounts = []

    for payment in payments:
        timestamp = parse_timestamp(payment["timestamp"])
        if window_start <= timestamp < window_end:
            if is_in_target_segment(payment, target_segment):
                attempts += 1
                if payment["status"] == "success":
                    successes += 1
                    latencies.append(payment["latency_ms"])
                    amounts.append(payment["amount"])
                else:
                    failures += 1
                    latency = payment["latency_ms"]
                    latencies.append(latency)
                    amounts.append(payment["amount"])
                    failure_type = categorize_failure(payment.get("error_code"))
                    if failure_type == "customer_caused":
                        customer_caused += 1
                    elif failure_type == "technical":
                        technical += 1
                    else:
                        other += 1

    success_rate = successes / attempts if attempts > 0 else 0
    failure_rate = failures / attempts if attempts > 0 else 0

    # Calculate statistics
    def safe_mean(values):
        return sum(values) / len(values) if values else 0

    def safe_median(values):
        if not values:
            return 0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n % 2 == 0:
            return (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2
        else:
            return sorted_vals[n//2]

    def safe_p95(values):
        if not values:
            return 0
        sorted_vals = sorted(values)
        index = int(0.95 * len(sorted_vals))
        if index >= len(sorted_vals):
            index = len(sorted_vals) - 1
        return sorted_vals[index]

    return {
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "customer_caused": customer_caused,
        "technical": technical,
        "other": other,
        "average_latency_ms": safe_mean(latencies),
        "p95_latency_ms": safe_p95(latencies),
        "average_amount": safe_mean(amounts),
        "median_amount": safe_median(amounts),
        "failure_breakdown": {
            "customer_caused": customer_caused,
            "technical": technical,
            "other": other
        }
    }

def get_segment_key_from_dict(segment: Dict[str, Any]) -> str:
    """Generate segment key from segment dictionary."""
    method = segment.get("payment_method", "UNKNOWN")
    bank = segment.get("bank")
    device = segment.get("device")
    upi_app = segment.get("upi_app")

    if method in ["CARD", "NETBANKING"]:
        return f"{method}|{device or 'ANY'}"
    else:  # UPI or unknown
        return f"{method}|{bank or 'ANY'}|{device or 'ANY'}|{upi_app or 'ANY'}"

def get_deterministic_error_code(seed: int, error_options: List[str]) -> str:
    """Get deterministic error code based on seed."""
    random.seed(seed)
    return random.choice(error_options)

def get_deterministic_customer_error(seed: int) -> str:
    """Get deterministic customer error code."""
    customer_errors = ["INSUFFICIENT_FUNDS", "WRONG_PIN", "OTP_FAILED", "USER_CANCELLED"]
    random.seed(seed)
    return random.choice(customer_errors)

def main():
    parser = argparse.ArgumentParser(description="Inject degradation scenarios into healthy payment data")
    parser.add_argument("--scenario", choices=["A", "B", "C", "D", "E"], required=True,
                       help="Scenario to inject")
    parser.add_argument("--merchant", default="merch_upi_smb",
                       help="Merchant ID (default: merch_upi_smb)")
    parser.add_argument("--hours", type=float, default=1.5,
                       help="Scenario duration in hours (default: 1.5)")
    parser.add_argument("--seed", type=int, default=None,
                       help="Random seed for reproducibility (default: derived from window)")

    args = parser.parse_args()

    # Set up paths
    project_root = Path(__file__).parent.parent
    generated_dir = project_root / "data" / "generated"
    scenario_dir = project_root / "data" / "scenarios" / f"scenario_{args.scenario}"
    baseline_dir = generated_dir / "baselines"

    # Load healthy data
    print(f"Loading healthy data for merchant {args.merchant}...")
    payments = load_healthy_payments(args.merchant, generated_dir)
    print(f"Loaded {len(payments)} payments")

    if not payments:
        print("ERROR: No payments found!")
        sys.exit(1)

    # Determine injection window
    print(f"Determinating {args.hours}-hour scenario window...")
    window_start, window_end = determine_scenario_window(args.merchant, payments, args.hours)
    print(f"Injection window: {window_start.isoformat()} to {window_end.isoformat()}")

    # Count payments in window
    window_payments = [p for p in payments if window_start <= parse_timestamp(p["timestamp"]) < window_end]
    print(f"Payments in window: {len(window_payments)}")

    # Load merchant profile
    merchant_profile = load_merchant_profile(args.merchant)

    # Apply scenario injection
    print(f"Injecting Scenario {args.scenario}...")
    if args.scenario == "A":
        modified_payments, stats = apply_scenario_a_injection(payments, window_start, window_end, merchant_profile)
        scenario_name = "bank_device_method_degradation"
        affected_segment = {"payment_method": "UPI", "bank": "BANK_X", "device": "ANDROID", "upi_app": None}
        expected_classification = "INCIDENT"
        expected_severity = "HIGH"
        expected_behavior = {
            "success_rate_target": [0.76, 0.80],
            "technical_error_increase": True,
            "localized": True
        }
    elif args.scenario == "B":
        modified_payments, stats = apply_scenario_b_injection(payments, window_start, window_end, merchant_profile)
        scenario_name = "method_degradation"
        affected_segment = {"payment_method": "UPI", "bank": None, "device": None, "upi_app": None}
        expected_classification = "INCIDENT"
        expected_severity = "MEDIUM"
        expected_behavior = {
            "success_rate_target": [0.78, 0.85],
            "technical_error_increase": True,
            "localized": False  # Method-level, not localized to specific bank/device
        }
    elif args.scenario == "C":
        modified_payments, stats = apply_scenario_c_injection(payments, window_start, window_end, merchant_profile)
        scenario_name = "merchant_wide_degradation"
        affected_segment = {"payment_method": "MULTIPLE", "bank": None, "device": None}
        expected_classification = "INCIDENT"
        expected_severity = "HIGH"
        expected_behavior = {
            "success_rate_target": [0.80, 0.90],
            "technical_error_increase": True,
            "localized": False  # Widespread across methods
        }
    elif args.scenario == "D":
        modified_payments, stats = apply_scenario_d_injection(payments, window_start, window_end, merchant_profile)
        scenario_name = "device_degradation"
        affected_segment = {"payment_method": None, "bank": None, "device": "ANDROID", "upi_app": None}
        expected_classification = "INCIDENT"
        expected_severity = "MEDIUM"
        expected_behavior = {
            "success_rate_target": [0.80, 0.88],
            "technical_error_increase": True,
            "localized": True  # Device-level localization
        }
    elif args.scenario == "E":
        modified_payments, stats = apply_scenario_e_injection(payments, window_start, window_end, merchant_profile)
        scenario_name = "customer_caused_failure_spike"
        affected_segment = {"payment_method": None, "bank": None, "device": None, "upi_app": None}
        expected_classification = "NORMAL"
        expected_severity = "LOW"
        expected_behavior = {
            "success_rate_target": [0.70, 0.85],  # Success rate may drop but should not trigger incident
            "customer_error_increase": True,
            "technical_error_increase": False,
            "expected_intervention": False
        }

    modified_count = stats.get("modified", 0)
    print(f"Modified {modified_count} payments")

    # Save scenario data
    print(f"Saving scenario data to {scenario_dir}...")
    save_payments(modified_payments, args.merchant, scenario_dir)
    # Copy baseline to baselines subdirectory to match expected structure
    scenario_baseline_dir = scenario_dir / "baselines"
    copy_baseline(baseline_dir, scenario_baseline_dir)

    # Create ground truth
    window_info = {
        "start": window_start.isoformat(),
        "end": window_end.isoformat()
    }
    # Fix true cause to avoid double _DEGRADATION
    if args.scenario == "E":
        true_cause = "CUSTOMER_CAUSED_FAILURE_SPIKE"
    else:
        true_cause = f"{args.scenario}_{scenario_name.upper()}"
    create_ground_truth(
        args.scenario, scenario_name, args.merchant,
        affected_segment, window_info,
        expected_classification, expected_severity,
        expected_behavior, scenario_dir, true_cause
    )

    # Print statistics
    print("\n=== INJECTION COMPLETE ===")
    print(f"Scenario: {args.scenario} ({scenario_name})")
    print(f"Modified payments: {modified_count}")
    print(f"Window: {window_info['start']} to {window_info['end']}")
    print(f"Ground truth saved to: {scenario_dir / 'ground_truth.json'}")
    print(f"Scenario data saved to: {scenario_dir}")

    # Calculate and show actual rates after injection
    modified_window_payments = [p for p in modified_payments if window_start <= parse_timestamp(p["timestamp"]) < window_end]
    if modified_window_payments:
        # Calculate overall stats for window
        total_attempts = len(modified_window_payments)
        successes = sum(1 for p in modified_window_payments if p["status"] == "success")
        failures = total_attempts - successes
        success_rate = successes / total_attempts if total_attempts > 0 else 0

        customer_caused = sum(1 for p in modified_window_payments
                            if p["status"] == "failed" and categorize_failure(p.get("error_code")) == "customer_caused")
        technical = sum(1 for p in modified_window_payments
                       if p["status"] == "failed" and categorize_failure(p.get("error_code")) == "technical")

        print(f"\nWindow statistics after injection:")
        print(f"  Total attempts: {total_attempts}")
        print(f"  Success rate: {success_rate:.3f} ({success_rate*100:.1f}%)")
        print(f"  Customer-caused errors: {customer_caused} ({customer_caused/total_attempts*100:.1f}% of total)")
        print(f"  Technical errors: {technical} ({technical/total_attempts*100:.1f}% of total)")

if __name__ == "__main__":
    main()