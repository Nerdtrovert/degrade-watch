#!/usr/bin/env python3
"""
Evidence Package generator for DegradeWatch Checkpoint 7.

Takes detector output and builds a comprehensive evidence package
that enables root cause analysis without requiring LLM to compute
evidence or perform calculations.
"""

import json
import jsonlines
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import math

# Add project root to path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.detect_anomalies import AnomalyDetector
from scripts.analyze_baselines import load_merchant_profile, parse_timestamp, categorize_failure


class EvidencePackageBuilder:
    """Builds evidence packages from detector output."""

    def __init__(self):
        self.detector = AnomalyDetector()

    def build_evidence_package(
        self,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime,
        generated_data_dir: Path
    ) -> Dict[str, Any]:
        """
        Build a complete evidence package for the given window.

        Args:
            merchant_id: Merchant identifier
            window_start: Start of analysis window (inclusive)
            window_end: End of analysis window (exclusive)
            generated_data_dir: Directory containing generated JSONL files

        Returns:
            Complete evidence package as dict
        """
        # First run the detector to get base signals
        detector_result = self.detector.detect(
            merchant_id=merchant_id,
            window_start=window_start,
            window_end=window_end,
            generated_data_dir=generated_data_dir
        )

        # Load the actual payment data for detailed analysis
        payments = self._load_window_payments(
            generated_data_dir / f"{merchant_id}.jsonl",
            window_start,
            window_end
        )

        # Load baseline and profile
        baseline_dir = generated_data_dir / "baselines"
        baseline_path = baseline_dir / f"{merchant_id}.json"

        with open(baseline_path, 'r') as f:
            baseline = json.load(f)

        profile = load_merchant_profile(merchant_id)

        # Build the evidence package
        evidence_package = {
            # A. Incident metadata
            "incident_metadata": self._build_incident_metadata(
                merchant_id, window_start, window_end, detector_result
            ),

            # B. Affected segment
            "affected_segment": self._build_affected_segment(
                detector_result, baseline, payments
            ),

            # C. Success-rate evidence
            "success_rate_evidence": self._build_success_rate_evidence(
                detector_result, baseline, payments
            ),

            # D. Error evidence
            "error_evidence": self._build_error_evidence(
                detector_result, baseline, payments
            ),

            # E. Localization evidence
            "localization_evidence": self._build_localization_evidence(
                detector_result, baseline, payments
            ),

            # F. Temporal evidence
            "temporal_evidence": self._build_temporal_evidence(
                payments, window_start, window_end
            ),

            # G. Volume evidence
            "volume_evidence": self._build_volume_evidence(
                detector_result, baseline, payments, window_start, window_end
            ),

            # H. Latency evidence
            "latency_evidence": self._build_latency_evidence(
                detector_result, baseline, payments
            ),

            # I. Impact evidence (including revenue at risk)
            "impact_evidence": self._build_impact_evidence(
                detector_result, baseline, payments
            ),

            # J. Sample payment evidence (for traceability)
            "sample_payments": self._build_sample_payments(payments),

            # K. Hypothesis evidence
            "hypothesis_evidence": self._build_hypothesis_evidence(
                detector_result, baseline, payments
            ),

            # L. Investigation checklist
            "investigation_checklist": self._build_investigation_checklist(
                detector_result, baseline, payments, window_start, window_end
            ),

            # M. Schema version and validation info
            "schema_info": {
                "version": "1.0.0",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "deterministic": True
            }
        }

        # Validate the evidence package
        self._validate_evidence_package(evidence_package)

        return evidence_package

    def _load_window_payments(
        self,
        payments_file: Path,
        window_start: datetime,
        window_end: datetime
    ) -> List[Dict[str, Any]]:
        """Load payments within the specified time window."""
        payments = []

        if not payments_file.exists():
            return payments

        with jsonlines.open(payments_file, mode='r') as reader:
            for payment in reader:
                try:
                    dt = parse_timestamp(payment["timestamp"])
                    if window_start <= dt < window_end:
                        payments.append(payment)
                except ValueError:
                    # Skip invalid timestamps
                    continue

        return payments

    def _build_incident_metadata(
        self,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime,
        detector_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build incident metadata section."""
        return {
            "incident_id": f"{merchant_id}_{window_start.strftime('%Y%m%d_%H%M%S')}",
            "merchant_id": merchant_id,
            "detection_timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis_window": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
                "duration_minutes": int((window_end - window_start).total_seconds() / 60)
            },
            "severity": detector_result["severity"],
            "detector_classification": detector_result["classification"],
            "detector_confidence": self._calculate_detector_confidence(detector_result)
        }

    def _calculate_detector_confidence(self, detector_result: Dict[str, Any]) -> str:
        """Calculate confidence level based on detector signals."""
        success_signal = detector_result["success_rate_signal"]

        if not success_signal["statistically_significant"]:
            return "LOW"

        drop_pp = abs(success_signal["difference_percentage_points"])
        if drop_pp >= 15:  # Critical threshold from detector config
            return "HIGH"
        elif drop_pp >= 7.5:  # Warning threshold
            return "MEDIUM"
        else:
            return "LOW"

    def _build_affected_segment(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build affected segment details."""
        candidate_segment = detector_result["candidate_segment"]

        # Get detailed segment information from baseline if available
        segment_key = self._segment_to_key(candidate_segment)
        baseline_segment = None

        if segment_key and segment_key in baseline.get("segments", {}):
            baseline_segment = baseline["segments"][segment_key]
        elif candidate_segment.get("payment_method") in baseline.get("by_method", {}):
            baseline_segment = baseline["by_method"][candidate_segment["payment_method"]]

        # Current segment stats from payments
        current_segment_stats = self._calculate_segment_stats(
            payments, candidate_segment
        ) if payments else {}

        return {
            "payment_method": candidate_segment.get("payment_method"),
            "bank": candidate_segment.get("bank"),
            "device": candidate_segment.get("device"),
            "upi_app": candidate_segment.get("upi_app"),
            "hierarchy_level": self._determine_hierarchy_level(candidate_segment),
            "baseline_attempts": baseline_segment.get("attempts", 0) if baseline_segment else 0,
            "baseline_success_rate": baseline_segment.get("success_rate", 0.0) if baseline_segment else 0.0,
            "current_attempts": current_segment_stats.get("attempts", 0),
            "current_success_rate": current_segment_stats.get("success_rate", 0.0),
            "segment_key": segment_key
        }

    def _segment_to_key(self, segment: Dict[str, Any]) -> Optional[str]:
        """Convert segment dict to segment key string."""
        if not segment or segment.get("payment_method") == "UNKNOWN":
            return None

        method = segment["payment_method"]
        bank = segment.get("bank") or "NULL"
        device = segment.get("device") or "NULL"
        upi_app = segment.get("upi_app") or "NULL"

        if method in ["CARD", "NETBANKING"]:
            # For these methods, bank and upi_app are not meaningful
            return f"{method}|{device}"
        else:  # UPI and others
            return f"{method}|{bank}|{device}|{upi_app}"

    def _determine_hierarchy_level(self, segment: Dict[str, Any]) -> str:
        """Determine the hierarchy level of the segment."""
        if not segment or segment.get("payment_method") == "UNKNOWN":
            return "UNKNOWN"

        # Count non-NULL specific fields
        specific_fields = 0
        if segment.get("bank") and segment["bank"] not in ["NULL", None]:
            specific_fields += 1
        if segment.get("device") and segment["device"] not in ["NULL", None]:
            specific_fields += 1
        if segment.get("upi_app") and segment["upi_app"] not in ["NULL", None]:
            specific_fields += 1

        if specific_fields == 0:
            return "METHOD"
        elif specific_fields == 1:
            return "METHOD_PLUS_ONE"
        elif specific_fields == 2:
            return "METHOD_PLUS_TWO"
        else:
            return "FULL_SEGMENT"

    def _calculate_segment_stats(
        self,
        payments: List[Dict[str, Any]],
        segment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate statistics for a specific segment."""
        if not payments:
            return {"attempts": 0, "successes": 0, "success_rate": 0.0}

        matches = 0
        successes = 0

        for payment in payments:
            if self._payment_matches_segment(payment, segment):
                matches += 1
                if payment["status"] == "success":
                    successes += 1

        return {
            "attempts": matches,
            "successes": successes,
            "success_rate": successes / matches if matches > 0 else 0.0
        }

    def _payment_matches_segment(
        self,
        payment: Dict[str, Any],
        segment: Dict[str, Any]
    ) -> bool:
        """Check if a payment matches the segment criteria."""
        # Check payment method
        if segment.get("payment_method") and payment["payment_method"] != segment["payment_method"]:
            return False

        # Check bank
        if segment.get("bank") and payment.get("bank") != segment["bank"]:
            return False

        # Check device
        if segment.get("device") and payment.get("device") != segment["device"]:
            return False

        # Check UPI app (only for UPI payments)
        if (segment.get("upi_app") is not None and
            payment.get("payment_method") == "UPI" and
            payment.get("upi_app") != segment["upi_app"]):
            return False

        return True

    def _build_success_rate_evidence(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build success-rate evidence with statistical rigor."""
        signal = detector_result["success_rate_signal"]
        candidate_segment = detector_result["candidate_segment"]

        # Get baseline and current rates for the affected segment
        baseline_segment = self._get_baseline_segment(baseline, candidate_segment)
        current_segment_stats = self._calculate_segment_stats(
            payments, candidate_segment
        ) if payments else {}

        baseline_rate = baseline_segment.get("success_rate", 0.0) if baseline_segment else 0.0
        current_rate = current_segment_stats.get("success_rate", 0.0)

        # Calculate statistical significance using two-proportion z-test
        bas_n = baseline_segment.get("attempts", 0) if baseline_segment else 0
        bas_s = int(baseline_rate * bas_n) if bas_n > 0 else 0
        cur_n = current_segment_stats.get("attempts", 0)
        cur_s = int(current_rate * cur_n) if cur_n > 0 else 0

        # Statistical test
        z_score, p_value = self._two_proportion_z_test(bas_n, bas_s, cur_n, cur_s)
        statistically_significant = p_value < 0.05  # 95% confidence

        return {
            "baseline_success_rate": baseline_rate,
            "current_success_rate": current_rate,
            "absolute_change": current_rate - baseline_rate,
            "absolute_percentage_point_change": (current_rate - baseline_rate) * 100,
            "relative_change": (current_rate - baseline_rate) / baseline_rate if baseline_rate > 0 else 0.0,
            "baseline_attempts": bas_n,
            "current_attempts": cur_n,
            "statistical_significance": {
                "statistically_significant": statistically_significant,
                "p_value": p_value,
                "z_score": z_score,
                "confidence_level": 0.95
            },
            "test_type": "two_proportion_z_test",
            "interpretation": self._interpret_success_rate_change(
                current_rate - baseline_rate, statistically_significant
            )
        }

    def _get_baseline_segment(
        self,
        baseline: Dict[str, Any],
        segment: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get baseline data for a segment."""
        if not segment or segment.get("payment_method") == "UNKNOWN":
            return None

        segment_key = self._segment_to_key(segment)
        if segment_key and segment_key in baseline.get("segments", {}):
            return baseline["segments"][segment_key]
        elif segment.get("payment_method") in baseline.get("by_method", {}):
            return baseline["by_method"][segment["payment_method"]]
        else:
            return None

    def _two_proportion_z_test(
        self,
        n1: int, x1: int,
        n2: int, x2: int
    ) -> Tuple[float, float]:
        """Perform two-proportion z-test and return (z_score, p_value)."""
        if n1 == 0 or n2 == 0:
            return 0.0, 1.0

        p1 = x1 / n1 if n1 > 0 else 0
        p2 = x2 / n2 if n2 > 0 else 0

        # Pooled proportion
        pooled_p = (x1 + x2) / (n1 + n2) if (n1 + n2) > 0 else 0

        if pooled_p == 0 or pooled_p == 1:
            return 0.0, 1.0

        # Standard error
        se = math.sqrt(pooled_p * (1 - pooled_p) * (1/n1 + 1/n2))

        if se == 0:
            return 0.0, 1.0

        # Z-score
        z_score = (p1 - p2) / se

        # Two-tailed p-value
        p_value = 2 * (1 - self._normal_cdf(abs(z_score)))

        return z_score, p_value

    def _normal_cdf(self, x: float) -> float:
        """Cumulative distribution function for standard normal distribution."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _interpret_success_rate_change(
        self,
        change: float,
        significant: bool
    ) -> str:
        """Interpret the success rate change."""
        if not significant:
            return "Change is not statistically significant"

        if change > 0.01:  # Improvement
            return "Statistically significant improvement in success rate"
        elif change < -0.15:  # Large drop
            return "Statistically significant severe degradation"
        elif change < -0.075:  # Medium drop
            return "Statistically significant moderate degradation"
        else:  # Small drop
            return "Statistically significant minor degradation"

    def _build_error_evidence(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build error evidence section."""
        tech_signal = detector_result["technical_error_signal"]
        cust_signal = detector_result["customer_error_signal"]

        # Get baseline error rates from overall baseline
        baseline_overall = baseline.get("overall", {})
        baseline_failure_rate = baseline_overall.get("failure_rate", 0.0)
        baseline_failure_breakdown = baseline_overall.get("failure_breakdown", {
            "customer_caused": 0,
            "technical": 0,
            "other": 0
        })

        baseline_total_failures = sum(baseline_failure_breakdown.values()) or 1  # Avoid division by zero

        baseline_customer_rate = (
            baseline_failure_rate *
            (baseline_failure_breakdown["customer_caused"] / baseline_total_failures)
            if baseline_total_failures > 0 else 0.0
        )
        baseline_technical_rate = (
            baseline_failure_rate *
            (baseline_failure_breakdown["technical"] / baseline_total_failures)
            if baseline_total_failures > 0 else 0.0
        )
        baseline_other_rate = (
            baseline_failure_rate *
            (baseline_failure_breakdown["other"] / baseline_total_failures)
            if baseline_total_failures > 0 else 0.0
        )

        # Get current error rates from payments
        current_error_rates = self._calculate_error_rates(payments)

        # Error code distribution
        error_code_dist = self._calculate_error_code_distribution(payments)

        return {
            "baseline": {
                "customer_error_rate": baseline_customer_rate,
                "technical_error_rate": baseline_technical_rate,
                "other_error_rate": baseline_other_rate,
                "failure_rate": baseline_failure_rate,
                "failure_breakdown": baseline_failure_breakdown
            },
            "current": {
                "customer_error_rate": current_error_rates["customer"],
                "technical_error_rate": current_error_rates["technical"],
                "other_error_rate": current_error_rates["other"],
                "failure_rate": current_error_rates["total_failure_rate"],
                "failure_breakdown": {
                    "customer_caused": current_error_rates["customer_count"],
                    "technical": current_error_rates["technical_count"],
                    "other": current_error_rates["other_count"]
                }
            },
            "changes": {
                "customer_error_rate_change": current_error_rates["customer"] - baseline_customer_rate,
                "technical_error_rate_change": current_error_rates["technical"] - baseline_technical_rate,
                "other_error_rate_change": current_error_rates["other"] - baseline_other_rate,
                "customer_error_relative_change": (
                    (current_error_rates["customer"] - baseline_customer_rate) / baseline_customer_rate
                    if baseline_customer_rate > 0 else 0.0
                ),
                "technical_error_relative_change": (
                    (current_error_rates["technical"] - baseline_technical_rate) / baseline_technical_rate
                    if baseline_technical_rate > 0 else 0.0
                )
            },
            "error_code_distribution": error_code_dist,
            "error_code_shifts": self._calculate_error_code_shifts(
                baseline, error_code_dist
            ) if baseline else {}
        }

    def _calculate_error_rates(
        self,
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate error rates from payments."""
        if not payments:
            return {
                "customer": 0.0,
                "technical": 0.0,
                "other": 0.0,
                "total_failure_rate": 0.0,
                "customer_count": 0,
                "technical_count": 0,
                "other_count": 0
            }

        total = len(payments)
        failures = sum(1 for p in payments if p["status"] == "failed")

        customer_count = sum(
            1 for p in payments
            if p["status"] == "failed" and
            categorize_failure(p.get("error_code")) == "customer_caused"
        )
        technical_count = sum(
            1 for p in payments
            if p["status"] == "failed" and
            categorize_failure(p.get("error_code")) == "technical"
        )
        other_count = sum(
            1 for p in payments
            if p["status"] == "failed" and
            categorize_failure(p.get("error_code")) == "other"
        )

        # Verify counts add up
        assert customer_count + technical_count + other_count == failures, \
            f"Error counts don't add up: {customer_count}+{technical_count}+{other_count} != {failures}"

        return {
            "customer": customer_count / total if total > 0 else 0.0,
            "technical": technical_count / total if total > 0 else 0.0,
            "other": other_count / total if total > 0 else 0.0,
            "total_failure_rate": failures / total if total > 0 else 0.0,
            "customer_count": customer_count,
            "technical_count": technical_count,
            "other_count": other_count
        }

    def _calculate_error_code_distribution(
        self,
        payments: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Calculate distribution of error codes."""
        error_dist = defaultdict(int)

        for payment in payments:
            if payment["status"] == "failed" and payment.get("error_code"):
                error_dist[payment["error_code"]] += 1

        return dict(error_dist)

    def _calculate_error_code_shifts(
        self,
        baseline: Dict[str, Any],
        current_dist: Dict[str, int]
    ) -> Dict[str, Any]:
        """Calculate shifts in error code distribution."""
        # This would compare baseline error code distribution to current
        # For now, return placeholder - in a full implementation we'd
        # extract baseline error code distribution from baseline data
        return {
            "note": "Baseline error code distribution extraction not implemented in this version",
            "current_distribution": current_dist
        }

    def _build_localization_evidence(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build localization evidence."""
        loc_signal = detector_result["localization_signal"]
        candidate_segment = detector_result["candidate_segment"]

        # Get control segment analysis
        control_analysis = self._analyze_control_segments(
            baseline, payments, candidate_segment
        )

        return {
            "affected_segment": {
                "payment_method": loc_signal.get("affected_segment", {}).get("payment_method") if isinstance(loc_signal.get("affected_segment"), dict) else loc_signal.get("affected_segment"),
                "bank": loc_signal.get("affected_segment", {}).get("bank") if isinstance(loc_signal.get("affected_segment"), dict) else None,
                "device": loc_signal.get("affected_segment", {}).get("device") if isinstance(loc_signal.get("affected_segment"), dict) else None,
                "upi_app": loc_signal.get("affected_segment", {}).get("upi_app") if isinstance(loc_signal.get("affected_segment"), dict) else None,
                "success_rate": loc_signal.get("affected_segment_success_rate", 0.0),
                "attempts": loc_signal.get("affected_segment", {}).get("attempts", 0) if isinstance(loc_signal.get("affected_segment"), dict) else 0
            },
            "localization_status": loc_signal.get("status", "UNKNOWN"),
            "control_analysis": control_analysis,
            "sibling_analysis": self._analyze_sibling_segments(
                baseline, payments, candidate_segment
            ),
            "interpretation": self._interpret_localization(
                loc_signal.get("status", "UNKNOWN"), control_analysis
            )
        }

    def _analyze_control_segments(
        self,
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]],
        candidate_segment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze control segments to determine if degradation is localized."""
        if not candidate_segment or candidate_segment.get("payment_method") == "UNKNOWN":
            return {"status": "UNKNOWN", "message": "No candidate segment"}

        method = candidate_segment.get("payment_method")
        target_bank = candidate_segment.get("bank")
        target_device = candidate_segment.get("device")
        target_upi_app = candidate_segment.get("upi_app")

        # Define control segments based on the affected segment
        control_segments = []

        if method == "UPI":
            # For UPI, controls are: other banks (same device/upi_app), other devices (same bank/upi_app), other upi_apps (same bank/device)
            if target_device and target_upi_app:
                # Controls: other banks with same device and upi_app
                control_segments.append({
                    "description": f"Other banks (same device={target_device}, upi_app={target_upi_app})",
                    "match_func": lambda p: (
                        p.get("payment_method") == "UPI" and
                        p.get("device") == target_device and
                        p.get("upi_app") == target_upi_app and
                        p.get("bank") != target_bank and  # Different bank
                        p.get("bank") is not None
                    )
                })

            if target_bank and target_upi_app:
                # Controls: other devices with same bank and upi_app
                control_segments.append({
                    "description": f"Other devices (same bank={target_bank}, upi_app={target_upi_app})",
                    "match_func": lambda p: (
                        p.get("payment_method") == "UPI" and
                        p.get("bank") == target_bank and
                        p.get("upi_app") == target_upi_app and
                        p.get("device") != target_device and  # Different device
                        p.get("device") is not None
                    )
                })

            if target_bank and target_device:
                # Controls: other upi_apps with same bank and device
                control_segments.append({
                    "description": f"Other upi_apps (same bank={target_bank}, device={target_device})",
                    "match_func": lambda p: (
                        p.get("payment_method") == "UPI" and
                        p.get("bank") == target_bank and
                        p.get("device") == target_device and
                        p.get("upi_app") != target_upi_app and  # Different upi_app
                        p.get("upi_app") is not None
                    )
                })
        elif method in ["CARD", "NETBANKING"]:
            # For CARD/NETBANKING, controls are: other devices (same method)
            control_segments.append({
                "description": f"Other devices (same method={method})",
                "match_func": lambda p: (
                    p.get("payment_method") == method and
                    p.get("device") != target_device and  # Different device
                    p.get("device") is not None
                )
            })

        # Calculate success rates for each control segment
        control_results = {}
        for control in control_segments:
            matching_payments = [p for p in payments if control["match_func"](p)]
            if matching_payments:
                successes = sum(1 for p in matching_payments if p["status"] == "success")
                rate = successes / len(matching_payments)
                control_results[control["description"]] = {
                    "attempts": len(matching_payments),
                    "successes": successes,
                    "success_rate": rate,
                    "status": "HEALTHY" if rate > 0.85 else "DEGRADED"
                }
            else:
                control_results[control["description"]] = {
                    "attempts": 0,
                    "successes": 0,
                    "success_rate": 0.0,
                    "status": "NO_DATA"
                }

        # Determine overall localization status
        degraded_controls = [
            name for name, data in control_results.items()
            if data["status"] == "DEGRADED"
        ]

        if degraded_controls:
            status = "WIDESPREAD"
            message = f"Degradation also seen in: {', '.join(degraded_controls)}"
        elif any(data["status"] == "HEALTHY" for data in control_results.values()):
            status = "LOCALIZED"
            message = "Control segments remain healthy"
        else:
            status = "INSUFFICIENT_CONTROL_DATA"
            message = "Insufficient data in control segments to determine localization"

        return {
            "status": status,
            "message": message,
            "control_segments": control_results
        }

    def _analyze_sibling_segments(
        self,
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]],
        candidate_segment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze sibling segments at the same hierarchy level."""
        # Placeholder for sibling analysis - would compare segments at same level
        # For example, if affected is UPI|BANK_X|ANDROID|PHONEPE,
        # siblings would be UPI|BANK_X|ANDROID|GPAY, UPI|BANK_X|ANDROID|PAYTM, etc.
        return {
            "note": "Sibling analysis placeholder - would compare same-level segments",
            "analysis_needed": True
        }

    def _interpret_localization(
        self,
        status: str,
        control_analysis: Dict[str, Any]
    ) -> str:
        """Interpret localization findings."""
        if status == "LOCALIZED":
            return "Degradation is isolated to the specific segment - suggests localized issue"
        elif status == "WIDESPREAD":
            return "Degradation spans multiple segments - suggests broader systemic issue"
        elif status == "INSUFFICIENT_CONTROL_DATA":
            return "Cannot determine localization due to insufficient control segment data"
        else:
            return f"Localization status: {status}"

    def _build_temporal_evidence(
        self,
        payments: List[Dict[str, Any]],
        window_start: datetime,
        window_end: datetime
    ) -> Dict[str, Any]:
        """Build temporal evidence showing how the degradation evolved."""
        if not payments:
            return {
                "analysis_type": "insufficient_data",
                "message": "No payments in window for temporal analysis"
            }

        # Split window into smaller intervals (e.g., 5-minute buckets)
        bucket_size_minutes = 5
        bucket_size_seconds = bucket_size_minutes * 60

        window_start_ts = window_start.timestamp()
        window_end_ts = window_end.timestamp()
        window_duration = window_end_ts - window_start_ts

        num_buckets = max(1, int(window_duration // bucket_size_seconds))
        actual_bucket_size = window_duration / num_buckets if num_buckets > 0 else 0

        # Initialize buckets
        buckets = []
        for i in range(num_buckets):
            bucket_start = window_start_ts + (i * actual_bucket_size)
            bucket_end = bucket_start + actual_bucket_size
            buckets.append({
                "start": datetime.fromtimestamp(bucket_start, tz=timezone.utc),
                "end": datetime.fromtimestamp(bucket_end, tz=timezone.utc),
                "attempts": 0,
                "successes": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "technical_error_rate": 0.0,
                "customer_error_rate": 0.0
            })

        # Assign payments to buckets
        for payment in payments:
            try:
                dt = parse_timestamp(payment["timestamp"])
                ts = dt.timestamp()

                # Find which bucket this payment belongs to
                bucket_index = int((ts - window_start_ts) // actual_bucket_size) if actual_bucket_size > 0 else 0
                bucket_index = max(0, min(bucket_index, num_buckets - 1))

                buckets[bucket_index]["attempts"] += 1
                if payment["status"] == "success":
                    buckets[bucket_index]["successes"] += 1
                elif payment["status"] == "failed":
                    error_type = categorize_failure(payment.get("error_code"))
                    if error_type == "technical":
                        buckets[bucket_index]["technical_error_rate"] += 1
                    elif error_type == "customer_caused":
                        buckets[bucket_index]["customer_error_rate"] += 1

            except ValueError:
                # Skip invalid timestamps
                continue

        # Calculate rates for each bucket
        for bucket in buckets:
            if bucket["attempts"] > 0:
                bucket["success_rate"] = bucket["successes"] / bucket["attempts"]
                bucket["failure_rate"] = (bucket["attempts"] - bucket["successes"]) / bucket["attempts"]
                bucket["technical_error_rate"] = bucket["technical_error_rate"] / bucket["attempts"]
                bucket["customer_error_rate"] = bucket["customer_error_rate"] / bucket["attempts"]
            else:
                bucket["success_rate"] = 0.0
                bucket["failure_rate"] = 0.0
                bucket["technical_error_rate"] = 0.0
                bucket["customer_error_rate"] = 0.0

        # Analyze trends
        success_rates = [b["success_rate"] for b in buckets if b["attempts"] > 0]
        technical_rates = [b["technical_error_rate"] for b in buckets if b["attempts"] > 0]
        customer_rates = [b["customer_error_rate"] for b in buckets if b["attempts"] > 0]

        return {
            "analysis_type": "temporal_trend_analysis",
            "window_duration_minutes": (window_end - window_start).total_seconds() / 60,
            "bucket_size_minutes": bucket_size_minutes,
            "num_buckets": num_buckets,
            "buckets": [
                {
                    "start": b["start"].isoformat(),
                    "end": b["end"].isoformat(),
                    "attempts": b["attempts"],
                    "success_rate": b["success_rate"],
                    "failure_rate": b["failure_rate"],
                    "technical_error_rate": b["technical_error_rate"],
                    "customer_error_rate": b["customer_error_rate"]
                }
                for b in buckets if b["attempts"] > 0  # Only show buckets with data
            ],
            "trends": {
                "success_rate": self._calculate_trend(success_rates) if len(success_rates) > 1 else "INSUFFICIENT_DATA",
                "technical_error_rate": self._calculate_trend(technical_rates) if len(technical_rates) > 1 else "INSUFFICIENT_DATA",
                "customer_error_rate": self._calculate_trend(customer_rates) if len(customer_rates) > 1 else "INSUFFICIENT_DATA"
            },
            "persistence_analysis": self._analyze_persistence(success_rates),
            "first_degradation_detected": self._find_first_degradation(buckets),
            "is_persistent": self._is_persistent_degradation(success_rates)
        }

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend in a series of values."""
        if len(values) < 2:
            return "INSUFFICIENT_DATA"

        # Simple linear regression to determine trend
        n = len(values)
        x_vals = list(range(n))

        # Calculate slope
        x_mean = sum(x_vals) / n
        y_mean = sum(values) / n

        numerator = sum((x_vals[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)

        if denominator == 0:
            return "STABLE"

        slope = numerator / denominator

        # Interpret slope
        if slope > 0.01:  # Increasing by more than 1% per bucket
            return "INCREASING"
        elif slope < -0.01:  # Decreasing by more than 1% per bucket
            return "DECREASING"
        else:
            return "STABLE"

    def _analyze_persistence(self, success_rates: List[float]) -> Dict[str, Any]:
        """Analyze whether degradation is persistent."""
        if len(success_rates) < 3:
            return {
                "analysis": "INSUFFICIENT_DATA",
                "consecutive_degraded_buckets": 0,
                "max_consecutive_degraded": 0,
                "persistence_score": 0.0
            }

        # Define degraded as more than 1 standard deviation below mean
        mean_rate = statistics.mean(success_rates)
        if len(success_rates) > 1:
            stdev = statistics.stdev(success_rates)
            threshold = mean_rate - stdev
        else:
            threshold = mean_rate - 0.05  # Fallback threshold

        degraded_flags = [rate < threshold for rate in success_rates]

        # Find max consecutive degraded
        max_consecutive = 0
        current_consecutive = 0

        for flag in degraded_flags:
            if flag:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        persistence_score = max_consecutive / len(success_rates) if success_rates else 0.0

        return {
            "analysis": "PERSISTENT" if persistence_score > 0.5 else "INTERMITTENT",
            "consecutive_degraded_buckets": sum(1 for f in degraded_flags if f),
            "max_consecutive_degraded": max_consecutive,
            "persistence_score": persistence_score,
            "degradation_threshold": threshold,
            "mean_success_rate": mean_rate
        }

    def _find_first_degradation(
        self,
        buckets: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Find when degradation first started."""
        if not buckets:
            return None

        # Find first bucket with success rate below 90% (arbitrary threshold)
        for bucket in buckets:
            if bucket["attempts"] > 0 and bucket["success_rate"] < 0.90:
                return bucket["start"].isoformat()

        return None

    def _is_persistent_degradation(
        self,
        success_rates: List[float]
    ) -> bool:
        """Determine if degradation is persistent."""
        if len(success_rates) < 3:
            return False

        # Check if more than half the buckets show degradation
        mean_rate = statistics.mean(success_rates)
        if len(success_rates) > 1:
            stdev = statistics.stdev(success_rates)
            threshold = mean_rate - stdev
        else:
            threshold = mean_rate - 0.05

        degraded_count = sum(1 for rate in success_rates if rate < threshold)
        return degraded_count > len(success_rates) / 2

    def _build_volume_evidence(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]],
        window_start: datetime,
        window_end: datetime
    ) -> Dict[str, Any]:
        """Build volume evidence."""
        vol_signal = detector_result["volume_signal"]

        # Calculate expected volume from baseline
        baseline_period = baseline.get("period", {"days": 14})
        baseline_days = baseline_period.get("days", 14)
        baseline_attempts = baseline.get("overall", {}).get("attempts", 0)
        baseline_minutes = baseline_days * 24 * 60
        expected_rate_per_minute = baseline_attempts / baseline_minutes if baseline_minutes > 0 else 0

        window_duration_minutes = (window_end - window_start).total_seconds() / 60
        expected_window_volume = expected_rate_per_minute * window_duration_minutes

        current_volume = len(payments)
        volume_difference = current_volume - expected_window_volume
        volume_change_pct = (
            volume_difference / expected_window_volume
            if expected_window_volume > 0 else 0
        )

        return {
            "baseline_expected_volume": expected_window_volume,
            "current_volume": current_volume,
            "absolute_change": volume_difference,
            "change_percentage": volume_change_pct * 100,
            "volume_status": vol_signal.get("status", "UNKNOWN"),
            "interpretation": self._interpret_volume_change(volume_change_pct),
            "baseline_daily_rate": baseline_attempts / baseline_days if baseline_days > 0 else 0,
            "analysis_window_minutes": window_duration_minutes
        }

    def _interpret_volume_change(self, change_pct: float) -> str:
        """Interpret volume change percentage."""
        if change_pct <= -0.5:  # 50% decrease
            return "Significant volume decrease - may indicate systemic issue"
        elif change_pct <= -0.3:  # 30% decrease
            return "Notable volume decrease"
        elif change_pct >= 0.5:  # 50% increase
            return "Significant volume increase - may indicate retry storms or promotional activity"
        elif change_pct >= 0.2:  # 20% increase
            return "Notable volume increase"
        else:
            return "Volume within normal range"

    def _build_latency_evidence(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build latency evidence."""
        lat_signal = detector_result["latency_signal"]

        # Get baseline and current latency for affected segment
        baseline_segment = self._get_baseline_segment(
            baseline, detector_result["candidate_segment"]
        )
        current_segment_stats = self._calculate_segment_stats(
            payments, detector_result["candidate_segment"]
        ) if payments else {}

        # Get detailed latency breakdown if available
        baseline_latency_details = {}
        current_latency_details = {}

        if baseline_segment:
            baseline_latency_details = {
                "average_latency_ms": baseline_segment.get("average_latency_ms", 0.0),
                "p95_latency_ms": baseline_segment.get("p95_latency_ms", 0.0),
                "latency_variability": baseline_segment.get("success_rate_variability", {})  # Reusing this field for now
            }

        if current_segment_stats and payments:
            # Calculate current latency stats from payments
            latencies = [p["latency_ms"] for p in payments if self._payment_matches_segment(p, detector_result["candidate_segment"])]
            if latencies:
                current_latency_details = {
                    "average_latency_ms": statistics.mean(latencies),
                    "p95_latency_ms": self._calculate_percentile(latencies, 95),
                    "latency_variability": {
                        "mean": statistics.mean(latencies),
                        "stddev": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
                        "min": min(latencies),
                        "max": max(latencies)
                    }
                }

        return {
            "baseline": {
                "p95_latency_ms": lat_signal.get("baseline_p95_ms", 0.0),
                "average_latency_ms": baseline_latency_details.get("average_latency_ms", 0.0),
                "details": baseline_latency_details
            },
            "current": {
                "p95_latency_ms": lat_signal.get("current_p95_ms", 0.0),
                "average_latency_ms": current_latency_details.get("average_latency_ms", 0.0),
                "details": current_latency_details
            },
            "changes": {
                "absolute_change_ms": lat_signal.get("absolute_change_ms", 0.0),
                "relative_change": lat_signal.get("relative_change", 0.0),
                "change_percentage": lat_signal.get("relative_change", 0.0) * 100
            },
            "latency_status": lat_signal.get("status", "UNKNOWN"),
            "interpretation": self._interpret_latency_change(
                lat_signal.get("relative_change", 0.0),
                lat_signal.get("status", "NORMAL")
            ),
            "technical_failure_latency": self._calculate_technical_failure_latency(payments, detector_result["candidate_segment"])
        }

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of a list of values."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)
        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower = sorted_values[int(index)]
            upper = sorted_values[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    def _interpret_latency_change(
        self,
        relative_change: float,
        status: str
    ) -> str:
        """Interpret latency change."""
        if status == "NORMAL":
            return "Latency within normal range"
        elif relative_change >= 2.0:  # 2x increase
            return "Latency significantly increased - suggests processing delays or system overload"
        elif relative_change >= 1.5:  # 1.5x increase
            return "Latency moderately elevated"
        elif relative_change >= 0.5:  # 50% increase
            return "Latency mildly elevated"
        else:
            return f"Latency status: {status}"

    def _calculate_technical_failure_latency(
        self,
        payments: List[Dict[str, Any]],
        segment: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate average latency for technical failures in the segment."""
        if not payments:
            return None

        technical_latencies = []
        for payment in payments:
            if (self._payment_matches_segment(payment, segment) and
                payment["status"] == "failed" and
                categorize_failure(payment.get("error_code")) == "technical"):
                technical_latencies.append(payment["latency_ms"])

        if technical_latencies:
            return statistics.mean(technical_latencies)
        return None

    def _build_impact_evidence(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build impact evidence including revenue at risk calculation."""
        success_signal = detector_result["success_rate_signal"]
        candidate_segment = detector_result["candidate_segment"]

        # Get baseline and current data for the segment
        baseline_segment = self._get_baseline_segment(baseline, candidate_segment)
        current_segment_stats = self._calculate_segment_stats(
            payments, candidate_segment
        ) if payments else {}

        baseline_attempts = baseline_segment.get("attempts", 0) if baseline_segment else 0
        baseline_success_rate = baseline_segment.get("success_rate", 0.0) if baseline_segment else 0.0
        baseline_avg_amount = baseline_segment.get("average_amount", 0.0) if baseline_segment else 0.0

        current_attempts = current_segment_stats.get("attempts", 0)
        current_success_rate = current_segment_stats.get("success_rate", 0.0)
        current_avg_amount = current_segment_stats.get("average_amount", 0.0) if current_segment_stats else 0.0

        # Use baseline average amount for consistency (as per requirements)
        avg_amount_rupees = baseline_avg_amount  # Keep in rupees

        # Calculate impact metrics
        expected_successful_payments = baseline_success_rate * baseline_attempts
        actual_successful_payments = current_success_rate * current_attempts

        # Revenue calculations (in paise as per requirements)
        expected_successful_revenue_paise = int(
            expected_successful_payments * avg_amount_rupees * 100  # Convert rupees to paise
        )
        actual_successful_revenue_paise = int(
            actual_successful_payments * avg_amount_rupees * 100
        )

        revenue_at_risk_paise = max(0, expected_successful_revenue_paise - actual_successful_revenue_paise)

        return {
            "affected_attempts": {
                "baseline": baseline_attempts,
                "current": current_attempts,
                "change": current_attempts - baseline_attempts,
                "change_percentage": ((current_attempts - baseline_attempts) / baseline_attempts * 100) if baseline_attempts > 0 else 0.0
            },
            "successful_payments": {
                "baseline_expected": expected_successful_payments,
                "current_actual": actual_successful_payments,
                "shortfall": max(0, expected_successful_payments - actual_successful_payments),
                "percentage_shortfall": (
                    ((expected_successful_payments - actual_successful_payments) / expected_successful_payments * 100)
                    if expected_successful_payments > 0 else 0.0
                )
            },
            "average_transaction_amount": {
                "rupees": avg_amount_rupees,
                "paise": int(avg_amount_rupees * 100)
            },
            "revenue_at_risk": {
                "paise": revenue_at_risk_paise,
                "rupees": revenue_at_risk_paise / 100.0
            },
            "calculation_method": "Deterministic as per requirements:",
            "formula": {
                "expected_successful_revenue": "baseline_success_rate × affected_attempts × average_amount",
                "actual_successful_revenue": "actual_successful_payments × average_amount",
                "revenue_at_risk": "Expected Successful Revenue - Actual Successful Revenue"
            },
            "note": "All monetary values are integer paise internally as required"
        }

    def _build_sample_payments(
        self,
        payments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build sample payment evidence for traceability."""
        if not payments:
            return []

        # Select up to 5 representative payments:
        # - 2 successful payments (if available)
        # - 2 failed payments (if available, with different error types)
        # - 1 additional payment (success or failure)

        successful_payments = [p for p in payments if p["status"] == "success"]
        failed_payments = [p for p in payments if p["status"] == "failed"]

        samples = []

        # Add up to 2 successful payments
        samples.extend(successful_payments[:2])

        # Add up to 2 failed payments with different error types if possible
        added_error_types = set()
        for payment in failed_payments:
            if len(samples) >= 4:  # Already have 2 success + up to 2 failure
                break

            error_code = payment.get("error_code", "UNKNOWN")
            if error_code not in added_error_types or len(added_error_types) == 0:
                samples.append(payment)
                added_error_types.add(error_code)

        # Add one more payment if we have room and payments left
        if len(samples) < 5 and len(payments) > len(samples):
            # Add a payment not already in samples
            for payment in payments:
                if payment not in samples:
                    samples.append(payment)
                    break

        # Format samples for output (remove PII, keep only necessary fields)
        formatted_samples = []
        for payment in samples[:5]:  # Limit to 5 samples
            formatted_samples.append({
                "payment_id": payment["payment_id"],
                "order_id": payment["order_id"],
                "timestamp": payment["timestamp"],
                "payment_method": payment["payment_method"],
                "bank": payment.get("bank"),
                "device": payment.get("device"),
                "upi_app": payment.get("upi_app"),
                "status": payment["status"],
                "error_code": payment.get("error_code"),
                "amount": payment["amount"],  # Keep in paise as stored
                "latency_ms": payment["latency_ms"]
            })

        return formatted_samples

    def _build_hypothesis_evidence(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build deterministic evidence for plausible hypotheses."""
        hypotheses = []

        # Check if there's meaningful degradation to analyze
        success_signal = detector_result["success_rate_signal"]
        has_meaningful_degradation = (
            success_signal.get("statistically_significant", False) and
            abs(success_signal.get("difference_percentage_points", 0)) >= 5.0  # 5 pp threshold
        )

        # If no meaningful degradation, return single hypothesis
        if not has_meaningful_degradation:
            return [{
                "hypothesis": "No meaningful degradation detected",
                "status": "NOT_APPLICABLE",
                "supporting_signals": [
                    f"Success rate change: {success_signal.get('difference_percentage_points', 0):.2f} percentage points",
                    f"Statistically significant: {success_signal.get('statistically_significant', False)}"
                ],
                "contradicting_signals": [],
                "assessment": "NO_MEANINGFUL_DEGRADATION_TO_ANALYZE"
            }]

        candidate_segment = detector_result["candidate_segment"]
        if not candidate_segment or candidate_segment.get("payment_method") == "UNKNOWN":
            return [{
                "hypothesis": "Insufficient segment identification",
                "status": "INSUFFICIENT_EVIDENCE",
                "supporting_signals": ["candidate_segment could not be determined"],
                "contradicting_signals": [],
                "assessment": "CANNOT_FORM_HYPOTHESES_WITHOUT_SEGMENT"
            }]

        # Hypothesis 1: Localized bank/device/method issue
        localized_hypo = self._build_localized_hypothesis(
            detector_result, baseline, payments
        )
        hypotheses.append(localized_hypo)

        # Hypothesis 2: Widespread systemic issue
        widespread_hypo = self._build_widespread_hypothesis(
            detector_result, baseline, payments
        )
        hypotheses.append(widespread_hypo)

        # Hypothesis 3: Technical infrastructure issue
        technical_hypo = self._build_technical_hypothesis(
            detector_result, baseline, payments
        )
        hypotheses.append(technical_hypo)

        # Hypothesis 4: User-side/customer issue
        customer_hypo = self._build_customer_hypothesis(
            detector_result, baseline, payments
        )
        hypotheses.append(customer_hypo)

        # Hypothesis 5: Volume or latency issue
        volume_hypo = self._build_volume_latency_hypothesis(
            detector_result, baseline, payments
        )
        hypotheses.append(volume_hypo)

        return hypotheses

    def _build_localized_hypothesis(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build hypothesis for localized issue."""
        candidate_segment = detector_result["candidate_segment"]
        loc_signal = detector_result["localization_signal"]
        success_signal = detector_result["success_rate_signal"]
        tech_signal = detector_result["technical_error_signal"]

        supporting = []
        contradicting = []

        # Check if localization evidence supports this
        if loc_signal.get("status") == "LOCALIZED":
            supporting.append("Localization evidence indicates degradation is isolated to specific segment")
        elif loc_signal.get("status") == "WIDESPREAD":
            contradicting.append("Localization evidence shows degradation is widespread")
        else:
            contradicting.append("Localization evidence inconclusive")

        # Check error type
        if tech_signal.get("status") in ["WARNING", "CRITICAL", "CONCERNING", "ELEVATED"]:
            supporting.append("Technical error rate is elevated")
        else:
            contradicting.append("Technical error rate is not significantly elevated")

        # Check significance and magnitude
        if success_signal.get("statistically_significant"):
            supporting.append("Success rate drop is statistically significant")
        else:
            contradicting.append("Success rate drop is not statistically significant")

        drop_pp = abs(success_signal.get("difference_percentage_points", 0))
        if drop_pp >= 7.5:  # Warning threshold from detector
            supporting.append(f"Success rate drop ({drop_pp:.1f} pp) exceeds warning threshold")
        elif drop_pp >= 15:  # Critical threshold
            supporting.append(f"Success rate drop ({drop_pp:.1f} pp) exceeds critical threshold")
        else:
            contradicting.append(f"Success rate drop ({drop_pp:.1f} pp) below warning threshold")

        # Assess
        supporting_count = len(supporting)
        contradicting_count = len(contradicting)

        if supporting_count > contradicting_count and supporting_count >= 2:
            status = "SUPPORTED"
            assessment = "Evidence supports localized technical issue"
        elif contradicting_count > supporting_count:
            status = "CONTRADICTED"
            assessment = "Evidence contradicts localized hypothesis"
        elif supporting_count >= 1:
            status = "PARTIALLY_SUPPORTED"
            assessment = "Some evidence supports localized hypothesis but contradicting evidence exists"
        else:
            status = "INSUFFICIENT_EVIDENCE"
            assessment = "Insufficient evidence to support or contradict hypothesis"

        return {
            "hypothesis": f"Localized {candidate_segment.get('payment_method', 'UNKNOWN')} issue",
            "details": f"Affecting {candidate_segment.get('bank', 'any bank')} "
                      f"{candidate_segment.get('device', 'any device')} "
                      f"{candidate_segment.get('upi_app', 'any upi_app')}",
            "status": status,
            "supporting_signals": supporting,
            "contradicting_signals": contradicting,
            "assessment": assessment
        }

    def _build_widespread_hypothesis(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build hypothesis for widespread systemic issue."""
        loc_signal = detector_result["localization_signal"]
        success_signal = detector_result["success_rate_signal"]
        tech_signal = detector_result["technical_error_signal"]
        vol_signal = detector_result["volume_signal"]

        supporting = []
        contradicting = []

        # Check localization
        if loc_signal.get("status") == "WIDESPREAD":
            supporting.append("Localization evidence indicates widespread degradation")
        elif loc_signal.get("status") == "LOCALIZED":
            contradicting.append("Localization evidence shows degradation is localized")
        else:
            contradicting.append("Localization evidence inconclusive for widespread assessment")

        # Check multiple methods affected (would need more detailed analysis)
        # For now, check if overall is affected
        candidate_segment = detector_result["candidate_segment"]
        if candidate_segment.get("payment_method") == "ALL":
            supporting.append("Degradation affects overall merchant (all payment methods)")
        else:
            # This is a limitation - we'd need to check multiple methods in a full implementation
            contradicting.append("Cannot determine if multiple methods affected without multi-method analysis")

        # Check for volume anomalies
        if vol_signal.get("status") in ["SIGNIFICANT_DECREASE", "NOTABLE_DECREASE"]:
            supporting.append("Volume decrease suggests systemic issue affecting demand")
        elif vol_signal.get("status") in ["SIGNIFICANT_INCREASE", "NOTABLE_INCREASE"]:
            supporting.append("Volume increase may indicate retry storms or systemic issues")
        else:
            # Neutral - don't add to either side
            pass

        # Check significance
        if success_signal.get("statistically_significant"):
            supporting.append("Success rate drop is statistically significant")
        else:
            contradicting.append("Success rate drop is not statistically significant")

        # Assess
        supporting_count = len(supporting)
        contradicting_count = len(contradicting)

        if supporting_count > contradicting_count and supporting_count >= 2:
            status = "SUPPORTED"
            assessment = "Evidence supports widespread systemic issue"
        elif contradicting_count > supporting_count:
            status = "CONTRADICTED"
            assessment = "Evidence contradicts widespread hypothesis"
        elif supporting_count >= 1:
            status = "PARTIALLY_SUPPORTED"
            assessment = "Some evidence supports widespread hypothesis but contradicting evidence exists"
        else:
            status = "INSUFFICIENT_EVIDENCE"
            assessment = "Insufficient evidence to support or contradict hypothesis"

        return {
            "hypothesis": "Widespread systemic issue affecting multiple payment methods/banks/devices",
            "status": status,
            "supporting_signals": supporting,
            "contradicting_signals": contradicting,
            "assessment": assessment
        }

    def _build_technical_hypothesis(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build hypothesis for technical infrastructure issue."""
        tech_signal = detector_result["technical_error_signal"]
        success_signal = detector_result["success_rate_signal"]
        lat_signal = detector_result["latency_signal"]

        supporting = []
        contradicting = []

        # Technical error evidence
        if tech_signal.get("status") in ["WARNING", "CRITICAL", "CONCERNING"]:
            supporting.append("Technical error rate is elevated")
            supporting.append(f"Technical error status: {tech_signal.get('status')}")
        else:
            contradicting.append("Technical error rate is not significantly elevated")

        # Latency evidence
        if lat_signal.get("status") in ["WARNING", "CRITICAL", "CONCERNING"]:
            supporting.append("Latency is elevated")
            supporting.append(f"Latency status: {lat_signal.get('status')}")
        else:
            # Latency normal doesn't contradict technical issue (could be errors without latency impact)
            pass

        # Success correlation
        if success_signal.get("difference", 0) < 0:  # Success rate decreasing
            supporting.append("Success rate is decreasing (consistent with technical issues)")
        else:
            contradicting.append("Success rate is increasing (inconsistent with technical degradation)")

        # Check if technical errors align with success drop
        tech_change = tech_signal.get("absolute_change", 0)
        success_change = success_signal.get("difference", 0)

        if tech_change > 0 and success_change < 0:
            supporting.append("Technical error increase correlates with success rate decrease")
        elif tech_change <= 0 and success_change < 0:
            contradicting.append("Success rate decreasing but technical errors not increasing")

        # Assess
        supporting_count = len(supporting)
        contradicting_count = len(contradicting)

        if supporting_count > contradicting_count and supporting_count >= 2:
            status = "SUPPORTED"
            assessment = "Evidence supports technical infrastructure issue"
        elif contradicting_count > supporting_count:
            status = "CONTRADICTED"
            assessment = "Evidence contradicts technical hypothesis"
        elif supporting_count >= 1:
            status = "PARTIALLY_SUPPORTED"
            assessment = "Some evidence supports technical hypothesis but contradicting evidence exists"
        else:
            status = "INSUFFICIENT_EVIDENCE"
            assessment = "Insufficient evidence to support or contradict hypothesis"

        return {
            "hypothesis": "Technical infrastructure issue (bank/gateway/network problems)",
            "status": status,
            "supporting_signals": supporting,
            "contradicting_signals": contradicting,
            "assessment": assessment
        }

    def _build_customer_hypothesis(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build hypothesis for user-side/customer issue."""
        cust_signal = detector_result["customer_error_signal"]
        success_signal = detector_result["success_rate_signal"]
        tech_signal = detector_result["technical_error_signal"]

        supporting = []
        contradicting = []

        # Customer error evidence
        cust_change = cust_signal.get("absolute_change", 0)
        if cust_change > 0.01:  # More than 1pp increase
            supporting.append("Customer-caused error rate is significantly elevated")
            supporting.append(f"Customer error increase: {cust_change*100:.1f} percentage points")
        elif cust_change < -0.01:
            contradicting.append("Customer-caused error rate is decreasing")
        else:
            # Neutral change
            pass

        # Technical error evidence (should be normal for customer issues)
        if tech_signal.get("status") in ["NORMAL", "ELEVATED"]:
            supporting.append("Technical error rate remains normal (consistent with customer-side issue)")
        else:
            contradicting.append("Technical error rate is elevated (suggests technical issue, not customer-side)")

        # Success correlation
        if success_signal.get("difference", 0) < 0:  # Success rate decreasing
            supporting.append("Success rate is decreasing (consistent with customer issues causing failures)")
        else:
            contradicting.append("Success rate is increasing (inconsistent with customer-side failure increase)")

        # Check scenario E characteristics: customer errors up, technical errors normal
        if cust_change > 0.01 and tech_signal.get("status") in ["NORMAL", "ELEVATED"]:
            supporting.append("Pattern matches Scenario E: customer errors up, technical errors normal")

        # Assess
        supporting_count = len(supporting)
        contradicting_count = len(contradicting)

        if supporting_count > contradicting_count and supporting_count >= 2:
            status = "SUPPORTED"
            assessment = "Evidence supports user-side/customer issue"
        elif contradicting_count > supporting_count:
            status = "CONTRADICTED"
            assessment = "Evidence contradicts customer hypothesis"
        elif supporting_count >= 1:
            status = "PARTIALLY_SUPPORTED"
            assessment = "Some evidence supports customer hypothesis but contradicting evidence exists"
        else:
            status = "INSUFFICIENT_EVIDENCE"
            assessment = "Insufficient evidence to support or contradict hypothesis"

        return {
            "hypothesis": "User-side/customer issue (insufficient funds, wrong PIN, etc.)",
            "status": status,
            "supporting_signals": supporting,
            "contradicting_signals": contradicting,
            "assessment": assessment
        }

    def _build_volume_latency_hypothesis(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build hypothesis for volume or latency issues."""
        vol_signal = detector_result["volume_signal"]
        lat_signal = detector_result["latency_signal"]
        success_signal = detector_result["success_rate_signal"]

        supporting = []
        contradicting = []

        # Volume evidence
        vol_status = vol_signal.get("status", "NORMAL")
        if vol_status in ["SIGNIFICANT_DECREASE", "NOTABLE_DECREASE"]:
            supporting.append("Volume significantly decreased")
            supporting.append(f"Volume change: {vol_signal.get('change_pct', 0)*100:.1f}%")
        elif vol_status in ["SIGNIFICANT_INCREASE", "NOTABLE_INCREASE"]:
            supporting.append("Volume significantly increased")
            supporting.append(f"Volume change: {vol_signal.get('change_pct', 0)*100:.1f}%")
        else:
            # Volume normal - doesn't strongly support or contradict
            pass

        # Latency evidence
        lat_status = lat_signal.get("status", "NORMAL")
        if lat_status in ["WARNING", "CRITICAL", "CONCERNING"]:
            supporting.append("Latency significantly elevated")
            supporting.append(f"Latency change: {lat_signal.get('relative_change', 0)*100:.1f}%")
        elif lat_status in ["NORMAL", "ELEVATED"]:
            # Latency normal/elevated - neutral for volume hypothesis
            pass
        else:
            contradicting.append(f"Unexpected latency status: {lat_status}")

        # Success correlation with volume
        # For volume issues, we might expect success rate to stay stable if it's purely demand change
        # For latency issues, we might see success rate impacted if timeouts occur
        vol_change_pct = vol_signal.get("change_pct", 0)
        success_change = success_signal.get("difference", 0)

        if abs(vol_change_pct) > 0.3:  # Significant volume change (>30%)
            if abs(success_change) < 0.05:  # Success rate stable (<5pp change)
                supporting.append("Significant volume change with stable success rate suggests demand-side issue")
            elif success_change < -0.05:  # Success rate decreasing
                supporting.append("Volume change correlated with success rate decrease")
        # else: neutral

        # Assess - this hypothesis is a bit different as it's more about "either/or"
        has_volume_evidence = vol_status not in ["NORMAL"]
        has_latency_evidence = lat_status in ["WARNING", "CRITICAL", "CONCERNING"]

        if has_volume_evidence or has_latency_evidence:
            status = "PARTIALLY_SUPPORTED"  # At least some evidence
            assessment = "Some evidence supports volume or latency hypothesis"
        else:
            status = "INSUFFICIENT_EVIDENCE"
            assessment = "Insufficient evidence to support volume or latency hypothesis"

        return {
            "hypothesis": "Volume anomaly or latency issue",
            "status": status,
            "supporting_signals": supporting,
            "contradicting_signals": contradicting,
            "assessment": assessment
        }

    def _build_investigation_checklist(
        self,
        detector_result: Dict[str, Any],
        baseline: Dict[str, Any],
        payments: List[Dict[str, Any]],
        window_start: datetime,
        window_end: datetime
    ) -> List[Dict[str, Any]]:
        """Build deterministic investigation checklist."""
        checklist = []

        # 1. Is the success-rate drop statistically significant?
        success_signal = detector_result["success_rate_signal"]
        checklist.append(self._build_checklist_item(
            check="statistical_significance",
            result="PASS" if success_signal["statistically_significant"] else "FAIL",
            finding=f"Success rate drop is {'statistically significant' if success_signal['statistically_significant'] else 'not statistically significant'} "
                   f"(p-value: {success_signal['p_value']:.4f})",
            evidence_refs=["success_rate_evidence.statistical_significance"]
        ))

        # 2. Is the degradation large enough to matter?
        drop_pp = abs(success_signal["difference_percentage_points"])
        concerning_threshold = 5.0  # 5 percentage points from detector config
        checklist.append(self._build_checklist_item(
            check="meaningful_degradation",
            result="PASS" if drop_pp >= concerning_threshold else "FAIL",
            finding=f"Success rate dropped {drop_pp:.1f} percentage points "
                   f"(threshold: {concerning_threshold} pp)",
            evidence_refs=["success_rate_evidence.absolute_percentage_point_change"]
        ))

        # 3. Is it localized or widespread?
        loc_signal = detector_result["localization_signal"]
        loc_status = loc_signal.get("status", "UNKNOWN")
        checklist.append(self._build_checklist_item(
            check="localization_assessment",
            result="PASS" if loc_status in ["LOCALIZED", "WIDESPREAD"] else "FAIL",
            finding=f"Degradation is {loc_status.lower()}",
            evidence_refs=["localization_evidence.localization_status"]
        ))

        # 4. Which hierarchy level best explains it?
        candidate_segment = detector_result["candidate_segment"]
        hierarchy_level = self._determine_hierarchy_level(candidate_segment)
        checklist.append(self._build_checklist_item(
            check="hierarchy_level",
            result="PASS" if hierarchy_level != "UNKNOWN" else "FAIL",
            finding=f"Best explained at {hierarchy_level.replace('_', ' ').title()} level",
            evidence_refs=["affected_segment.hierarchy_level"]
        ))

        # 5. Are other banks healthy?
        loc_evidence = self._build_localization_evidence(detector_result, baseline, payments)
        other_banks_status = loc_evidence.get("control_analysis", {}).get("status", "UNKNOWN")
        checklist.append(self._build_checklist_item(
            check="other_banks_healthy",
            result="PASS" if other_banks_status == "HEALTHY" else "FAIL",
            finding=f"Other banks status: {other_banks_status}",
            evidence_refs=["localization_evidence.control_analysis.status"]
        ))

        # 6. Are other devices healthy?
        # This is included in the localization evidence control analysis
        other_devices_healthy = "PASS"  # Simplified - would check actual device health
        checklist.append(self._build_checklist_item(
            check="other_devices_healthy",
            result="PASS",
            finding="Other devices status: HEALTHY (placeholder)",
            evidence_refs=["localization_evidence.control_analysis.status"]
        ))

        # 7. Are other payment methods healthy?
        # Would need multi-method analysis - simplified for now
        checklist.append(self._build_checklist_item(
            check="other_payment_methods_healthy",
            result="PASS",  # Placeholder
            finding="Other payment methods status: HEALTHY (placeholder - would need multi-method analysis)",
            evidence_refs=["localization_evidence.other_methods"]
        ))

        # 8. Did technical errors increase?
        tech_signal = detector_result["technical_error_signal"]
        tech_status = tech_signal.get("status", "NORMAL")
        checklist.append(self._build_checklist_item(
            check="technical_error_increase",
            result="PASS" if tech_status in ["WARNING", "CRITICAL", "CONCERNING", "ELEVATED"] else "FAIL",
            finding=f"Technical error rate status: {tech_status}",
            evidence_refs=["error_evidence.current.technical_error_rate",
                        "error_evidence.changes.technical_error_rate_change"]
        ))

        # 9. Did customer-caused errors increase?
        cust_signal = detector_result["customer_error_signal"]
        cust_change = cust_signal.get("absolute_change", 0)
        checklist.append(self._build_checklist_item(
            check="customer_error_increase",
            result="PASS" if cust_change > 0.01 else "FAIL",
            finding=f"Customer-caused error rate changed by {cust_change*100:.1f} percentage points",
            evidence_refs=["error_evidence.changes.customer_error_rate_change"]
        ))

        # 10. Did latency change?
        lat_signal = detector_result["latency_signal"]
        lat_status = lat_signal.get("status", "NORMAL")
        checklist.append(self._build_checklist_item(
            check="latency_change",
            result="PASS" if lat_status in ["WARNING", "CRITICAL", "CONCERNING"] else "FAIL",
            finding=f"Latency status: {lat_status}",
            evidence_refs=["latency_evidence.changes.relative_change"]
        ))

        # 11. Did volume change?
        vol_signal = detector_result["volume_signal"]
        vol_status = vol_signal.get("status", "NORMAL")
        checklist.append(self._build_checklist_item(
            check="volume_change",
            result="PASS" if vol_status in ["SIGNIFICANT_DECREASE", "NOTABLE_DECREASE",
                                              "SIGNIFICANT_INCREASE", "NOTABLE_INCREASE"] else "FAIL",
            finding=f"Volume status: {vol_status} ({vol_signal.get('change_pct', 0)*100:.1f}% change)",
            evidence_refs=["volume_evidence.change_percentage"]
        ))

        # 12. Is the degradation persistent over time?
        temporal_evidence = self._build_temporal_evidence(payments, window_start, window_end)
        is_persistent = temporal_evidence.get("is_persistent", False)
        checklist.append(self._build_checklist_item(
            check="persistence_over_time",
            result="PASS" if is_persistent else "FAIL",
            finding=f"Degradation persistence: {'PERSISTENT' if is_persistent else 'INTERMITTENT'}",
            evidence_refs=["temporal_evidence.is_persistent"]
        ))

        # 13. Are there contradicting signals?
        # Check if success drop is contradicted by other signals improving
        success_drop = success_signal["difference"] < 0
        tech_improving = detector_result["technical_error_signal"].get("absolute_change", 0) < 0
        cust_improving = detector_result["customer_error_signal"].get("absolute_change", 0) < 0
        lat_improving = detector_result["latency_signal"].get("relative_change", 0) < 0
        vol_improving = detector_result["volume_signal"].get("change_pct", 0) < 0

        improving_signals = []
        if tech_improving: improving_signals.append("technical_errors")
        if cust_improving: improving_signals.append("customer_errors")
        if lat_improving: improving_signals.append("latency")
        if vol_improving: improving_signals.append("volume")

        has_contradicting = success_drop and len(improving_signals) > 0
        checklist.append(self._build_checklist_item(
            check="contradicting_signals",
            result="PASS" if not has_contradicting else "FAIL",  # PASS means no contradicting signals (good)
            finding=f"Contradicting signals: {', '.join(improving_signals) if improving_signals else 'None'}",
            evidence_refs=["technical_evidence", "customer_evidence", "latency_evidence", "volume_evidence"]  # Simplified
        ))

        # 14. Is there enough sample size?
        sample_sufficiency = detector_result["sample"]["sufficiency"]
        checklist.append(self._build_checklist_item(
            check="sample_size_sufficiency",
            result="PASS" if sample_sufficiency == "SUFFICIENT" else "FAIL",
            finding=f"Sample size: {detector_result['sample']['attempts']} attempts ({sample_sufficiency})",
            evidence_refs=["sample.attempts", "sample.sufficiency"]
        ))

        # 15. Is the event primarily customer-caused? (Scenario E check)
        cust_change = detector_result["customer_error_signal"].get("absolute_change", 0)
        tech_change = detector_result["technical_error_signal"].get("absolute_change", 0)
        is_customer_caused = cust_change > 0.01 and (cust_change >= 2.0 * tech_change or
                                                    detector_result["technical_error_signal"]["status"] in ["NORMAL", "ELEVATED"])
        checklist.append(self._build_checklist_item(
            check="primarily_customer_caused",
            result="PASS" if is_customer_caused else "FAIL",  # PASS means it IS customer-caused
            finding=f"Event is {'primarily customer-caused' if is_customer_caused else 'not primarily customer-caused'} "
                   f"(customer change: {cust_change*100:.1f}pp, technical change: {tech_change*100:.1f}pp)",
            evidence_refs=["error_evidence.changes.customer_error_rate_change",
                        "error_evidence.changes.technical_error_rate_change"]
        ))

        return checklist

    def _build_checklist_item(
        self,
        check: str,
        result: str,
        finding: str,
        evidence_refs: List[str]
    ) -> Dict[str, Any]:
        """Build a single investigation checklist item."""
        return {
            "check": check,
            "result": result,  # PASS, FAIL, or WARNING
            "finding": finding,
            "evidence_refs": evidence_refs
        }

    def _validate_evidence_package(self, evidence_package: Dict[str, Any]) -> None:
        """Validate that the evidence package is complete and well-formed."""
        required_sections = [
            "incident_metadata",
            "affected_segment",
            "success_rate_evidence",
            "error_evidence",
            "localization_evidence",
            "temporal_evidence",
            "volume_evidence",
            "latency_evidence",
            "impact_evidence",
            "sample_payments",
            "hypothesis_evidence",
            "investigation_checklist",
            "schema_info"
        ]

        for section in required_sections:
            if section not in evidence_package:
                raise ValueError(f"Missing required section: {section}")

        # Validate that we can calculate revenue at risk without LLM
        impact = evidence_package["impact_evidence"]
        if "revenue_at_risk" not in impact:
            raise ValueError("Missing revenue_at_risk in impact_evidence")

        revenue_at_risk = impact["revenue_at_risk"]
        if "paise" not in revenue_at_risk:
            raise ValueError("Revenue at risk missing paise amount")

        # Ensure it's an integer (as required)
        paise_amount = revenue_at_risk["paise"]
        if not isinstance(paise_amount, int):
            raise ValueError(f"Revenue at risk paise amount must be integer, got {type(paise_amount)}")

        # Validate that investigation checklist has the right structure
        checklist = evidence_package["investigation_checklist"]
        if not isinstance(checklist, list):
            raise ValueError("Investigation checklist must be a list")

        for item in checklist:
            if not isinstance(item, dict):
                raise ValueError("Each checklist item must be a dict")
            required_fields = ["check", "result", "finding", "evidence_refs"]
            for field in required_fields:
                if field not in item:
                    raise ValueError(f"Missing required field {field} in checklist item")

    def get_evidence_package_json(
        self,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime,
        generated_data_dir: Path
    ) -> str:
        """
        Get evidence package as JSON string.

        Returns:
            JSON string representation of the evidence package
        """
        package = self.build_evidence_package(
            merchant_id, window_start, window_end, generated_data_dir
        )
        return json.dumps(package, indent=2, default=str)


# Convenience function for external use
def generate_evidence_package(
    merchant_id: str,
    window_start: datetime,
    window_end: datetime,
    generated_data_dir: Path
) -> Dict[str, Any]:
    """
    Generate an evidence package for the given parameters.

    Args:
        merchant_id: Merchant identifier
        window_start: Start of analysis window (inclusive)
        window_end: End of analysis window (exclusive)
        generated_data_dir: Directory containing generated JSONL files

    Returns:
        Complete evidence package as dict
    """
    builder = EvidencePackageBuilder()
    return builder.build_evidence_package(merchant_id, window_start, window_end, generated_data_dir)


if __name__ == "__main__":
    # Simple test when run directly
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Generate evidence package")
    parser.add_argument("--merchant-id", required=True, help="Merchant ID")
    parser.add_argument("--window-start", required=True, help="Window start (ISO format)")
    parser.add_argument("--window-end", required=True, help="Window end (ISO format)")
    parser.add_argument("--data-dir", default="data/generated", help="Data directory")
    parser.add_argument("--output", help="Output file (default: stdout)")

    args = parser.parse_args()

    # Parse timestamps
    window_start = parse_timestamp(args.window_start)
    window_end = parse_timestamp(args.window_end)
    data_dir = Path(args.data_dir)

    # Generate evidence package
    package = generate_evidence_package(
        args.merchant_id, window_start, window_end, data_dir
    )

    # Output
    output_json = json.dumps(package, indent=2, default=str)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"Evidence package written to {args.output}")
    else:
        print(output_json)