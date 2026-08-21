#!/usr/bin/env python3
"""
Validation script for merchant profiles.
Validates all JSON files in data/profiles/ against the schema and business rules.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple


def load_json_file(filepath: Path) -> Dict[str, Any]:
    """Load and parse a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def validate_required_fields(profile: Dict[str, Any]) -> List[str]:
    """Check that all required fields are present."""
    required_fields = [
        "merchant_id", "name", "method_distribution", "baseline_success_rates",
        "normal_variance", "device_distribution", "upi_app_distribution",
        "upi_bank_distribution", "daily_volume", "peak_hours", "traffic_profile",
        "normal_error_profile"
    ]

    missing_fields = []
    for field in required_fields:
        if field not in profile:
            missing_fields.append(field)

    return missing_fields


def validate_distribution_sum(field_name: str, distribution: Dict[str, float], tolerance: float = 0.001) -> Tuple[bool, str]:
    """Validate that a distribution sums to approximately 1.0."""
    total = sum(distribution.values())
    if abs(total - 1.0) > tolerance:
        return False, f"{field_name} sums to {total:.4f}, expected approximately 1.0"
    return True, ""


def validate_success_rates(profile: Dict[str, Any]) -> List[str]:
    """Validate that success rates are between 0 and 1."""
    errors = []
    success_rates = profile.get("baseline_success_rates", {})

    for method, rate in success_rates.items():
        if not isinstance(rate, (int, float)) or rate < 0 or rate > 1:
            errors.append(f"baseline_success_rates.{method} = {rate} must be between 0 and 1")

    return errors


def validate_variance(profile: Dict[str, Any]) -> List[str]:
    """Validate that normal variance is between 0 and 1."""
    errors = []
    variance = profile.get("normal_variance", {})

    for key, value in variance.items():
        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            errors.append(f"normal_variance.{key} = {value} must be between 0 and 1")

    return errors


def validate_daily_volume(profile: Dict[str, Any]) -> List[str]:
    """Validate daily_volume.min <= daily_volume.max."""
    errors = []
    daily_volume = profile.get("daily_volume", {})

    min_vol = daily_volume.get("min")
    max_vol = daily_volume.get("max")

    if min_vol is not None and max_vol is not None:
        if not isinstance(min_vol, int) or min_vol < 0:
            errors.append(f"daily_volume.min = {min_vol} must be a non-negative integer")
        if not isinstance(max_vol, int) or max_vol < 0:
            errors.append(f"daily_volume.max = {max_vol} must be a non-negative integer")
        if min_vol > max_vol:
            errors.append(f"daily_volume.min ({min_vol}) must be <= daily_volume.max ({max_vol})")

    return errors


def validate_peak_hours(profile: Dict[str, Any]) -> List[str]:
    """Validate peak_hours is a list of integers between 0-23."""
    errors = []
    peak_hours = profile.get("peak_hours", [])

    if not isinstance(peak_hours, list):
        errors.append("peak_hours must be a list")
    else:
        for hour in peak_hours:
            if not isinstance(hour, int) or hour < 0 or hour > 23:
                errors.append(f"peak_hours contains invalid hour: {hour} (must be 0-23)")

    return errors


def main():
    """Main validation function."""
    profiles_dir = Path(__file__).parent.parent / "data" / "profiles"

    if not profiles_dir.exists():
        print(f"Error: Profiles directory not found at {profiles_dir}")
        sys.exit(1)

    # Expected merchant IDs
    expected_merchant_ids = {
        "merch_large_ecom",
        "merch_upi_smb",
        "merch_subscription",
        "merch_small"
    }

    # Find all JSON files
    profile_files = list(profiles_dir.glob("*.json"))

    if not profile_files:
        print(f"No JSON files found in {profiles_dir}")
        sys.exit(1)

    print(f"Found {len(profile_files)} profile files to validate:\n")

    all_valid = True
    merchant_ids_found = set()

    # Validate each profile
    for profile_file in sorted(profile_files):
        print(f"Validating {profile_file.name}...")

        try:
            profile = load_json_file(profile_file)
        except json.JSONDecodeError as e:
            print(f"  ❌ Invalid JSON: {e}")
            all_valid = False
            continue
        except Exception as e:
            print(f"  ❌ Error reading file: {e}")
            all_valid = False
            continue

        # Track merchant ID for uniqueness check
        merchant_id = profile.get("merchant_id")
        if merchant_id:
            if merchant_id in merchant_ids_found:
                print(f"  ❌ Duplicate merchant_id: {merchant_id}")
                all_valid = False
            else:
                merchant_ids_found.add(merchant_id)

        # Run validations
        errors = []

        # 1. Required fields
        missing_fields = validate_required_fields(profile)
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")

        # 2. Distribution sums (only if distributions exist)
        distributions_to_check = [
            ("method_distribution", profile.get("method_distribution", {})),
            ("device_distribution", profile.get("device_distribution", {})),
            ("upi_app_distribution", profile.get("upi_app_distribution", {})),
            ("upi_bank_distribution", profile.get("upi_bank_distribution", {})),
            ("normal_error_profile", profile.get("normal_error_profile", {}))
        ]

        for dist_name, dist_data in distributions_to_check:
            if dist_data:  # Only validate if not empty
                is_valid, error_msg = validate_distribution_sum(dist_name, dist_data)
                if not is_valid:
                    errors.append(error_msg)

        # 3. Success rates
        errors.extend(validate_success_rates(profile))

        # 4. Variance
        errors.extend(validate_variance(profile))

        # 5. Daily volume
        errors.extend(validate_daily_volume(profile))

        # 6. Peak hours
        errors.extend(validate_peak_hours(profile))

        # Report results
        if errors:
            print(f"  ❌ Validation failed:")
            for error in errors:
                print(f"    - {error}")
            all_valid = False
        else:
            print(f"  ✅ Validation passed")

        print()  # Empty line for readability

    # Check that we found all expected merchant IDs
    missing_ids = expected_merchant_ids - merchant_ids_found
    if missing_ids:
        print(f"❌ Missing expected merchant profiles: {', '.join(sorted(missing_ids))}")
        all_valid = False

    extra_ids = merchant_ids_found - expected_merchant_ids
    if extra_ids:
        print(f"⚠️  Found unexpected merchant profiles: {', '.join(sorted(extra_ids))}")
        # This is not necessarily an error, but worth noting

    # Final result
    if all_valid:
        print("🎉 All profile validations passed!")
        return 0
    else:
        print("❌ Profile validation failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())