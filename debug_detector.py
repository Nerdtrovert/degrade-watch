#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "backend"))

from scripts.detect_anomalies import AnomalyDetector
from scripts.analyze_baselines import load_merchant_profile, load_merchant_profile, parse_timestamp, categorize_failure, calculate_statistics, calculate_percentiles

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
    print(f"Loaded {len(current_payments)} payments in window")

    # Load merchant profile
    profile = load_merchant_profile(merchant_id)

    # Ensure baseline has failure_breakdown in overall section (backward compatibility)
    if "failure_breakdown" not in baseline["overall"]:
        # Calculate overall failure breakdown by summing up the by_method breakdowns
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

    # Ensure baseline has failure_breakdown in overall section (backward compatibility)
    if "failure_breakdown" not in baseline["overall"]:
        # Calculate overall failure breakdown from by_method data
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

            # Normalize if needed
            if total_weighted > 0:
                baseline["overall"]["failure_breakdown"] = {
                    "customer_caused": weighted_breakdown["customer_caused"] / total_weighted,
                    "technical": weighted_breakdown["technical"] / total_weighted,
                    "other": weighted_breakdown["other"] / total_weighted
                }
            else:
                # Fallback: distribute proportionally
                baseline["overall"]["failure_breakdown"] = {
                    "customer_caused": baseline["overall"]["failures"] * 0.8,  # Approximately 80% customer caused
                    "technical": baseline["overall"]["failures"] * 0.15,      # Approximately 15% technical
                    "other": baseline["overall"]["failures"] * 0.05          # Approximately 5% other
                }
        else:
            baseline["overall"]["failure_breakdown"] = {"customer_caused": 0, "technical": 0, "other": 0}

    # Analyze current window
    current_stats = detector._analyze_payment_window(current_payments, profile)

    print("\n=== BASELINE OVERALL ===")
    print(json.dumps(baseline["overall"], indent=2))

    print("\n=== CURRENT STATS OVERALL ===")
    print(json.dumps(current_stats["overall"], indent=2))

    # Get all keys to evaluate.
    keys_to_evaluate = ["OVERALL"] + list(current_stats["by_method"].keys()) + list(current_stats["segments"].keys())
    print(f"\nKeys to evaluate: {keys_to_evaluate}")

    active_segments = {}
    anomalies = set()
    customer_caused_anomalies = set()
    segment_signals = {}

    for key in keys_to_evaluate:
        # Get current stats for this key
        if key == "OVERALL":
            key_current = current_stats
        elif key in current_stats["by_method"]:
            key_current = current_stats["by_method"][key]
        else:
            key_current = current_stats["segments"][key]

        # Skip if volume is below min_attempts_limited
        if key_current["attempts"] < detector.config.min_attempts_limited:
            print(f"Skipping key {key} because attempts {key_current['attempts']} < {detector.config.min_attempts_limited}")
            continue

        # Get baseline for this key
        if key == "OVERALL":
            key_baseline = baseline["overall"]
        elif key in baseline["by_method"]:
            key_baseline = baseline["by_method"][key]
        else:
            key_baseline = baseline["segments"].get(key, {"success_rate": 0, "failures": 0, "attempts": 0, "technical_error_rate": 0, "customer_error_rate": 0, "latency_p95_ms": 0})

        # Wrap baseline with default values if needed
        wrapped_baseline = {
            "success_rate": key_baseline.get("success_rate", 0),
            "failures": key_baseline.get("failures", 0),
            "attempts": key_baseline.get("attempts", 0),
            "technical_error_rate": key_baseline.get("technical_error_rate", 0),
            "customer_error_rate": key_baseline.get("customer_error_rate", 0),
            "latency_p95_ms": key_baseline.get("latency_p95_ms", 0),
        }

        # Calculate signals
        suc_signal = detector._calculate_success_rate_signal(wrapped_baseline, key_current)
        tech_signal = detector._calculate_technical_error_signal(wrapped_baseline, key_current)
        cust_signal = detector._calculate_customer_error_signal(wrapped_baseline, key_current)
        vol_signal = detector._calculate_volume_signal(wrapped_baseline, key_current, window_start, window_end)
        lat_signal = detector._calculate_latency_signal(wrapped_baseline, key_current)

        print(f"\n--- Key: {key} ---")
        print(f"  Baseline: {wrapped_baseline}")
        print(f"  Current: {key_current}")
        print(f"  Success rate signal: {suc_signal}")
        print(f"  Technical error signal: {tech_signal}")
        print(f"  Customer error signal: {cust_signal}")
        print(f"  Volume signal: {vol_signal}")
        print(f"  Latency signal: {lat_signal}")

        # Check if this segment is degraded
        success_rate_declining = suc_signal["difference"] < 0
        success_drop_pp = abs(suc_signal["difference_percentage_points"])
        statistically_significant = suc_signal["statistically_significant"]

        concerning_threshold_pp = detector.config.min_success_rate_drop_concerning * 100 if detector.config.min_success_rate_drop_concerning < 1.0 else detector.config.min_success_rate_drop_concerning
        is_degraded = success_rate_declining and statistically_significant and success_drop_pp >= concerning_threshold_pp

        # Check for technical/latency/volume drop evidence
        tech_status = tech_signal["status"]
        lat_status = lat_signal["status"]
        vol_status = vol_signal["status"]

        has_tech_evidence = tech_status in ["WARNING", "CRITICAL", "CONCERNING"]
        has_lat_evidence = lat_status in ["WARNING", "CRITICAL", "CONCERNING"]
        has_vol_evidence = vol_status in ["SIGNIFICANT_DECREASE", "NOTABLE_DECREASE"]

        # Scenario E check: is it primarily customer-caused?
        cust_change = cust_signal["absolute_change"]
        tech_change = tech_signal["absolute_change"]
        is_customer_caused = cust_change > 0.01 and (cust_change >= 2.0 * tech_change or tech_status in ["NORMAL", "ELEVATED"])

        print(f"  Success rate declining: {success_rate_declining}")
        print(f"  Success drop pp: {success_drop_pp}")
        print(f"  Statistically significant: {statistically_significant}")
        print(f"  Concerning threshold pp: {concerning_threshold_pp}")
        print(f"  Is degraded: {is_degraded}")
        print(f"  Has tech evidence: {has_tech_evidence}")
        print(f"  Has lat evidence: {has_lat_evidence}")
        print(f"  Has vol evidence: {has_vol_evidence}")
        print(f"  Tech status: {tech_status}")
        print(f"  Lat status: {lat_status}")
        print(f"  Vol status: {vol_status}")
        print(f"  Cust change: {cust_change}")
        print(f"  Tech change: {tech_change}")
        print(f"  Is customer caused: {is_customer_caused}")

        if is_degraded:
            if is_customer_caused:
                customer_caused_anomalies.add(key)
                print(f"  -> Added to customer_caused_anomalies")
            elif has_tech_evidence or has_lat_evidence or has_vol_evidence:
                anomalies.add(key)
                print(f"  -> Added to anomalies")
            else:
                print(f"  -> Degraded but not added to any set (no evidence?)")
        else:
            print(f"  -> Not degraded")

        # Store signals for later
        segment_signals[key] = {
            "success_rate_signal": suc_signal,
            "technical_error_signal": tech_signal,
            "customer_error_signal": cust_signal,
            "volume_signal": vol_signal,
            "latency_signal": lat_signal,
        }
        active_segments[key] = key_current

    print(f"\nAnomalies (technical): {anomalies}")
    print(f"Customer caused anomalies: {customer_caused_anomalies}")

    if anomalies:
        pruned_anomalies = detector._prune_anomalies(anomalies, active_segments)
        if not pruned_anomalies:
            pruned_anomalies = anomalies
        candidate_key = max(
            pruned_anomalies,
            key=lambda k: (
                1 if active_segments[k]["attempts"] >= detector.config.min_attempts_sufficient else 0,
                abs(segment_signals[k]["success_rate_signal"]["difference_percentage_points"])
            )
        )
        print(f"Candidate key: {candidate_key}")
        cand_signals = segment_signals[candidate_key]
        cand_current = active_segments[candidate_key]
        cand_suc = cand_signals["success_rate_signal"]
        cand_tech = cand_signals["technical_error_signal"]
        cand_cust = cand_signals["customer_error_signal"]
        cand_vol = cand_signals["volume_signal"]
        cand_lat = cand_signals["latency_signal"]

        # Determine sufficiency for candidate key
        sufficiency = detector._assess_sample_sufficiency(cand_current["attempts"])
        if sufficiency == "SUFFICIENT":
            classification = "INCIDENT"
        else:
            classification = "SUSPICIOUS"

        print(f"Sufficiency: {sufficiency}")
        print(f"Classification would be: {classification}")

        # Determine severity based on success drop pp
        drop_pp = abs(cand_suc["difference_percentage_points"])
        critical_threshold_pp = detector.config.min_success_rate_drop_critical * 100 if detector.config.min_success_rate_drop_critical < 1.0 else detector.config.min_success_rate_drop_critical
        warning_threshold_pp = detector.config.min_success_rate_drop_warning * 100 if detector.config.min_success_rate_drop_warning < 1.0 else detector.config.min_success_rate_drop_warning

        if drop_pp >= critical_threshold_pp:
            severity = "HIGH"
        elif drop_pp >= warning_threshold_pp:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        print(f"Drop pp: {drop_pp}")
        print(f"Critical threshold pp: {critical_threshold_pp}")
        print(f"Warning threshold pp: {warning_threshold_pp}")
        print(f"Severity would be: {severity}")

        # Populate evidence
        segment_name = f"Segment {candidate_key}" if candidate_key != "OVERALL" else "Overall merchant"
        evidence = []
        evidence.append(
            f"{segment_name} success rate dropped {drop_pp:.1f} percentage points "
            f"(baseline: {cand_suc['baseline_stats']['success_rate']:.3f}, current: {cand_current['success_rate']:.3f})"
        )
        if cand_suc["statistically_significant"]:
            evidence.append(f"Success rate drop in {candidate_key} is statistically significant")
        else:
            evidence.append(f"Success rate drop in {candidate_key} is not statistically significant")

        if cand_tech["status"] != "NORMAL":
            evidence.append(f"Technical error rate status is {cand_tech['status']} (baseline: {cand_tech['baseline_rate']:.3f}, current: {cand_tech['current_rate']:.3f})")
        if cand_lat["status"] != "NORMAL":
            evidence.append(f"P95 latency status is {cand_lat['status']} (baseline: {cand_lat['baseline_p95_ms']:.1f}ms, current: {cand_lat['current_p95_ms']:.1f}ms)")
        if cand_vol["status"] != "NORMAL":
            evidence.append(f"Volume status is {cand_vol['status']} (baseline: {cand_vol['baseline']:.3f}, current: {cand_vol['current']:.3f})")
        print(f"Evidence would be: {evidence}")
    else:
        print("No technical anomalies found, so classification will be NORMAL")
        classification = "NORMAL"
        severity = "LOW"

    print(f"\n=== FINAL RESULT ===")
    print(f"Classification: {classification}")
    print(f"Severity: {severity}")

if __name__ == "__main__":
    main()