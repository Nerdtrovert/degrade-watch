#!/usr/bin/env python3
"""
Baseline analysis module for DegradeWatch.

Generates structured baseline representations from healthy payment data.
"""

import json
import jsonlines
import statistics
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

def load_merchant_profile(merchant_id: str) -> Dict[str, Any]:
    """Load a merchant profile from JSON file."""
    profile_path = Path(__file__).parent.parent / "data" / "profiles" / f"{merchant_id}.json"
    with open(profile_path, 'r') as f:
        return json.load(f)

def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO-8601 timestamp string to datetime object."""
    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

def categorize_failure(error_code: Optional[str]) -> str:
    """Categorize failure type based on error code."""
    if error_code is None:
        return "none"  # Should not happen for failed payments

    customer_caused = ["INSUFFICIENT_FUNDS", "WRONG_PIN", "OTP_FAILED", "USER_CANCELLED"]
    technical = ["BANK_TECHNICAL_ERROR", "UPI_TIMEOUT", "GATEWAY_ERROR", "NETWORK_ERROR"]

    if error_code in customer_caused:
        return "customer_caused"
    elif error_code in technical:
        return "technical"
    else:
        return "other"

def calculate_statistics(values: List[float]) -> Dict[str, Any]:
    """Calculate basic statistics for a list of values."""
    if not values:
        return {
            "mean": None,
            "median": None,
            "stddev": 0.0,
            "min": None,
            "max": None,
            "count": 0
        }

    return {
        "mean": statistics.mean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "stddev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "count": len(values)
    }

def calculate_percentiles(values: List[float], percentiles: List[int]) -> Dict[str, float]:
    """Calculate specified percentiles for a list of values."""
    if not values:
        return {f"p{p}": None for p in percentiles}

    sorted_values = sorted(values)
    result = {}
    for p in percentiles:
        if p == 50:
            result[f"p{p}"] = statistics.median(sorted_values)
        else:
            index = (p / 100) * (len(sorted_values) - 1)
            if index.is_integer():
                result[f"p{p}"] = sorted_values[int(index)]
            else:
                lower = sorted_values[int(index)]
                upper = sorted_values[int(index) + 1]
                result[f"p{p}"] = lower + (upper - lower) * (index - int(index))
        # Round to handle floating point precision issues
        if result[f"p{p}"] is not None:
            result[f"p{p}"] = round(result[f"p{p}"], 10)

    return result

def generate_baseline_for_merchant(merchant_id: str, payments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate baseline for a single merchant."""
    if not payments:
        return {}

    # Sort payments by timestamp
    payments_sorted = sorted(payments, key=lambda p: parse_timestamp(p["timestamp"]))

    # Extract date range
    start_date = parse_timestamp(payments_sorted[0]["timestamp"]).date()
    end_date = parse_timestamp(payments_sorted[-1]["timestamp"]).date()
    days = (end_date - start_date).days + 1

    # Initialize baseline structure
    baseline = {
        "merchant_id": merchant_id,
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days
        },
        "overall": {},
        "by_method": {},
        "segments": {},
        "hourly": {},
        "sufficiency_rules": {
            "SUFFICIENT": {"min_attempts": 100, "min_windows": 5},
            "LIMITED": {"min_attempts": 30, "min_windows": 3},
            "INSUFFICIENT": {"min_attempts": 0, "min_windows": 0}
        }
    }

    # Overall statistics
    total_attempts = len(payments)
    successes = sum(1 for p in payments if p["status"] == "success")
    failures = total_attempts - successes

    baseline["overall"] = {
        "attempts": total_attempts,
        "successes": successes,
        "failures": failures,
        "success_rate": successes / total_attempts if total_attempts > 0 else 0,
        "failure_rate": failures / total_attempts if total_attempts > 0 else 0,
        "average_amount": statistics.mean([p["amount"] for p in payments]) / 100 if payments else 0,  # Convert to rupees
        "median_amount": statistics.median([p["amount"] for p in payments]) / 100 if payments else 0,
        "average_latency_ms": statistics.mean([p["latency_ms"] for p in payments]) if payments else 0,
        "p95_latency_ms": calculate_percentiles([p["latency_ms"] for p in payments], [95])["p95"] if payments else 0
    }

    # Group by payment method
    method_groups = defaultdict(list)
    for payment in payments:
        method_groups[payment["payment_method"]].append(payment)

    for method, method_payments in method_groups.items():
        method_attempts = len(method_payments)
        method_successes = sum(1 for p in method_payments if p["status"] == "success")

        baseline["by_method"][method] = {
            "attempts": method_attempts,
            "successes": method_successes,
            "failures": method_attempts - method_successes,
            "success_rate": method_successes / method_attempts if method_attempts > 0 else 0,
            "failure_rate": (method_attempts - method_successes) / method_attempts if method_attempts > 0 else 0,
            "average_amount": statistics.mean([p["amount"] for p in method_payments]) / 100 if method_payments else 0,
            "median_amount": statistics.median([p["amount"] for p in method_payments]) / 100 if method_payments else 0,
            "average_latency_ms": statistics.mean([p["latency_ms"] for p in method_payments]) if method_payments else 0,
            "p95_latency_ms": calculate_percentiles([p["latency_ms"] for p in method_payments], [95])["p95"] if method_payments else 0,
            "failure_breakdown": {
                "customer_caused": sum(1 for p in method_payments if p["status"] == "failed" and categorize_failure(p.get("error_code")) == "customer_caused"),
                "technical": sum(1 for p in method_payments if p["status"] == "failed" and categorize_failure(p.get("error_code")) == "technical"),
                "other": sum(1 for p in method_payments if p["status"] == "failed" and categorize_failure(p.get("error_code")) == "other")
            }
        }

    # Create segment keys for UPI payments (method+bank+device+upi_app)
    # For CARD and NETBANKING, bank and upi_app should be None
    segment_groups = defaultdict(list)

    for payment in payments:
        method = payment["payment_method"]
        bank = payment.get("bank")
        device = payment.get("device")
        upi_app = payment.get("upi_app")

        # For CARD and NETBANKING, bank should be None - don't create segments based on bank
        if method in ["CARD", "NETBANKING"]:
            # For these methods, segment is method+device (bank and upi_app are not meaningful)
            segment_key = f"{method}|{device}"
        else:  # UPI
            # For UPI, create segment based on method+bank+device+upi_app
            segment_key = f"{method}|{bank}|{device}|{upi_app}"

        segment_groups[segment_key].append(payment)

    # Process segments
    for segment_key, segment_payments in segment_groups.items():
        segment_attempts = len(segment_payments)
        if segment_attempts == 0:
            continue

        segment_successes = sum(1 for p in segment_payments if p["status"] == "success")

        # Calculate failure breakdown
        failure_breakdown = {"customer_caused": 0, "technical": 0, "other": 0}
        error_code_dist = Counter()

        for payment in segment_payments:
            if payment["status"] == "failed":
                failure_type = categorize_failure(payment.get("error_code"))
                failure_breakdown[failure_type] += 1
                if payment.get("error_code"):
                    error_code_dist[payment["error_code"]] += 1

        # Calculate success rate variability by hour (for time-aware baseline)
        hourly_success_rates = []
        hourly_attempts = []
        hourly_latencies = []
        hourly_data = defaultdict(lambda: {"attempts": 0, "successes": 0, "latencies": []})

        for payment in segment_payments:
            dt = parse_timestamp(payment["timestamp"])
            hour = dt.hour
            hourly_data[hour]["attempts"] += 1
            if payment["status"] == "success":
                hourly_data[hour]["successes"] += 1
            hourly_data[hour]["latencies"].append(payment["latency_ms"])

        # Calculate hourly statistics
        hourly_stats = {}
        success_rates_for_stddev = []
        attempt_counts = []

        for hour in range(24):
            if hour in hourly_data and hourly_data[hour]["attempts"] > 0:
                hour_attempts = hourly_data[hour]["attempts"]
                hour_successes = hourly_data[hour]["successes"]
                hour_success_rate = hour_successes / hour_attempts if hour_attempts > 0 else 0
                hour_avg_latency = statistics.mean(hourly_data[hour]["latencies"]) if hourly_data[hour]["latencies"] else 0

                hourly_stats[str(hour)] = {
                    "attempts": hour_attempts,
                    "successes": hour_successes,
                    "success_rate": hour_success_rate,
                    "average_latency_ms": hour_avg_latency
                }

                success_rates_for_stddev.append(hour_success_rate)
                attempt_counts.append(hour_attempts)

        # Calculate success rate variability
        success_rate_stats = calculate_statistics(success_rates_for_stddev) if success_rates_for_stddev else {"mean": 0, "stddev": 0, "min": 0, "max": 0}

        # Calculate latency statistics
        latency_stats = calculate_statistics([p["latency_ms"] for p in segment_payments])
        latency_percentiles = calculate_percentiles([p["latency_ms"] for p in segment_payments], [95])

        # Calculate amount statistics (in rupees)
        amounts_rupees = [p["amount"] / 100 for p in segment_payments]
        amount_stats = calculate_statistics(amounts_rupees)

        baseline["segments"][segment_key] = {
            "attempts": segment_attempts,
            "successes": segment_successes,
            "failures": segment_attempts - segment_successes,
            "success_rate": segment_successes / segment_attempts if segment_attempts > 0 else 0,
            "failure_rate": (segment_attempts - segment_successes) / segment_attempts if segment_attempts > 0 else 0,
            "average_amount": amount_stats["mean"],
            "median_amount": amount_stats["median"],
            "average_latency_ms": latency_stats["mean"],
            "p95_latency_ms": latency_percentiles["p95"],
            "failure_breakdown": failure_breakdown,
            "error_code_distribution": dict(error_code_dist),
            "success_rate_variability": {
                "mean": success_rate_stats["mean"],
                "stddev": success_rate_stats["stddev"],
                "min": success_rate_stats["min"],
                "max": success_rate_stats["max"],
                "sample_count": len(success_rates_for_stddev)
            },
            "hourly": hourly_stats,
            "sample_size_info": {
                "total_attempts": segment_attempts,
                "observation_windows": len([h for h in range(24) if h in hourly_data and hourly_data[h]["attempts"] > 0]),
                "min_window_size": min([hourly_data[h]["attempts"] for h in range(24) if h in hourly_data and hourly_data[h]["attempts"] > 0]) if attempt_counts else 0,
                "max_window_size": max(attempt_counts) if attempt_counts else 0,
                "avg_window_size": statistics.mean(attempt_counts) if attempt_counts else 0
            }
        }

    # Determine sufficiency for each segment
    for segment_key, segment_data in baseline["segments"].items():
        total_attempts = segment_data["sample_size_info"]["total_attempts"]
        observation_windows = segment_data["sample_size_info"]["observation_windows"]

        sufficiency = "INSUFFICIENT"
        for level, rules in baseline["sufficiency_rules"].items():
            if total_attempts >= rules["min_attempts"] and observation_windows >= rules["min_windows"]:
                sufficiency = level
                # Break at first match (highest level that qualifies)
                break

        segment_data["sufficiency"] = sufficiency

    return baseline

def save_baseline(merchant_id: str, baseline: Dict[str, Any], output_dir: Path):
    """Save baseline to JSON file."""
    output_file = output_dir / f"{merchant_id}.json"
    with open(output_file, 'w') as f:
        json.dump(baseline, f, indent=2, default=str)
    print(f"Saved baseline for {merchant_id} to {output_file}")

def load_generated_payments(merchant_id: str, generated_dir: Path) -> List[Dict[str, Any]]:
    """Load generated payments for a merchant from JSONL file."""
    payments_file = generated_dir / f"{merchant_id}.jsonl"
    payments = []

    if payments_file.exists():
        with jsonlines.open(payments_file, mode='r') as reader:
            for payment in reader:
                payments.append(payment)

    return payments

def print_baseline_summary(baseline: Dict[str, Any]):
    """Print a human-readable summary of the baseline."""
    print(f"\n{'='*60}")
    print(f"MERCHANT: {baseline['merchant_id']}")
    print(f"{'='*60}")
    print(f"Period: {baseline['period']['start']} to {baseline['period']['end']} ({baseline['period']['days']} days)")

    # Overall
    overall = baseline["overall"]
    print(f"\nOVERALL:")
    print(f"  Attempts: {overall['attempts']:,}")
    print(f"  Success rate: {overall['success_rate']:.3f} ({overall['success_rate']*100:.1f}%)")
    print(f"  Failure rate: {overall['failure_rate']:.3f} ({overall['failure_rate']*100:.1f}%)")
    print(f"  Average amount: ₹{overall['average_amount']:.2f}")
    print(f"  Average latency: {overall['average_latency_ms']:.1f} ms")

    # By method
    print(f"\nBY METHOD:")
    for method, data in baseline["by_method"].items():
        print(f"  {method}:")
        print(f"    Attempts: {data['attempts']:,}")
        print(f"    Success rate: {data['success_rate']:.3f} ({data['success_rate']*100:.1f}%)")
        print(f"    Avg amount: ₹{data['average_amount']:.2f}")
        print(f"    Avg latency: {data['average_latency_ms']:.1f} ms")
        failure = data["failure_breakdown"]
        total_failures = sum(failure.values())
        if total_failures > 0:
            print(f"    Failure breakdown: Caused={failure['customer_caused']}/{total_failures} ({failure['customer_caused']/total_failures*100:.1f}%), "
                  f"Technical={failure['technical']}/{total_failures} ({failure['technical']/total_failures*100:.1f}%), "
                  f"Other={failure['other']}/{total_failures} ({failure['other']/total_failures*100:.1f}%)")

    # Find and highlight the HERO segment if it exists
    hero_segment_key = None
    for segment_key in baseline["segments"].keys():
        if "UPI|BANK_X|ANDROID" in segment_key:
            hero_segment_key = segment_key
            break

    if hero_segment_key:
        hero_data = baseline["segments"][hero_segment_key]
        print(f"\nHERO SEGMENT (UPI + BANK_X + ANDROID):")
        print(f"  Attempts: {hero_data['attempts']:,}")
        print(f"  Success rate: {hero_data['success_rate']:.3f} ({hero_data['success_rate']*100:.1f}%)")
        print(f"  Success rate variability: mean={hero_data['success_rate_variability']['mean']:.3f}, "
              f"stddev={hero_data['success_rate_variability']['stddev']:.3f}")
        print(f"  Average amount: ₹{hero_data['average_amount']:.2f}")
        print(f"  Average latency: {hero_data['average_latency_ms']:.1f} ms")
        print(f"  P95 latency: {hero_data['p95_latency_ms']:.1f} ms")
        failure = hero_data["failure_breakdown"]
        total_failures = sum(failure.values())
        if total_failures > 0:
            print(f"  Failure breakdown: Caused={failure['customer_caused']}/{total_failures} ({failure['customer_caused']/total_failures*100:.1f}%), "
                  f"Technical={failure['technical']}/{total_failures} ({failure['technical']/total_failures*100:.1f}%), "
                  f"Other={failure['other']}/{total_failures} ({failure['other']/total_failures*100:.1f}%)")
        print(f"  Sufficiency: {hero_data['sufficiency']}")
        sample_info = hero_data["sample_size_info"]
        print(f"  Sample size info: {sample_info['total_attempts']:,} total attempts, "
              f"{sample_info['observation_windows']} windows, "
              f"min={sample_info['min_window_size']}, max={sample_info['max_window_size']}, "
              f"avg={sample_info['avg_window_size']:.1f}")

        # Show hourly sample sizes
        hourly_attempts = [hour_data["attempts"] for hour, hour_data in hero_data["hourly"].items()]
        if hourly_attempts:
            print(f"  Hourly attempts range: {min(hourly_attempts)} - {max(hourly_attempts)}")
            print(f"  Hours with data: {len([h for h in hourly_attempts if h > 0])}/24")

    print(f"\n{'='*60}")

def main():
    """Main function to generate baselines for all merchants."""
    # Define merchants
    merchants = ["merch_large_ecom", "merch_upi_smb", "merch_subscription", "merch_small"]

    # Set up directories
    generated_dir = Path(__file__).parent.parent / "data" / "generated"
    baseline_dir = generated_dir / "baselines"

    # Ensure baseline directory exists
    baseline_dir.mkdir(parents=True, exist_ok=True)

    all_baselines = {}

    # Generate baseline for each merchant
    for merchant_id in merchants:
        print(f"Processing {merchant_id}...")
        payments = load_generated_payments(merchant_id, generated_dir)

        if not payments:
            print(f"  Warning: No payments found for {merchant_id}")
            continue

        print(f"  Loaded {len(payments):,} payments")
        baseline = generate_baseline_for_merchant(merchant_id, payments)

        if baseline:
            all_baselines[merchant_id] = baseline
            save_baseline(merchant_id, baseline, baseline_dir)
            print_baseline_summary(baseline)
        else:
            print(f"  Error: Failed to generate baseline for {merchant_id}")

    # Save combined baseline info
    combined_file = baseline_dir / "baseline_info.json"
    with open(combined_file, 'w') as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "merchants_processed": list(all_baselines.keys()),
            "total_merchants": len(all_baselines)
        }, f, indent=2, default=str)

    print(f"\nBaseline generation complete. Baselines saved to: {baseline_dir}")
    return 0

if __name__ == "__main__":
    sys.exit(main())