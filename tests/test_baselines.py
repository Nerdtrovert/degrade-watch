"""
Tests for the baseline analysis module.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pytest

# Add the project root to the path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from scripts.analyze_baselines import (
    load_merchant_profile,
    parse_timestamp,
    categorize_failure,
    calculate_statistics,
    calculate_percentiles,
    generate_baseline_for_merchant
)

def test_load_merchant_profile():
    """Test that we can load a merchant profile."""
    profile = load_merchant_profile("merch_large_ecom")
    assert profile["merchant_id"] == "merch_large_ecom"
    assert profile["name"] == "Large E-commerce"
    assert "method_distribution" in profile

def test_parse_timestamp():
    """Test timestamp parsing."""
    # Test UTC timestamp
    ts = "2026-08-20T12:30:45Z"
    dt = parse_timestamp(ts)
    assert dt.year == 2026
    assert dt.month == 8
    assert dt.day == 20
    assert dt.hour == 12
    assert dt.minute == 30
    assert dt.second == 45
    assert dt.tzinfo is not None

def test_categorize_failure():
    """Test failure categorization."""
    assert categorize_failure("INSUFFICIENT_FUNDS") == "customer_caused"
    assert categorize_failure("WRONG_PIN") == "customer_caused"
    assert categorize_failure("OTP_FAILED") == "customer_caused"
    assert categorize_failure("USER_CANCELLED") == "customer_caused"
    assert categorize_failure("UPI_TIMEOUT") == "technical"
    assert categorize_failure("BANK_TECHNICAL_ERROR") == "technical"
    assert categorize_failure("GATEWAY_ERROR") == "technical"
    assert categorize_failure("NETWORK_ERROR") == "technical"
    assert categorize_failure("UNKNOWN_ERROR") == "other"
    assert categorize_failure(None) == "none"

def test_calculate_statistics():
    """Test statistics calculation."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    stats = calculate_statistics(values)
    assert stats["mean"] == 3.0
    assert stats["median"] == 3.0
    assert stats["stddev"] == pytest.approx(1.581, abs=0.001)
    assert stats["min"] == 1.0
    assert stats["max"] == 5.0
    assert stats["count"] == 5

    # Test empty list
    empty_stats = calculate_statistics([])
    assert empty_stats["mean"] is None
    assert empty_stats["median"] is None
    assert empty_stats["stddev"] == 0.0
    assert empty_stats["min"] is None
    assert empty_stats["max"] is None
    assert empty_stats["count"] == 0

def test_calculate_percentiles():
    """Test percentile calculation."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    percentiles = calculate_percentiles(values, [50, 90, 95])
    assert percentiles["p50"] == 5.5  # Median of even list
    assert percentiles["p90"] == 9.1  # 90th percentile
    assert percentiles["p95"] == 9.55 # 95th percentile

    # Test empty list
    empty_percentiles = calculate_percentiles([], [50, 90])
    assert empty_percentiles["p50"] is None
    assert empty_percentiles["p90"] is None

def test_generate_baseline_for_merchant():
    """Test baseline generation with sample data."""
    # Create sample payment data
    sample_payments = [
        {
            "payment_id": "pay_001",
            "merchant_id": "merch_upi_smb",
            "timestamp": "2026-08-20T12:00:00Z",
            "amount": 10000,  # ₹100 in paise
            "currency": "INR",
            "payment_method": "UPI",
            "bank": "BANK_X",
            "device": "ANDROID",
            "upi_app": "PHONEPE",
            "status": "success",
            "error_code": None,
            "order_id": "order_001",
            "latency_ms": 200
        },
        {
            "payment_id": "pay_002",
            "merchant_id": "merch_upi_smb",
            "timestamp": "2026-08-20T12:05:00Z",
            "amount": 25000,  # ₹250 in paise
            "currency": "INR",
            "payment_method": "UPI",
            "bank": "BANK_X",
            "device": "ANDROID",
            "upi_app": "PHONEPE",
            "status": "failed",
            "error_code": "INSUFFICIENT_FUNDS",
            "order_id": "order_002",
            "latency_ms": 100
        },
        {
            "payment_id": "pay_003",
            "merchant_id": "merch_upi_smb",
            "timestamp": "2026-08-20T13:00:00Z",
            "amount": 5000,   # ₹50 in paise
            "currency": "INR",
            "payment_method": "CARD",
            "bank": None,
            "device": "IOS",
            "upi_app": None,
            "status": "success",
            "error_code": None,
            "order_id": "order_003",
            "latency_ms": 150
        }
    ]

    baseline = generate_baseline_for_merchant("merch_upi_smb", sample_payments)

    # Check overall stats
    assert baseline["merchant_id"] == "merch_upi_smb"
    assert baseline["overall"]["attempts"] == 3
    assert baseline["overall"]["successes"] == 2
    assert baseline["overall"]["failures"] == 1
    assert baseline["overall"]["success_rate"] == 2/3
    assert baseline["overall"]["average_amount"] == pytest.approx(133.33, abs=0.01)  # (100+250+50)/3 / 100

    # Check method breakdown
    assert "UPI" in baseline["by_method"]
    assert baseline["by_method"]["UPI"]["attempts"] == 2
    assert baseline["by_method"]["UPI"]["successes"] == 1
    assert baseline["by_method"]["UPI"]["success_rate"] == 0.5

    assert "CARD" in baseline["by_method"]
    assert baseline["by_method"]["CARD"]["attempts"] == 1
    assert baseline["by_method"]["CARD"]["successes"] == 1
    assert baseline["by_method"]["CARD"]["success_rate"] == 1.0

    # Check segments
    # UPI|BANK_X|ANDROID|PHONEPE should exist
    upi_segment_key = "UPI|BANK_X|ANDROID|PHONEPE"
    assert upi_segment_key in baseline["segments"]
    upi_segment = baseline["segments"][upi_segment_key]
    assert upi_segment["attempts"] == 2
    assert upi_segment["successes"] == 1
    assert upi_segment["failure_breakdown"]["customer_caused"] == 1

    # CARD|IOS|None should exist (since bank and upi_app are None for CARD)
    # Let's check what segment keys were actually created
    segment_keys = list(baseline["segments"].keys())
    card_segments = [k for k in segment_keys if k.startswith("CARD|")]
    assert len(card_segments) > 0

if __name__ == "__main__":
    # Allow running the test file directly for debugging
    pytest.main([__file__, "-v"])