#!/usr/bin/env python3
"""
Tests for scenario injection system.
"""

import json
import jsonlines
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import pytest
import sys
import hashlib
import random

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.inject_scenario import (
    load_healthy_payments,
    save_payments,
    determine_scenario_window,
    get_segment_key,
    is_in_target_segment,
    apply_scenario_a_injection,
    apply_scenario_b_injection,
    apply_scenario_c_injection,
    apply_scenario_d_injection,
    apply_scenario_e_injection,
    calculate_segment_baseline
)
from scripts.analyze_baselines import load_merchant_profile, parse_timestamp, categorize_failure

class TestScenarioInjection:
    """Test cases for scenario injection."""

    @classmethod
    def setup_class(cls):
        """Set up test fixtures."""
        cls.project_root = Path(__file__).parent.parent
        cls.generated_dir = cls.project_root / "data" / "generated"
        cls.merchant_id = "merch_upi_smb"

        # Load test data
        cls.payments = load_healthy_payments(cls.merchant_id, cls.generated_dir)
        assert len(cls.payments) > 0, "No test payments available"

        cls.merchant_profile = load_merchant_profile(cls.merchant_id)
        cls.window_start, cls.window_end = determine_scenario_window(cls.merchant_id, cls.payments, 1.5)

    def test_load_healthy_payments(self):
        """Test loading healthy payments."""
        payments = load_healthy_payments(self.merchant_id, self.generated_dir)
        assert isinstance(payments, list)
        assert len(payments) > 0
        assert "payment_id" in payments[0]
        assert "timestamp" in payments[0]
        assert "status" in payments[0]

    def test_determine_scenario_window(self):
        """Test scenario window determination."""
        window_start, window_end = determine_scenario_window(
            self.merchant_id, self.payments, 1.5
        )

        assert isinstance(window_start, datetime)
        assert isinstance(window_end, datetime)
        assert window_end > window_start
        assert (window_end - window_start).total_seconds() == 1.5 * 3600

        # Window should be within data bounds
        timestamps = [parse_timestamp(p["timestamp"]) for p in self.payments]
        assert window_start >= min(timestamps)
        assert window_end <= max(timestamps)

    def test_get_segment_key(self):
        """Test segment key generation."""
        # UPI payment
        upi_payment = {
            "payment_method": "UPI",
            "bank": "BANK_X",
            "device": "ANDROID",
            "upi_app": "PHONEPE"
        }
        key = get_segment_key(upi_payment)
        assert key == "UPI|BANK_X|ANDROID|PHONEPE"

        # CARD payment
        card_payment = {
            "payment_method": "CARD",
            "device": "ANDROID"
        }
        key = get_segment_key(card_payment)
        assert key == "CARD|ANDROID"

    def test_is_in_target_segment(self):
        """Test segment membership checking."""
        target_segment = {
            "payment_method": "UPI",
            "bank": "BANK_X",
            "device": "ANDROID",
            "upi_app": "PHONEPE"
        }

        # Matching payment
        matching_payment = {
            "payment_method": "UPI",
            "bank": "BANK_X",
            "device": "ANDROID",
            "upi_app": "PHONEPE",
            "status": "success"
        }
        assert is_in_target_segment(matching_payment, target_segment) == True

        # Non-matching payment (wrong bank)
        non_matching_payment = {
            "payment_method": "UPI",
            "bank": "HDFC",
            "device": "ANDROID",
            "upi_app": "PHONEPE",
            "status": "success"
        }
        assert is_in_target_segment(non_matching_payment, target_segment) == False

        # Non-matching payment (wrong method)
        wrong_method_payment = {
            "payment_method": "CARD",
            "bank": "BANK_X",
            "device": "ANDROID",
            "upi_app": None,
            "status": "success"
        }
        assert is_in_target_segment(wrong_method_payment, target_segment) == False

    def test_calculate_segment_baseline(self):
        """Test segment baseline calculation."""
        # Use a small window for testing
        test_start = self.window_start
        test_end = self.window_start + timedelta(minutes=10)

        # Test overall segment (no target)
        overall_stats = calculate_segment_baseline(
            self.payments, test_start, test_end, None, self.merchant_profile
        )
        assert "attempts" in overall_stats
        assert "success_rate" in overall_stats
        assert 0 <= overall_stats["success_rate"] <= 1

        # Test UPI segment
        upi_segment = {
            "payment_method": "UPI",
            "bank": None,
            "device": None,
            "upi_app": None
        }
        upi_stats = calculate_segment_baseline(
            self.payments, test_start, test_end, upi_segment, self.merchant_profile
        )
        assert upi_stats["attempts"] >= 0
        assert upi_stats["success_rate"] >= 0

    def test_apply_scenario_a_injection(self):
        """Test Scenario A injection."""
        # Use a subset of payments for faster testing
        window_payments = [
            p for p in self.payments
            if self.window_start <= parse_timestamp(p["timestamp"]) < self.window_end
        ][:100]  # Limit to 100 payments for speed

        if len(window_payments) == 0:
            pytest.skip("No payments in test window")

        # Apply injection
        modified_payments, stats = apply_scenario_a_injection(
            window_payments, self.window_start, self.window_end, self.merchant_profile
        )

        assert isinstance(modified_payments, list)
        assert len(modified_payments) == len(window_payments)
        assert isinstance(stats, dict)
        assert "modified" in stats

        # Check that some payments were modified
        if stats["modified"] > 0:
            # Verify modified payments have correct changes
            modified_count = 0
            for orig, mod in zip(window_payments, modified_payments):
                if orig["status"] != mod["status"] or orig.get("error_code") != mod.get("error_code"):
                    modified_count += 1
                    # Check that success was converted to failure
                    if orig["status"] == "success" and mod["status"] == "failed":
                        assert mod.get("error_code") is not None
                        assert mod["latency_ms"] >= orig["latency_ms"]  # Latency should increase

            assert modified_count == stats["modified"]

    def test_apply_scenario_b_injection(self):
        """Test Scenario B injection."""
        # Use a subset of payments for faster testing
        window_payments = [
            p for p in self.payments
            if self.window_start <= parse_timestamp(p["timestamp"]) < self.window_end
        ][:100]

        if len(window_payments) == 0:
            pytest.skip("No payments in test window")

        # Apply injection
        modified_payments, stats = apply_scenario_b_injection(
            window_payments, self.window_start, self.window_end, self.merchant_profile
        )

        assert isinstance(modified_payments, list)
        assert len(modified_payments) == len(window_payments)
        assert isinstance(stats, dict)
        assert "modified" in stats

    def test_apply_scenario_c_injection(self):
        """Test Scenario C injection."""
        # Use a subset of payments for faster testing
        window_payments = [
            p for p in self.payments
            if self.window_start <= parse_timestamp(p["timestamp"]) < self.window_end
        ][:100]

        if len(window_payments) == 0:
            pytest.skip("No payments in test window")

        # Apply injection
        modified_payments, stats = apply_scenario_c_injection(
            window_payments, self.window_start, self.window_end, self.merchant_profile
        )

        assert isinstance(modified_payments, list)
        assert len(modified_payments) == len(window_payments)
        assert isinstance(stats, dict)
        assert "modified" in stats

    def test_apply_scenario_d_injection(self):
        """Test Scenario D injection."""
        # Use a subset of payments for faster testing
        window_payments = [
            p for p in self.payments
            if self.window_start <= parse_timestamp(p["timestamp"]) < self.window_end
        ][:100]

        if len(window_payments) == 0:
            pytest.skip("No payments in test window")

        # Apply injection
        modified_payments, stats = apply_scenario_d_injection(
            window_payments, self.window_start, self.window_end, self.merchant_profile
        )

        assert isinstance(modified_payments, list)
        assert len(modified_payments) == len(window_payments)
        assert isinstance(stats, dict)
        assert "modified" in stats

    def test_apply_scenario_e_injection(self):
        """Test Scenario E injection."""
        # Use a subset of payments for faster testing
        window_payments = [
            p for p in self.payments
            if self.window_start <= parse_timestamp(p["timestamp"]) < self.window_end
        ][:100]

        if len(window_payments) == 0:
            pytest.skip("No payments in test window")

        # Apply injection
        modified_payments, stats = apply_scenario_e_injection(
            window_payments, self.window_start, self.window_end, self.merchant_profile
        )

        assert isinstance(modified_payments, list)
        assert len(modified_payments) == len(window_payments)
        assert isinstance(stats, dict)
        assert "modified" in stats

    def test_deterministic_seeds(self):
        """Test that same seed produces same output."""
        window_payments = [
            p for p in self.payments
            if self.window_start <= parse_timestamp(p["timestamp"]) < self.window_end
        ][:50]

        if len(window_payments) == 0:
            pytest.skip("No payments in test window")

        # Apply injection twice with same parameters
        modified_payments1, stats1 = apply_scenario_a_injection(
            window_payments, self.window_start, self.window_end, self.merchant_profile
        )

        modified_payments2, stats2 = apply_scenario_a_injection(
            window_payments, self.window_start, self.window_end, self.merchant_profile
        )

        # Should be identical
        assert json.dumps(modified_payments1, sort_keys=True) == json.dumps(modified_payments2, sort_keys=True)
        assert stats1 == stats2

    def test_immutable_fields(self):
        """Test that immutable fields are not changed."""
        window_payments = [
            p for p in self.payments
            if self.window_start <= parse_timestamp(p["timestamp"]) < self.window_end
        ][:50]

        if len(window_payments) == 0:
            pytest.skip("No payments in test window")

        # Apply injection
        modified_payments, stats = apply_scenario_a_injection(
            window_payments, self.window_start, self.window_end, self.merchant_profile
        )

        # Check that immutable fields are preserved
        for orig, mod in zip(window_payments, modified_payments):
            assert orig["payment_id"] == mod["payment_id"]
            assert orig["order_id"] == mod["order_id"]
            assert orig["merchant_id"] == mod["merchant_id"]
            assert orig["timestamp"] == mod["timestamp"]
            assert orig["amount"] == mod["amount"]
            assert orig["currency"] == mod["currency"]
            # payment_method, bank, device, upi_app should be unchanged unless scenario specifically modifies them
            # For Scenario A, these should NOT be changed
            assert orig["payment_method"] == mod["payment_method"]
            assert orig["bank"] == mod["bank"]
            assert orig["device"] == mod["device"]
            assert orig["upi_app"] == mod["upi_app"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])