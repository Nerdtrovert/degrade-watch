#!/usr/bin/env python3
"""
Tests for the LLM Report Generator module (Checkpoint 8).
"""

import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

# Add the project root to the path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from backend.app.llm_report_generator import (
    LLMReportGenerator,
    LLM_OUTPUT_SCHEMA,
    generate_forensic_report
)
from backend.app.evidence_package import generate_evidence_package
from scripts.analyze_baselines import parse_timestamp


class TestLLMReportGenerator(unittest.TestCase):
    """Test cases for the LLM Report Generator."""

    def setUp(self):
        """Set up test fixtures."""
        # Use a fixed datetime for consistent testing
        self.window_start = parse_timestamp("2026-08-20T10:00:00Z")
        self.window_end = parse_timestamp("2026-08-20T10:30:00Z")
        self.merchant_id = "test_merchant"
        self.data_dir = Path(__file__).parent.parent / "data" / "generated"

        # Create a minimal evidence package for testing
        self.sample_evidence_package = {
            "incident_metadata": {
                "incident_id": "test_merchant_20260820_100000",
                "merchant_id": "test_merchant",
                "detection_timestamp": datetime.now(timezone.utc).isoformat(),
                "analysis_window": {
                    "start": self.window_start.isoformat(),
                    "end": self.window_end.isoformat(),
                    "duration_minutes": 30
                },
                "severity": "MEDIUM",
                "detector_classification": "INCIDENT",
                "detector_confidence": "MEDIUM"
            },
            "affected_segment": {
                "payment_method": "UPI",
                "bank": "BANK_X",
                "device": "ANDROID",
                "upi_app": "PHONEPE",
                "hierarchy_level": "FULL_SEGMENT",
                "baseline_attempts": 1000,
                "baseline_success_rate": 0.95,
                "current_attempts": 800,
                "current_success_rate": 0.80,
                "segment_key": "UPI|BANK_X|ANDROID|PHONEPE"
            },
            "success_rate_evidence": {
                "baseline_success_rate": 0.95,
                "current_success_rate": 0.80,
                "absolute_change": -0.15,
                "absolute_percentage_point_change": -15.0,
                "relative_change": -0.1579,
                "baseline_attempts": 1000,
                "current_attempts": 800,
                "statistical_significance": {
                    "statistically_significant": True,
                    "p_value": 0.001,
                    "z_score": -3.29,
                    "confidence_level": 0.95
                },
                "test_type": "two_proportion_z_test",
                "interpretation": "Statistically significant severe degradation"
            },
            "error_evidence": {
                "baseline": {
                    "customer_error_rate": 0.02,
                    "technical_error_rate": 0.03,
                    "other_error_rate": 0.00,
                    "failure_rate": 0.05,
                    "failure_breakdown": {
                        "customer_caused": 20,
                        "technical": 30,
                        "other": 0
                    }
                },
                "current": {
                    "customer_error_rate": 0.025,
                    "technical_error_rate": 0.175,
                    "other_error_rate": 0.00,
                    "failure_rate": 0.20,
                    "failure_breakdown": {
                        "customer_caused": 20,
                        "technical": 140,
                        "other": 0
                    }
                },
                "changes": {
                    "customer_error_rate_change": 0.005,
                    "technical_error_rate_change": 0.145,
                    "other_error_rate_change": 0.0,
                    "customer_error_relative_change": 0.25,
                    "technical_error_relative_change": 3.833
                },
                "error_code_distribution": {
                    "TECHNICAL_ERROR_001": 100,
                    "INSUFFICIENT_FUNDS": 20
                },
                "error_code_shifts": {}
            },
            "localization_evidence": {
                "affected_segment": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE",
                    "success_rate": 0.80,
                    "attempts": 800
                },
                "localization_status": "LOCALIZED",
                "control_analysis": {
                    "status": "LOCALIZED",
                    "message": "Control segments remain healthy",
                    "control_segments": {
                        "Other banks (same device=ANDROID, upi_app=PHONEPE)": {
                            "attempts": 200,
                            "successes": 190,
                            "success_rate": 0.95,
                            "status": "HEALTHY"
                        }
                    }
                },
                "sibling_analysis": {},
                "interpretation": "Degradation is isolated to the specific segment - suggests localized issue"
            },
            "temporal_evidence": {
                "analysis_type": "temporal_trend_analysis",
                "window_duration_minutes": 30.0,
                "bucket_size_minutes": 5,
                "num_buckets": 6,
                "buckets": [],
                "trends": {
                    "success_rate": "STABLE",
                    "technical_error_rate": "STABLE",
                    "customer_error_rate": "STABLE"
                },
                "persistence_analysis": {
                    "analysis": "INTERMITTENT",
                    "consecutive_degraded_buckets": 2,
                    "max_consecutive_degraded": 2,
                    "persistence_score": 0.333
                },
                "first_degradation_detected": self.window_start.isoformat(),
                "is_persistent": False
            },
            "volume_evidence": {
                "baseline_expected_volume": 900,
                "current_volume": 800,
                "absolute_change": -100,
                "change_percentage": -11.11,
                "volume_status": "NOTABLE_DECREASE",
                "interpretation": "Notable volume decrease",
                "baseline_daily_rate": 42.86,
                "analysis_window_minutes": 30.0
            },
            "latency_evidence": {
                "baseline": {
                    "p95_latency_ms": 200.0,
                    "average_latency_ms": 150.0,
                    "details": {}
                },
                "current": {
                    "p95_latency_ms": 300.0,
                    "average_latency_ms": 200.0,
                    "details": {}
                },
                "changes": {
                    "absolute_change_ms": 100.0,
                    "relative_change": 0.5,
                    "change_percentage": 50.0
                },
                "latency_status": "ELEVATED",
                "interpretation": "Latency mildly elevated",
                "technical_failure_latency": 350.0
            },
            "impact_evidence": {
                "affected_attempts": {
                    "baseline": 1000,
                    "current": 800,
                    "change": -200,
                    "change_percentage": -20.0
                },
                "successful_payments": {
                    "baseline_expected": 950.0,
                    "current_actual": 640.0,
                    "shortfall": 310.0,
                    "percentage_shortfall": 32.63
                },
                "average_transaction_amount": {
                    "rupees": 150.0,
                    "paise": 15000
                },
                "revenue_at_risk": {
                    "paise": 4650000,  # 310 * 150 * 100
                    "rupees": 46500.0
                },
                "calculation_method": "Deterministic as per requirements:",
                "formula": {
                    "expected_successful_revenue": "baseline_success_rate × affected_attempts × average_amount",
                    "actual_successful_revenue": "actual_successful_payments × average_amount",
                    "revenue_at_risk": "Expected Successful Revenue - Actual Successful Revenue"
                },
                "note": "All monetary values are integer paise internally as required"
            },
            "sample_payments": [
                {
                    "payment_id": "pay_001",
                    "order_id": "order_001",
                    "timestamp": "2026-08-20T10:05:00Z",
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE",
                    "status": "success",
                    "error_code": None,
                    "amount": 15000,
                    "latency_ms": 180
                },
                {
                    "payment_id": "pay_002",
                    "order_id": "order_002",
                    "timestamp": "2026-08-20T10:10:00Z",
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE",
                    "status": "failed",
                    "error_code": "TECHNICAL_ERROR_001",
                    "amount": 15000,
                    "latency_ms": 320
                }
            ],
            "hypothesis_evidence": [
                {
                    "hypothesis": "Localized UPI issue",
                    "details": "Affecting BANK_X ANDROID PHONEPE",
                    "status": "SUPPORTED",
                    "supporting_signals": [
                        "Localization evidence indicates degradation is isolated to specific segment",
                        "Technical error rate is elevated",
                        "Success rate drop is statistically significant",
                        "Success rate drop (-15.00 pp) exceeds warning threshold"
                    ],
                    "contradicting_signals": [],
                    "assessment": "Evidence supports localized technical issue"
                },
                {
                    "hypothesis": "Widespread systemic issue affecting multiple payment methods/banks/devices",
                    "status": "PARTIALLY_SUPPORTED",
                    "supporting_signals": [
                        "Success rate drop is statistically significant"
                    ],
                    "contradicting_signals": [
                        "Localization evidence shows degradation is localized",
                        "Cannot determine if multiple methods affected without multi-method analysis"
                    ],
                    "assessment": "Some evidence supports widespread hypothesis but contradicting evidence exists"
                },
                {
                    "hypothesis": "Technical infrastructure issue (bank/gateway/network problems)",
                    "status": "SUPPORTED",
                    "supporting_signals": [
                        "Technical error rate is elevated",
                        "Latency is elevated",
                        "Success rate is decreasing (consistent with technical issues)",
                        "Technical error increase correlates with success rate decrease"
                    ],
                    "contradicting_signals": [],
                    "assessment": "Evidence supports technical infrastructure issue"
                },
                {
                    "hypothesis": "User-side/customer issue (insufficient funds, wrong PIN, etc.)",
                    "status": "INSUFFICIENT_EVIDENCE",
                    "supporting_signals": [],
                    "contradicting_signals": [
                        "Customer-caused error rate change: 0.50 percentage points",
                        "Technical error rate is elevated (suggests technical issue, not customer-side)"
                    ],
                    "assessment": "Insufficient evidence to support or contradict hypothesis"
                },
                {
                    "hypothesis": "Volume anomaly or latency issue",
                    "status": "PARTIALLY_SUPPORTED",
                    "supporting_signals": [
                        "Volume significantly decreased",
                        "Volume change: -11.11%",
                        "Latency significantly elevated",
                        "Latency change: 50.0%"
                    ],
                    "contradicting_signals": [],
                    "assessment": "Some evidence supports volume or latency hypothesis"
                }
            ],
            "investigation_checklist": [
                {
                    "check": "statistical_significance",
                    "result": "PASS",
                    "finding": "Success rate drop is statistically significant (p-value: 0.0010)",
                    "evidence_refs": ["success_rate_evidence.statistical_significance"]
                },
                {
                    "check": "meaningful_degradation",
                    "result": "PASS",
                    "finding": "Success rate dropped 15.0 percentage points (threshold: 5.0 pp)",
                    "evidence_refs": ["success_rate_evidence.absolute_percentage_point_change"]
                }
                # ... more checklist items would be present in real usage
            ],
            "schema_info": {
                "version": "1.0.0",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "deterministic": True
            }
        }

    def test_llm_output_schema_structure(self):
        """Test that the LLM_OUTPUT_SCHEMA has the correct structure."""
        # Check required top-level fields
        required_fields = [
            "incident_id", "severity", "status",
            "summary", "likely_cause", "alternative_hypotheses",
            "recommended_next_steps", "recovery", "timeline"
        ]

        for field in required_fields:
            self.assertIn(field, LLM_OUTPUT_SCHEMA["properties"])

        # Check summary structure
        summary_props = LLM_OUTPUT_SCHEMA["properties"]["summary"]["properties"]
        self.assertIn("title", summary_props)
        self.assertIn("what_happened", summary_props)
        self.assertIn("where", summary_props)
        self.assertIn("confidence", summary_props)
        self.assertIn("confidence_level", summary_props)
        self.assertIn("confidence_explanation", summary_props)
        self.assertIn("evidence_summary", summary_props)

        # Check where structure
        where_props = LLM_OUTPUT_SCHEMA["properties"]["summary"]["properties"]["where"]["properties"]
        self.assertIn("payment_method", where_props)
        self.assertIn("bank", where_props)
        self.assertIn("device", where_props)
        self.assertIn("upi_app", where_props)

        # Check likely_cause structure
        likely_cause_props = LLM_OUTPUT_SCHEMA["properties"]["likely_cause"]["properties"]
        self.assertIn("primary", likely_cause_props)
        self.assertIn("confidence", likely_cause_props)
        self.assertIn("evidence_refs", likely_cause_props)

        # Check alternative_hypotheses structure
        alt_hypo_items = LLM_OUTPUT_SCHEMA["properties"]["alternative_hypotheses"]["items"]
        self.assertIn("properties", alt_hypo_items)
        alt_hypo_props = alt_hypo_items["properties"]
        self.assertIn("hypothesis", alt_hypo_props)
        self.assertIn("assessment", alt_hypo_props)
        self.assertIn("explanation", alt_hypo_props)
        self.assertIn("evidence_refs", alt_hypo_props)

        # Check recovery structure
        recovery_props = LLM_OUTPUT_SCHEMA["properties"]["recovery"]["properties"]
        self.assertIn("recommendation", recovery_props)
        self.assertIn("eligible", recovery_props)
        self.assertIn("reason", recovery_props)

    def test_openai_client_initialization(self):
        """Test that OpenAI client initializes correctly when API key is present."""
        with patch('backend.app.llm_report_generator.OPENAI_AVAILABLE', True), \
             patch('backend.app.llm_report_generator.openai') as mock_openai:
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
                generator = LLMReportGenerator(provider="openai")
                self.assertIsNotNone(generator.openai_client)
                mock_openai.OpenAI.assert_called_once_with(api_key='test-key')

    def test_anthropic_client_initialization(self):
        """Test that Anthropic client initializes correctly when API key is present."""
        with patch('backend.app.llm_report_generator.anthropic') as mock_anthropic, \
             patch('backend.app.llm_report_generator.ANTHROPIC_AVAILABLE', True):
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
                generator = LLMReportGenerator(provider="anthropic")
                self.assertIsNotNone(generator.anthropic_client)
                mock_anthropic.Anthropic.assert_called_once_with(api_key='test-key')

    def test_unsupported_provider_raises_error(self):
        """Test that unsupported LLM provider raises RuntimeError."""
        with self.assertRaises(RuntimeError) as context:
            LLMReportGenerator(provider="unsupported_provider")
        self.assertIn("Unsupported LLM provider: unsupported_provider", str(context.exception))

    def test_openai_missing_api_key_logs_warning(self):
        """Test that missing OpenAI API key logs warning."""
        with patch('backend.app.llm_report_generator.OPENAI_AVAILABLE', True), \
             patch('backend.app.llm_report_generator.openai') as mock_openai:
            with patch.dict(os.environ, {}, clear=True):  # Clear env vars
                with self.assertLogs('backend.app.llm_report_generator', level='WARNING') as log:
                    generator = LLMReportGenerator(provider="openai")
                    # The client should be None when API key is missing
                    self.assertIsNone(generator.openai_client)
                    # Check that warning was logged
                    self.assertTrue(any("OPENAI_API_KEY not set" in msg for msg in log.output))

    def test_anthropic_missing_api_key_logs_warning(self):
        """Test that missing Anthropic API key logs warning."""
        with patch('backend.app.llm_report_generator.anthropic') as mock_anthropic, \
             patch('backend.app.llm_report_generator.ANTHROPIC_AVAILABLE', True):
            with patch.dict(os.environ, {}, clear=True):  # Clear env vars
                with self.assertLogs('backend.app.llm_report_generator', level='WARNING') as log:
                    generator = LLMReportGenerator(provider="anthropic")
                    # The client should be None when API key is missing
                    self.assertIsNone(generator.anthropic_client)
                    # Check that warning was logged
                    self.assertTrue(any("ANTHROPIC_API_KEY not set" in msg for msg in log.output))

    def test_groq_client_initialization(self):
        """Test that Groq client initializes correctly when API key is present."""
        with patch('backend.app.llm_report_generator.GROQ_AVAILABLE', True), \
             patch('backend.app.llm_report_generator.Groq') as mock_groq:
            with patch.dict(os.environ, {'GROQ_API_KEY': 'test-key'}):
                generator = LLMReportGenerator(provider="groq")
                self.assertIsNotNone(generator.groq_client)
                mock_groq.assert_called_once_with(api_key='test-key')

    def test_groq_missing_api_key_logs_warning(self):
        """Test that missing Groq API key logs warning."""
        with patch('backend.app.llm_report_generator.GROQ_AVAILABLE', True), \
             patch('backend.app.llm_report_generator.Groq') as mock_groq:
            with patch.dict(os.environ, {}, clear=True):  # Clear env vars
                with self.assertLogs('backend.app.llm_report_generator', level='WARNING') as log:
                    generator = LLMReportGenerator(provider="groq")
                    # The client should be None when API key is missing
                    self.assertIsNone(generator.groq_client)
                    # Check that warning was logged
                    self.assertTrue(any("GROQ_API_KEY not set" in msg for msg in log.output))

    @patch('backend.app.llm_report_generator.Groq')
    def test_call_llm_groq_success(self, mock_groq_class):
        """Test successful Groq API call."""
        # Mock the Groq response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"test": "response"}'

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class.return_value = mock_client

        with patch.dict(os.environ, {'GROQ_API_KEY': 'test-key'}):
            generator = LLMReportGenerator(provider="groq")

            result = generator._call_llm("test prompt")

            self.assertEqual(result, '{"test": "response"}')
            mock_client.chat.completions.create.assert_called_once()

    @patch('backend.app.llm_report_generator.Groq')
    def test_call_llm_groq_failure(self, mock_groq_class):
        """Test Groq API call failure raises RuntimeError."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_groq_class.return_value = mock_client

        with patch.dict(os.environ, {'GROQ_API_KEY': 'test-key'}):
            generator = LLMReportGenerator(provider="groq")

            with self.assertRaises(RuntimeError) as context:
                generator._call_llm("test prompt")

            self.assertIn("Groq API call failed", str(context.exception))

    def test_validate_evidence_package_input_valid(self):
        """Test that valid evidence package passes validation."""
        generator = LLMReportGenerator()
        # Should not raise any exception
        generator._validate_evidence_package_input(self.sample_evidence_package)

    def test_validate_evidence_package_input_missing_section(self):
        """Test that missing evidence package section raises ValueError."""
        generator = LLMReportGenerator()
        invalid_package = self.sample_evidence_package.copy()
        del invalid_package["incident_metadata"]

        with self.assertRaises(ValueError) as context:
            generator._validate_evidence_package_input(invalid_package)
        self.assertIn("Missing required evidence package section: incident_metadata", str(context.exception))

    def test_validate_evidence_package_input_missing_metadata_fields(self):
        """Test that missing incident metadata fields raises ValueError."""
        generator = LLMReportGenerator()
        invalid_package = self.sample_evidence_package.copy()
        invalid_package["incident_metadata"] = {
            "incident_id": "test_123"
            # Missing severity and detector_classification
        }

        with self.assertRaises(ValueError) as context:
            generator._validate_evidence_package_input(invalid_package)
        self.assertIn("Incident metadata missing required fields", str(context.exception))

    @patch('backend.app.llm_report_generator.openai')
    def test_create_llm_prompt_includes_evidence(self, mock_openai):
        """Test that LLM prompt includes the evidence package."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            generator = LLMReportGenerator(provider="openai")
            prompt = generator._create_llm_prompt(self.sample_evidence_package)

            # Check that prompt contains evidence package JSON
            self.assertIn("test_merchant_20260820_100000", prompt)
            self.assertIn("UPI", prompt)
            self.assertIn("BANK_X", prompt)
            self.assertIn("ANDROID", prompt)
            self.assertIn("PHONEPE", prompt)

            # Check that prompt contains instructions
            self.assertIn("You are a forensic analysis AI", prompt)
            self.assertIn("Treat it as the sole source of truth", prompt)
            self.assertIn("Do NOT access the database", prompt)
            self.assertIn("OUTPUT FORMAT", prompt)

    @patch('backend.app.llm_report_generator.openai')
    def test_call_llm_openai_success(self, mock_openai):
        """Test successful OpenAI API call."""
        # Mock the OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"test": "response"}'

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            generator = LLMReportGenerator(provider="openai")
            generator.openai_client = mock_client

            result = generator._call_llm("test prompt")

            self.assertEqual(result, '{"test": "response"}')
            mock_client.chat.completions.create.assert_called_once()

    @patch('backend.app.llm_report_generator.openai')
    def test_call_llm_openai_failure(self, mock_openai):
        """Test OpenAI API call failure raises RuntimeError."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            generator = LLMReportGenerator(provider="openai")
            generator.openai_client = mock_client

            with self.assertRaises(RuntimeError) as context:
                generator._call_llm("test prompt")

            self.assertIn("OpenAI API call failed", str(context.exception))

    @patch('backend.app.llm_report_generator.anthropic')
    def test_call_llm_anthropic_success(self, mock_anthropic):
        """Test successful Anthropic API call."""
        # Mock the Anthropic response
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = '{"test": "response"}'

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            generator = LLMReportGenerator(provider="anthropic")
            generator.anthropic_client = mock_client

            result = generator._call_llm("test prompt")

            self.assertEqual(result, '{"test": "response"}')
            mock_client.messages.create.assert_called_once()

    @patch('backend.app.llm_report_generator.anthropic')
    def test_call_llm_anthropic_failure(self, mock_anthropic):
        """Test Anthropic API call failure raises RuntimeError."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error")

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            generator = LLMReportGenerator(provider="anthropic")
            generator.anthropic_client = mock_client

            with self.assertRaises(RuntimeError) as context:
                generator._call_llm("test prompt")

            self.assertIn("Anthropic API call failed", str(context.exception))

    def test_validate_report_consistency_matching_incident_id(self):
        """Test that report with matching incident ID passes validation."""
        generator = LLMReportGenerator()

        report = {
            "incident_id": "test_merchant_20260820_100000",  # Matches evidence
            "severity": "MEDIUM",
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "Test Incident",
                "what_happened": "Test description",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on evidence",
                "evidence_summary": ["Evidence point 1", "Evidence point 2", "Evidence point 3"]
            },
            "likely_cause": {
                "primary": "Test cause",
                "confidence": 0.8,
                "evidence_refs": ["success_rate_evidence"]
            },
            "alternative_hypotheses": [],
            "recommended_next_steps": ["Step 1"],
            "recovery": {
                "recommendation": "Test recommendation",
                "eligible": True,
                "reason": "Test reason"
            },
            "timeline": []
        }

        # Should not raise any exception
        generator._validate_report_consistency(report, self.sample_evidence_package)

    def test_validate_report_consistency_mismatched_incident_id(self):
        """Test that report with mismatched incident ID raises ValueError."""
        generator = LLMReportGenerator()

        report = {
            "incident_id": "wrong_merchant_20260820_100000",  # Doesn't match evidence
            "severity": "MEDIUM",
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "Test Incident",
                "what_happened": "Test description",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on evidence",
                "evidence_summary": ["Evidence point 1", "Evidence point 2", "Evidence point 3"]
            },
            "likely_cause": {
                "primary": "Test cause",
                "confidence": 0.8,
                "evidence_refs": ["success_rate_evidence"]
            },
            "alternative_hypotheses": [],
            "recommended_next_steps": ["Step 1"],
            "recovery": {
                "recommendation": "Test recommendation",
                "eligible": True,
                "reason": "Test reason"
            },
            "timeline": []
        }

        with self.assertRaises(ValueError) as context:
            generator._validate_report_consistency(report, self.sample_evidence_package)

        self.assertIn("Report incident_id", str(context.exception))
        self.assertIn("doesn't match evidence", str(context.exception))

    def test_validate_report_consistency_mismatched_segment(self):
        """Test that report with mismatched affected segment raises ValueError."""
        generator = LLMReportGenerator()

        report = {
            "incident_id": "test_merchant_20260820_100000",  # Matches evidence
            "severity": "MEDIUM",
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "Test Incident",
                "what_happened": "Test description",
                "where": {
                    "payment_method": "CARD",  # Wrong payment method
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on evidence",
                "evidence_summary": ["Evidence point 1", "Evidence point 2", "Evidence point 3"]
            },
            "likely_cause": {
                "primary": "Test cause",
                "confidence": 0.8,
                "evidence_refs": ["success_rate_evidence"]
            },
            "alternative_hypotheses": [],
            "recommended_next_steps": ["Step 1"],
            "recovery": {
                "recommendation": "Test recommendation",
                "eligible": True,
                "reason": "Test reason"
            },
            "timeline": []
        }

        with self.assertRaises(ValueError) as context:
            generator._validate_report_consistency(report, self.sample_evidence_package)

        self.assertIn("Report 'payment_method'", str(context.exception))
        self.assertIn("doesn't match evidence", str(context.exception))

    @patch('backend.app.llm_report_generator.openai')
    def test_generate_report_success(self, mock_openai):
        """Test successful end-to-end report generation."""
        # Mock the OpenAI response with a valid report structure
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "incident_id": "test_merchant_20260820_100000",
            "severity": "MEDIUM",
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "UPI payments from Bank X on Android are failing more than usual",
                "what_happened": "Payment success rate for UPI + Bank X + Android fell from 95.0% to 80.0% during the incident window.",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on multiple supporting signals including statistical significance and localization evidence",
                "evidence_summary": [
                    "Success rate dropped 15.0 percentage points below baseline",
                    "Technical error rate increased significantly",
                    "Localization evidence indicates degradation is isolated to UPI/BANK_X/ANDROID/PHONEPE segment"
                ]
            },
            "likely_cause": {
                "primary": "The evidence is most consistent with elevated Bank X / UPI technical failures concentrated on Android.",
                "confidence": 0.85,
                "evidence_refs": [
                    "success_rate_evidence.statistical_significance",
                    "error_evidence.changes.technical_error_rate_change",
                    "localization_evidence.localization_status"
                ]
            },
            "alternative_hypotheses": [
                {
                    "hypothesis": "Localized UPI issue",
                    "assessment": "SUPPORTED",
                    "explanation": "Evidence supports localized technical issue",
                    "evidence_refs": ["localization_evidence.localization_status"]
                }
            ],
            "recommended_next_steps": [
                "Monitor payment success rate for the next 15-20 minutes",
                "Consider asking affected customers to try another available UPI app"
            ],
            "recovery": {
                "recommendation": "Recovery may be appropriate for eligible failed orders",
                "eligible": True,
                "reason": "Technical error rate is elevated suggesting recoverable technical issue"
            },
            "timeline": [
                {
                    "time": self.window_start.isoformat(),
                    "event": "Incident window start"
                },
                {
                    "time": self.window_end.isoformat(),
                    "event": "Incident window end"
                }
            ]
        })

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            generator = LLMReportGenerator(provider="openai")
            generator.openai_client = mock_client

            report = generator.generate_report(self.sample_evidence_package)

            # Check that report has the expected structure
            self.assertEqual(report["incident_id"], "test_merchant_20260820_100000")
            self.assertEqual(report["severity"], "MEDIUM")
            self.assertEqual(report["status"], "ACTION_PROPOSED")

            # Check that backend-computed fields were added
            self.assertIn("estimated_revenue_at_risk", report)
            self.assertEqual(report["estimated_revenue_at_risk"]["paise"], 4650000)
            self.assertEqual(report["estimated_revenue_at_risk"]["rupees"], 46500.0)

            # Check summary
            self.assertEqual(report["summary"]["title"], "UPI payments from Bank X on Android are failing more than usual")
            self.assertEqual(report["summary"]["where"]["payment_method"], "UPI")
            self.assertEqual(report["summary"]["where"]["bank"], "BANK_X")
            self.assertEqual(report["summary"]["where"]["device"], "ANDROID")
            self.assertEqual(report["summary"]["where"]["upi_app"], "PHONEPE")

            # Check likely cause
            self.assertIn("elevated Bank X / UPI technical failures", report["likely_cause"]["primary"])

            # Check that validation didn't raise exceptions
            # The validation happens inside generate_report

    def test_create_merchant_view(self):
        """Test creation of merchant view from report."""
        report = {
            "summary": {
                "title": "Test Incident Title",
                "what_happened": "Test what happened",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "evidence_summary": ["Evidence 1", "Evidence 2", "Evidence 3"]
            },
            "severity": "HIGH",
            "likely_cause": {
                "primary": "Test likely cause"
            },
            "recommended_next_steps": ["Step 1", "Step 2"],
            "recovery": {
                "eligible": True
            },
            "estimated_revenue_at_risk": {
                "paise": 500000,
                "rupees": 5000.0
            }
        }

        generator = LLMReportGenerator()
        merchant_view = generator.create_merchant_view(report)

        self.assertEqual(merchant_view["title"], "Test Incident Title")
        self.assertEqual(merchant_view["what_happened"], "Test what happened")
        self.assertEqual(merchant_view["where"]["payment_method"], "UPI")
        self.assertEqual(merchant_view["how_serious"], "HIGH")
        self.assertEqual(merchant_view["likely_explanation"], "Test likely cause")
        self.assertEqual(merchant_view["evidence_summary"], ["Evidence 1", "Evidence 2", "Evidence 3"])
        self.assertEqual(merchant_view["recommended_next_steps"], ["Step 1", "Step 2"])
        self.assertTrue(merchant_view["automated_recovery_available"])
        self.assertEqual(merchant_view["revenue_at_risk"]["paise"], 500000)
        self.assertEqual(merchant_view["revenue_at_risk"]["rupees"], 5000.0)

    def test_create_support_view(self):
        """Test creation of support view from report and evidence package."""
        report = {
            "timeline": [{"time": "2026-08-20T10:00:00Z", "event": "Start"}],
            "summary": {"title": "Test"},
            "likely_cause": {"primary": "Test cause"},
            "alternative_hypotheses": [],
            "recovery": {"eligible": True, "reason": "Test", "recommendation": "Test"}
        }

        generator = LLMReportGenerator()
        support_view = generator.create_support_view(report, self.sample_evidence_package)

        self.assertEqual(support_view["incident_metadata"], self.sample_evidence_package["incident_metadata"])
        self.assertEqual(support_view["affected_segment"], self.sample_evidence_package["affected_segment"])
        self.assertEqual(support_view["timeline"], report["timeline"])
        self.assertEqual(support_view["summary"], report["summary"])
        self.assertEqual(support_view["likely_cause"], report["likely_cause"])
        self.assertEqual(support_view["alternative_hypotheses"], report["alternative_hypotheses"])
        self.assertEqual(support_view["investigation_checklist"], self.sample_evidence_package["investigation_checklist"])
        self.assertIn("evidence_details", support_view)
        self.assertEqual(support_view["sample_payments"], self.sample_evidence_package["sample_payments"])
        self.assertIn("report_validation", support_view)
        self.assertTrue(support_view["report_validation"]["llm_generated"])
        self.assertTrue(support_view["report_validation"]["backend_validated"])
        self.assertTrue(support_view["report_validation"]["consistent_with_evidence"])

    @patch('backend.app.llm_report_generator.LLMReportGenerator')
    def test_generate_forensic_report_convenience_function(self, mock_generator_class):
        """Test the convenience function for generating forensic reports."""
        # Setup mock
        mock_generator = Mock()
        mock_generator.generate_report.return_value = {"test": "report"}
        mock_generator_class.return_value = mock_generator

        # Call the function
        result = generate_forensic_report(self.sample_evidence_package, provider="openai", model="test-model")

        # Check that generator was instantiated with correct parameters
        mock_generator_class.assert_called_once_with(provider="openai", model="test-model")

        # Check that generate_report was called
        mock_generator.generate_report.assert_called_once_with(self.sample_evidence_package)

        # Check result
        self.assertEqual(result, {"test": "report"})

    def test_scenario_e_no_action(self):
        """Test that Scenario E (customer-caused) results in NO_ACTION."""
        # Create evidence package mimicking Scenario E
        scenario_e_evidence = self.sample_evidence_package.copy()

        # Modify to represent Scenario E: customer errors up, technical errors normal
        scenario_e_evidence["error_evidence"] = {
            "baseline": {
                "customer_error_rate": 0.02,
                "technical_error_rate": 0.03,
                "other_error_rate": 0.00,
                "failure_rate": 0.05,
                "failure_breakdown": {
                    "customer_caused": 20,
                    "technical": 30,
                    "other": 0
                }
            },
            "current": {
                "customer_error_rate": 0.15,  # Significantly increased
                "technical_error_rate": 0.035,  # Normal
                "other_error_rate": 0.00,
                "failure_rate": 0.185,
                "failure_breakdown": {
                    "customer_caused": 120,
                    "technical": 28,
                    "other": 0
                }
            },
            "changes": {
                "customer_error_rate_change": 0.13,
                "technical_error_rate_change": 0.005,
                "other_error_rate_change": 0.0,
                "customer_error_relative_change": 5.5,
                "technical_error_relative_change": 0.167
            },
            "error_code_distribution": {
                "INSUFFICIENT_FUNDS": 100,
                "WRONG_PIN": 20
            },
            "error_code_shifts": {}
        }

        # Update investigation checklist to reflect Scenario E
        scenario_e_evidence["investigation_checklist"] = [
            {
                "check": "statistical_significance",
                "result": "PASS",
                "finding": "Success rate drop is statistically significant (p-value: 0.0010)",
                "evidence_refs": ["success_rate_evidence.statistical_significance"]
            },
            {
                "check": "meaningful_degradation",
                "result": "PASS",
                "finding": "Success rate dropped 10.0 percentage points (threshold: 5.0 pp)",
                "evidence_refs": ["success_rate_evidence.absolute_percentage_point_change"]
            },
            {
                "check": "primarily_customer_caused",  # This should be PASS for Scenario E
                "result": "PASS",
                "finding": "Event is primarily customer-caused (customer change: 13.0pp, technical change: 0.5pp)",
                "evidence_refs": ["error_evidence.changes.customer_error_rate_change",
                              "error_evidence.changes.technical_error_rate_change"]
            }
            # ... other checklist items
        ]

        # With proper prompting, the LLM should set status to "NO_ACTION" for Scenario E
        # Since we can't easily test the actual LLM output without mocking extensively,
        # we'll test that our validation doesn't prevent NO_ACTION status

        generator = LLMReportGenerator()

        # This report should be valid (NO_ACTION is a valid status)
        valid_report = {
            "incident_id": scenario_e_evidence["incident_metadata"]["incident_id"],
            "severity": "LOW",  # Scenario E should be LOW severity
            "status": "NO_ACTION",  # Key point: NO_ACTION for customer-caused
            "summary": {
                "title": "Payment success rate decrease due to customer-side issues",
                "what_happened": "Payment success rate decreased but analysis shows this is due to customer-side issues, not technical problems.",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.80,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on error pattern showing customer errors increased while technical errors remained normal",
                "evidence_summary": [
                    "Customer-caused error rate increased significantly",
                    "Technical error rate remained within normal range",
                    "Success rate decrease is attributable to customer-side issues"
                ]
            },
            "likely_cause": {
                "primary": "The success rate degradation is primarily due to customer-side issues such as insufficient funds or wrong PIN entries.",
                "confidence": 0.80,
                "evidence_refs": ["error_evidence.changes.customer_error_rate_change"]
            },
            "alternative_hypotheses": [
                {
                    "hypothesis": "User-side/customer issue (insufficient funds, wrong PIN, etc.)",
                    "assessment": "SUPPORTED",
                    "explanation": "Customer error rate increased significantly while technical error rate remained normal",
                    "evidence_refs": ["error_evidence.changes.customer_error_rate_change",
                                  "error_evidence.changes.technical_error_rate_change"]
                }
            ],
            "recommended_next_steps": [
                "Consider informing customers about payment method alternatives",
                "Monitor for recurrence to determine if intervention is needed"
            ],
            "recovery": {
                "recommendation": "Recovery is not recommended as this is a customer-side issue",
                "eligible": False,
                "reason": "Issue is customer-caused, not technical"
            },
            "timeline": []
        }

        # Should not raise validation exception
        generator._validate_report_consistency(valid_report, scenario_e_evidence)

        # Check that status is NO_ACTION
        self.assertEqual(valid_report["status"], "NO_ACTION")

        # Check that recovery eligible is False
        self.assertFalse(valid_report["recovery"]["eligible"])

    def test_llm_cannot_invent_revenue_at_risk(self):
        """Test that LLM cannot invent revenue at risk - backend adds it after."""
        # This test validates the design principle that revenue_at_risk comes from backend

        # Create a report that tries to invent revenue at risk
        invented_report = {
            "incident_id": "test_merchant_20260820_100000",
            "severity": "MEDIUM",
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "Test Incident",
                "what_happened": "Test description",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on evidence",
                "evidence_summary": ["Evidence point 1", "Evidence point 2", "Evidence point 3"]
            },
            "likely_cause": {
                "primary": "Test cause",
                "confidence": 0.8,
                "evidence_refs": ["success_rate_evidence"]
            },
            "alternative_hypotheses": [],
            "recommended_next_steps": ["Step 1"],
            "recovery": {
                "recommendation": "Test recommendation",
                "eligible": True,
                "reason": "Test reason"
            },
            "timeline": [],
            # LLM tries to invent this - but backend will overwrite it
            "estimated_revenue_at_risk": {
                "paise": 999999999,  # Obviously wrong value
                "rupees": 9999999.99
            }
        }

        generator = LLMReportGenerator()

        # The validation should pass (consistency check doesn't cover revenue_at_risk yet)
        # but the _add_backend_computed_fields method will overwrite the LLM's value
        result = generator._add_backend_computed_fields(invented_report, self.sample_evidence_package)

        # Backend value should overwrite LLM's invented value
        self.assertEqual(result["estimated_revenue_at_risk"]["paise"], 4650000)  # From evidence
        self.assertEqual(result["estimated_revenue_at_risk"]["rupees"], 46500.0)
        self.assertNotEqual(result["estimated_revenue_at_risk"]["paise"], 999999999)

    def test_llm_temperature_and_max_tokens(self):
        """Test that LLM generation uses appropriate parameters for deterministic output."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            generator = LLMReportGenerator(provider="openai")

            # Check that temperature is low for deterministic output
            self.assertEqual(generator.temperature, 0.1)

            # Check that max_tokens is reasonable
            self.assertEqual(generator.max_tokens, 2000)

    def test_empty_alternative_hypotheses_allowed(self):
        """Test that empty alternative hypotheses array is valid."""
        generator = LLMReportGenerator()

        report = {
            "incident_id": "test_merchant_20260820_100000",
            "severity": "MEDIUM",
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "Test Incident",
                "what_happened": "Test description",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on evidence",
                "evidence_summary": ["Evidence point 1", "Evidence point 2", "Evidence point 3"]
            },
            "likely_cause": {
                "primary": "Test cause",
                "confidence": 0.8,
                "evidence_refs": ["success_rate_evidence"]
            },
            "alternative_hypotheses": [],  # Empty is allowed
            "recommended_next_steps": ["Step 1"],
            "recovery": {
                "recommendation": "Test recommendation",
                "eligible": True,
                "reason": "Test reason"
            },
            "timeline": []
        }

        # Should not raise validation exception
        generator._validate_report_consistency(report, self.sample_evidence_package)

    def test_adversarial_revenue_at_risk_overwritten(self):
        """Test that the backend overwrites/ignores any LLM-supplied revenue at risk values."""
        generator = LLMReportGenerator()
        report = {
            "incident_id": "test_merchant_20260820_100000",
            "severity": "MEDIUM",
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "Test Incident",
                "what_happened": "Test description",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on evidence",
                "evidence_summary": ["Evidence point 1", "Evidence point 2", "Evidence point 3"]
            },
            "likely_cause": {
                "primary": "Test cause",
                "confidence": 0.8,
                "evidence_refs": ["success_rate_evidence"]
            },
            "alternative_hypotheses": [],
            "recommended_next_steps": ["Step 1"],
            "recovery": {
                "recommendation": "Test recommendation",
                "eligible": True,
                "reason": "Test reason"
            },
            "timeline": [],
            "estimated_revenue_at_risk": {
                "paise": 999999999,
                "rupees": 9999999.99
            }
        }
        
        result = generator._add_backend_computed_fields(report, self.sample_evidence_package)
        self.assertEqual(result["estimated_revenue_at_risk"]["paise"], 4650000)
        self.assertEqual(result["estimated_revenue_at_risk"]["rupees"], 46500.0)

    def test_adversarial_severity_overwritten(self):
        """Test that the backend forces the severity to the deterministic value from metadata."""
        generator = LLMReportGenerator()
        report = {
            "incident_id": "test_merchant_20260820_100000",
            "severity": "LOW",  # LLM tries to downgrade severity
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "Test Incident",
                "what_happened": "Test description",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on evidence",
                "evidence_summary": ["Evidence point 1", "Evidence point 2", "Evidence point 3"]
            },
            "likely_cause": {
                "primary": "Test cause",
                "confidence": 0.8,
                "evidence_refs": ["success_rate_evidence"]
            },
            "alternative_hypotheses": [],
            "recommended_next_steps": ["Step 1"],
            "recovery": {
                "recommendation": "Test recommendation",
                "eligible": True,
                "reason": "Test reason"
            },
            "timeline": []
        }
        
        result = generator._add_backend_computed_fields(report, self.sample_evidence_package)
        # Should be forced back to detector severity (MEDIUM)
        self.assertEqual(result["severity"], "MEDIUM")

    def test_evidence_refs_validation_rejects_hallucinations(self):
        """Test that validation fails if LLM includes hallucinated/nonexistent references."""
        generator = LLMReportGenerator()
        report = {
            "incident_id": "test_merchant_20260820_100000",
            "severity": "MEDIUM",
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "Test Incident",
                "what_happened": "Test description",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on evidence",
                "evidence_summary": ["Evidence point 1", "Evidence point 2", "Evidence point 3"]
            },
            "likely_cause": {
                "primary": "Test cause",
                "confidence": 0.8,
                "evidence_refs": ["BANK_X_OUTAGE_CONFIRMED"]  # Nonexistent reference!
            },
            "alternative_hypotheses": [],
            "recommended_next_steps": ["Step 1"],
            "recovery": {
                "recommendation": "Test recommendation",
                "eligible": True,
                "reason": "Test reason"
            },
            "timeline": []
        }
        
        with self.assertRaises(ValueError) as context:
            generator._validate_report_consistency(report, self.sample_evidence_package)
        self.assertIn("Hallucinated evidence reference", str(context.exception))

    def test_evidence_refs_bracket_notation_validation(self):
        """Test that list bracket notation (e.g. sample_payments[0].payment_id) is successfully validated."""
        generator = LLMReportGenerator()
        report = {
            "incident_id": "test_merchant_20260820_100000",
            "severity": "MEDIUM",
            "status": "ACTION_PROPOSED",
            "summary": {
                "title": "Test Incident",
                "what_happened": "Test description",
                "where": {
                    "payment_method": "UPI",
                    "bank": "BANK_X",
                    "device": "ANDROID",
                    "upi_app": "PHONEPE"
                },
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "confidence_explanation": "Based on evidence",
                "evidence_summary": ["Evidence point 1", "Evidence point 2", "Evidence point 3"]
            },
            "likely_cause": {
                "primary": "Test cause",
                "confidence": 0.8,
                "evidence_refs": ["sample_payments[0].payment_id"]  # Valid reference!
            },
            "alternative_hypotheses": [],
            "recommended_next_steps": ["Step 1"],
            "recovery": {
                "recommendation": "Test recommendation",
                "eligible": True,
                "reason": "Test reason"
            },
            "timeline": []
        }
        
        # Should validate successfully without errors
        generator._validate_report_consistency(report, self.sample_evidence_package)


if __name__ == '__main__':
    unittest.main()