#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "backend"))

from scripts.detect_anomalies import AnomalyDetector
from scripts.analyze_baselines import load_merchant_profile

def main():
    detector = AnomalyDetector()
    merchant_id = "merch_upi_smb"
    window_start = datetime.fromisoformat("2026-08-10T17:53:16.504000+00:00")
    window_end = datetime.fromisoformat("2026-08-10T19:23:16.504000+00:00")
    data_dir = Path("/Users/prajwalnavadagp/Engineering/Projects/degrade-watch/data/generated")

    # Load baseline
    baseline_dir = data_dir / "baselines"
    baseline_path = baseline_dir / f"{merchant_id}.json"
    with open(baseline_path, 'r') as f:
        baseline = json.load(f)

    # Load current window payments
    payments_file = data_dir / f"{merchant_id}.jsonl"
    current_payments = detector._load_window_payments(payments_file, window_start, window_end)

    # Load merchant profile
    profile = load_merchant_profile(merchant_id)

    # Ensure baseline has failure_breakdown in overall section (backward compatibility)
    if "failure_breakdown" not in baseline["overall"]:
        baseline["overall"]["failure_breakdown"] = {
            "customer_caused": sum(
                method_data.get("failure_breakdown", {}).get("customer_caused", 0)
                for method_data in baseline["by_method"].values()
            ),
            "technical": sum(
                method_data.get("failure_breakdown", {}).get("technical", 0)
                for method_data in baseline["by_method"].values()
            ),
            "other": sum(
                method_data.get("failure_breakdown", {}).get("other", 0)
                for method_data in baseline["by_method"].values()
            )
        }

    if "failure_breakdown" not in baseline["overall"]:
        baseline_failures = baseline["overall"]["failures"]
        if baseline_failures > 0:
            weighted_breakdown = {"customer_caused": 0, "technical": 0, "other": 0}
            total_weighted = 0
            for method, method_data in baseline["by_method"].items():
                method_failures = method_data["failures"]
                if method_failures > 0:
                    weight = method_failures / baseline_failures
                    weighted_breakdown["customer_caused"] += method_data["failure_breakdown"]["customer_caused"] * weight
                    weighted_breakdown["technical"] += method_data["failure_breakdown"]["technical"] * weight
                    weighted_breakdown["other"] += method_data["failure_breakdown"]["other"] * weight
                    total_weighted += weight

            if total_weighted > 0:
                baseline["overall"]["failure_breakdown"] = {
                    "customer_caused": weighted_breakdown["customer_caused"] / total_weighted,
                    "technical": weighted_breakdown["technical"] / total_weighted,
                    "other": weighted_breakdown["other"] / total_weighted
                }
            else:
                baseline["overall"]["failure_breakdown"] = {
                    "customer_caused": baseline["overall"]["failures"] * 0.8,
                    "technical": baseline["overall"]["failures"] * 0.15,
                    "other": baseline["overall"]["failures"] * 0.05
                }
        else:
            baseline["overall"]["failure_breakdown"] = {"customer_caused": 0, "technical": 0, "other": 0}

    # Analyze current window
    current_stats = detector._analyze_payment_window(current_payments, profile)

    # Helper to print signals for a key
    def print_signals(key, key_current, key_baseline):
        wrapped_baseline = {
            "success_rate": key_baseline.get("success_rate", 0),
            "failures": key_baseline.get("failures", 0),
            "attempts": key_baseline.get("attempts", 0),
            "technical_error_rate": key_baseline.get("technical_error_rate", 0),
            "customer_error_rate": key_baseline.get("customer_error_rate", 0),
            "latency_p95_ms": key_baseline.get("latency_p95_ms", 0),
        }
        suc_signal = detector._calculate_success_rate_signal(wrapped_baseline, key_current)
        tech_signal = detector._calculate_technical_error_signal(wrapped_baseline, key_current)
        cust_signal = detector._calculate_customer_error_signal(wrapped_baseline, key_current)
        vol_signal = detector._calculate_volume_signal(wrapped_baseline, key_current, window_start, window_end)
        lat_signal = detector._calculate_latency_signal(wrapped_baseline, key_current)

        print(f"\n{key}:")
        print(f"  Baseline success rate: {wrapped_baseline['success_rate']:.4f}")
        print(f"  Current success rate: {key_current['success_rate']:.4f}")
        print(f"  Success rate change: {suc_signal['difference']:.4f} ({suc_signal['difference_percentage_points']:.2f} pp)")
        print(f"  Success rate relative change: {suc_signal['relative_change']:.4f}")
        print(f"  Success rate statistically significant: {suc_signal['statistically_significant']}")
        print(f"  Baseline technical error rate: {wrapped_baseline['technical_error_rate']:.4f}")
        print(f"  Current technical error rate: {key_current['technical_error_rate']:.4f}")
        print(f"  Technical error change: {tech_signal['absolute_change']:.4f}")
        print(f"  Technical error relative change: {tech_signal['relative_change']:.4f}")
        print(f"  Technical error status: {tech_signal['status']}")
        print(f"  Baseline customer error rate: {wrapped_baseline['customer_error_rate']:.4f}")
        print(f"  Current customer error rate: {key_current['customer_error_rate']:.4f}")
        print(f"  Customer error change: {cust_signal['absolute_change']:.4f}")
        print(f"  Customer error relative change: {cust_signal['relative_change']:.4f}")
        print(f"  Customer error status: {cust_signal['status']}")
        print(f"  Volume status: {vol_signal['status']}")
        print(f"  Latency status: {lat_signal['status']}")

        # Scenario E check
        cust_change = cust_signal["absolute_change"]
        tech_change = tech_signal["absolute_change"]
        is_customer_caused = cust_change > 0.01 and (cust_change >= 2.0 * tech_change or tech_signal["status"] in ["NORMAL", "ELEVATED"])
        print(f"  Customer change: {cust_change:.4f}")
        print(f"  Tech change: {tech_change:.4f}")
        print(f"  Is customer caused (per detector logic): {is_customer_caused}")

    # Overall
    print("\n=== OVERALL ===")
    print_signals("OVERALL", current_stats, baseline["overall"])

    # Affected segment from ground truth: UPI|BANK_X|ANDROID
    segment_key = "UPI|BANK_X|ANDROID"
    if segment_key in current_stats["segments"]:
        print(f"\n=== SEGMENT: {segment_key} ===")
        print_signals(segment_key, current_stats["segments"][segment_key], baseline["segments"].get(segment_key, {}))
    else:
        print(f"\nSegment {segment_key} not found in current stats segments.")

    # Also check the candidate segment from detector output
    # We'll run the detect method to get the candidate segment
    result = detector.detect(
        merchant_id=merchant_id,
        window_start=window_start,
        window_end=window_end,
        generated_data_dir=data_dir
    )
    print(f"\n=== DETECTOR RESULT ===")
    print(f"Classification: {result['classification']}")
    print(f"Severity: {result['severity']}")
    print(f"Candidate segment: {result.get('candidate_segment', {})}")
    print(f"Evidence: {result.get('evidence', [])}")

if __name__ == "__main__":
    main()