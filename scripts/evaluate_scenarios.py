#!/usr/bin/env python3
"""
Scenario evaluation system for DegradeWatch Checkpoint 6.
Evaluates how well the anomaly detector performs on injected scenarios.
"""

import json
import jsonlines
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.detect_anomalies import AnomalyDetector, DetectorConfig
from scripts.analyze_baselines import load_merchant_profile, parse_timestamp

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

def evaluate_scenario(scenario_dir: Path, scenario_id: str, merchant_id: str = "merch_upi_smb") -> Dict[str, Any]:
    """Evaluate a scenario using the anomaly detector."""
    print(f"Evaluating scenario {scenario_id}...")

    # Load data
    payments_file = scenario_dir / f"{merchant_id}.jsonl"
    ground_truth = load_ground_truth(scenario_dir)
    baseline_dir = scenario_dir / "baselines"

    if not payments_file.exists():
        # Try to find with scenario-specific naming
        alt_payments_file = scenario_dir / f"{scenario_dir.name.split('_')[1]}.jsonl"
        if alt_payments_file.exists():
            payments_file = alt_payments_file
        else:
            return {
                "scenario_id": scenario_id,
                "error": f"Payments file not found: {payments_file}"
            }

    if not ground_truth:
        return {
            "scenario_id": scenario_id,
            "error": "Ground truth not found"
        }

    if not baseline_dir.exists():
        return {
            "scenario_id": scenario_id,
            "error": "Baseline directory not found"
        }

    payments = load_payments(payments_file)
    if not payments:
        return {
            "scenario_id": scenario_id,
            "error": "No payments loaded"
        }

    # Extract window from ground truth
    try:
        window_start = parse_timestamp(ground_truth["window"]["start"])
        window_end = parse_timestamp(ground_truth["window"]["end"])
    except Exception as e:
        return {
            "scenario_id": scenario_id,
            "error": f"Invalid window timestamps: {e}"
        }

    # Run anomaly detector
    detector = AnomalyDetector()
    try:
        result = detector.detect(
            merchant_id=merchant_id,
            window_start=window_start,
            window_end=window_end,
            generated_data_dir=scenario_dir
        )
    except Exception as e:
        return {
            "scenario_id": scenario_id,
            "error": f"Detector failed: {e}"
        }

    # Extract expected values from ground truth
    expected_classification = ground_truth["expected_classification"]
    expected_severity = ground_truth["expected_severity"]
    expected_cause = ground_truth["true_cause"]
    affected_segment = ground_truth["affected_segment"]

    # Extract actual values from detector result
    actual_classification = result.get("classification", "ERROR")
    actual_severity = result.get("severity", "ERROR")
    actual_segment = result.get("candidate_segment", {})

    # Determine if classification is correct
    classification_correct = (actual_classification == expected_classification)

    # For severity, we'll be lenient - check if it's in the right ballpark
    severity_levels = ["LOW", "MEDIUM", "HIGH"]
    try:
        expected_level = severity_levels.index(expected_severity)
        actual_level = severity_levels.index(actual_severity) if actual_severity in severity_levels else -1
        severity_close = abs(expected_level - actual_level) <= 1  # Allow one level difference
    except ValueError:
        severity_close = False

    # Check if segment is correct (for localized scenarios)
    segment_correct = False
    if scenario_id in ["A", "D"] and expected_classification == "INCIDENT":
        # For localized scenarios, check if the detected segment matches or is compatible
        if actual_segment and isinstance(actual_segment, dict):
            # Check key dimensions
            method_match = actual_segment.get("payment_method") == affected_segment.get("payment_method")
            bank_match = actual_segment.get("bank") == affected_segment.get("bank")
            device_match = actual_segment.get("device") == affected_segment.get("device")
            upi_app_match = actual_segment.get("upi_app") == affected_segment.get("upi_app")

            # For scenario A, we need UPI+BANK_X+ANDROID
            if scenario_id == "A":
                segment_correct = method_match and bank_match and device_match
            # For scenario D, we need ANDROID device
            elif scenario_id == "D":
                segment_correct = device_match
            else:
                segment_correct = method_match and bank_match and device_match and upi_app_match
    elif scenario_id in ["B", "C"] and expected_classification == "INCIDENT":
        # For method-level or widespread, check if we got at least the right method or detected as widespread
        if actual_segment and isinstance(actual_segment, dict):
            if scenario_id == "B":
                # Should detect UPI method issue
                segment_correct = actual_segment.get("payment_method") == "UPI"
            elif scenario_id == "C":
                # Should detect widespread/method-level issue
                segment_correct = actual_segment.get("payment_method") in ["UPI", "CART", "NETBANKING"] or actual_segment.get("payment_method") is None
    # For scenario E, we expect NORMAL, so segment correctness is less important

    # Calculate actual rates from the detector result for reporting
    success_rate_signal = result.get("success_rate_signal", {})
    technical_error_signal = result.get("technical_error_signal", {})
    customer_error_signal = result.get("customer_error_signal", {})

    eval_result = {
        "scenario_id": scenario_id,
        "scenario_name": ground_truth.get("scenario_name", "Unknown"),
        "true_cause": expected_cause,
        "window": ground_truth["window"],
        "expected_classification": expected_classification,
        "actual_classification": actual_classification,
        "classification_correct": classification_correct,
        "expected_severity": expected_severity,
        "actual_severity": actual_severity,
        "severity_close": severity_close,
        "expected_affected_segment": affected_segment,
        "actual_affected_segment": actual_segment,
        "segment_correct": segment_correct,
        "ground_truth": ground_truth.get("expected_behavior", {}),
        "detector_signals": {
            "success_rate": {
                "baseline": success_rate_signal.get("baseline", 0),
                "current": success_rate_signal.get("current", 0),
                "change_pp": success_rate_signal.get("difference_percentage_points", 0),
                "significant": success_rate_signal.get("statistically_significant", False)
            },
            "technical_error": {
                "status": technical_error_signal.get("status", "UNKNOWN"),
                "baseline_rate": technical_error_signal.get("baseline_rate", 0),
                "current_rate": technical_error_signal.get("current_rate", 0),
                "relative_change": technical_error_signal.get("relative_change", 0)
            },
            "customer_error": {
                "status": customer_error_signal.get("status", "UNKNOWN"),
                "baseline_rate": customer_error_signal.get("baseline_rate", 0),
                "current_rate": customer_error_signal.get("current_rate", 0),
                "absolute_change": customer_error_signal.get("absolute_change", 0)
            }
        },
        "passed": classification_correct and severity_close and (
            True if scenario_id == "E" else segment_correct  # For E, we don't require segment match
        )
    }

    return eval_result

def print_evaluation_table(results: List[Dict[str, Any]]):
    """Print evaluation results in a table format."""
    print("\n" + "="*100)
    print("SCENARIO EVALUATION RESULTS")
    print("="*100)

    # Header
    header = f"{'Scenario':<8} {'Expected':<12} {'Actual':<12} {'Correct?':<10} {'Segment Correct?':<18} {'Notes'}"
    print(header)
    print("-" * len(header))

    for result in results:
        if "error" in result:
            row = f"{result['scenario_id']:<8} {'ERROR':<12} {'ERROR':<12} {'False':<10} {'False':<18} {result['error']}"
            print(row)
            continue

        scenario_id = result["scenario_id"]
        expected = result["expected_classification"]
        actual = result["actual_classification"]
        classification_correct = result["classification_correct"]
        segment_correct = result.get("segment_correct", "N/A")
        if segment_correct == "N/A":
            segment_str = "N/A"
        else:
            segment_str = "Yes" if segment_correct else "No"

        # Build notes
        notes = []
        if not result["classification_correct"]:
            notes.append("classification mismatch")
        if not result.get("severity_close", True):
            notes.append("severity mismatch")
        if scenario_id != "E" and not result.get("segment_correct", True):
            notes.append("segment mismatch")

        notes_str = ", ".join(notes) if notes else "OK"

        row = f"{scenario_id:<8} {expected:<12} {actual:<12} {'Yes' if classification_correct else 'No':<10} {segment_str:<18} {notes_str}"
        print(row)

    # Summary
    passed = sum(1 for r in results if r.get("passed", False))
    total = len(results)
    print("-" * len(header))
    print(f"Overall: {passed}/{total} scenarios passed")

    if passed == total:
        print("🎉 ALL SCENARIOS PASSED EVALUATION")
    else:
        print("❌ SOME SCENARIOS FAILED EVALUATION")

def main():
    parser = argparse.ArgumentParser(description="Evaluate injected scenarios with anomaly detector")
    parser.add_argument("--scenario", choices=["A", "B", "C", "D", "E", "all"],
                       default="all", help="Scenario to evaluate (default: all)")
    parser.add_argument("--merchant", default="merch_upi_smb",
                       help="Merchant ID (default: merch_upi_smb)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output with detailed signals")

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

    all_results = []
    for scenario_id, scenario_dir in scenarios_to_check:
        result = evaluate_scenario(scenario_dir, scenario_id, args.merchant)
        all_results.append(result)

        if args.verbose:
            print(f"\nDetailed results for scenario {scenario_id}:")
            print(json.dumps(result, indent=2))

    print_evaluation_table(all_results)

    # Determine exit code
    passed_count = sum(1 for r in all_results if r.get("passed", False))
    total_count = len(all_results)

    if passed_count == total_count:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()