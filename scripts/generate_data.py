#!/usr/bin/env python3
"""
Synthetic payment data generator for DegradeWatch.

Generates healthy payment events based on merchant profiles.
"""

import argparse
import json
import jsonlines
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import sys

# Add the project root to the path so we can import from scripts if needed
sys.path.append(str(Path(__file__).parent.parent))

def load_merchant_profile(merchant_id: str) -> Dict[str, Any]:
    """Load a merchant profile from JSON file."""
    profile_path = Path(__file__).parent.parent / "data" / "profiles" / f"{merchant_id}.json"
    with open(profile_path, 'r') as f:
        return json.load(f)

def validate_profile(profile: Dict[str, Any]) -> bool:
    """Basic validation of merchant profile."""
    required_fields = [
        "merchant_id", "name", "method_distribution", "baseline_success_rates",
        "normal_variance", "device_distribution", "upi_app_distribution",
        "upi_bank_distribution", "daily_volume", "peak_hours", "traffic_profile",
        "normal_error_profile"
    ]
    for field in required_fields:
        if field not in profile:
            raise ValueError(f"Missing required field: {field}")
    return True

def get_hourly_weights(traffic_profile: str) -> List[float]:
    """
    Get base hourly weights for a traffic profile.
    Returns a list of 24 floats representing relative weight for each hour (0-23).
    """
    # Base weights for each profile type
    if traffic_profile == "large_ecommerce":
        # Two peaks: 11-14 and 19-22
        weights = [0.5] * 24
        for h in range(11, 15):  # 11,12,13,14
            weights[h] = 2.0
        for h in range(19, 23):  # 19,20,21,22
            weights[h] = 2.0
    elif traffic_profile == "upi_smb":
        # Peaks: 12-15 and 18-21
        weights = [0.5] * 24
        for h in range(12, 16):  # 12,13,14,15
            weights[h] = 2.0
        for h in range(18, 22):  # 18,19,20,21
            weights[h] = 2.0
    elif traffic_profile == "subscription_flat":
        # Relatively flat with mild variation
        weights = [1.0] * 24
        # Slightly higher during business hours
        for h in range(9, 18):  # 9am-6pm
            weights[h] = 1.2
    elif traffic_profile == "small_noisy":
        # Noisy but still somewhat business-hour biased
        weights = [0.7] * 24
        for h in range(8, 20):  # 8am-8pm
            weights[h] = 1.3
    else:
        # Default to flat
        weights = [1.0] * 24

    # Normalize to sum to 24 (so average weight is 1.0)
    total = sum(weights)
    return [w * 24 / total for w in weights]

def add_noise_to_weights(base_weights: List[float], noise_level: float = 0.1, rng: random.Random = None) -> List[float]:
    """Add multiplicative noise to hourly weights."""
    if rng is None:
        rng = random

    noisy_weights = []
    for w in base_weights:
        noise = rng.uniform(1 - noise_level, 1 + noise_level)
        noisy_weights.append(w * noise)
    # Renormalize
    total = sum(noisy_weights)
    return [w * 24 / total for w in noisy_weights]

def select_weighted_option(options: Dict[str, float], rng: random.Random = None) -> str:
    """Select an option based on weighted probabilities."""
    if rng is None:
        rng = random

    if not options:
        raise ValueError("Empty options dictionary")

    # Normalize weights to sum to 1.0
    total = sum(options.values())
    if total == 0:
        # Fallback to uniform if all weights are zero
        items = list(options.keys())
        return rng.choice(items)

    normalized = {k: v/total for k, v in options.items()}

    # Generate random number and select
    r = rng.random()
    cumulative = 0.0
    for option, weight in normalized.items():
        cumulative += weight
        if r <= cumulative:
            return option
    # Fallback (should not happen)
    return list(options.keys())[-1]

def generate_payment_id(rng: random.Random = None) -> str:
    """Generate a unique payment ID."""
    if rng is None:
        rng = random
    # Generate 6 bytes (12 hex chars) using the provided RNG
    random_bytes = rng.getrandbits(64)  # 64 bits = 8 bytes
    # We want 12 hex chars = 6 bytes, so adjust
    random_bytes = rng.getrandbits(48)  # 48 bits = 6 bytes
    hex_str = format(random_bytes, '012x')
    return f"pay_{hex_str}"

def generate_order_id(rng: random.Random = None) -> str:
    """Generate a unique order ID."""
    if rng is None:
        rng = random
    # Generate 6 bytes (12 hex chars) using the provided RNG
    random_bytes = rng.getrandbits(48)  # 48 bits = 6 bytes
    hex_str = format(random_bytes, '012x')
    return f"order_{hex_str}"

def generate_timestamp(base_date: datetime, hour: int, minute: int, second: int) -> str:
    """Generate UTC ISO-8601 timestamp."""
    # Create a datetime in UTC using the date from base_date and specified time
    dt = datetime(base_date.year, base_date.month, base_date.day,
                  hour, minute, second, tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")

def generate_amount(rng: random.Random = None) -> int:
    """
    Generate realistic transaction amount in paise.
    Uses a log-normal distribution to create a realistic skew.
    Most transactions are small, fewer are large.
    """
    if rng is None:
        rng = random

    # Parameters for log-normal in rupees, then convert to paise
    # Mean around ₹500, std dev such that most transactions are ₹100-₹2000
    mu = 6.0  # ln(400) ≈ 6.0
    sigma = 1.5
    amount_rupees = rng.lognormvariate(mu, sigma)
    # Clamp to reasonable range: ₹1 to ₹50,000
    amount_rupees = max(1.0, min(50000.0, amount_rupees))
    # Convert to paise and round to integer
    return int(round(amount_rupees * 100))

def generate_latency(success: bool, is_technical_failure: bool, rng: random.Random = None) -> int:
    """
    Generate realistic payment latency in milliseconds.
    Success: lower latency (100-1000ms typical)
    Failure: varies by type
    """
    if rng is None:
        rng = random

    if success:
        # Successful payments: 100ms to 800ms
        return int(rng.triangular(100, 800, 300))
    else:
        if is_technical_failure:
            # Technical failures (especially timeouts): higher latency
            return int(rng.triangular(1000, 8000, 3000))
        else:
            # Customer-caused failures: variable but often quick
            return int(rng.triangular(50, 2000, 500))

def get_error_code_for_failure(error_type: str, rng: random.Random = None) -> str:
    """
    Get a specific error code based on the error type category.
    """
    if rng is None:
        rng = random

    error_taxonomy = {
        "customer_caused": [
            "INSUFFICIENT_FUNDS",
            "WRONG_PIN",
            "OTP_FAILED",
            "USER_CANCELLED"
        ],
        "technical": [
            "BANK_TECHNICAL_ERROR",
            "UPI_TIMEOUT",
            "GATEWAY_ERROR",
            "NETWORK_ERROR"
        ],
        "other": [
            "UNKNOWN_ERROR"
        ]
    }

    if error_type not in error_taxonomy:
        return "UNKNOWN_ERROR"

    return rng.choice(error_taxonomy[error_type])

def generate_payment(
    merchant_profile: Dict[str, Any],
    base_date: datetime,
    hour: int,
    minute: int,
    second: int,
    rng: random.Random
) -> Dict[str, Any]:
    """Generate a single payment event."""
    # 1. Select payment method based on method_distribution
    payment_method = select_weighted_option(merchant_profile["method_distribution"], rng)

    # 2. Select device based on device_distribution
    device = select_weighted_option(merchant_profile["device_distribution"], rng)

    # 3. For UPI payments, select bank and upi_app
    bank = None
    upi_app = None
    if payment_method == "UPI":
        bank = select_weighted_option(merchant_profile["upi_bank_distribution"], rng)
        upi_app = select_weighted_option(merchant_profile["upi_app_distribution"], rng)

    # 4. Determine success/failure based on method-specific baseline success rate
    method_key = payment_method  # UPI, CARD, or NETBANKING
    baseline_success = merchant_profile["baseline_success_rates"].get(
        method_key,
        merchant_profile["baseline_success_rates"]["overall"]
    )

    # Add small daily/hourly noise to success rate (±2%)
    success_rate_variation = rng.uniform(-0.02, 0.02)
    adjusted_success_rate = max(0.0, min(1.0, baseline_success + success_rate_variation))

    is_success = rng.random() < adjusted_success_rate

    # 5. Determine error code if failed
    error_code = None
    is_technical_failure = False
    if not is_success:
        # Select error type based on normal_error_profile
        error_type = select_weighted_option(merchant_profile["normal_error_profile"], rng)
        if error_type == "technical":
            is_technical_failure = True
        error_code = get_error_code_for_failure(error_type, rng)

    # 6. Generate amount and latency
    amount = generate_amount(rng)
    latency_ms = generate_latency(is_success, is_technical_failure, rng)

    return {
        "payment_id": generate_payment_id(rng),
        "merchant_id": merchant_profile["merchant_id"],
        "timestamp": generate_timestamp(base_date, hour, minute, second),
        "amount": amount,
        "currency": "INR",
        "payment_method": payment_method,
        "bank": bank,
        "device": device,
        "upi_app": upi_app,
        "status": "success" if is_success else "failed",
        "error_code": error_code,
        "order_id": generate_order_id(rng),
        "latency_ms": latency_ms
    }

def generate_merchant_data(
    merchant_id: str,
    num_days: int,
    start_date: datetime,
    seed: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generate payment data for a single merchant over multiple days.

    Returns:
        Tuple of (list of payment events, statistics dictionary)
    """
    # Load merchant profile
    profile = load_merchant_profile(merchant_id)
    validate_profile(profile)

    # Create isolated random number generator for this merchant
    if seed is not None:
        # Derive a seed for this merchant from the base seed
        merchant_seed = hash((seed, merchant_id)) % 2**32
    else:
        merchant_seed = None

    rng = random.Random(merchant_seed)

    all_payments = []
    stats = {
        "merchant_id": merchant_id,
        "days": num_days,
        "total_payments": 0,
        "method_counts": {"UPI": 0, "CARD": 0, "NETBANKING": 0},
        "success_counts": {"UPI": 0, "CARD": 0, "NETBANKING": 0, "overall": 0},
        "failure_counts": {"customer_caused": 0, "technical": 0, "other": 0},
        "device_counts": {"ANDROID": 0, "IOS": 0, "WEB": 0},
        "upi_app_counts": {"PHONEPE": 0, "GPAY": 0, "PAYTM": 0, "OTHER": 0},
        "upi_bank_counts": {},  # Will populate dynamically
        "amount_stats": {"total_paise": 0, "count": 0},
        "latency_stats": {"success": [], "failure": []}
    }

    # Get hourly weights for traffic profile
    base_hourly_weights = get_hourly_weights(profile["traffic_profile"])

    for day_offset in range(num_days):
        current_date = start_date + timedelta(days=day_offset)

        # Choose daily volume within the merchant's range with some variation
        daily_min = profile["daily_volume"]["min"]
        daily_max = profile["daily_volume"]["max"]

        # Use triangular distribution to favor the middle of the range
        most_likely = (daily_min + daily_max) / 2
        daily_volume = int(round(rng.triangular(daily_min, daily_max, most_likely)))

        # Add noise to hourly weights for this day
        hourly_weights = add_noise_to_weights(base_hourly_weights, noise_level=0.15, rng=rng)

        # Normalize weights to sum to 1.0
        weight_sum = sum(hourly_weights)
        hourly_probabilities = [w / weight_sum for w in hourly_weights]

        # Distribute payments across hours
        payments_generated = 0
        while payments_generated < daily_volume:
            # Select hour based on probability
            hour = rng.choices(range(24), weights=hourly_probabilities)[0]

            # Determine how many payments in this hour (at least 1 if we have remaining)
            remaining = daily_volume - payments_generated
            if remaining <= 0:
                break

            # For simplicity, generate 1-5 payments per hour slot
            # Adjust based on remaining volume and hour probability
            max_in_hour = min(5, remaining)
            if max_in_hour < 1:
                break

            num_in_hour = rng.randint(1, max_in_hour)
            # But don't exceed remaining
            num_in_hour = min(num_in_hour, remaining)

            # Generate payments for this hour
            for _ in range(num_in_hour):
                # Distribute within the hour
                minute = rng.randint(0, 59)
                second = rng.randint(0, 59)

                payment = generate_payment(profile, current_date, hour, minute, second, rng)
                all_payments.append(payment)
                payments_generated += 1

                # Update statistics
                stats["total_payments"] += 1
                method = payment["payment_method"]
                stats["method_counts"][method] = stats["method_counts"].get(method, 0) + 1

                if payment["status"] == "success":
                    stats["success_counts"][method] = stats["success_counts"].get(method, 0) + 1
                    stats["success_counts"]["overall"] += 1
                    stats["latency_stats"]["success"].append(payment["latency_ms"])
                else:
                    stats["latency_stats"]["failure"].append(payment["latency_ms"])
                    # Determine failure type from error_code
                    error_code = payment["error_code"]
                    if error_code in ["INSUFFICIENT_FUNDS", "WRONG_PIN", "OTP_FAILED", "USER_CANCELLED"]:
                        stats["failure_counts"]["customer_caused"] += 1
                    elif error_code in ["BANK_TECHNICAL_ERROR", "UPI_TIMEOUT", "GATEWAY_ERROR", "NETWORK_ERROR"]:
                        stats["failure_counts"]["technical"] += 1
                    else:
                        stats["failure_counts"]["other"] += 1

                # Update device counts
                device = payment["device"]
                stats["device_counts"][device] = stats["device_counts"].get(device, 0) + 1

                # Update UPI app counts (only for UPI)
                if method == "UPI" and payment["upi_app"]:
                    upi_app = payment["upi_app"]
                    stats["upi_app_counts"][upi_app] = stats["upi_app_counts"].get(upi_app, 0) + 1

                # Update UPI bank counts (only for UPI)
                if method == "UPI" and payment["bank"]:
                    bank = payment["bank"]
                    stats["upi_bank_counts"][bank] = stats["upi_bank_counts"].get(bank, 0) + 1

                # Update amount stats
                stats["amount_stats"]["total_paise"] += payment["amount"]
                stats["amount_stats"]["count"] += 1

    return all_payments, stats

def print_generation_summary(stats: Dict[str, Any]) -> None:
    """Print a summary of the generated data."""
    print(f"\nMerchant: {stats['merchant_id']}")
    print(f"Days: {stats['days']}")
    print(f"Total payments: {stats['total_payments']:,}")

    # Method distribution
    print("\nObserved method mix:")
    total_methods = sum(stats["method_counts"].values())
    for method in ["UPI", "CARD", "NETBANKING"]:
        count = stats["method_counts"].get(method, 0)
        pct = (count / total_methods * 100) if total_methods > 0 else 0
        print(f"  {method}: {pct:.1f}%")

    # Success rates
    print("\nObserved success rates:")
    for method in ["UPI", "CARD", "NETBANKING"]:
        success = stats["success_counts"].get(method, 0)
        attempts = stats["method_counts"].get(method, 0)
        rate = (success / attempts * 100) if attempts > 0 else 0
        print(f"  {method}: {rate:.1f}%")
    overall_success = stats["success_counts"]["overall"]
    overall_attempts = stats["total_payments"]
    overall_rate = (overall_success / overall_attempts * 100) if overall_attempts > 0 else 0
    print(f"  Overall: {overall_rate:.1f}%")

    # Device distribution
    print("\nDevice distribution:")
    total_devices = sum(stats["device_counts"].values())
    for device in ["ANDROID", "IOS", "WEB"]:
        count = stats["device_counts"].get(device, 0)
        pct = (count / total_devices * 100) if total_devices > 0 else 0
        print(f"  {device}: {pct:.1f}%")

    # UPI app distribution (if any UPI payments)
    if stats["method_counts"].get("UPI", 0) > 0:
        print("\nUPI apps:")
        total_upi_apps = sum(stats["upi_app_counts"].values())
        for app in ["PHONEPE", "GPAY", "PAYTM", "OTHER"]:
            count = stats["upi_app_counts"].get(app, 0)
            pct = (count / total_upi_apps * 100) if total_upi_apps > 0 else 0
            print(f"  {app}: {pct:.1f}%")

    # Failure types
    print("\nFailure types:")
    total_failures = sum(stats["failure_counts"].values())
    if total_failures > 0:
        for ftype in ["customer_caused", "technical", "other"]:
            count = stats["failure_counts"].get(ftype, 0)
            pct = (count / total_failures * 100)
            print(f"  {ftype}: {pct:.1f}%")
    else:
        print("  No failures generated")

    # Latency stats
    print("\nAverage latency:")
    if stats["latency_stats"]["success"]:
        avg_success = sum(stats["latency_stats"]["success"]) / len(stats["latency_stats"]["success"])
        print(f"  Success: {avg_success:.0f} ms")
    if stats["latency_stats"]["failure"]:
        avg_failure = sum(stats["latency_stats"]["failure"]) / len(stats["latency_stats"]["failure"])
        print(f"  Failure: {avg_failure:.0f} ms")

    # Amount stats
    if stats["amount_stats"]["count"] > 0:
        avg_amount_paise = stats["amount_stats"]["total_paise"] / stats["amount_stats"]["count"]
        avg_amount_rupees = avg_amount_paise / 100
        print(f"\nAverage transaction amount: ₹{avg_amount_rupees:.2f}")

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic payment data for DegradeWatch")
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days to generate (default: 14)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: None for random seed)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD format (default: today - days)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/generated",
        help="Output directory for JSONL files (default: data/generated)"
    )

    args = parser.parse_args()

    # Set up output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine start date
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        # Default to today minus the number of days
        start_date = datetime.now() - timedelta(days=args.days)

    # Set the global random seed if provided
    if args.seed is not None:
        random.seed(args.seed)
        print(f"Using global seed: {args.seed}")

    # List of merchants to generate
    merchants = ["merch_large_ecom", "merch_upi_smb", "merch_subscription", "merch_small"]

    all_stats = {}

    for merchant_id in merchants:
        print(f"\nGenerating data for {merchant_id}...")
        payments, stats = generate_merchant_data(
            merchant_id=merchant_id,
            num_days=args.days,
            start_date=start_date,
            seed=args.seed
        )

        # Write to JSONL file
        output_file = output_dir / f"{merchant_id}.jsonl"
        with jsonlines.open(output_file, mode='w') as writer:
            writer.write_all(payments)

        print(f"  Generated {len(payments):,} payments -> {output_file}")

        # Store stats for summary
        all_stats[merchant_id] = stats

    # Print summaries
    print("\n" + "="*60)
    print("GENERATION SUMMARY")
    print("="*60)

    for merchant_id, stats in all_stats.items():
        print_generation_summary(stats)

    print("\n" + "="*60)
    print("Generation complete!")
    print("="*60)

if __name__ == "__main__":
    main()