"""
Tests for the synthetic payment generator.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
import pytest

# Add the project root to the path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from scripts.generate_data import (
    load_merchant_profile,
    generate_payment_id,
    generate_order_id,
    generate_timestamp,
    generate_amount,
    generate_latency,
    select_weighted_option,
    get_hourly_weights,
    add_noise_to_weights,
    generate_payment,
    generate_merchant_data
)

def test_load_merchant_profile():
    """Test that we can load a merchant profile."""
    profile = load_merchant_profile("merch_large_ecom")
    assert profile["merchant_id"] == "merch_large_ecom"
    assert profile["name"] == "Large E-commerce"
    assert "method_distribution" in profile
    assert "baseline_success_rates" in profile

def test_generate_id_uniqueness():
    """Test that ID generation produces unique values."""
    ids = set()
    for _ in range(1000):
        ids.add(generate_payment_id())
        ids.add(generate_order_id())
    # Should have 2000 unique IDs (though there's a tiny chance of collision)
    assert len(ids) >= 1990  # Allow for extremely unlikely collisions

def test_generate_timestamp():
    """Test timestamp generation."""
    base_date = datetime(2026, 8, 20, 12, 0, 0)
    ts = generate_timestamp(base_date, 12, 30, 45)
    # Should end with Z for UTC
    assert ts.endswith("Z")
    # Should be parseable
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert dt.year == 2026
    assert dt.month == 8
    assert dt.day == 20
    assert dt.hour == 12
    assert dt.minute == 30
    assert dt.second == 45

def test_generate_amount():
    """Test amount generation is in reasonable range."""
    for _ in range(100):
        amount = generate_amount()
        # Should be positive integer paise
        assert isinstance(amount, int)
        assert amount > 0
        # Should be reasonable: between 1 paise and 5,000,000 paise (₹50,000)
        assert 1 <= amount <= 5_000_000

def test_generate_latency():
    """Test latency generation."""
    # Success latency should be in reasonable range
    for _ in range(100):
        lat = generate_latency(True, False)
        assert isinstance(lat, int)
        assert lat > 0
        # Success: typically 100-800ms, but allow wider range for triangular distribution
        assert 50 <= lat <= 2000

    # Failure latency should also be positive
    for _ in range(100):
        lat = generate_latency(False, True)  # Technical failure
        assert isinstance(lat, int)
        assert lat > 0
        assert 50 <= lat <= 10000  # Allow up to 10 seconds

def test_select_weighted_option():
    """Test weighted selection works correctly."""
    options = {"A": 0.0, "B": 1.0, "C": 0.0}
    # Should always pick B
    for _ in range(100):
        assert select_weighted_option(options) == "B"

    options = {"A": 1.0, "B": 1.0}
    # Should pick A or B roughly evenly
    counts = {"A": 0, "B": 0}
    for _ in range(1000):
        choice = select_weighted_option(options)
        counts[choice] += 1
    # Each should be between 40% and 60%
    assert 400 <= counts["A"] <= 600
    assert 400 <= counts["B"] <= 600

def test_get_hourly_weights():
    """Test hourly weight generation for different profiles."""
    # Test large_ecommerce
    weights = get_hourly_weights("large_ecommerce")
    assert len(weights) == 24
    # Peaks at 11-14 and 19-22 should be higher
    assert weights[12] > weights[10]  # 12pm > 10am
    assert weights[20] > weights[18]  # 8pm > 6pm

    # Test subscription_flat
    weights = get_hourly_weights("subscription_flat")
    assert len(weights) == 24
    # Should be relatively flat but slightly higher 9-18
    # Average of 9-18 should be > average of 0-8 and 19-23
    day_hours = sum(weights[9:19]) / 10
    night_hours = (sum(weights[0:9]) + sum(weights[19:24])) / 14
    assert day_hours > night_hours

def test_add_noise_to_weights():
    """Test that noise addition preserves relative order approximately."""
    base_weights = [1.0] * 24
    base_weights[12] = 2.0  # Make noon higher

    noisy_weights = add_noise_to_weights(base_weights, noise_level=0.1)
    # After noise, noon should still tend to be higher
    # Run multiple times to reduce flakiness
    noon_higher_count = 0
    for _ in range(10):
        w = add_noise_to_weights(base_weights, noise_level=0.1)
        if w[12] > sum(w) / 24:  # Above average
            noon_higher_count += 1
    # Should be higher most of the time
    assert noon_higher_count >= 7

def test_generate_payment_structure():
    """Test that generated payment has correct structure."""
    profile = load_merchant_profile("merch_upi_smb")

    # Use a fixed seed for reproducibility
    import random
    rng = random.Random(42)

    payment = generate_payment(
        profile,
        datetime(2026, 8, 20),
        12, 30, 0,
        rng
    )

    # Check required fields exist
    required_fields = [
        "payment_id", "merchant_id", "timestamp", "amount", "currency",
        "payment_method", "bank", "device", "upi_app", "status",
        "error_code", "order_id", "latency_ms"
    ]
    for field in required_fields:
        assert field in payment

    # Check types and constraints
    assert isinstance(payment["payment_id"], str)
    assert payment["payment_id"].startswith("pay_")
    assert payment["merchant_id"] == "merch_upi_smb"
    assert isinstance(payment["amount"], int)
    assert payment["amount"] > 0
    assert payment["currency"] == "INR"
    assert payment["payment_method"] in ["UPI", "CARD", "NETBANKING"]
    assert payment["device"] in ["ANDROID", "IOS", "WEB"]
    assert payment["status"] in ["success", "failed"]
    assert isinstance(payment["order_id"], str)
    assert payment["order_id"].startswith("order_")
    assert isinstance(payment["latency_ms"], int)
    assert payment["latency_ms"] > 0

    # Check conditional fields
    if payment["payment_method"] == "UPI":
        assert isinstance(payment["bank"], str)
        assert isinstance(payment["upi_app"], str)
        assert payment["upi_app"] in ["PHONEPE", "GPAY", "PAYTM", "OTHER"]
    else:
        assert payment["bank"] is None
        assert payment["upi_app"] is None

    # Check error_code consistency
    if payment["status"] == "success":
        assert payment["error_code"] is None
    else:
        assert isinstance(payment["error_code"], str)
        valid_errors = [
            "INSUFFICIENT_FUNDS", "WRONG_PIN", "OTP_FAILED", "USER_CANCELLED",
            "BANK_TECHNICAL_ERROR", "UPI_TIMEOUT", "GATEWAY_ERROR", "NETWORK_ERROR",
            "UNKNOWN_ERROR"
        ]
        assert payment["error_code"] in valid_errors

def test_reproducibility_with_seed():
    """Test that same seed produces same data."""
    # Generate data for one merchant for one day with fixed seed
    payments1, stats1 = generate_merchant_data(
        "merch_upi_smb",
        num_days=1,
        start_date=datetime(2026, 8, 20),
        seed=12345
    )

    payments2, stats2 = generate_merchant_data(
        "merch_upi_smb",
        num_days=1,
        start_date=datetime(2026, 8, 20),
        seed=12345
    )

    # Should be identical
    assert len(payments1) == len(payments2)
    assert stats1["total_payments"] == stats2["total_payments"]

    # Check each payment is identical
    for p1, p2 in zip(payments1, payments2):
        assert p1["payment_id"] == p2["payment_id"]
        assert p1["timestamp"] == p2["timestamp"]
        assert p1["amount"] == p2["amount"]
        # All fields should match
        assert p1 == p2

def test_different_seeds_produce_different_data():
    """Test that different seeds produce different data."""
    payments1, _ = generate_merchant_data(
        "merch_upi_smb",
        num_days=1,
        start_date=datetime(2026, 8, 20),
        seed=12345
    )

    payments2, _ = generate_merchant_data(
        "merch_upi_smb",
        num_days=1,
        start_date=datetime(2026, 8, 20),
        seed=67890
    )

    # Should produce different data (different payment IDs, amounts, etc.)
    # At minimum, the first payment should be different
    assert len(payments1) > 0
    assert len(payments2) > 0
    assert payments1[0]["payment_id"] != payments2[0]["payment_id"]
    assert payments1[0]["timestamp"] != payments2[0]["timestamp"]
    assert payments1[0]["amount"] != payments2[0]["amount"]

def test_upi_app_rules():
    """Test that UPI app is only set for UPI payments."""
    profile = load_merchant_profile("merch_upi_smb")
    import random
    rng = random.Random(42)

    # Generate a bunch of payments
    for _ in range(100):
        payment = generate_payment(
            profile,
            datetime(2026, 8, 20),
            12, 0, 0,
            rng
        )

        if payment["payment_method"] == "UPI":
            assert payment["upi_app"] is not None
            assert payment["upi_app"] in ["PHONEPE", "GPAY", "PAYTM", "OTHER"]
            assert payment["bank"] is not None
        else:
            assert payment["upi_app"] is None
            assert payment["bank"] is None

def test_error_status_consistency():
    """Test that error codes align with success/failure status."""
    profile = load_merchant_profile("merch_large_ecom")
    import random
    rng = random.Random(42)

    for _ in range(100):
        payment = generate_payment(
            profile,
            datetime(2026, 8, 20),
            12, 0, 0,
            rng
        )

        if payment["status"] == "success":
            assert payment["error_code"] is None
        else:
            assert payment["error_code"] is not None
            assert isinstance(payment["error_code"], str)
            assert len(payment["error_code"]) > 0

def test_payment_id_order_id_uniqueness_within_batch():
    """Test that within a generated batch, IDs are unique."""
    payments, stats = generate_merchant_data(
        "merch_subscription",
        num_days=3,  # Multiple days
        start_date=datetime(2026, 8, 20),
        seed=54321
    )

    payment_ids = set()
    order_ids = set()

    for payment in payments:
        pid = payment["payment_id"]
        oid = payment["order_id"]

        assert pid not in payment_ids, f"Duplicate payment_id: {pid}"
        payment_ids.add(pid)

        assert oid not in order_ids, f"Duplicate order_id: {oid}"
        order_ids.add(oid)

    assert len(payment_ids) == len(payments)
    assert len(order_ids) == len(payments)
    assert stats["total_payments"] == len(payments)

def test_method_distribution_approximately_correct():
    """Test that generated method distribution matches profile approximately."""
    profile = load_merchant_profile("merch_large_ecom")
    payments, stats = generate_merchant_data(
        "merch_large_ecom",
        num_days=7,  # A week for better statistics
        start_date=datetime(2026, 8, 20),
        seed=9999
    )

    total = len(payments)
    assert total > 0

    # Check each method
    for method in ["UPI", "CARD", "NETBANKING"]:
        observed = stats["method_counts"].get(method, 0) / total
        expected = profile["method_distribution"][method]
        # Should be within 10% for a week of data
        assert abs(observed - expected) < 0.10, \
            f"Method {method}: observed {observed:.3f}, expected {expected:.3f}"

def test_daily_volume_within_range():
    """Test that daily volume stays within configured min/max."""
    profile = load_merchant_profile("merch_small")
    payments, stats = generate_merchant_data(
        "merch_small",
        num_days=10,
        start_date=datetime(2026, 8, 20),
        seed=11111
    )

    # Group payments by day
    from collections import defaultdict
    daily_counts = defaultdict(int)

    for payment in payments:
        # Extract date from timestamp
        date_str = payment["timestamp"][:10]  # YYYY-MM-DD
        daily_counts[date_str] += 1

    min_vol = profile["daily_volume"]["min"]
    max_vol = profile["daily_volume"]["max"]

    for day, count in daily_counts.items():
        assert min_vol <= count <= max_vol, \
            f"Day {day}: volume {count} not in range [{min_vol}, {max_vol}]"

def test_timestamp_span_correct_days():
    """Test that generated timestamps span the correct number of days."""
    start_date = datetime(2026, 8, 20)
    num_days = 5

    payments, stats = generate_merchant_data(
        "merch_subscription",
        num_days=num_days,
        start_date=start_date,
        seed=22222
    )

    # Extract unique dates
    dates = set()
    for payment in payments:
        date_str = payment["timestamp"][:10]  # YYYY-MM-DD
        dates.add(date_str)

    # Should have exactly num_days unique dates
    assert len(dates) == num_days

    # Check that dates are consecutive from start_date
    expected_dates = set()
    for i in range(num_days):
        date = start_date.replace(day=start_date.day + i)
        expected_dates.add(date.strftime("%Y-%m-%d"))

    assert dates == expected_dates

if __name__ == "__main__":
    # Allow running the test file directly for debugging
    pytest.main([__file__, "-v"])