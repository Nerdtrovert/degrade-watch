#!/usr/bin/env python3
"""
Regression tests for Evidence Package Builder fixes.
1. Normalization of revenue-at-risk attempts
2. Latency checklist mapping for NORMAL, ELEVATED, WARNING, CRITICAL statuses
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from app.evidence_package import EvidencePackageBuilder

class TestEvidencePackageFixes(unittest.TestCase):
    def test_revenue_at_risk_normalization(self):
        builder = EvidencePackageBuilder()
        
        # Define baseline with 14 days (20,160 minutes)
        baseline = {
            "period": {"days": 14},
            "overall": {
                "attempts": 10000,
                "success_rate": 0.90,
                "average_amount": 10.0
            },
            "by_method": {
                "UPI": {
                    "attempts": 10000,
                    "success_rate": 0.90,
                    "average_amount": 10.0
                }
            }
        }
        
        # Test Case 1: Window duration is 90 minutes.
        # expected_baseline_attempts = 10000 * (90 / 20160) = 44.6428
        # expected_successful = 0.90 * 44.6428 = 40.1785
        # If current_attempts = 40, success_rate = 0.50 (20 successes)
        # expected_revenue = 40.1785 * 10 * 100 = 40178 paise (rounded)
        # actual_revenue = 20 * 10 * 100 = 20000 paise
        # revenue_at_risk_paise = max(0, 40178 - 20000) = 20178 paise
        detector_result = {
            "candidate_segment": {
                "payment_method": "UPI",
                "bank": None,
                "device": None,
                "upi_app": None
            },
            "success_rate_signal": {
                "difference": -0.10,
                "difference_percentage_points": -10.0
            },
            "window": {
                "duration_minutes": 90
            }
        }
        
        # 40 attempts, 20 success, 20 failed
        payments = []
        for i in range(20):
            payments.append({"payment_method": "UPI", "status": "success", "amount": 1000, "latency_ms": 100})
            payments.append({"payment_method": "UPI", "status": "failed", "amount": 1000, "latency_ms": 100, "error_code": "BAD_PIN"})
            
        impact = builder._build_impact_evidence(detector_result, baseline, payments)
        
        # Check normalization is correct
        self.assertAlmostEqual(impact["successful_payments"]["baseline_expected"], 40.17857142857143)
        self.assertEqual(impact["successful_payments"]["current_actual"], 20.0)
        self.assertEqual(impact["revenue_at_risk"]["paise"], 20178)

        # Test Case 2: Window duration is 180 minutes.
        # expected_baseline_attempts = 10000 * (180 / 20160) = 89.2857
        # expected_successful = 0.90 * 89.2857 = 80.3571
        # expected_revenue = 80.3571 * 10 * 100 = 80357 paise (rounded)
        # actual_revenue = 20 * 10 * 100 = 20000 paise
        # revenue_at_risk_paise = max(0, 80357 - 20000) = 60357 paise
        detector_result["window"]["duration_minutes"] = 180
        impact2 = builder._build_impact_evidence(detector_result, baseline, payments)
        
        self.assertAlmostEqual(impact2["successful_payments"]["baseline_expected"], 80.35714285714286)
        self.assertEqual(impact2["revenue_at_risk"]["paise"], 60357)

    def test_latency_checklist_mapping(self):
        builder = EvidencePackageBuilder()
        
        baseline = {
            "period": {"days": 14},
            "overall": {"attempts": 1000, "success_rate": 0.9, "average_amount": 10.0},
            "by_method": {
                "UPI": {
                    "attempts": 1000,
                    "success_rate": 0.9,
                    "average_amount": 10.0
                }
            }
        }
        payments = []

        def get_latency_check_result(lat_status):
            detector_result = {
                "candidate_segment": {
                    "payment_method": "UPI",
                    "bank": None,
                    "device": None,
                    "upi_app": None
                },
                "success_rate_signal": {
                    "statistically_significant": True,
                    "p_value": 0.001,
                    "difference": -0.10,
                    "difference_percentage_points": -10.0
                },
                "technical_error_signal": {
                    "status": "NORMAL",
                    "absolute_change": 0.0
                },
                "customer_error_signal": {
                    "absolute_change": 0.0
                },
                "localization_signal": {
                    "status": "LOCALIZED"
                },
                "volume_signal": {
                    "status": "NORMAL"
                },
                "latency_signal": {
                    "status": lat_status
                },
                "sample": {
                    "attempts": 100,
                    "sufficiency": "SUFFICIENT"
                }
            }
            checklist = builder._build_investigation_checklist(
                detector_result, baseline, payments, datetime.now(timezone.utc), datetime.now(timezone.utc)
            )
            for item in checklist:
                if item["check"] == "latency_change":
                    return item["result"]
            return None

        # Assert according to requirements:
        # NORMAL -> FAIL (latency did not change)
        # ELEVATED -> PASS (supporting evidence, safety check passed)
        # WARNING -> PASS
        # CRITICAL -> PASS
        self.assertEqual(get_latency_check_result("NORMAL"), "FAIL")
        self.assertEqual(get_latency_check_result("ELEVATED"), "PASS")
        self.assertEqual(get_latency_check_result("WARNING"), "PASS")
        self.assertEqual(get_latency_check_result("CRITICAL"), "PASS")

if __name__ == "__main__":
    unittest.main()
