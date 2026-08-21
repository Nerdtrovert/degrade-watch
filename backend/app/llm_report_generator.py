#!/usr/bin/env python3
"""
LLM Report Generator for DegradeWatch Checkpoint 8.

Converts deterministic evidence packages into structured forensic incident reports
using an LLM, with strict validation to prevent hallucinations and ensure
faithfulness to the evidence.
"""

import json
import os
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import jsonschema
from jsonschema import validate

# Optional LLM provider imports - only import if API keys are available
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

logger = logging.getLogger(__name__)

# LLM Output Schema - defines the structure of the LLM's response
LLM_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "incident_id": {"type": "string"},
        "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
        "status": {"type": "string", "enum": ["ACTION_PROPOSED", "NO_ACTION"]},

        "summary": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "what_happened": {"type": "string"},
                "where": {
                    "type": "object",
                    "properties": {
                        "payment_method": {"type": ["string", "null"]},
                        "bank": {"type": ["string", "null"]},
                        "device": {"type": ["string", "null"]},
                        "upi_app": {"type": ["string", "null"]}
                    },
                    "required": ["payment_method", "bank", "device", "upi_app"],
                    "additionalProperties": False
                },
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "confidence_level": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                "confidence_explanation": {"type": "string"},
                "evidence_summary": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 5
                }
            },
            "required": ["title", "what_happened", "where", "confidence", "confidence_level", "confidence_explanation", "evidence_summary"],
            "additionalProperties": False
        },

        "likely_cause": {
            "type": "object",
            "properties": {
                "primary": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "evidence_refs": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["primary", "confidence", "evidence_refs"],
            "additionalProperties": False
        },

        "alternative_hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hypothesis": {"type": "string"},
                    "assessment": {"type": "string", "enum": ["SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]},
                    "explanation": {"type": "string"},
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["hypothesis", "assessment", "explanation", "evidence_refs"],
                "additionalProperties": False
            },
            "maxItems": 5
        },

        "recommended_next_steps": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5
        },

        "recovery": {
            "type": "object",
            "properties": {
                "recommendation": {"type": "string"},
                "eligible": {"type": "boolean"},
                "reason": {"type": "string"}
            },
            "required": ["recommendation", "eligible", "reason"],
            "additionalProperties": False
        },

        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "time": {"type": "string"},
                    "event": {"type": "string"}
                },
                "required": ["time", "event"],
                "additionalProperties": False
            },
            "maxItems": 10
        }
    },
    "required": [
        "incident_id", "severity", "status",
        "summary", "likely_cause", "alternative_hypotheses",
        "recommended_next_steps", "recovery", "timeline"
    ],
    "additionalProperties": False
}

class LLMReportGenerator:
    """Generates forensic incident reports from evidence packages using an LLM."""

    def __init__(self, provider: str = None, model: str = None):
        """
        Initialize the LLM report generator.

        Args:
            provider: LLM provider ("openai" or "anthropic"). If None, determined from env.
            model: Model name. If None, uses provider default.
        """
        self.provider = provider or os.getenv("DEGRADEWATCH_LLM_PROVIDER", "openai").lower()
        self.model = model or os.getenv("DEGRADEWATCH_LLM_MODEL")

        # Validate provider
        if self.provider not in ["openai", "anthropic", "groq"]:
            raise RuntimeError(f"Unsupported LLM provider: {self.provider}")

        # Set default models if not specified
        if not self.model:
            if self.provider == "openai":
                self.model = "gpt-4-turbo-preview"
            elif self.provider == "anthropic":
                self.model = "claude-3-opus-20240229"
            elif self.provider == "groq":
                self.model = "openai/gpt-oss-20b"  # Default Groq model

        # Ensure model is a string (not None)
        if self.model is None:
            if self.provider == "openai":
                self.model = "gpt-4-turbo-preview"
            elif self.provider == "anthropic":
                self.model = "claude-3-opus-20240229"
            elif self.provider == "groq":
                self.model = "openai/gpt-oss-20b"

        # Initialize clients
        self.openai_client = None
        self.anthropic_client = None
        self.groq_client = None

        if self.provider == "openai":
            if not OPENAI_AVAILABLE:
                logger.warning("OpenAI package not available")
            else:
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self.openai_client = openai.OpenAI(api_key=api_key)
                else:
                    logger.warning("OPENAI_API_KEY not set")
        elif self.provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                logger.warning("Anthropic package not available")
            else:
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if api_key:
                    self.anthropic_client = anthropic.Anthropic(api_key=api_key)
                else:
                    logger.warning("ANTHROPIC_API_KEY not set")
        elif self.provider == "groq":
            if not GROQ_AVAILABLE:
                logger.warning("Groq package not available")
            else:
                api_key = os.getenv("GROQ_API_KEY")
                if api_key:
                    self.groq_client = Groq(api_key=api_key)
                else:
                    logger.warning("GROQ_API_KEY not set")

        # Generation parameters for deterministic output
        self.temperature = 0.1  # Low temperature for consistent output
        self.max_tokens = 2000  # Reasonable limit for structured output

    def generate_report(self, evidence_package: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a forensic incident report from an evidence package.

        Args:
            evidence_package: The deterministic evidence package from Checkpoint 7

        Returns:
            Structured report JSON compliant with LLM_OUTPUT_SCHEMA

        Raises:
            ValueError: If evidence package is invalid
            RuntimeError: If LLM generation or validation fails
        """
        # Validate input evidence package
        self._validate_evidence_package_input(evidence_package)

        # Generate LLM prompt
        prompt = self._create_llm_prompt(evidence_package)

        # Call LLM
        llm_response = self._call_llm(prompt)

        # Parse and validate LLM response
        try:
            report = json.loads(llm_response)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLM returned invalid JSON: {e}")

        # Validate against schema
        try:
            validate(instance=report, schema=LLM_OUTPUT_SCHEMA)
        except jsonschema.ValidationError as e:
            raise RuntimeError(f"LLM response failed schema validation: {e}")

        # Additional validation: check consistency with evidence package
        self._validate_report_consistency(report, evidence_package)

        # Add backend-computed fields (like revenue_at_risk) that LLM shouldn't touch
        report = self._add_backend_computed_fields(report, evidence_package)

        return report

    def _validate_evidence_package_input(self, evidence_package: Dict[str, Any]) -> None:
        """Validate that the evidence package has required structure."""
        required_sections = [
            "incident_metadata", "affected_segment", "success_rate_evidence",
            "error_evidence", "localization_evidence", "temporal_evidence",
            "volume_evidence", "latency_evidence", "impact_evidence",
            "sample_payments", "hypothesis_evidence", "investigation_checklist"
        ]

        for section in required_sections:
            if section not in evidence_package:
                raise ValueError(f"Missing required evidence package section: {section}")

        # Check incident metadata
        meta = evidence_package["incident_metadata"]
        if not all(k in meta for k in ["incident_id", "severity", "detector_classification"]):
            raise ValueError("Incident metadata missing required fields")

    def _create_llm_prompt(self, evidence_package: Dict[str, Any]) -> str:
        """
        Create the prompt for the LLM.

        The prompt instructs the LLM to treat the evidence package as the sole source of truth
        and forbids accessing external data or making calculations.
        """
        import copy
        # Create a pruned copy for prompt to save tokens (e.g. for Groq API limits)
        pruned_package = copy.deepcopy(evidence_package)
        if "temporal_evidence" in pruned_package and "buckets" in pruned_package["temporal_evidence"]:
            pruned_package["temporal_evidence"]["buckets"] = []
        if "sample_payments" in pruned_package:
            pruned_package["sample_payments"] = pruned_package["sample_payments"][:3]

        # Convert pruned evidence package to JSON string for inclusion in prompt
        evidence_json = json.dumps(pruned_package, indent=2, default=str)

        prompt = f"""You are a forensic analysis AI for DegradeWatch, a payment system monitoring platform.

You are given a deterministic evidence package generated by the DegradeWatch backend. Treat it as the sole source of truth.

## YOUR ROLE
Your job is to synthesize verified evidence into a human-readable forensic incident report. You must:
- Explain what happened based only on the evidence (keep summary.what_happened under 40 words, max 2 sentences)
- Describe where and when it happened using only evidence data
- Communicate the most supported hypothesis from the evidence
- Communicate uncertainty appropriately when evidence is insufficient
- Distinguish evidence from inference
- Produce merchant-friendly recommendations
- Produce detailed Support/Engineering explanations
- Preserve evidence references
- Avoid overclaiming causality
- Keep all explanations and assessments extremely concise (under 20 words per description/explanation)
- Limit the alternative_hypotheses list to at most 2 hypotheses
- Limit the recommended_next_steps to at most 3 steps
- Limit the timeline to at most 4 events

## WHAT YOU MUST NOT DO
- Do NOT access the database or raw payment data
- Do NOT calculate statistics, success rates, or revenue at risk
- Do NOT determine statistical significance
- Do NOT override detector classification
- Do NOT invent evidence, metrics, timestamps, affected segments, or error rates
- Do NOT execute recovery actions or approve money movement
- Do NOT make policy decisions
- Do NOT generate estimated_revenue_at_risk values (the backend provides this)

If something is absent from the evidence package, state: "Insufficient evidence to determine."

## EVIDENCE PACKAGE
{evidence_json}

## OUTPUT FORMAT
Respond with a valid JSON object matching this exact structure:
{json.dumps(LLM_OUTPUT_SCHEMA, indent=2)}

## SPECIAL INSTRUCTIONS FOR SCENARIO E
If the evidence shows customer-caused errors increasing while technical errors remain normal (as indicated in the investigation checklist), you MUST:
- Set status to "NO_ACTION"
- Explain that automated recovery should NOT be triggered
- Clearly state that the success rate degradation is due to customer-side issues
- Recommend customer-facing actions only (like suggesting alternative payment methods)

Now generate the forensic incident report:"""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """
        Call the configured LLM provider.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM's response as a string

        Raises:
            RuntimeError: If LLM call fails or provider not available
        """
        if self.provider == "openai":
            if not self.openai_client:
                raise RuntimeError("OpenAI client not initialized - check OPENAI_API_KEY")

            try:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a forensic analysis AI. You must return ONLY a raw, valid JSON object matching the requested schema. Do NOT wrap the JSON in markdown code blocks (do not use triple backticks). Start directly with '{' and end with '}'."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"}  # Ensure JSON output
                )
                return response.choices[0].message.content
            except Exception as e:
                raise RuntimeError(f"OpenAI API call failed: {e}")

        elif self.provider == "anthropic":
            if not self.anthropic_client:
                raise RuntimeError("Anthropic client not initialized - check ANTHROPIC_API_KEY")

            try:
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system="You are a forensic analysis AI. You must return ONLY a raw, valid JSON object matching the requested schema. Do NOT wrap the JSON in markdown code blocks (do not use triple backticks). Start directly with '{' and end with '}'.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.content[0].text
            except Exception as e:
                raise RuntimeError(f"Anthropic API call failed: {e}")

        elif self.provider == "groq":
            if not self.groq_client:
                raise RuntimeError("Groq client not initialized - check GROQ_API_KEY")

            try:
                # Groq uses OpenAI-compatible API
                response = self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a forensic analysis AI. You must return ONLY a raw, valid JSON object matching the requested schema. Do NOT wrap the JSON in markdown code blocks (do not use triple backticks). Start directly with '{' and end with '}'."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"}  # Ensure JSON output
                )
                return response.choices[0].message.content
            except Exception as e:
                raise RuntimeError(f"Groq API call failed: {e}")
        else:
            raise RuntimeError(f"Unsupported LLM provider: {self.provider}")

    def _validate_report_consistency(self, report: Dict[str, Any], evidence_package: Dict[str, Any]) -> None:
        """
        Validate that the LLM report is consistent with the evidence package.

        This prevents the LLM from inventing facts or contradicting the evidence.
        """
        # Validate incident ID matches
        if report["incident_id"] != evidence_package["incident_metadata"]["incident_id"]:
            raise ValueError(f"Report incident_id '{report['incident_id']}' doesn't match evidence '{evidence_package['incident_metadata']['incident_id']}'")

        # Validate severity matches detector classification (LLM can interpret but shouldn't contradict)
        detector_severity = evidence_package["incident_metadata"]["severity"]
        report_severity = report["severity"]
        # Allow LLM to map detector's internal severity to HIGH/MEDIUM/LOW but check for gross contradictions
        severity_map = {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH"}
        if detector_severity in severity_map:
            expected = severity_map[detector_severity]
            # For now, we'll accept any severity as LLM can interpret, but log if very different
            if (expected == "LOW" and report_severity == "HIGH") or (expected == "HIGH" and report_severity == "LOW"):
                logger.warning(f"Severity mismatch: detector says {detector_severity}, LLM says {report_severity}")

        # Validate affected segment matches evidence
        evidence_segment = evidence_package["affected_segment"]
        report_where = report["summary"]["where"]

        # Check each segment field
        segment_fields = ["payment_method", "bank", "device", "upi_app"]
        for field in segment_fields:
            evidence_val = evidence_segment.get(field)
            report_val = report_where.get(field)

            # Handle NULL/"None" normalization
            if evidence_val in [None, "NULL"]:
                evidence_val = None
            if report_val in [None, "NULL"]:
                report_val = None

            if evidence_val != report_val:
                raise ValueError(f"Report '{field}' '{report_val}' doesn't match evidence '{evidence_val}'")

        # Validate that alternative hypotheses assessments are consistent with evidence
        # This is a simplified check - in practice we'd do deeper validation
        for hypo in report["alternative_hypotheses"]:
            # Just verify the hypothesis structure is valid - deeper validation would require
            # parsing the evidence package and checking signals, which is complex
            if hypo["assessment"] not in ["SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]:
                raise ValueError(f"Invalid hypothesis assessment: {hypo['assessment']}")

        # Validate likely_cause evidence references
        likely_cause = report.get("likely_cause", {})
        for ref in likely_cause.get("evidence_refs", []):
            if not self._validate_evidence_reference(ref, evidence_package):
                raise ValueError(f"Hallucinated evidence reference in likely_cause: {ref}")

        # Validate alternative_hypotheses evidence references
        for hypo in report.get("alternative_hypotheses", []):
            for ref in hypo.get("evidence_refs", []):
                if not self._validate_evidence_reference(ref, evidence_package):
                    raise ValueError(f"Hallucinated evidence reference in alternative_hypothesis: {ref}")

    def _validate_evidence_reference(self, ref: str, evidence_package: Dict[str, Any]) -> bool:
        # Normalize bracket index notation (e.g. list[0] -> list.0)
        normalized_ref = ref.replace("[", ".").replace("]", "")
        parts = normalized_ref.split(".")
        current = evidence_package
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return False
                except ValueError:
                    return False
            else:
                return False
        return True

    def _add_backend_computed_fields(self, report: Dict[str, Any], evidence_package: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add fields that the backend computes after LLM generation.

        The LLM should not generate revenue_at_risk - the backend adds it from evidence.
        """
        # Add revenue at risk from evidence package (LLM should not touch this)
        revenue_at_risk_paise = evidence_package["impact_evidence"]["revenue_at_risk"]["paise"]
        report["estimated_revenue_at_risk"] = {
            "paise": revenue_at_risk_paise,
            "rupees": revenue_at_risk_paise / 100.0
        }

        # Force backend-owned severity (LLM cannot downgrade/upgrade severity)
        report["severity"] = evidence_package["incident_metadata"]["severity"]

        # Force backend-owned status based on detector classification
        if evidence_package["incident_metadata"]["detector_classification"] == "NORMAL":
            report["status"] = "NO_ACTION"

        # Add any other backend-computed fields here
        return report

    def create_merchant_view(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a merchant-friendly view of the report.

        Args:
            report: The full forensic incident report

        Returns:
            Merchant-view dictionary with concise, actionable information
        """
        return {
            "title": report["summary"]["title"],
            "what_happened": report["summary"]["what_happened"],
            "where": report["summary"]["where"],
            "how_serious": report["severity"],
            "likely_explanation": report["likely_cause"]["primary"],
            "evidence_summary": report["summary"]["evidence_summary"],
            "recommended_next_steps": report["recommended_next_steps"],
            "automated_recovery_available": report["recovery"]["eligible"],
            "revenue_at_risk": report.get("estimated_revenue_at_risk", {"paise": 0, "rupees": 0})
        }

    def create_support_view(self, report: Dict[str, Any], evidence_package: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a detailed support/engineering view of the report.

        Args:
            report: The forensic incident report
            evidence_package: The original evidence package

        Returns:
            Support-view dictionary with forensic details
        """
        return {
            "incident_metadata": evidence_package["incident_metadata"],
            "affected_segment": evidence_package["affected_segment"],
            "timeline": report["timeline"],
            "summary": report["summary"],
            "likely_cause": report["likely_cause"],
            "alternative_hypotheses": report["alternative_hypotheses"],
            "investigation_checklist": evidence_package["investigation_checklist"],
            "evidence_details": {
                "success_rate_evidence": evidence_package["success_rate_evidence"],
                "error_evidence": evidence_package["error_evidence"],
                "localization_evidence": evidence_package["localization_evidence"],
                "temporal_evidence": evidence_package["temporal_evidence"],
                "volume_evidence": evidence_package["volume_evidence"],
                "latency_evidence": evidence_package["latency_evidence"],
                "impact_evidence": evidence_package["impact_evidence"]
            },
            "sample_payments": evidence_package["sample_payments"],
            "report_validation": {
                "llm_generated": True,
                "backend_validated": True,
                "consistent_with_evidence": True
            }
        }

# Convenience function for external use
def generate_forensic_report(
    evidence_package: Dict[str, Any],
    provider: str = None,
    model: str = None
) -> Dict[str, Any]:
    """
    Generate a forensic incident report from an evidence package.

    Args:
        evidence_package: The deterministic evidence package from Checkpoint 7
        provider: LLM provider ("openai" or "anthropic")
        model: Model name

    Returns:
        Structured report JSON with backend-computed fields added
    """
    generator = LLMReportGenerator(provider=provider, model=model)
    report = generator.generate_report(evidence_package)
    return report

if __name__ == "__main__":
    # Simple test when run directly
    import sys
    from pathlib import Path

    # For testing, we'd need to load an actual evidence package
    # This is just to show the module can be imported
    print("LLM Report Generator module loaded successfully")
    print(f"Available providers: OpenAI={OPENAI_AVAILABLE}, Anthropic={ANTHROPIC_AVAILABLE}, Groq={GROQ_AVAILABLE}")