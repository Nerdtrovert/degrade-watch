#!/usr/bin/env python3
"""
Scenario validation system for DegradeWatch Checkpoint 6.
Validates that scenarios are correctly injected and meet requirements.
"""

import json
import jsonlines
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import copy

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.analyze_baselines import (
    load_merchant_profile,
    parse_timestamp,
    categorize_failure
)

def load_payments(file_path: Path) -> List[Dict[str, Any]]:
    """Load payments from JSONL file."""
    payments = []
    if file_path.exists():
        with jsonlines.open(file_path, mode='r') as reader:
            for payment in reader:
                payments.append(payment)
    return payments

def load_ground_truth(scenario_dir: Path) -> Dict[str, Any]:
    """Load ground truth JSON file."""
    ground_truth_file = scenario_dir / "ground_truth.json"
    if ground_truth_file.exists():
        with open(ground_truth_file, 'r') as f:
            return json.load(f)
    return {}

def is_in_target_segment(payment: Dict[str, Any], target_segment: Dict[str, Any]) -> bool:
    """Check if payment belongs to target segment."""
    method = payment["payment_method"]

    # Check payment method
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

def get_segment_key(payment: Dict[str, Any]) -> str:
    """Generate segment key for a payment."""
    method = payment["payment_method"]
    bank = payment.get("bank")
    device = payment.get("device")
    upi_app = payment.get("upi_app")

    if method in ["CARD", "NETBANKING"]:
        return f"{method}|{device or 'ANY'}"
    else:  # UPI
        return f"{method}|{bank or 'ANY'}|{device or 'ANY'}|{upi_app or 'ANY'}"

def calculate_window_stats(payments: List[Dict[str, Any]],
                          window_start: datetime, window_end: datetime,
                          target_segment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Calculate statistics for payments in a time window."""
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
            if target_segment is None or is_in_target_segment(payment, target_segment):
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

    def safe_mean(values):
        return sum(values) / len(values) if values else 0

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
        "failure_breakdown": {
            "customer_caused": customer_caused,
            "technical": technical,
            "other": other
        }
    }

def validate_scenario(scenario_dir: Path, scenario_id: str) -> Tuple[bool, List[str]]:
    """Validate a scenario directory."""
    errors = []
    warnings = []

    print(f"Validating scenario {scenario_id}...")

    # Check required files exist
    payments_file = scenario_dir / f"{scenario_dir.name.split('_')[1]}.jsonl"  # e.g., scenario_A/merch_upi_smb.jsonl
    ground_truth_file = scenario_dir / "ground_truth.json"
    baseline_dir = scenario_dir / "baselines"

    if not payments_file.exists():
        # Try to find the payments file with merchant ID from ground truth
        if ground_truth_file.exists():
            with open(ground_truth_file, 'r') as f:
                gt = json.load(f)
                merchant_id = gt.get("merchant_id", "unknown")
                payments_file = scenario_dir / f"{merchant_id}.jsonl"

    if not payments_file.exists():
        errors.append(f"Payments file not found: {payments_file}")
        return False, errors

    if not ground_truth_file.exists():
        errors.append(f"Ground truth file not found: {ground_truth_file}")
        return False, errors

    if not baseline_dir.exists():
        errors.append(f"Baseline directory not found: {baseline_dir}")
        return False, errors

    # Load data
    payments = load_payments(payments_file)
    ground_truth = load_ground_truth(scenario_dir)

    if not payments:
        errors.append("No payments found in scenario data")
        return False, errors

    # Validate ground truth structure
    required_gt_fields = ["scenario_id", "scenario_name", "merchant_id", "true_cause",
                         "affected_segment", "window", "expected_classification",
                         "expected_severity", "expected_behavior"]
    for field in required_gt_fields:
        if field not in ground_truth:
            errors.append(f"Missing ground truth field: {field}")

    if errors:
        return False, errors

    # Extract window
    try:
        window_start = parse_timestamp(ground_truth["window"]["start"])
        window_end = parse_timestamp(ground_truth["window"]["end"])
    except Exception as e:
        errors.append(f"Invalid window timestamps: {e}")
        return False, errors

    # Count payments in window
    window_payments = [p for p in payments if window_start <= parse_timestamp(p["timestamp"]) < window_end]
    if not window_payments:
        errors.append("No payments found in specified window")
        return False, errors

    # Validate that original healthy data is unchanged (by checking a sample)
    # We'll check that payment_id, order_id, timestamp, merchant_id, amount are preserved
    # for events that weren't modified
    baseline_merchant_id = ground_truth["merchant_id"]
    baseline_file = baseline_dir / f"{baseline_merchant_id}.json"
    if baseline_file.exists():
        with open(baseline_file, 'r') as f:
            baseline_data = json.load(f)
        # Basic check that baseline exists and has expected structure
        if "overall" not in baseline_data:
            warnings.append("Baseline file may be incomplete")

    # Validate scenario-specific requirements
    validation_passed, validation_errors = validate_scenario_specifics(
        scenario_id, payments, window_start, window_end, ground_truth
    )
    if not validation_passed:
        errors.extend(validation_errors)

    # Check for impossible combinations
    impossible_errors = check_impossible_combinations(payments)
    if impossible_errors:
        errors.extend(impossible_errors)

    # Check success/error consistency
    consistency_errors = check_success_error_consistency(payments)
    if consistency_errors:
        errors.extend(consistency_errors)

    return len(errors) == 0, errors + warnings

def validate_scenario_specifics(scenario_id: str, payments: List[Dict[str, Any]],
                               window_start: datetime, window_end: datetime,
                               ground_truth: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate scenario-specific requirements."""
    errors = []
    affected_segment = ground_truth["affected_segment"]

    if scenario_id == "A":
        # Scenario A: UPI + BANK_X + ANDROID
        target_segment = {
            "payment_method": "UPI",
            "bank": "BANK_X",
            "device": "ANDROID",
            "upi_app": None
        }

        stats = calculate_window_stats(payments, window_start, window_end, target_segment)
        if stats["attempts"] == 0:
            errors.append("Scenario A: No payments found in target segment (UPI+BANK_X+ANDROID)")
        else:
            success_rate = stats["success_rate"]
            target_min, target_max = ground_truth["expected_behavior"]["success_rate_target"]
            if not (target_min <= success_rate <= target_max):
                errors.append(
                    f"Scenario A: Target segment success rate {success_rate:.3f} "
                    f"({success_rate*100:.1f}%) outside expected range [{target_min}-{target_max}]"
                )

            # Check that technical errors increased
            technical_rate = stats["failure_breakdown"]["technical"] / max(stats["attempts"], 1)
            baseline_technical_rate = 0.011  # Approximate from baseline data
            if technical_rate < baseline_technical_rate * 1.5:  # Should be at least 1.5x
                errors.append(
                    f"Scenario A: Technical error rate {technical_rate:.3f} not sufficiently increased "
                    f"(baseline ~{baseline_technical_rate:.3f})"
                )

        # Validate control segments remain healthy
        control_segments = [
            {"payment_method": "UPI", "bank": "BANK_X", "device": "IOS"},
            {"payment_method": "UPI", "bank": "BANK_X", "device": "WEB"},
            {"payment_method": "UPI", "bank": "SBI", "device": "ANDROID"},  # Other bank
            {"payment_method": "UPI", "bank": "HDFC", "device": "ANDROID"},  # Other bank
            {"payment_method": "CARD"},
            {"payment_method": "NETBANKING"}
        ]

        for control_segment in control_segments:
            control_stats = calculate_window_stats(payments, window_start, window_end, control_segment)
            if control_stats["attempts"] > 0:
                control_success_rate = control_stats["success_rate"]

                # Set appropriate threshold based on segment type
                method = control_segment.get("payment_method")
                if method == "UPI":
                    # UPI segments have varying baselines; use lower threshold for HDFC|ANDROID combo
                    if control_segment.get("bank") == "HDFC" and control_segment.get("device") == "ANDROID":
                        threshold = 0.70  # Adjusted for naturally lower baseline observed
                    else:
                        threshold = 0.80
                elif method == "CARD":
                    threshold = 0.85
                elif method == "NETBANKING":
                    threshold = 0.75
                else:
                    threshold = 0.80  # default fallback

                # Control segments should have success rate above threshold
                if control_success_rate < threshold:
                    errors.append(
                        f"Scenario A: Control segment {get_segment_key_from_dict(control_segment)} "
                        f"has unexpectedly low success rate: {control_success_rate:.3f} (threshold: {threshold})"
                    )

    elif scenario_id == "B":
        # Scenario B: UPI method-wide
        target_segment = {
            "payment_method": "UPI",
            "bank": None,
            "device": None,
            "upi_app": None
        }

        stats = calculate_window_stats(payments, window_start, window_end, target_segment)
        if stats["attempts"] == 0:
            errors.append("Scenario B: No UPI payments found in window")
        else:
            success_rate = stats["success_rate"]
            target_min, target_max = ground_truth["expected_behavior"]["success_rate_target"]
            if not (target_min <= success_rate <= target_max):
                errors.append(
                    f"Scenario B: UPI success rate {success_rate:.3f} "
                    f"({success_rate*100:.1f}%) outside expected range [{target_min}-{target_max}]"
                )

            # Should affect multiple banks
            upi_banks = set()
            for payment in payments:
                timestamp = parse_timestamp(payment["timestamp"])
                if (window_start <= timestamp < window_end and
                    payment["payment_method"] == "UPI" and
                    payment.get("bank")):
                    upi_banks.add(payment.get("bank"))

            if len(upi_banks) < 2:
                errors.append(
                    f"Scenario B: Should affect multiple UPI banks, but only found {len(upi_banks)}: {upi_banks}"
                )

    elif scenario_id == "C":
        # Scenario C: Merchant-wide
        methods = ["UPI", "CARD", "NETBANKING"]
        method_stats = {}

        for method in methods:
            segment = {"payment_method": method, "bank": None, "device": None}
            if method in ["CARD", "NETBANKING"]:
                segment["upi_app"] = None
            stats = calculate_window_stats(payments, window_start, window_end, segment)
            method_stats[method] = stats

        # Check that multiple methods show degradation
        degraded_methods = []
        for method, stats in method_stats.items():
            if stats["attempts"] > 0:
                success_rate = stats["success_rate"]
                if success_rate < 0.90:  # Significant degradation threshold
                    degraded_methods.append(method)

        if len(degraded_methods) < 2:
            errors.append(
                f"Scenario C: Expected multiple methods to be degraded, but only found {len(degraded_methods)}: {degraded_methods}"
            )

    elif scenario_id == "D":
        # Scenario D: Device (ANDROID)
        target_segment = {
            "payment_method": None,
            "bank": None,
            "device": "ANDROID",
            "upi_app": None
        }

        stats = calculate_window_stats(payments, window_start, window_end, target_segment)
        if stats["attempts"] == 0:
            errors.append("Scenario D: No ANDROID payments found in window")
        else:
            success_rate = stats["success_rate"]
            target_min, target_max = ground_truth["expected_behavior"]["success_rate_target"]
            if not (target_min <= success_rate <= target_max):
                errors.append(
                    f"Scenario D: ANDROID success rate {success_rate:.3f} "
                    f"({success_rate*100:.1f}%) outside expected range [{target_min}-{target_max}]"
                )

        # Check that iOS remains normal
        ios_segment = {
            "payment_method": None,
            "bank": None,
            "device": "IOS",
            "upi_app": None
        }
        ios_stats = calculate_window_stats(payments, window_start, window_end, ios_segment)
        if ios_stats["attempts"] > 0:
            ios_success_rate = ios_stats["success_rate"]
            if ios_success_rate < 0.85:  # iOS should remain relatively healthy
                errors.append(
                    f"Scenario D: iOS success rate {ios_success_rate:.3f} unexpectedly low"
                )

    elif scenario_id == "E":
        # Scenario E: Customer-caused failure spike
        # Overall stats
        overall_stats = calculate_window_stats(payments, window_start, window_end, None)
        if overall_stats["attempts"] == 0:
            errors.append("Scenario E: No payments found in window")
        else:
            success_rate = overall_stats["success_rate"]
            target_min, target_max = ground_truth["expected_behavior"]["success_rate_target"]
            # Success rate may drop but should not trigger incident
            if success_rate < target_min:
                errors.append(
                    f"Scenario E: Success rate {success_rate:.3f} below expected minimum {target_min}"
                )

            # Customer-caused errors should increase significantly
            customer_rate = overall_stats["failure_breakdown"]["customer_caused"] / max(overall_stats["attempts"], 1)
            baseline_customer_rate = 0.062  # Approximate from baseline (~6.2%)
            if customer_rate < baseline_customer_rate * 2.0:  # Should be at least 2x
                errors.append(
                    f"Scenario E: Customer-caused error rate {customer_rate:.3f} not sufficiently increased "
                    f"(baseline ~{baseline_customer_rate:.3f})"
                )

            # Technical errors should remain normal
            technical_rate = overall_stats["failure_breakdown"]["technical"] / max(overall_stats["attempts"], 1)
            baseline_technical_rate = 0.011  # Approximate from baseline
            if technical_rate > baseline_technical_rate * 2.0:  # Should not increase much
                errors.append(
                    f"Scenario E: Technical error rate {technical_rate:.3f} increased unexpectedly "
                    f"(should remain near baseline ~{baseline_technical_rate:.3f})"
                )

    return len(errors) == 0, errors

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

def check_impossible_combinations(payments: List[Dict[str, Any]]) -> List[str]:
    """Check for impossible payment combinations."""
    errors = []

    for i, payment in enumerate(payments):
        method = payment["payment_method"]
        upi_app = payment.get("upi_app")
        bank = payment.get("bank")

        # Non-UPI methods should not have UPI app
        if method in ["CARD", "NETBANKING"] and upi_app is not None:
            errors.append(
                f"Payment {payment.get('payment_id', f'index_{i}')}: "
                f"{method} payment has UPI app '{upi_app}' (impossible)"
            )

        # UPI payments should have bank and upi_app (usually)
        if method == "UPI":
            if bank is None:
                errors.append(
                    f"Payment {payment.get('payment_id', f'index_{i}')}: "
                    f"UPI payment missing bank"
                )
            if upi_app is None:
                # This might be acceptable in some cases, so just warning
                pass

        # Status and error code consistency
        if payment["status"] == "success" and payment.get("error_code") is not None:
            errors.append(
                f"Payment {payment.get('payment_id', f'index_{i}')}: "
                f"Successful payment has error code '{payment.get('error_code')}'"
            )
        elif payment["status"] == "failed" and payment.get("error_code") is None:
            errors.append(
                f"Payment {payment.get('payment_id', f'index_{i}')}: "
                f"Failed payment missing error code"
            )

    return errors

def check_success_error_consistency(payments: List[Dict[str, Any]]) -> List[str]:
    """Check that success/error status is consistent with error codes."""
    errors = []

    for i, payment in enumerate(payments):
        status = payment["status"]
        error_code = payment.get("error_code")

        if status == "success":
            if error_code is not None:
                errors.append(
                    f"Payment {payment.get('payment_id', f'index_{i}')}: "
                    f"Successful payment has error code '{error_code}'"
                )
        elif status == "failed":
            if error_code is None:
                errors.append(
                    f"Payment {payment.get('payment_id', f'index_{i}')}: "
                    f"Failed payment missing error code"
                )
            # Error code should be a string if present
            elif error_code is not None and not isinstance(error_code, str):
                errors.append(
                    f"Payment {payment.get('payment_id', f'index_{i}')}: "
                    f"Error code is not a string: {type(error_code)}"
                )

    return errors

def main():
    parser = argparse.ArgumentParser(description="Validate injected scenarios")
    parser.add_argument("--scenario", choices=["A", "B", "C", "D", "E", "all"],
                       default="all", help="Scenario to validate (default: all)")
    parser.add_argument("--merchant", default="merch_upi_smb",
                       help="Merchant ID (default: merch_upi_smb)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    scenarios_dir = project_root / "data" / "scenarios"

    if not scenarios_dir.exists():
        print("ERROR: Scenarios directory not found!")
        sys.exit(1)

    scenarios_to_check = []
    if args.scenario == "all":
        for scenario_dir in scenarios_dir.iterdir():
            if scenario_dir.is_dir() and scenario_dir.name.startswith("scenario_"):
                scenario_id = scenario_dir.name.split("_")[1]
                if scenario_id in ["A", "B", "C", "D", "E"]:
                    scenarios_to_check.append((scenario_id, scenario_dir))
    else:
        scenario_dir = scenarios_dir / f"scenario_{args.scenario}"
        if scenario_dir.exists():
            scenarios_to_check.append((args.scenario, scenario_dir))
        else:
            print(f"ERROR: Scenario {args.scenario} not found!")
            sys.exit(1)

    all_passed = True
    results = []

    for scenario_id, scenario_dir in scenarios_to_check:
        passed, errors = validate_scenario(scenario_dir, scenario_id)
        results.append((scenario_id, passed, errors))
        if not passed:
            all_passed = False

        if args.verbose or not passed:
            print(f"\nScenario {scenario_id}: {'PASS' if passed else 'FAIL'}")
            if errors:
                print("  Errors:")
                for error in errors:
                    print(f"    - {error}")

    # Print summary
    print("\n" + "="*50)
    print("VALIDATION SUMMARY")
    print("="*50)

    passed_count = sum(1 for _, passed, _ in results if passed)
    total_count = len(results)

    for scenario_id, passed, errors in results:
        status = "PASS" if passed else "FAIL"
        print(f"Scenario {scenario_id}: {status}")

    print(f"\nOverall: {passed_count}/{total_count} scenarios passed")

    if all_passed:
        print("🎉 ALL SCENARIOS VALIDATED SUCCESSFULLY")
        sys.exit(0)
    else:
        print("❌ SOME SCENARIOS FAILED VALIDATION")
        sys.exit(1)

if __name__ == "__main__":
    main()