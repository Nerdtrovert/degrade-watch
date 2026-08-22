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

    result = detector.detect(
        merchant_id=merchant_id,
        window_start=window_start,
        window_end=window_end,
        generated_data_dir=data_dir
    )
    print("=== DETECTOR RESULT ===")
    print(f"Classification: {result['classification']}")
    print(f"Severity: {result['severity']}")
    print(f"Candidate segment: {result.get('candidate_segment', {})}")
    print(f"Evidence: {result.get('evidence', [])}")
    print(f"Success rate signal: {result.get('success_rate_signal', {})}")
    print(f"Technical error signal: {result.get('technical_error_signal', result.get('technical_error_signal', {}))}")
    print(f"Customer error signal: {result.get('customer_error_signal', {})}")
    print(f"Localization signal: {result.get('localization_signal', {})}")
    print(f"Volume signal: {result.get('volume_signal', {})}")
    print(f"Latency signal: {result.get('latency_signal', {})}")

    # Now let's manually compute what the detector should see.
    # Load baseline
    baseline_dir = data_dir / "baselines"
    baseline_path = baseline_dir / f"{merchant_id}.json"
    with open(baseline_path, 'r') as f:
        baseline = json.load(f)

    # Load current window payments
    payments_file = data_dir / f"{merchant_id}.jsonl"
    current_payments = detector._load_window_payments(payments_file, window_start, window_end)
    print(f"\nLoaded {len(current_payments)} payments in window")

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
    print(f"\nCurrent stats overall: {current_stats}")

    # Let's compute the signals for the overall segment
    key = "OVERALL"
    key_current = current_stats
    key_baseline = baseline["overall"]
    wrapped_baseline = {"overall": key_baseline}
    suc_signal = detector._calculate_success_rate_signal(wrapped_baseline, key_current)
    tech_signal = detector._calculate_technical_error_signal(wrapped_baseline, key_current)
    cust_signal = detector._calculate_customer_error_signal(wrapped_baseline, key_current)
    vol_signal = detector._calculate_volume_signal(wrapped_baseline, key_current, window_start, window_end)
    lat_signal = detector._calculate_latency_signal(wrapped_baseline, key_current)
    print(f"\n--- Overall segment signals ---")
    print(f"Success rate signal: {suc_signal}")
    print(f"Technical error signal: {tech_signal}")
    print(f"Customer error signal: {cust_signal}")
    print(f"Volume signal: {vol_signal}")
    print(f"Latency signal: {lat_signal}")

    # Check if this segment is degraded
    success_rate_declining = suc_signal["difference"] < 0
    success_drop_pp = abs(suc_signal["difference_percentage_points"])
    statistically_significant = suc_signal["statistically_significant"]
    concerning_threshold_pp = detector.config.min_success_rate_drop_concerning * 100 if detector.config.min_success_rate_drop_concerning < 1.0 else detector.config.min_success_rate_drop_concerning
    is_degraded = success_rate_declining and statistically_significant and success_drop_pp >= concerning_threshold_pp
    print(f"\n--- Degradation check for overall ---")
    print(f"Success rate declining: {success_rate_declining}")
    print(f"Success drop pp: {success_drop_pp}")
    print(f"Statistically significant: {statistically_significant}")
    print(f"Concerning threshold pp: {concerning_threshold_pp}")
    print(f"Is degraded: {is_degraded}")

    # Check for technical/latency/volume drop evidence
    tech_status = tech_signal["status"]
    lat_status = lat_signal["status"]
    vol_status = vol_signal["status"]
    has_tech_evidence = tech_status in ["WARNING", "CRITICAL", "CONCERNING"]
    has_lat_evidence = lat_status in ["WARNING", "CRITICAL", "CONCERNING"]
    has_vol_evidence = vol_status in ["SIGNIFICANT_DECREASE", "NOTABLE_DECREASE"]
    print(f"Has tech evidence: {has_tech_evidence} (status: {tech_status})")
    print(f"Has lat evidence: {has_lat_evidence} (status: {lat_status})")
    print(f"Has vol evidence: {has_vol_evidence} (status: {vol_status})")

    # Scenario E check: is it primarily customer-caused?
    cust_change = cust_signal["absolute_change"]
    tech_change = tech_signal["absolute_change"]
    is_customer_caused = cust_change > 0.01 and (cust_change >= 2.0 * tech_change or tech_status in ["NORMAL", "ELEVATED"])
    print(f"Is customer caused: {is_customer_caused} (cust_change: {cust_change}, tech_change: {tech_change})")

    # Now let's check the affected segment from ground truth: UPI|BANK_X|ANDROID
    segment_key = "UPI|BANK_X|ANDROID"
    if segment_key in current_stats["segments"]:
        key_current = current_stats["segments"][segment_key]
        key_baseline = baseline["segments"].get(segment_key, {"success_rate": 0, "failures": 0, "attempts": 0, "technical_error_rate": 0, "customer_error_rate": 0, "latency_p95_ms": 0})
        wrapped_baseline = {"overall": key_baseline}
        suc_signal = detector._calculate_success_rate_signal(wrapped_baseline, key_current)
        tech_signal = detector._calculate_technical_error_signal(wrapped_baseline, key_current)
        cust_signal = detector._calculate_customer_error_signal(wrapped_baseline, key_current)
        vol_signal = detector._calculate_volume_signal(wrapped_baseline, key_current, window_start, window_end)
        lat_signal = detector._calculate_latency_signal(wrapped_baseline, key_current)
        print(f"\n--- Segment {segment_key} signals ---")
        print(f"Success rate signal: {suc_signal}")
        print(f"Technical error signal: {tech_signal}")
        print(f"Customer error signal: {cust_signal}")
        print(f"Volume signal: {vol_signal}")
        print(f"Latency signal: {lat_signal}")
        success_rate_declining = suc_signal["difference"] < 0
        success_drop_pp = abs(suc_signal["difference_percentage_points"])
        statistically_significant = suc_signal["statistically_significant"]
        is_degraded = success_rate_declining and statistically_significant and success_drop_pp >= concerning_threshold_pp
        print(f"Success rate declining: {success_rate_declining}")
        print(f"Success drop pp: {success_drop_pp}")
        print(f"Statistically significant: {statistically_significant}")
        print(f"Is degraded: {is_degraded}")
        tech_status = tech_signal["status"]
        lat_status = lat_signal["status"]
        vol_status = vol_signal["status"]
        has_tech_evidence = tech_status in ["WARNING", "CRITICAL", "CONCERNING"]
        has_lat_evidence = lat_status in ["WARNING", "CRITICAL", "CONCERNING"]
        has_vol_evidence = vol_status in ["SIGNIFICANT_DECREASE", "NOTABLE_DECREASE"]
        print(f"Has tech evidence: {has_tech_evidence} (status: {tech_status})")
        print(f"Has lat evidence: {has_lat_evidence} (status: {lat_status})")
        print(f"Has vol evidence: {has_vol_evidence} (status: {vol_status})")
        cust_change = cust_signal["absolute_change"]
        tech_change = tech_signal["absolute_change"]
        is_customer_caused = cust_change > 0.01 and (cust_change >= 2.0 * tech_change or tech_status in ["NORMAL", "ELEVATED"])
        print(f"Is customer caused: {is_customer_caused} (cust_change: {cust_change}, tech_change: {tech_change})")
    else:
        print(f"\nSegment {segment_key} not found in current stats segments.")

if __name__ == "__main__":
    main()
