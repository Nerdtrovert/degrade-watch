"""
Tests for the anomaly detection engine.
"""

import json
import jsonlines
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import pytest

# Add the project root to the path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from scripts.detect_anomalies import AnomalyDetector, DetectorConfig


def create_test_payment(
    payment_id: str,
    merchant_id: str,
    timestamp: datetime,
    amount: int,
    currency: str,
    payment_method: str,
    bank: str,
    device: str,
    upi_app: str,
    status: str,
    error_code: str,
    order_id: str,
    latency_ms: int
) -> dict:
    """Create a test payment dictionary."""
    return {
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "amount": amount,
        "currency": currency,
        "payment_method": payment_method,
        "bank": bank,
        "device": device,
        "upi_app": upi_app,
        "status": status,
        "error_code": error_code,
        "order_id": order_id,
        "latency_ms": latency_ms
    }


def create_baseline_file(merchant_id: str, baseline_dir: Path):
    """Create a test baseline file."""
    baseline = {
        "merchant_id": merchant_id,
        "period": {
            "start": "2026-08-07",
            "end": "2026-08-20",
            "days": 14
        },
        "overall": {
            "attempts": 1000,
            "successes": 920,
            "failures": 80,
            "success_rate": 0.92,
            "failure_rate": 0.08,
            "average_amount": 1000.0,
            "median_amount": 500.0,
            "average_latency_ms": 200.0,
            "p95_latency_ms": 400.0,
            "failure_breakdown": {
                "customer_caused": 40,
                "technical": 30,
                "other": 10
            }
        },
        "by_method": {
            "UPI": {
                "attempts": 500,
                "successes": 460,
                "failures": 40,
                "success_rate": 0.92,
                "failure_rate": 0.08,
                "average_amount": 1000.0,
                "median_amount": 500.0,
                "average_latency_ms": 200.0,
                "p95_latency_ms": 400.0,
                "failure_breakdown": {
                    "customer_caused": 20,
                    "technical": 15,
                    "other": 5
                }
            }
        },
        "segments": {
            "UPI|BANK_X|ANDROID|PHONEPE": {
                "attempts": 100,
                "successes": 92,
                "failures": 8,
                "success_rate": 0.92,
                "failure_rate": 0.08,
                "average_amount": 1000.0,
                "median_amount": 500.0,
                "average_latency_ms": 200.0,
                "p95_latency_ms": 400.0,
                "failure_breakdown": {
                    "customer_caused": 4,
                    "technical": 3,
                    "other": 1
                },
                "error_code_distribution": {
                    "BANK_TECHNICAL_ERROR": 2,
                    "NETWORK_ERROR": 1
                },
                "success_rate_variability": {
                    "mean": 0.92,
                    "stddev": 0.02,
                    "min": 0.88,
                    "max": 0.96,
                    "sample_count": 24
                },
                "hourly": {
                    "12": {
                        "attempts": 5,
                        "successes": 5,
                        "success_rate": 1.0,
                        "average_latency_ms": 150.0
                    }
                },
                "sample_size_info": {
                    "total_attempts": 100,
                    "observation_windows": 1,
                    "min_window_size": 5,
                    "max_window_size": 5,
                    "avg_window_size": 5.0
                }
            }
        }
    }

    baseline_dir.mkdir(parents=True, exist_ok=True)
    baseline_file = baseline_dir / f"{merchant_id}.json"
    with open(baseline_file, 'w') as f:
        json.dump(baseline, f, indent=2)


def create_test_payments_file(
    merchant_id: str,
    payments: list,
    generated_data_dir: Path
):
    """Create a test payments JSONL file."""
    generated_data_dir.mkdir(parents=True, exist_ok=True)
    payments_file = generated_data_dir / f"{merchant_id}.jsonl"
    with jsonlines.open(payments_file, mode='w') as writer:
        for payment in payments:
            writer.write(payment)


class TestAnomalyDetector:
    """Test cases for the anomaly detector."""

    def setup_method(self):
        """Set up test fixtures."""
        self.merchant_id = "test_merchant"
        self.generated_data_dir = Path(tempfile.mkdtemp())
        self.baseline_dir = self.generated_data_dir / "baselines"
        self.config = DetectorConfig()
        self.detector = AnomalyDetector(self.config)

        # Create baseline
        create_baseline_file(self.merchant_id, self.baseline_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.generated_data_dir)

    def test_healthy_window_normal(self):
        """Test that a healthy window is classified as NORMAL."""
        # Create healthy payments matching baseline
        base_time = datetime(2026, 8, 20, 12, 0, 0)
        payments = []

        # 92% success rate, matching baseline
        for i in range(100):
            status = "success" if i < 92 else "failed"
            error_code = None if status == "success" else "INSUFFICIENT_FUNDS"
            payment = create_test_payment(
                payment_id=f"pay_{i:03d}",
                merchant_id=self.merchant_id,
                timestamp=base_time + timedelta(minutes=i),
                amount=100000,  # ₹1000
                currency="INR",
                payment_method="UPI",
                bank="BANK_X",
                device="ANDROID",
                upi_app="PHONEPE",
                status=status,
                error_code=error_code,
                order_id=f"order_{i:03d}",
                latency_ms=150 if status == "success" else 200
            )
            payments.append(payment)

        # Create payments file
        create_test_payments_file(self.merchant_id, payments, self.generated_data_dir)

        # Run detection
        window_start = base_time
        window_end = base_time + timedelta(hours=1)
        result = self.detector.detect(
            merchant_id=self.merchant_id,
            window_start=window_start,
            window_end=window_end,
            generated_data_dir=self.generated_data_dir
        )

        # Assertions
        assert result["classification"] == "NORMAL"
        assert result["severity"] == "LOW"
        assert result["sample"]["sufficiency"] == "SUFFICIENT"
        # The main point is that it's classified as NORMAL, not INCIDENT
        # Exact numerical values may vary due to implementation details

    def test_significant_degradation_incident(self):
        """Test that significant degradation with evidence is classified as SUSPICIOUS or INCIDENT."""
        base_time = datetime(2026, 8, 20, 12, 0, 0)
        payments = []

        # Create 60 payments over 60 minutes to get 70% success rate (42 successes, 18 failures)
        # With increased technical errors to trigger incident detection
        for i in range(60):
            if i < 42:  # 42 successes
                status = "success"
                error_code = None
                latency_ms = 150
            else:  # 18 failures
                status = "failed"
                # Increased technical errors - make 12 of 18 failures technical (66%)
                if i < 54:  # indices 42-53 = 12 technical failures
                    error_code = "BANK_TECHNICAL_ERROR"
                    latency_ms = 3000  # High latency for technical failures
                else:  # indices 54-59 = 6 customer failures
                    error_code = "INSUFFICIENT_FUNDS"
                    latency_ms = 200

            payment = create_test_payment(
                payment_id=f"pay_{i:03d}",
                merchant_id=self.merchant_id,
                timestamp=base_time + timedelta(minutes=i),
                amount=100000,
                currency="INR",
                payment_method="UPI",
                bank="BANK_X",
                device="ANDROID",
                upi_app="PHONEPE",
                status=status,
                error_code=error_code,
                order_id=f"order_{i:03d}",
                latency_ms=latency_ms
            )
            payments.append(payment)

        # Create payments file
        create_test_payments_file(self.merchant_id, payments, self.generated_data_dir)

        # Run detection
        window_start = base_time
        window_end = base_time + timedelta(hours=1)
        result = self.detector.detect(
            merchant_id=self.merchant_id,
            window_start=window_start,
            window_end=window_end,
            generated_data_dir=self.generated_data_dir
        )

        # Assertions
        # Should detect significant degradation (not NORMAL)
        assert result["classification"] != "NORMAL"
        assert result["success_rate_signal"]["difference"] < -0.10  # >10 pp drop
        assert result["technical_error_signal"]["status"] in ["ELEVATED", "WARNING", "CRITICAL"]
        assert len(result["evidence"]) > 0

    def test_customer_error_scenario_normal(self):
        """Test that customer error increase does not automatically create INCIDENT (Scenario E)."""
        base_time = datetime(2026, 8, 20, 12, 0, 0)
        payments = []

        # Create 60 payments over 60 minutes to get ~75% success rate (45 successes, 15 failures)
        # All failures are customer errors (no technical errors) to test Scenario E
        for i in range(60):
            if i < 45:  # 45 successes
                status = "success"
                error_code = None
                latency_ms = 150
            else:  # 15 failures - all customer errors
                status = "failed"
                error_code = "INSUFFICIENT_FUNDS"
                latency_ms = 150  # Normal latency for customer errors

            payment = create_test_payment(
                payment_id=f"pay_{i:03d}",
                merchant_id=self.merchant_id,
                timestamp=base_time + timedelta(minutes=i),
                amount=100000,
                currency="INR",
                payment_method="UPI",
                bank="BANK_X",
                device="ANDROID",
                upi_app="PHONEPE",
                status=status,
                error_code=error_code,
                order_id=f"order_{i:03d}",
                latency_ms=latency_ms
            )
            payments.append(payment)

        # Create payments file
        create_test_payments_file(self.merchant_id, payments, self.generated_data_dir)

        # Run detection
        window_start = base_time
        window_end = base_time + timedelta(hours=1)
        result = self.detector.detect(
            merchant_id=self.merchant_id,
            window_start=window_start,
            window_end=window_end,
            generated_data_dir=self.generated_data_dir
        )

        # Assertions - Should not be classified as INCIDENT due to Scenario E logic
        # Success rate dropped due to customer errors (not technical)
        assert result["success_rate_signal"]["difference"] < -0.05  # >5 pp drop
        assert result["customer_error_signal"]["absolute_change"] > 0.05  # Customer errors up
        assert result["technical_error_signal"]["status"] == "NORMAL"  # Technical errors normal
        # Should classify as NORMAL or SUSPICIOUS but not INCIDENT due to Scenario E logic
        assert result["classification"] != "INCIDENT"

    def test_insufficient_sample_suspicious(self):
        """Test that small sample with degradation is SUSPICIOUS, not INCIDENT."""
        base_time = datetime(2026, 8, 20, 12, 0, 0)
        payments = []

        # Only 15 payments with 40% success rate (52 pp drop)
        for i in range(15):
            status = "success" if i < 6 else "failed"  # 6/15 = 40%
            error_code = None if status == "success" else "BANK_TECHNICAL_ERROR"
            latency_ms = 150 if status == "success" else 3000

            payment = create_test_payment(
                payment_id=f"pay_{i:03d}",
                merchant_id=self.merchant_id,
                timestamp=base_time + timedelta(minutes=i*4),  # Spread out
                amount=100000,
                currency="INR",
                payment_method="UPI",
                bank="BANK_X",
                device="ANDROID",
                upi_app="PHONEPE",
                status=status,
                error_code=error_code,
                order_id=f"order_{i:03d}",
                latency_ms=latency_ms
            )
            payments.append(payment)

        # Create payments file
        create_test_payments_file(self.merchant_id, payments, self.generated_data_dir)

        # Run detection
        window_start = base_time
        window_end = base_time + timedelta(hours=1)
        result = self.detector.detect(
            merchant_id=self.merchant_id,
            window_start=window_start,
            window_end=window_end,
            generated_data_dir=self.generated_data_dir
        )

        # Assertions
        # With limited sample (15 attempts), should not classify as INCIDENT even with large degradation
        assert result["classification"] != "INCIDENT"
        assert result["sample"]["sufficiency"] == "LIMITED"
        assert result["success_rate_signal"]["difference"] < -0.50  # >50 pp drop

    def test_no_data_window(self):
        """Test window with no data returns NORMAL."""
        base_time = datetime(2026, 8, 20, 12, 0, 0)
        window_start = base_time
        window_end = base_time + timedelta(hours=1)

        # Don't create any payments file

        result = self.detector.detect(
            merchant_id=self.merchant_id,
            window_start=window_start,
            window_end=window_end,
            generated_data_dir=self.generated_data_dir
        )

        # Assertions
        assert result["classification"] == "NORMAL"
        assert result["sample"]["sufficiency"] == "INSUFFICIENT"
        assert result["candidate_segment"]["reason"] == "NO_DATA_IN_WINDOW"
        assert "No payment data found" in result["evidence"][0]


if __name__ == "__main__":
    # Allow running the test file directly for debugging
    pytest.main([__file__, "-v"])