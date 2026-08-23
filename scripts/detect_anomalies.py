#!/usr/bin/env python3
"""
Deterministic anomaly detection engine for DegradeWatch.

Compares current payment windows against healthy baselines to healthy baselines and
generates explainable signals for incident classification.
"""

import json
import jsonlines
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional, Set
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.analyze_baselines import (
    load_merchant_profile,
    parse_timestamp,
    categorize_failure,
    calculate_statistics,
    calculate_percentiles
)


class DetectorConfig:
    """Configuration for the anomaly detector."""

    def __init__(self):
        # Sample size thresholds
        self.min_attempts_sufficient = 30
        self.min_attempts_limited = 10

        # Statistical significance
        self.significance_level = 0.05  # 95% confidence

        # Success rate deviation thresholds (percentage points)
        self.min_success_rate_drop_concerning = 0.05  # 5 pp
        self.min_success_rate_drop_warning = 0.075    # 7.5 pp
        self.min_success_rate_drop_critical = 0.15    # 15 pp

        # Technical error multiplier thresholds
        self.technical_error_increase_concerning = 2.0   # 2x baseline
        self.technical_error_increase_warning = 3.0      # 3x baseline
        self.technical_error_increase_critical = 5.0     # 5x baseline

        # Localization tolerance (how much control segments can deviate)
        self.control_segment_tolerance = 0.05  # 5 pp

        # Volume anomaly thresholds
        self.volume_decrease_concerning = 0.3   # 30% decrease
        self.volume_decrease_warning = 0.5      # 50% decrease

        # Severity thresholds (based on success rate drop)
        self.severity_low_threshold = 0.05    # 5 pp drop
        self.severity_medium_threshold = 0.075 # 7.5 pp drop
        self.severity_high_threshold = 0.15   # 15 pp drop


class AnomalyDetector:
    """Deterministic anomaly detection engine."""

    def __init__(self, config: Optional[DetectorConfig] = None):
        self.config = config or DetectorConfig()

    def detect(
        self,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime,
        generated_data_dir: Path
    ) -> Dict[str, Any]:
        """
        Detect anomalies in a payment window.

        Args:
            merchant_id: Merchant identifier
            window_start: Start of analysis window (inclusive)
            window_end: End of analysis window (exclusive)
            generated_data_dir: Directory containing generated JSONL files

        Returns:
            Structured detection result
        """
        # Load healthy baseline
        baseline_dir = generated_data_dir / "baselines"
        baseline_path = baseline_dir / f"{merchant_id}.json"

        if not baseline_path.exists():
            raise FileNotFoundError(f"Baseline not found for merchant {merchant_id}")

        with open(baseline_path, 'r') as f:
            baseline = json.load(f)

        # Load current window payments
        payments_file = generated_data_dir / f"{merchant_id}.jsonl"
        current_payments = self._load_window_payments(
            payments_file, window_start, window_end
        )

        if not current_payments:
            return self._create_insufficient_data_result(
                merchant_id, window_start, window_end
            )

        # Load merchant profile for error code taxonomy
        profile = load_merchant_profile(merchant_id)

        # Ensure baseline has failure_breakdown in overall section (backward compatibility)
        if "failure_breakdown" not in baseline["overall"]:
            # Calculate overall failure breakdown by summing up the by_method breakdowns
            baseline["overall"]["failure_breakdown"] = {
                "customer_caused": sum(
                    method_data.get("failure_breakdown", {}).get("customer_caused", 0)
                    for method_data in baseline["by_method"].values()
                ),
                "technical": sum(
                    method_data.get("failure_breakdown", {}).get("technical", 0)
                    for method_data in baseline["by_method"].values()
                ),
                "other": sum(
                    method_data.get("failure_breakdown", {}).get("other", 0)
                    for method_data in baseline["by_method"].values()
                )
            }

        # Ensure baseline has failure_breakdown in overall section (backward compatibility)
        if "failure_breakdown" not in baseline["overall"]:
            # Calculate overall failure breakdown from by_method data
            baseline_failures = baseline["overall"]["failures"]
            if baseline_failures > 0:
                weighted_breakdown = {"customer_caused": 0, "technical": 0, "other": 0}
                total_weighted = 0
                for method, method_data in baseline["by_method"].items():
                    method_failures = method_data["failures"]
                    if method_failures > 0:
                        weight = method_failures / baseline_failures
                        weighted_breakdown["customer_caused"] += method_data["failure_breakdown"]["customer_caused"] * weight
                        weighted_breakdown["technical"] += method_data["failure_breakdown"]["technical"] * weight
                        weighted_breakdown["other"] += method_data["failure_breakdown"]["other"] * weight
                        total_weighted += weight

                # Normalize if needed
                if total_weighted > 0:
                    baseline["overall"]["failure_breakdown"] = {
                        "customer_caused": weighted_breakdown["customer_caused"] / total_weighted,
                        "technical": weighted_breakdown["technical"] / total_weighted,
                        "other": weighted_breakdown["other"] / total_weighted
                    }
                else:
                    # Fallback: distribute proportionally
                    baseline["overall"]["failure_breakdown"] = {
                        "customer_caused": baseline["overall"]["failures"] * 0.8,  # Approximately 80% customer caused
                        "technical": baseline["overall"]["failures"] * 0.15,      # Approximately 15% technical
                        "other": baseline["overall"]["failures"] * 0.05          # Approximately 5% other
                    }
            else:
                baseline["overall"]["failure_breakdown"] = {"customer_caused": 0, "technical": 0, "other": 0}

        # Analyze current window
        current_stats = self._analyze_payment_window(current_payments, profile)

        # Get all keys to evaluate.
        keys_to_evaluate = ["OVERALL"] + list(current_stats["by_method"].keys()) + list(current_stats["segments"].keys())

        active_segments = {}
        anomalies = set()
        customer_caused_anomalies = set()
        segment_signals = {}

        for key in keys_to_evaluate:
            # Get current stats for this key
            if key == "OVERALL":
                key_current = current_stats
            elif key in current_stats["by_method"]:
                key_current = current_stats["by_method"][key]
            else:
                key_current = current_stats["segments"][key]

            # Skip if volume is below min_attempts_limited
            if key_current["attempts"] < self.config.min_attempts_limited:
                continue

            # Get baseline for this key
            key_baseline = self._aggregate_baseline(baseline, key)
            if not key_baseline or key_baseline["attempts"] == 0:
                continue

            # Calculate signals for this segment
            wrapped_baseline = {"overall": key_baseline, "period": baseline.get("period", {"days": 14})}
            
            suc_signal = self._calculate_success_rate_signal(wrapped_baseline, key_current)
            tech_signal = self._calculate_technical_error_signal(wrapped_baseline, key_current)
            cust_signal = self._calculate_customer_error_signal(wrapped_baseline, key_current)
            vol_signal = self._calculate_volume_signal(wrapped_baseline, key_current, window_start, window_end)
            lat_signal = self._calculate_latency_signal(wrapped_baseline, key_current)

            active_segments[key] = key_current
            segment_signals[key] = {
                "success_rate_signal": suc_signal,
                "technical_error_signal": tech_signal,
                "customer_error_signal": cust_signal,
                "volume_signal": vol_signal,
                "latency_signal": lat_signal,
                "baseline_stats": key_baseline
            }

            # Check if this segment is degraded
            success_rate_declining = suc_signal["difference"] < 0
            success_drop_pp = abs(suc_signal["difference_percentage_points"])
            statistically_significant = suc_signal["statistically_significant"]

            concerning_threshold_pp = self.config.min_success_rate_drop_concerning * 100 if self.config.min_success_rate_drop_concerning < 1.0 else self.config.min_success_rate_drop_concerning
            is_degraded = success_rate_declining and statistically_significant and success_drop_pp >= concerning_threshold_pp

            # Check for technical/latency/volume drop evidence
            tech_status = tech_signal["status"]
            lat_status = lat_signal["status"]
            vol_status = vol_signal["status"]

            has_tech_evidence = tech_status in ["WARNING", "CRITICAL", "CONCERNING"]
            has_lat_evidence = lat_status in ["WARNING", "CRITICAL", "CONCERNING"]
            has_vol_evidence = vol_status in ["SIGNIFICANT_DECREASE", "NOTABLE_DECREASE"]

            # Scenario E check: is it primarily customer-caused?
            cust_change = cust_signal["absolute_change"]
            tech_change = tech_signal["absolute_change"]
            is_customer_caused = cust_change > 0.01 and (cust_change >= 2.0 * tech_change or tech_status in ["NORMAL", "ELEVATED"])

            if is_degraded:
                if is_customer_caused:
                    customer_caused_anomalies.add(key)
                elif has_tech_evidence or has_lat_evidence or has_vol_evidence:
                    anomalies.add(key)

        classification = "NORMAL"
        severity = "LOW"
        candidate_key = None
        evidence = []

        if anomalies:
            pruned_anomalies = self._prune_anomalies(anomalies, active_segments)
            if not pruned_anomalies:
                pruned_anomalies = anomalies
            candidate_key = max(
                pruned_anomalies,
                key=lambda k: (
                    1 if active_segments[k]["attempts"] >= self.config.min_attempts_sufficient else 0,
                    abs(segment_signals[k]["success_rate_signal"]["difference_percentage_points"])
                )
            )
            cand_signals = segment_signals[candidate_key]
            cand_current = active_segments[candidate_key]
            cand_suc = cand_signals["success_rate_signal"]
            cand_tech = cand_signals["technical_error_signal"]
            cand_cust = cand_signals["customer_error_signal"]
            cand_vol = cand_signals["volume_signal"]
            cand_lat = cand_signals["latency_signal"]

            # Determine sufficiency for candidate key
            sufficiency = self._assess_sample_sufficiency(cand_current["attempts"])
            if sufficiency == "SUFFICIENT":
                classification = "INCIDENT"
            else:
                classification = "SUSPICIOUS"

            # Determine severity based on success drop pp
            drop_pp = abs(cand_suc["difference_percentage_points"])
            critical_threshold_pp = self.config.min_success_rate_drop_critical * 100 if self.config.min_success_rate_drop_critical < 1.0 else self.config.min_success_rate_drop_critical
            warning_threshold_pp = self.config.min_success_rate_drop_warning * 100 if self.config.min_success_rate_drop_warning < 1.0 else self.config.min_success_rate_drop_warning

            if drop_pp >= critical_threshold_pp:
                severity = "HIGH"
            elif drop_pp >= warning_threshold_pp:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            # Populate evidence
            segment_name = f"Segment {candidate_key}" if candidate_key != "OVERALL" else "Overall merchant"
            evidence.append(
                f"{segment_name} success rate dropped {drop_pp:.1f} percentage points "
                f"(baseline: {cand_signals['baseline_stats']['success_rate']:.3f}, current: {cand_current['success_rate']:.3f})"
            )
            if cand_suc["statistically_significant"]:
                evidence.append(f"Success rate drop in {candidate_key} is statistically significant")
            else:
                evidence.append(f"Success rate drop in {candidate_key} is not statistically significant")

            if cand_tech["status"] != "NORMAL":
                evidence.append(f"Technical error rate status is {cand_tech['status']} (baseline: {cand_tech['baseline_rate']:.3f}, current: {cand_tech['current_rate']:.3f})")
            if cand_lat["status"] != "NORMAL":
                evidence.append(f"P95 latency status is {cand_lat['status']} (baseline: {cand_lat['baseline_p95_ms']:.1f}ms, current: {cand_lat['current_p95_ms']:.1f}ms)")
            if cand_vol["status"] != "NORMAL":
                evidence.append(f"Payment volume status is {cand_vol['status']} (change: {cand_vol['change_pct']*100:.1f}%)")

            # Determine localization for candidate_key
            loc_signal = self._calculate_segment_localization(baseline, current_stats, candidate_key)
            if loc_signal["status"] == "LOCALIZED":
                evidence.append(f"Degradation appears localized to {candidate_key}")
            elif loc_signal["status"] == "WIDESPREAD":
                evidence.append("Degradation appears widespread across multiple segments")

            # Use candidate signals as top level signals for result
            success_rate_signal = cand_suc
            technical_error_signal = cand_tech
            customer_error_signal = cand_cust
            localization_signal = loc_signal
            volume_signal = cand_vol
            latency_signal = cand_lat

        elif customer_caused_anomalies:
            pruned_cust = self._prune_anomalies(customer_caused_anomalies, active_segments)
            if not pruned_cust:
                pruned_cust = customer_caused_anomalies
            candidate_key = max(
                pruned_cust,
                key=lambda k: (
                    1 if active_segments[k]["attempts"] >= self.config.min_attempts_sufficient else 0,
                    abs(segment_signals[k]["success_rate_signal"]["difference_percentage_points"])
                )
            )
            cand_signals = segment_signals[candidate_key]
            cand_current = active_segments[candidate_key]
            cand_suc = cand_signals["success_rate_signal"]
            drop_pp = abs(cand_suc["difference_percentage_points"])

            classification = "NORMAL"
            severity = "LOW"
            evidence.append(f"Success rate degraded {drop_pp:.1f} percentage points, but the increase is primarily customer-caused and technical errors remain within baseline.")

            loc_signal = self._calculate_segment_localization(baseline, current_stats, candidate_key)

            success_rate_signal = cand_suc
            technical_error_signal = cand_signals["technical_error_signal"]
            customer_error_signal = cand_signals["customer_error_signal"]
            localization_signal = loc_signal
            volume_signal = cand_signals["volume_signal"]
            latency_signal = cand_signals["latency_signal"]

        else:
            candidate_key = "OVERALL"
            wrapped_overall_baseline = {"overall": baseline["overall"], "period": baseline.get("period", {"days": 14})}
            success_rate_signal = self._calculate_success_rate_signal(wrapped_overall_baseline, current_stats)
            technical_error_signal = self._calculate_technical_error_signal(wrapped_overall_baseline, current_stats)
            customer_error_signal = self._calculate_customer_error_signal(wrapped_overall_baseline, current_stats)
            localization_signal = {
                "affected_segment": None,
                "affected_segment_success_rate": None,
                "other_banks": None,
                "other_devices": None,
                "other_methods": None,
                "status": "HEALTHY"
            }
            volume_signal = self._calculate_volume_signal(wrapped_overall_baseline, current_stats, window_start, window_end)
            latency_signal = self._calculate_latency_signal(wrapped_overall_baseline, current_stats)

            evidence.append(
                f"Overall merchant success rate is healthy at {current_stats['success_rate']:.3f} "
                f"(baseline: {baseline['overall']['success_rate']:.3f})"
            )

        candidate_segment_dict = self._parse_candidate_segment_key(candidate_key, active_segments.get(candidate_key, current_stats))

        # Build result
        result = {
            "merchant_id": merchant_id,
            "window": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
                "duration_minutes": int((window_end - window_start).total_seconds() / 60)
            },
            "classification": classification,
            "severity": severity,
            "candidate_segment": candidate_segment_dict,
            "sample": {
                "attempts": current_stats["attempts"],
                "sufficiency": self._assess_sample_sufficiency(current_stats["attempts"])
            },
            "success_rate_signal": success_rate_signal,
            "technical_error_signal": technical_error_signal,
            "customer_error_signal": customer_error_signal,
            "localization_signal": localization_signal,
            "volume_signal": volume_signal,
            "latency_signal": latency_signal,
            "evidence": evidence
        }

        return result

    def _parse_candidate_segment_key(self, key: str, segment_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Convert segment key string to structured candidate segment dict."""
        if not key or key == "OVERALL":
            return {
                "payment_method": "ALL",
                "bank": None,
                "device": None,
                "upi_app": None,
                "attempts": segment_stats.get("attempts", 0),
                "success_rate": segment_stats.get("success_rate", 0.0)
            }

        parts = key.split("|")
        method = parts[0]
        bank = None
        device = None
        upi_app = None

        if len(parts) == 1:
            if parts[0] in ["ANDROID", "IOS", "WEB"]:
                device = parts[0]
                method = "ALL"
            else:
                method = parts[0]
        elif len(parts) == 2:
            method = parts[0]
            if parts[1] in ["ANDROID", "IOS", "WEB"]:
                device = parts[1]
            else:
                bank = parts[1]
        elif len(parts) == 3:
            method = parts[0]
            bank = parts[1]
            device = parts[2]
        elif len(parts) == 4:
            method = parts[0]
            bank = parts[1]
            device = parts[2]
            upi_app = parts[3]

        return {
            "payment_method": method,
            "bank": bank,
            "device": device,
            "upi_app": upi_app,
            "attempts": segment_stats.get("attempts", 0),
            "success_rate": segment_stats.get("success_rate", 0.0)
        }

    def _calculate_segment_localization(
        self,
        baseline: Dict[str, Any],
        current_stats: Dict[str, Any],
        candidate_key: str
    ) -> Dict[str, Any]:
        if not candidate_key or candidate_key == "OVERALL":
            return {
                "affected_segment": "OVERALL",
                "affected_segment_success_rate": current_stats["success_rate"],
                "other_banks": None,
                "other_devices": None,
                "other_methods": None,
                "status": "WIDESPREAD"
            }

        leaf_key = None
        for seg_key in current_stats["segments"].keys():
            if seg_key == candidate_key or seg_key.startswith(candidate_key + "|"):
                leaf_key = seg_key
                break

        if not leaf_key:
            return {
                "affected_segment": candidate_key,
                "affected_segment_success_rate": 0.0,
                "other_banks": None,
                "other_devices": None,
                "other_methods": None,
                "status": "WIDESPREAD"
            }

        segment_parts = leaf_key.split("|")
        method = segment_parts[0]

        control_rates = self._calculate_control_segment_rates(
            current_stats, method, segment_parts
        )

        if candidate_key in current_stats["segments"]:
            affected_rate = current_stats["segments"][candidate_key]["success_rate"]
        elif candidate_key in current_stats["by_method"]:
            affected_rate = current_stats["by_method"][candidate_key]["success_rate"]
        else:
            affected_rate = current_stats["success_rate"]

        localization_status = self._determine_localization_status(
            affected_rate, control_rates
        )

        return {
            "affected_segment": candidate_key,
            "affected_segment_success_rate": affected_rate,
            "other_banks": control_rates.get("other_banks"),
            "other_devices": control_rates.get("other_devices"),
            "other_methods": control_rates.get("other_methods"),
            "status": localization_status
        }

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

    def _analyze_payment_window(
        self,
        payments: List[Dict[str, Any]],
        profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze a window of payments and compute statistics."""
        if not payments:
            return self._empty_stats()

        # Overall stats
        attempts = len(payments)
        successes = sum(1 for p in payments if p["status"] == "success")
        failures = attempts - successes

        # Calculate overall failure breakdown
        overall_failure_breakdown = {"customer_caused": 0, "technical": 0, "other": 0}
        for payment in payments:
            if payment["status"] == "failed":
                failure_type = categorize_failure(payment.get("error_code"))
                overall_failure_breakdown[failure_type] += 1

        amounts = [p["amount"] / 100 for p in payments]
        latencies = [p["latency_ms"] for p in payments]

        # Group payments by payment method
        method_groups = defaultdict(list)
        for payment in payments:
            method_groups[payment["payment_method"]].append(payment)

        by_method = {}
        for method, method_payments in method_groups.items():
            method_attempts = len(method_payments)
            method_successes = sum(1 for p in method_payments if p["status"] == "success")

            method_amounts = [p["amount"] / 100 for p in method_payments]
            method_latencies = [p["latency_ms"] for p in method_payments]

            method_failure_breakdown = {"customer_caused": 0, "technical": 0, "other": 0}
            for payment in method_payments:
                if payment["status"] == "failed":
                    failure_type = categorize_failure(payment.get("error_code"))
                    method_failure_breakdown[failure_type] += 1

            by_method[method] = {
                "attempts": method_attempts,
                "successes": method_successes,
                "failures": method_attempts - method_successes,
                "success_rate": method_successes / method_attempts if method_attempts > 0 else 0,
                "failure_rate": (method_attempts - method_successes) / method_attempts if method_attempts > 0 else 0,
                "average_amount": statistics.mean(method_amounts) if method_amounts else 0,
                "median_amount": statistics.median(method_amounts) if method_amounts else 0,
                "average_latency_ms": statistics.mean(method_latencies) if method_latencies else 0,
                "p95_latency_ms": calculate_percentiles(method_latencies, [95])["p95"] if method_latencies else 0,
                "failure_breakdown": method_failure_breakdown
            }

        # Build segment groups for all hierarchical levels
        segment_groups = defaultdict(list)
        for payment in payments:
            method = payment["payment_method"]
            bank = payment.get("bank")
            device = payment.get("device")
            upi_app = payment.get("upi_app")

            # 1. Device key
            if device:
                segment_groups[device].append(payment)
            
            # 2. Method + Device key
            if method and device:
                segment_groups[f"{method}|{device}"].append(payment)
                
            # 3. UPI specific keys
            if method == "UPI":
                if bank:
                    segment_groups[f"UPI|{bank}"].append(payment)
                if bank and device:
                    segment_groups[f"UPI|{bank}|{device}"].append(payment)
                if bank and device and upi_app:
                    segment_groups[f"UPI|{bank}|{device}|{upi_app}"].append(payment)
                if upi_app:
                    segment_groups[f"UPI|{upi_app}"].append(payment)

        segments = {}
        for segment_key, segment_payments in segment_groups.items():
            segment_attempts = len(segment_payments)
            segment_successes = sum(1 for p in segment_payments if p["status"] == "success")

            segment_amounts = [p["amount"] / 100 for p in segment_payments]
            segment_latencies = [p["latency_ms"] for p in segment_payments]

            segment_failure_breakdown = {"customer_caused": 0, "technical": 0, "other": 0}
            error_code_dist = defaultdict(int)
            for payment in segment_payments:
                if payment["status"] == "failed":
                    failure_type = categorize_failure(payment.get("error_code"))
                    segment_failure_breakdown[failure_type] += 1
                    if payment.get("error_code"):
                        error_code_dist[payment["error_code"]] += 1

            # Calculate hourly patterns
            hourly_data = defaultdict(lambda: {"attempts": 0, "successes": 0, "latencies": []})
            for payment in segment_payments:
                dt = parse_timestamp(payment["timestamp"])
                hour = dt.hour
                hourly_data[hour]["attempts"] += 1
                if payment["status"] == "success":
                    hourly_data[hour]["successes"] += 1
                hourly_data[hour]["latencies"].append(payment["latency_ms"])

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

            success_rate_stats = calculate_statistics(success_rates_for_stddev) if success_rates_for_stddev else {"mean": 0, "stddev": 0, "min": 0, "max": 0}

            segments[segment_key] = {
                "attempts": segment_attempts,
                "successes": segment_successes,
                "failures": segment_attempts - segment_successes,
                "success_rate": segment_successes / segment_attempts if segment_attempts > 0 else 0,
                "failure_rate": (segment_attempts - segment_successes) / segment_attempts if segment_attempts > 0 else 0,
                "average_amount": statistics.mean(segment_amounts) if segment_amounts else 0,
                "median_amount": statistics.median(segment_amounts) if segment_amounts else 0,
                "average_latency_ms": statistics.mean(segment_latencies) if segment_latencies else 0,
                "p95_latency_ms": calculate_percentiles(segment_latencies, [95])["p95"] if segment_latencies else 0,
                "failure_breakdown": segment_failure_breakdown,
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

        return {
            "attempts": attempts,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / attempts if attempts > 0 else 0,
            "failure_rate": failures / attempts if attempts > 0 else 0,
            "failure_breakdown": overall_failure_breakdown,
            "average_amount": statistics.mean(amounts) if amounts else 0,
            "median_amount": statistics.median(amounts) if amounts else 0,
            "average_latency_ms": statistics.mean(latencies) if latencies else 0,
            "p95_latency_ms": calculate_percentiles(latencies, [95])["p95"] if latencies else 0,
            "by_method": by_method,
            "segments": segments
        }

    def _empty_stats(self) -> Dict[str, Any]:
        """Return empty statistics structure."""
        return {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": 0,
            "failure_rate": 0,
            "failure_breakdown": {"customer_caused": 0, "technical": 0, "other": 0},
            "average_amount": 0,
            "median_amount": 0,
            "average_latency_ms": 0,
            "p95_latency_ms": 0,
            "by_method": {},
            "segments": {}
        }

    def _calculate_success_rate_signal(
        self,
        baseline: Dict[str, Any],
        current_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate success rate deviation signal."""
        baseline_rate = baseline["overall"]["success_rate"]
        current_rate = current_stats["success_rate"]
        absolute_change = current_rate - baseline_rate

        # Two-proportion z-test for statistical significance
        bas_n = baseline["overall"]["attempts"]
        bas_s = baseline["overall"]["successes"]
        cur_n = current_stats["attempts"]
        cur_s = current_stats["successes"]

        # Pooled proportion for standard error
        if bas_n + cur_n > 0 and bas_s + cur_s >= 0:
            pooled_p = (bas_s + cur_s) / (bas_n + cur_n)
            if pooled_p > 0 and pooled_p < 1:
                se = math.sqrt(pooled_p * (1 - pooled_p) * (1/bas_n + 1/cur_n))
                if se > 0:
                    z_score = absolute_change / se
                    # Two-tailed p-value
                    p_value = 2 * (1 - self._normal_cdf(abs(z_score)))
                    statistically_significant = p_value < self.config.significance_level
                else:
                    p_value = 1.0
                    statistically_significant = False
                    z_score = 0
            else:
                p_value = 1.0
                statistically_significant = False
                z_score = 0
        else:
            p_value = 1.0
            statistically_significant = False
            z_score = 0

        return {
            "baseline": baseline_rate,
            "current": current_rate,
            "difference": absolute_change,
            "difference_percentage_points": absolute_change * 100,
            "relative_change": absolute_change / baseline_rate if baseline_rate > 0 else 0,
            "statistically_significant": statistically_significant,
            "p_value": p_value,
            "z_score": z_score
        }

    def _normal_cdf(self, x: float) -> float:
        """Cumulative distribution function for standard normal distribution."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _calculate_technical_error_signal(
        self,
        baseline: Dict[str, Any],
        current_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate technical error rate signal."""
        baseline_technical_rate = baseline["overall"]["failure_rate"] * (
            baseline["overall"]["failure_breakdown"]["technical"] /
            max(baseline["overall"]["failures"], 1)
        ) if baseline["overall"]["failures"] > 0 else 0

        # Handle case where there are no failures in current window
        technical_failures = 0
        if current_stats["failures"] > 0 and "failure_breakdown" in current_stats:
            technical_failures = current_stats["failure_breakdown"].get("technical", 0)
            current_technical_rate = current_stats["failure_rate"] * (
                technical_failures /
                max(current_stats["failures"], 1)
            )
        else:
            current_technical_rate = 0.0

        absolute_change = current_technical_rate - baseline_technical_rate
        relative_change = (
            absolute_change / baseline_technical_rate
            if baseline_technical_rate > 0 else
            (float('inf') if absolute_change > 0 else 0)
        )

        return {
            "baseline_rate": baseline_technical_rate,
            "current_rate": current_technical_rate,
            "absolute_change": absolute_change,
            "relative_change": relative_change,
            "status": self._assess_technical_error_status(absolute_change, baseline_technical_rate, technical_failures)
        }

    def _assess_technical_error_status(
        self,
        absolute_change: float,
        baseline_rate: float,
        technical_failures_count: int
    ) -> str:
        """Assess technical error status based on increase magnitude."""
        if technical_failures_count < 3:
            return "NORMAL" if absolute_change <= 0.01 else "ELEVATED"

        if baseline_rate <= 0:
            return "NORMAL" if absolute_change <= 0.01 else "ELEVATED"

        increase_factor = absolute_change / baseline_rate if baseline_rate > 0 else float('inf')

        if increase_factor >= self.config.technical_error_increase_critical:
            return "CRITICAL"
        elif increase_factor >= self.config.technical_error_increase_warning:
            return "WARNING"
        elif increase_factor >= self.config.technical_error_increase_concerning:
            return "CONCERNING"
        elif absolute_change <= 0.005:  # Very small absolute increase
            return "NORMAL"
        else:
            return "ELEVATED"

    def _calculate_customer_error_signal(
        self,
        baseline: Dict[str, Any],
        current_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate customer error rate signal."""
        baseline_customer_rate = baseline["overall"]["failure_rate"] * (
            baseline["overall"]["failure_breakdown"]["customer_caused"] /
            max(baseline["overall"]["failures"], 1)
        ) if baseline["overall"]["failures"] > 0 else 0

        # Handle case where there are no failures in current window or missing failure_breakdown
        if current_stats["failures"] > 0 and "failure_breakdown" in current_stats:
            current_customer_rate = current_stats["failure_rate"] * (
                current_stats["failure_breakdown"]["customer_caused"] /
                max(current_stats["failures"], 1)
            )
        else:
            current_customer_rate = 0.0

        absolute_change = current_customer_rate - baseline_customer_rate

        return {
            "baseline_rate": baseline_customer_rate,
            "current_rate": current_customer_rate,
            "absolute_change": absolute_change,
            "status": "INCREASED" if absolute_change > 0.01 else "DECREASED" if absolute_change < -0.01 else "NORMAL"
        }

    def _calculate_localization_signal(
        self,
        baseline: Dict[str, Any],
        current_stats: Dict[str, Any],
        merchant_id: str,
        generated_data_dir: Path
    ) -> Dict[str, Any]:
        """Calculate localization signal by comparing affected segment to controls."""
        # Find the worst-performing segment
        worst_segment_key = None
        worst_segment_success_rate = float('inf')

        for segment_key, segment_data in current_stats["segments"].items():
            if segment_data["attempts"] >= self.config.min_attempts_limited:
                if segment_data["success_rate"] < worst_segment_success_rate:
                    worst_segment_success_rate = segment_data["success_rate"]
                    worst_segment_key = segment_key

        if worst_segment_key is None:
            return {
                "affected_segment": None,
                "other_banks": None,
                "other_devices": None,
                "other_methods": None,
                "status": "NO_SUFFICIENT_SEGMENT"
            }

        # Parse the worst segment
        segment_parts = worst_segment_key.split("|")
        method = segment_parts[0]

        # Calculate control segment success rates
        control_rates = self._calculate_control_segment_rates(
            current_stats, method, segment_parts
        )

        affected_rate = current_stats["segments"][worst_segment_key]["success_rate"]

        # Determine localization status
        localization_status = self._determine_localization_status(
            affected_rate, control_rates
        )

        return {
            "affected_segment": worst_segment_key,
            "affected_segment_success_rate": affected_rate,
            "other_banks": control_rates.get("other_banks"),
            "other_devices": control_rates.get("other_devices"),
            "other_methods": control_rates.get("other_methods"),
            "status": localization_status
        }

    def _calculate_control_segment_rates(
        self,
        current_stats: Dict[str, Any],
        method: str,
        segment_parts: List[str]
    ) -> Dict[str, Optional[float]]:
        """Calculate success rates for control segments."""
        control_rates = {
            "other_banks": None,
            "other_devices": None,
            "other_methods": None
        }

        if method == "UPI" and len(segment_parts) >= 4:
            # UPI segment: method|bank|device|upi_app
            _, bank, device, upi_app = segment_parts

            # Other banks (same device and upi_app)
            other_bank_rates = []
            for segment_key, segment_data in current_stats["segments"].items():
                parts = segment_key.split("|")
                if (len(parts) == 4 and
                    parts[0] == "UPI" and
                    parts[2] == device and
                    parts[3] == upi_app and
                    parts[1] != bank and  # Different bank
                    segment_data["attempts"] >= self.config.min_attempts_limited):
                    other_bank_rates.append(segment_data["success_rate"])

            if other_bank_rates:
                control_rates["other_banks"] = statistics.mean(other_bank_rates)

            # Other devices (same bank and upi_app)
            other_device_rates = []
            for segment_key, segment_data in current_stats["segments"].items():
                parts = segment_key.split("|")
                if (len(parts) == 4 and
                    parts[0] == "UPI" and
                    parts[1] == bank and
                    parts[3] == upi_app and
                    parts[2] != device and  # Different device
                    segment_data["attempts"] >= self.config.min_attempts_limited):
                    other_device_rates.append(segment_data["success_rate"])

            if other_device_rates:
                control_rates["other_devices"] = statistics.mean(other_device_rates)

        # Other methods (any successful method)
        method_rates = []
        for m, method_data in current_stats["by_method"].items():
            if (m != method and
                method_data["attempts"] >= self.config.min_attempts_limited):
                method_rates.append(method_data["success_rate"])

        if method_rates:
            control_rates["other_methods"] = statistics.mean(method_rates)

        return control_rates

    def _determine_localization_status(
        self,
        affected_rate: float,
        control_rates: Dict[str, Optional[float]]
    ) -> str:
        """Determine if degradation is localized."""
        # Check if control segments are healthy
        healthy_controls = []
        unhealthy_controls = []

        for control_type, rate in control_rates.items():
            if rate is not None:
                # Healthy if within tolerance of overall success rate or better
                # For simplicity, consider healthy if > 85% success rate
                if rate > 0.85:
                    healthy_controls.append(control_type)
                else:
                    unhealthy_controls.append(control_type)

        # Localized if affected segment is degraded but controls are healthy
        if affected_rate < 0.85 and len(healthy_controls) > 0:
            return "LOCALIZED"
        elif affected_rate < 0.85 and len(unhealthy_controls) > 0:
            return "WIDESPREAD"
        else:
            return "HEALTHY"

    def _calculate_volume_signal(
        self,
        baseline: Dict[str, Any],
        current_stats: Dict[str, Any],
        window_start: datetime,
        window_end: datetime
    ) -> Dict[str, Any]:
        """Calculate volume anomaly signal."""
        # Expected volume per minute from baseline
        baseline_days = baseline["period"]["days"]
        baseline_attempts = baseline["overall"]["attempts"]
        baseline_minutes = baseline_days * 24 * 60
        expected_rate_per_minute = baseline_attempts / baseline_minutes if baseline_minutes > 0 else 0

        window_duration_minutes = (window_end - window_start).total_seconds() / 60
        expected_window_volume = expected_rate_per_minute * window_duration_minutes

        current_volume = current_stats["attempts"]
        volume_difference = current_volume - expected_window_volume
        volume_change_pct = (
            volume_difference / expected_window_volume
            if expected_window_volume > 0 else 0
        )

        return {
            "baseline_expected": expected_window_volume,
            "current": current_volume,
            "absolute_change": volume_difference,
            "change_pct": volume_change_pct,
            "status": self._assess_volume_status(volume_change_pct)
        }

    def _assess_volume_status(self, change_pct: float) -> str:
        """Assess volume status based on percentage change."""
        if change_pct <= -self.config.volume_decrease_warning:
            return "SIGNIFICANT_DECREASE"
        elif change_pct <= -self.config.volume_decrease_concerning:
            return "NOTABLE_DECREASE"
        elif change_pct >= 0.5:  # 50% increase
            return "SIGNIFICANT_INCREASE"
        elif change_pct >= 0.2:  # 20% increase
            return "NOTABLE_INCREASE"
        else:
            return "NORMAL"

    def _calculate_latency_signal(
        self,
        baseline: Dict[str, Any],
        current_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate latency signal."""
        baseline_p95 = baseline["overall"]["p95_latency_ms"]
        current_p95 = current_stats["p95_latency_ms"]

        absolute_change = current_p95 - baseline_p95
        relative_change = absolute_change / baseline_p95 if baseline_p95 > 0 else 0

        return {
            "baseline_p95_ms": baseline_p95,
            "current_p95_ms": current_p95,
            "absolute_change_ms": absolute_change,
            "relative_change": relative_change,
            "status": self._assess_latency_status(absolute_change, baseline_p95)
        }

    def _assess_latency_status(
        self,
        absolute_change: float,
        baseline_p95: float
    ) -> str:
        """Assess latency status based on increase magnitude."""
        if baseline_p95 <= 0:
            return "NORMAL" if absolute_change <= 100 else "ELEVATED"

        increase_factor = absolute_change / baseline_p95 if baseline_p95 > 0 else float('inf')

        if increase_factor >= 3.0:  # 3x increase
            return "CRITICAL"
        elif increase_factor >= 2.0:  # 2x increase
            return "WARNING"
        elif increase_factor >= 1.5:  # 1.5x increase
            return "CONCERNING"
        elif absolute_change <= 50:  # Small absolute increase
            return "NORMAL"
        else:
            return "ELEVATED"

    def _assess_sample_sufficiency(self, attempts: int) -> str:
        """Assess sample size sufficiency."""
        if attempts >= self.config.min_attempts_sufficient:
            return "SUFFICIENT"
        elif attempts >= self.config.min_attempts_limited:
            return "LIMITED"
        else:
            return "INSUFFICIENT"

    def _identify_candidate_segment(self, current_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Identify the candidate segment for reporting."""
        # Find segment with lowest success rate that has sufficient data
        worst_segment_key = None
        worst_success_rate = float('inf')

        for segment_key, segment_data in current_stats["segments"].items():
            if (segment_data["attempts"] >= self.config.min_attempts_limited and
                segment_data["success_rate"] < worst_success_rate):
                worst_success_rate = segment_data["success_rate"]
                worst_segment_key = segment_key

        if worst_segment_key is None:
            # Fallback to overall method breakdown
            worst_method = None
            worst_method_rate = float('inf')

            for method, method_data in current_stats["by_method"].items():
                if (method_data["attempts"] >= self.config.min_attempts_limited and
                    method_data["success_rate"] < worst_method_rate):
                    worst_method_rate = method_data["success_rate"]
                    worst_method = method

            if worst_method is None:
                return {"payment_method": "UNKNOWN", "reason": "INSUFFICIENT_DATA"}

            return {
                "payment_method": worst_method,
                "bank": None,
                "device": None,
                "upi_app": None,
                "reason": "METHOD_LEVEL_ONLY"
            }

        # Parse segment key
        parts = worst_segment_key.split("|")
        method = parts[0]

        result = {
            "payment_method": method,
            "attempts": current_stats["segments"][worst_segment_key]["attempts"],
            "success_rate": current_stats["segments"][worst_segment_key]["success_rate"]
        }

        if method in ["CARD", "NETBANKING"]:
            if len(parts) >= 2:
                result["device"] = parts[1]
            result["bank"] = None
            result["upi_app"] = None
        else:  # UPI
            if len(parts) >= 4:
                result["bank"] = parts[1]
                result["device"] = parts[2]
                result["upi_app"] = parts[3]
            else:
                result["bank"] = None
                result["device"] = None
                result["upi_app"] = None

        return result

    def _make_classification_decision(
        self,
        success_rate_signal: Dict[str, Any],
        technical_error_signal: Dict[str, Any],
        customer_error_signal: Dict[str, Any],
        localization_signal: Dict[str, Any],
        volume_signal: Dict[str, Any],
        latency_signal: Dict[str, Any],
        current_stats: Dict[str, Any]
    ) -> Tuple[str, str, List[str]]:
        """
        Make classification decision based on signals.

        Returns:
            Tuple of (classification, severity, evidence_list)
        """
        evidence = []

        # Check sample sufficiency
        sample_sufficiency = self._assess_sample_sufficiency(current_stats["attempts"])
        if sample_sufficiency == "INSUFFICIENT":
            evidence.append(f"Insufficient sample size: {current_stats['attempts']} attempts")
            return "NORMAL", "LOW", evidence

        # Success rate deviation
        success_drop_pp = abs(success_rate_signal["difference_percentage_points"])
        success_significant = success_rate_signal["statistically_significant"]
        success_declining = success_rate_signal["difference"] < 0

        if success_declining:
            evidence.append(
                f"Success rate dropped {success_drop_pp:.1f} percentage points "
                f"(baseline: {success_rate_signal['baseline']:.3f}, "
                f"current: {success_rate_signal['current']:.3f})"
            )

            if success_significant:
                evidence.append("Success rate drop is statistically significant")
            else:
                evidence.append("Success rate drop is not statistically significant")
        else:
            evidence.append("Success rate is stable or improved")

        # Technical error signal
        tech_status = technical_error_signal["status"]
        if tech_status in ["WARNING", "CRITICAL"]:
            evidence.append(
                f"Technical error rate increased {technical_error_signal['relative_change']:.1f}x "
                f"(baseline: {technical_error_signal['baseline_rate']:.3f}, "
                f"current: {technical_error_signal['current_rate']:.3f})"
            )
        elif tech_status == "CONCERNING":
            evidence.append("Technical error rate moderately elevated")

        # Customer error signal
        cust_change = customer_error_signal["absolute_change"]
        if cust_change > 0.01:  # 1 pp increase
            evidence.append(
                f"Customer-caused error rate increased {cust_change*100:.1f} percentage points"
            )
        elif cust_change < -0.01:  # 1 pp decrease
            evidence.append(
                f"Customer-caused error rate decreased {abs(cust_change)*100:.1f} percentage points"
            )

        # Localization signal
        loc_status = localization_signal["status"]
        if loc_status == "LOCALIZED":
            evidence.append("Degradation appears localized to specific segment")
        elif loc_status == "WIDESPREAD":
            evidence.append("Degradation appears widespread across multiple segments")
        elif loc_status == "HEALTHY":
            evidence.append("All segments appear healthy")

        # Volume signal
        vol_status = volume_signal["status"]
        if vol_status in ["SIGNIFICANT_DECREASE", "NOTABLE_DECREASE"]:
            evidence.append(
                f"Payment volume decreased {abs(volume_signal['change_pct'])*100:.1f}%"
            )
        elif vol_status in ["SIGNIFICANT_INCREASE", "NOTABLE_INCREASE"]:
            evidence.append(
                f"Payment volume increased {volume_signal['change_pct']*100:.1f}%"
            )

        # Latency signal
        lat_status = latency_signal["status"]
        if lat_status in ["WARNING", "CRITICAL"]:
            evidence.append(
                f"Latency increased {latency_signal['relative_change']*100:.1f}% "
                f"(baseline: {latency_signal['baseline_p95_ms']:.0f}ms, "
                f"current: {latency_signal['current_p95_ms']:.0f}ms)"
            )
        elif lat_status == "CONCERNING":
            evidence.append("Latency moderately elevated")

        # Decision logic
        classification, severity = self._apply_decision_logic(
            success_declining, success_drop_pp, success_significant,
            tech_status, cust_change, loc_status,
            vol_status, lat_status, current_stats["attempts"]
        )

        return classification, severity, evidence

    def _apply_decision_logic(
        self,
        success_declining: bool,
        success_drop_pp: float,
        success_significant: bool,
        tech_status: str,
        cust_change: float,
        loc_status: str,
        vol_status: str,
        lat_status: str,
        attempts: int
    ) -> Tuple[str, str]:
        """Apply decision logic to determine classification and severity."""

        # Rule 1: Insufficient evidence for incident
        if not success_declining or success_drop_pp < self.config.min_success_rate_drop_concerning:
            return "NORMAL", "LOW"

        # Rule 2: Sample size too low for confident incident
        if attempts < self.config.min_attempts_sufficient:
            return "SUSPICIOUS", "LOW"

        # Rule 3: Success rate drop not statistically significant
        if not success_significant:
            return "SUSPICIOUS", "MEDIUM"

        # Rule 4: Check for Scenario E pattern (customer errors up, technical errors normal)
        if cust_change > 0.01 and tech_status in ["NORMAL", "ELEVATED"]:
            # Customer errors increased, technical errors not significantly up
            # This suggests user-side issues, not technical degradation
            return "NORMAL", "LOW"

        # Rule 5: Determine if we have enough evidence for incident
        has_technical_evidence = tech_status in ["WARNING", "CRITICAL", "CONCERNING"]
        has_localization_evidence = loc_status == "LOCALIZED"
        has_latency_evidence = lat_status in ["WARNING", "CRITICAL", "CONCERNING"]

        evidence_count = sum([
            has_technical_evidence,
            has_localization_evidence,
            has_latency_evidence
        ])

        # Rule 6: Strong incident requires multiple corroborating signals
        if success_drop_pp >= self.config.min_success_rate_drop_critical and evidence_count >= 2:
            classification = "INCIDENT"
            severity = "HIGH"
        elif success_drop_pp >= self.config.min_success_rate_drop_warning and evidence_count >= 1:
            classification = "INCIDENT"
            severity = "MEDIUM"
        elif success_drop_pp >= self.config.min_success_rate_drop_concerning:
            classification = "SUSPICIOUS"
            severity = "MEDIUM" if evidence_count > 0 else "LOW"
        else:
            classification = "SUSPICIOUS"
            severity = "LOW"

        return classification, severity

    def _create_insufficient_data_result(
        self,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime
    ) -> Dict[str, Any]:
        """Create result when insufficient data is available."""
        return {
            "merchant_id": merchant_id,
            "window": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
                "duration_minutes": int((window_end - window_start).total_seconds() / 60)
            },
            "classification": "NORMAL",
            "severity": "LOW",
            "candidate_segment": {
                "payment_method": "UNKNOWN",
                "reason": "NO_DATA_IN_WINDOW"
            },
            "sample": {
                "attempts": 0,
                "sufficiency": "INSUFFICIENT"
            },
            "success_rate_signal": {
                "baseline": 0.0,
                "current": 0.0,
                "difference": 0.0,
                "difference_percentage_points": 0.0,
                "relative_change": 0.0,
                "statistically_significant": False,
                "p_value": 1.0,
                "z_score": 0.0
            },
            "technical_error_signal": {
                "baseline_rate": 0.0,
                "current_rate": 0.0,
                "absolute_change": 0.0,
                "relative_change": 0.0,
                "status": "NORMAL"
            },
            "customer_error_signal": {
                "baseline_rate": 0.0,
                "current_rate": 0.0,
                "absolute_change": 0.0,
                "status": "NORMAL"
            },
            "localization_signal": {
                "affected_segment": None,
                "affected_segment_success_rate": None,
                "other_banks": None,
                "other_devices": None,
                "other_methods": None,
                "status": "NO_DATA"
            },
            "volume_signal": {
                "baseline_expected": 0.0,
                "current": 0.0,
                "absolute_change": 0.0,
                "change_pct": 0.0,
                "status": "NO_DATA"
            },
            "latency_signal": {
                "baseline_p95_ms": 0.0,
                "current_p95_ms": 0.0,
                "absolute_change_ms": 0.0,
                "relative_change": 0.0,
                "status": "NO_DATA"
            },
            "evidence": [
                f"No payment data found in window {window_start.isoformat()} to {window_end.isoformat()}"
            ]
        }

    def _matches_hierarchy(self, segment_key: str, h_parts: List[str]) -> bool:
        s_parts = segment_key.split("|")
        
        # 1. Device-only key: e.g. "ANDROID"
        if len(h_parts) == 1 and h_parts[0] in ["ANDROID", "IOS", "WEB"]:
            if len(s_parts) == 2:
                return s_parts[1] == h_parts[0]
            elif len(s_parts) == 4:
                return s_parts[2] == h_parts[0]
            return False
            
        # 2. Method-only key: e.g. "UPI"
        if len(h_parts) == 1:
            return s_parts[0] == h_parts[0]
            
        # For multi-part keys, the first part must match the method
        if s_parts[0] != h_parts[0]:
            return False
            
        # 3. Method + Device key: e.g. "CARD|ANDROID" or "UPI|ANDROID"
        if len(h_parts) == 2 and h_parts[1] in ["ANDROID", "IOS", "WEB"]:
            if len(s_parts) == 2:
                return s_parts[1] == h_parts[1]
            elif len(s_parts) == 4:
                return s_parts[2] == h_parts[1]
            return False
            
        # 4. Method + Bank key: e.g. "UPI|BANK_X"
        if len(h_parts) == 2: # must be UPI bank
            if len(s_parts) == 4:
                return s_parts[1] == h_parts[1]
            return False
            
        # 5. Method + Bank + Device key: e.g. "UPI|BANK_X|ANDROID"
        if len(h_parts) == 3:
            if len(s_parts) == 4:
                return s_parts[1] == h_parts[1] and s_parts[2] == h_parts[2]
            return False
            
        # 6. Method + Bank + Device + App key: e.g. "UPI|BANK_X|ANDROID|PHONEPE"
        if len(h_parts) == 4:
            if len(s_parts) == 4:
                return s_parts[1] == h_parts[1] and s_parts[2] == h_parts[2] and s_parts[3] == h_parts[3]
            return False
            
        return False

    def _get_parent_keys(self, key: str) -> List[str]:
        if key == "OVERALL":
            return []
        h_parts = key.split("|")
        if len(h_parts) == 1:
            return ["OVERALL"]
        if len(h_parts) == 2:
            parents = [h_parts[0]]
            if h_parts[1] in ["ANDROID", "IOS", "WEB"]:
                parents.append(h_parts[1])
            return parents
        if len(h_parts) == 3:
            return [f"UPI|{h_parts[1]}", f"UPI|{h_parts[2]}"]
        if len(h_parts) == 4:
            return [f"UPI|{h_parts[1]}|{h_parts[2]}"]
        return []

    def _aggregate_baseline(self, baseline: Dict[str, Any], hierarchy_key: str) -> Optional[Dict[str, Any]]:
        h_parts = hierarchy_key.split("|")
        if hierarchy_key == "OVERALL":
            return baseline["overall"]
        if len(h_parts) == 1 and h_parts[0] not in ["ANDROID", "IOS", "WEB"]:
            return baseline["by_method"].get(hierarchy_key)
            
        attempts = 0
        successes = 0
        failures = 0
        weighted_latency = 0.0
        weighted_p95_latency = 0.0
        failure_breakdown = {"customer_caused": 0, "technical": 0, "other": 0}
        
        matched = False
        for seg_key, seg_data in baseline["segments"].items():
            if self._matches_hierarchy(seg_key, h_parts):
                matched = True
                seg_attempts = seg_data["attempts"]
                attempts += seg_attempts
                successes += seg_data["successes"]
                failures += seg_data["failures"]
                weighted_latency += seg_data["average_latency_ms"] * seg_attempts
                weighted_p95_latency += seg_data["p95_latency_ms"] * seg_attempts
                
                fb = seg_data.get("failure_breakdown", {})
                failure_breakdown["customer_caused"] += fb.get("customer_caused", 0)
                failure_breakdown["technical"] += fb.get("technical", 0)
                failure_breakdown["other"] += fb.get("other", 0)
                
        if not matched or attempts == 0:
            return None
            
        return {
            "attempts": attempts,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / attempts,
            "failure_rate": failures / attempts,
            "average_amount": 0.0,
            "median_amount": 0.0,
            "average_latency_ms": weighted_latency / attempts,
            "p95_latency_ms": weighted_p95_latency / attempts,
            "failure_breakdown": failure_breakdown
        }

    def _get_sibling_group(self, key: str, parent: str, active_segments: Dict[str, Any]) -> List[str]:
        h_parts = key.split("|")
        siblings = []
        for other in active_segments.keys():
            o_parts = other.split("|")
            if len(o_parts) != len(h_parts):
                continue
            if parent not in self._get_parent_keys(other):
                continue
            if len(h_parts) == 1:
                is_dev1 = h_parts[0] in ["ANDROID", "IOS", "WEB"]
                is_dev2 = o_parts[0] in ["ANDROID", "IOS", "WEB"]
                if is_dev1 != is_dev2:
                    continue
            elif len(h_parts) == 2:
                is_dev1 = h_parts[1] in ["ANDROID", "IOS", "WEB"]
                is_dev2 = o_parts[1] in ["ANDROID", "IOS", "WEB"]
                if is_dev1 != is_dev2:
                    continue
            siblings.append(other)
        return siblings

    def _prune_anomalies(self, anomalies: Set[str], active_segments: Dict[str, Any]) -> Set[str]:
        pruned = set(anomalies)
        
        # Pre-populate all active ancestors
        all_keys = set(anomalies)
        for key in anomalies:
            curr = [key]
            while curr:
                next_level = []
                for k in curr:
                    parents = self._get_parent_keys(k)
                    for p in parents:
                        if p not in all_keys and p in active_segments:
                            all_keys.add(p)
                            next_level.append(p)
                curr = next_level
                
        # Sort keys by count of '|' descending, so we process deepest children first.
        sorted_keys = sorted(list(all_keys), key=lambda k: (k.count("|"), k == "OVERALL"), reverse=True)
        
        for key in sorted_keys:
            if key not in pruned:
                continue
            parents = self._get_parent_keys(key)
            for parent in parents:
                siblings = self._get_sibling_group(key, parent, active_segments)
                degraded_siblings = [s for s in siblings if s in pruned]
                active_siblings = [s for s in siblings if active_segments[s]["attempts"] >= self.config.min_attempts_limited]
                
                if len(active_siblings) >= 1:
                    if len(degraded_siblings) / len(active_siblings) >= 0.5:
                        pruned.add(parent)
                        for s in degraded_siblings:
                            if s != parent:
                                pruned.discard(s)
                    else:
                        pruned.discard(parent)
                else:
                    pruned.discard(parent)
                    
        return pruned


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Run anomaly detection on payment windows")
    parser.add_argument("--merchant-id", required=True, help="Merchant ID to analyze")
    parser.add_argument("--window-start", required=True, help="Window start time (ISO format)")
    parser.add_argument("--window-end", required=True, help="Window end time (ISO format)")
    parser.add_argument(
        "--data-dir",
        default="data/generated",
        help="Directory containing generated data (default: data/generated)"
    )
    parser.add_argument(
        "--output",
        help="Output file for JSON result (default: stdout)"
    )

    args = parser.parse_args()

    # Parse timestamps
    try:
        window_start = datetime.fromisoformat(args.window_start.replace("Z", "+00:00"))
        window_end = datetime.fromisoformat(args.window_end.replace("Z", "+00:00"))
    except ValueError as e:
        print(f"Error parsing timestamps: {e}")
        sys.exit(1)

    # Run detection
    detector = AnomalyDetector()
    generated_data_dir = Path(args.data_dir)

    try:
        result = detector.detect(
            merchant_id=args.merchant_id,
            window_start=window_start,
            window_end=window_end,
            generated_data_dir=generated_data_dir
        )

        # Output result
        output_json = json.dumps(result, indent=2, default=str)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(output_json)
            print(f"Detection result written to {args.output}")
        else:
            print(output_json)

    except Exception as e:
        print(f"Error during detection: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()