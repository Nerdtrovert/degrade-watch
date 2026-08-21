#!/usr/bin/env python3
"""
Validation script for generated payment data.

Validates JSONL files in data/generated/ against schema and business rules.
"""

import json
import jsonlines
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

def load_merchant_profile(merchant_id: str) -> Dict[str, Any]:
    """Load a merchant profile from JSON file."""
    profile_path = Path(__file__).parent.parent / "data" / "profiles" / f"{merchant_id}.json"
    with open(profile_path, 'r') as f:
        return json.load(f)

def validate_payment_schema(payment: Dict[str, Any], line_num: int) -> List[str]:
    """Validate a single payment against the schema."""
    errors = []

    # Required fields
    required_fields = [
        "payment_id", "merchant_id", "timestamp", "amount", "currency",
        "payment_method", "status", "order_id", "latency_ms"
    ]

    for field in required_fields:
        if field not in payment:
            errors.append(f"Line {line_num}: Missing required field '{field}'")

    if errors:
        return errors  # Can't validate further without basic fields

    # Field type and value validations
    # payment_id: string starting with "pay_"
    if not isinstance(payment["payment_id"], str) or not payment["payment_id"].startswith("pay_"):
        errors.append(f"Line {line_num}: payment_id must be a string starting with 'pay_'")

    # merchant_id: string
    if not isinstance(payment["merchant_id"], str):
        errors.append(f"Line {line_num}: merchant_id must be a string")

    # timestamp: valid ISO-8601 UTC string ending with Z
    try:
        dt = datetime.fromisoformat(payment["timestamp"].replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) != timezone.utc.utcoffset(dt):
            errors.append(f"Line {line_num}: timestamp must be in UTC timezone")
    except ValueError:
        errors.append(f"Line {line_num}: timestamp must be valid ISO-8601 format")

    # amount: positive integer (paise)
    if not isinstance(payment["amount"], int) or payment["amount"] <= 0:
        errors.append(f"Line {line_num}: amount must be a positive integer (paise)")

    # currency: must be "INR"
    if payment["currency"] != "INR":
        errors.append(f"Line {line_num}: currency must be 'INR'")

    # payment_method: must be UPI, CARD, or NETBANKING
    if payment["payment_method"] not in ["UPI", "CARD", "NETBANKING"]:
        errors.append(f"Line {line_num}: payment_method must be UPI, CARD, or NETBANKING")

    # device: must be ANDROID, IOS, or WEB
    if "device" not in payment or payment["device"] not in ["ANDROID", "IOS", "WEB"]:
        errors.append(f"Line {line_num}: device must be ANDROID, IOS, or WEB")

    # status: must be success or failed
    if payment["status"] not in ["success", "failed"]:
        errors.append(f"Line {line_num}: status must be 'success' or 'failed'")

    # order_id: string starting with "order_"
    if not isinstance(payment["order_id"], str) or not payment["order_id"].startswith("order_"):
        errors.append(f"Line {line_num}: order_id must be a string starting with 'order_'")

    # latency_ms: positive integer
    if not isinstance(payment["latency_ms"], int) or payment["latency_ms"] <= 0:
        errors.append(f"Line {line_num}: latency_ms must be a positive integer")

    # Conditional fields based on payment_method
    method = payment["payment_method"]

    # bank: should be null for CARD/NETBANKING, string for UPI
    if method in ["CARD", "NETBANKING"]:
        if payment.get("bank") is not None:
            errors.append(f"Line {line_num}: bank should be null for {method} payments")
    else:  # UPI
        if "bank" not in payment or not isinstance(payment["bank"], str):
            errors.append(f"Line {line_num}: bank must be a string for UPI payments")

    # upi_app: should be null for CARD/NETBANKING, string for UPI
    if method in ["CARD", "NETBANKING"]:
        if payment.get("upi_app") is not None:
            errors.append(f"Line {line_num}: upi_app should be null for {method} payments")
    else:  # UPI
        if "upi_app" not in payment or not isinstance(payment["upi_app"], str):
            errors.append(f"Line {line_num}: upi_app must be a string for UPI payments")

    # error_code: null for success, string for failed
    if payment["status"] == "success":
        if payment.get("error_code") is not None:
            errors.append(f"Line {line_num}: error_code must be null for successful payments")
    else:  # failed
        if "error_code" not in payment or not isinstance(payment["error_code"], str):
            errors.append(f"Line {line_num}: error_code must be a string for failed payments")
        else:
            # Validate error_code is from known taxonomy
            valid_errors = [
                "INSUFFICIENT_FUNDS", "WRONG_PIN", "OTP_FAILED", "USER_CANCELLED",
                "BANK_TECHNICAL_ERROR", "UPI_TIMEOUT", "GATEWAY_ERROR", "NETWORK_ERROR",
                "UNKNOWN_ERROR"
            ]
            if payment["error_code"] not in valid_errors:
                errors.append(f"Line {line_num}: error_code '{payment['error_code']}' is not valid")

    return errors

def validate_generated_data(
    generated_dir: Path,
    tolerance: float = 0.05
) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate all generated data files.

    Returns:
        Tuple of (all_valid, summary_statistics)
    """
    if not generated_dir.exists():
        print(f"Error: Generated data directory not found at {generated_dir}")
        return False, {}

    # Expected merchant IDs
    expected_merchant_ids = {
        "merch_large_ecom",
        "merch_upi_smb",
        "merch_subscription",
        "merch_small"
    }

    # Find all JSONL files
    jsonl_files = list(generated_dir.glob("*.jsonl"))

    if not jsonl_files:
        print(f"No JSONL files found in {generated_dir}")
        return False, {}

    print(f"Found {len(jsonl_files)} generated data files to validate:\n")

    all_valid = True
    all_payments = []
    merchant_stats = {}
    all_payment_ids = set()
    all_order_ids = set()

    # Process each file
    for jsonl_file in sorted(jsonl_files):
        merchant_id = jsonl_file.stem  # filename without extension

        # Check if merchant ID is expected
        if merchant_id not in expected_merchant_ids:
            print(f"⚠️  Unexpected merchant ID in filename: {merchant_id}")
            # Not necessarily invalid, but note it

        print(f"Validating {jsonl_file.name}...")

        # Load merchant profile for reference
        try:
            profile = load_merchant_profile(merchant_id)
        except FileNotFoundError:
            print(f"  ❌ Profile not found for merchant: {merchant_id}")
            all_valid = False
            continue
        except Exception as e:
            print(f"  ❌ Error loading profile: {e}")
            all_valid = False
            continue

        # Initialize stats for this merchant
        stats = {
            "payment_count": 0,
            "method_counts": {"UPI": 0, "CARD": 0, "NETBANKING": 0},
            "success_counts": {"UPI": 0, "CARD": 0, "NETBANKING": 0},
            "failure_counts": {"customer_caused": 0, "technical": 0, "other": 0},
            "device_counts": {"ANDROID": 0, "IOS": 0, "WEB": 0},
            "upi_app_counts": {"PHONEPE": 0, "GPAY": 0, "PAYTM": 0, "OTHER": 0},
            "upi_bank_counts": {},
            "amount_total_paise": 0,
            "latency_success": [],
            "latency_failure": [],
            "timestamps": []  # For day range validation
        }

        # Validate each payment in the file
        line_num = 0
        file_valid = True

        try:
            with jsonlines.open(jsonl_file, mode='r') as reader:
                for payment in reader:
                    line_num += 1

                    # Check for duplicate IDs
                    pid = payment.get("payment_id")
                    oid = payment.get("order_id")
                    if pid in all_payment_ids:
                        print(f"  ❌ Line {line_num}: Duplicate payment_id: {pid}")
                        all_valid = False
                        file_valid = False
                    else:
                        all_payment_ids.add(pid)

                    if oid in all_order_ids:
                        print(f"  ❌ Line {line_num}: Duplicate order_id: {oid}")
                        all_valid = False
                        file_valid = False
                    else:
                        all_order_ids.add(oid)

                    # Validate schema
                    schema_errors = validate_payment_schema(payment, line_num)
                    if schema_errors:
                        for error in schema_errors:
                            print(f"  ❌ {error}")
                        all_valid = False
                        file_valid = False

                    if not file_valid:
                        # Skip further processing for this payment if already invalid
                        continue

                    # Payment is valid, collect statistics
                    stats["payment_count"] += 1
                    all_payments.append(payment)

                    # Method counts
                    method = payment["payment_method"]
                    stats["method_counts"][method] = stats["method_counts"].get(method, 0) + 1

                    # Success/failure counts
                    if payment["status"] == "success":
                        stats["success_counts"][method] = stats["success_counts"].get(method, 0) + 1
                        stats["latency_success"].append(payment["latency_ms"])
                    else:
                        # Categorize failure
                        error_code = payment["error_code"]
                        if error_code in ["INSUFFICIENT_FUNDS", "WRONG_PIN", "OTP_FAILED", "USER_CANCELLED"]:
                            stats["failure_counts"]["customer_caused"] += 1
                        elif error_code in ["BANK_TECHNICAL_ERROR", "UPI_TIMEOUT", "GATEWAY_ERROR", "NETWORK_ERROR"]:
                            stats["failure_counts"]["technical"] += 1
                        else:
                            stats["failure_counts"]["other"] += 1
                        stats["latency_failure"].append(payment["latency_ms"])

                    # Device counts
                    device = payment["device"]
                    stats["device_counts"][device] = stats["device_counts"].get(device, 0) + 1

                    # UPI app counts (only for UPI)
                    if method == "UPI" and payment.get("upi_app"):
                        upi_app = payment["upi_app"]
                        stats["upi_app_counts"][upi_app] = stats["upi_app_counts"].get(upi_app, 0) + 1

                    # UPI bank counts (only for UPI)
                    if method == "UPI" and payment.get("bank"):
                        bank = payment["bank"]
                        stats["upi_bank_counts"][bank] = stats["upi_bank_counts"].get(bank, 0) + 1

                    # Amount total
                    stats["amount_total_paise"] += payment["amount"]

                    # Timestamp for day range validation
                    try:
                        ts = datetime.fromisoformat(payment["timestamp"].replace("Z", "+00:00"))
                        stats["timestamps"].append(ts)
                    except ValueError:
                        pass  # Already caught in schema validation

            if file_valid:
                print(f"  ✅ Validation passed ({stats['payment_count']} payments)")
            else:
                print(f"  ❌ Validation failed")

        except Exception as e:
            print(f"  ❌ Error reading file: {e}")
            all_valid = False
            file_valid = False

        merchant_stats[merchant_id] = stats
        print()  # Empty line for readability

    # Check that we have all expected merchants
    found_merchant_ids = set(merchant_stats.keys())
    missing_ids = expected_merchant_ids - found_merchant_ids
    if missing_ids:
        print(f"❌ Missing expected merchant data files: {', '.join(sorted(missing_ids))}")
        all_valid = False

    # Calculate distributions and compare with profiles
    if all_valid:
        print("🔍 Checking distributions against profiles...\n")
        for merchant_id, stats in merchant_stats.items():
            if merchant_id not in expected_merchant_ids:
                continue

            print(f"Checking {merchant_id}:")
            profile = load_merchant_profile(merchant_id)

            # Check method distribution
            total_methods = sum(stats["method_counts"].values())
            if total_methods > 0:
                for method in ["UPI", "CARD", "NETBANKING"]:
                    observed_pct = stats["method_counts"].get(method, 0) / total_methods
                    expected_pct = profile["method_distribution"].get(method, 0.0)
                    diff = abs(observed_pct - expected_pct)
                    if diff > tolerance:
                        print(f"  ⚠️  Method {method}: observed {observed_pct:.3f}, expected {expected_pct:.3f} (diff {diff:.3f} > {tolerance})")
                    else:
                        print(f"  ✅ Method {method}: {observed_pct:.3f} (expected {expected_pct:.3f})")

            # Check success rates
            for method in ["UPI", "CARD", "NETBANKING"]:
                success = stats["success_counts"].get(method, 0)
                attempts = stats["method_counts"].get(method, 0)
                if attempts > 0:
                    observed_rate = success / attempts
                    expected_rate = profile["baseline_success_rates"].get(method, 0.0)
                    diff = abs(observed_rate - expected_rate)
                    if diff > tolerance:
                        print(f"  ⚠️  Success rate {method}: observed {observed_rate:.3f}, expected {expected_rate:.3f} (diff {diff:.3f} > {tolerance})")
                    else:
                        print(f"  ✅ Success rate {method}: {observed_rate:.3f} (expected {expected_rate:.3f})")

            # Check device distribution
            total_devices = sum(stats["device_counts"].values())
            if total_devices > 0:
                for device in ["ANDROID", "IOS", "WEB"]:
                    observed_pct = stats["device_counts"].get(device, 0) / total_devices
                    expected_pct = profile["device_distribution"].get(device, 0.0)
                    diff = abs(observed_pct - expected_pct)
                    if diff > tolerance:
                        print(f"  ⚠️  Device {device}: observed {observed_pct:.3f}, expected {expected_pct:.3f} (diff {diff:.3f} > {tolerance})")
                    else:
                        print(f"  ✅ Device {device}: {observed_pct:.3f} (expected {expected_pct:.3f})")

            # Check UPI app distribution (if any UPI payments)
            if stats["method_counts"].get("UPI", 0) > 0:
                total_upi_apps = sum(stats["upi_app_counts"].values())
                if total_upi_apps > 0:
                    for app in ["PHONEPE", "GPAY", "PAYTM", "OTHER"]:
                        observed_pct = stats["upi_app_counts"].get(app, 0) / total_upi_apps
                        expected_pct = profile["upi_app_distribution"].get(app, 0.0)
                        diff = abs(observed_pct - expected_pct)
                        if diff > tolerance:
                            print(f"  ⚠️  UPI app {app}: observed {observed_pct:.3f}, expected {expected_pct:.3f} (diff {diff:.3f} > {tolerance})")
                        else:
                            print(f"  ✅ UPI app {app}: {observed_pct:.3f} (expected {expected_pct:.3f})")

            print()  # Empty line between merchants

    # Overall summary
    total_payments = len(all_payments)
    duplicate_payment_ids = len(all_payment_ids) != total_payments
    duplicate_order_ids = len(all_order_ids) != total_payments

    if duplicate_payment_ids:
        print(f"❌ Found duplicate payment IDs: {total_payments - len(all_payment_ids)} duplicates")
        all_valid = False
    if duplicate_order_ids:
        print(f"❌ Found duplicate order IDs: {total_payments - len(all_order_ids)} duplicates")
        all_valid = False

    if all_valid and total_payments > 0:
        print("🎉 All validations passed!")
        print(f"   Total payments validated: {total_payments:,}")
        print(f"   Unique payment IDs: {len(all_payment_ids):,}")
        print(f"   Unique order IDs: {len(all_order_ids):,}")
    elif total_payments == 0:
        print("⚠️  No payments found in generated data")
        all_valid = False

    return all_valid, {
        "total_payments": total_payments,
        "merchant_stats": merchant_stats,
        "all_payment_ids": list(all_payment_ids),
        "all_order_ids": list(all_order_ids)
    }

def main():
    """Main validation function."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate generated payment data")
    parser.add_argument(
        "--generated-dir",
        type=str,
        default="data/generated",
        help="Directory containing generated JSONL files (default: data/generated)"
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="Tolerance for distribution comparisons (default: 0.05 = 5%%)"
    )

    args = parser.parse_args()

    generated_dir = Path(args.generated_dir)

    is_valid, summary = validate_generated_data(generated_dir, args.tolerance)

    if is_valid:
        print("\n✅ DATA VALIDATION PASSED")
        sys.exit(0)
    else:
        print("\n❌ DATA VALIDATION FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()