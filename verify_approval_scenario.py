#!/usr/bin/env python3
"""
Verify that the created scenario results in HUMAN_APPROVAL according to the policy engine.
"""
import sys
import os
from datetime import datetime, timezone

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend'))

from app.policy_engine import PolicyEngine, PolicyConfig

def create_scenario_h_evidence():
    '''Create evidence package representing Scenario H: Requires Human Approval (low confidence)'''
    evidence_package = {
        'incident_metadata': {
            'incident_id': 'scenario_h_merchant_20260822_120000',
            'merchant_id': 'scenario_h_merchant',
            'detection_timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis_window': {
                'start': '2026-08-22T11:30:00Z',
                'end': '2026-08-22T12:00:00Z',
                'duration_minutes': 30
            },
            'severity': 'MEDIUM',
            'detector_classification': 'INCIDENT',
            'detector_confidence': 'HIGH'
        },
        'affected_segment': {
            'payment_method': 'UPI',
            'bank': 'BANK_H',
            'device': 'ANDROID',
            'upi_app': 'PAYTM',
            'hierarchy_level': 'FULL_SEGMENT',
            'baseline_attempts': 1000,
            'baseline_success_rate': 0.95,
            'current_attempts': 800,
            'current_success_rate': 0.80,
            'segment_key': 'UPI|BANK_H|ANDROID|PAYTM'
        },
        'success_rate_evidence': {
            'baseline_success_rate': 0.95,
            'current_success_rate': 0.80,
            'absolute_change': -0.15,
            'absolute_percentage_point_change': -15.0,
            'relative_change': -0.1579,
            'baseline_attempts': 1000,
            'current_attempts': 800,
            'statistical_significance': {
                'statistically_significant': True,
                'p_value': 0.001,
                'z_score': -3.29,
                'confidence_level': 0.95
            },
            'test_type': 'two_proportion_z_test',
            'interpretation': 'Statistically significant severe degradation'
        },
        'error_evidence': {
            'baseline': {
                'customer_error_rate': 0.02,
                'technical_error_rate': 0.03,
                'other_error_rate': 0.00,
                'failure_rate': 0.05,
                'failure_breakdown': {
                    'customer_caused': 20,
                    'technical': 30,
                    'other': 0
                }
            },
            'current': {
                'customer_error_rate': 0.020,
                'technical_error_rate': 0.175,
                'other_error_rate': 0.00,
                'failure_rate': 0.195,
                'failure_breakdown': {
                    'customer_caused': 16,
                    'technical': 140,
                    'other': 0
                }
            },
            'changes': {
                'customer_error_rate_change': 0.000,
                'technical_error_rate_change': 0.145,
                'other_error_rate_change': 0.0,
                'customer_error_relative_change': 0.0,
                'technical_error_relative_change': 3.833
            },
            'error_code_distribution': {
                'GATEWAY_TIMEOUT': 100,
                'NETWORK_ERROR': 40
            },
            'error_code_shifts': {}
        },
        'localization_evidence': {
            'affected_segment': {
                'payment_method': 'UPI',
                'bank': 'BANK_H',
                'device': 'ANDROID',
                'upi_app': 'PAYTM',
                'success_rate': 0.80,
                'attempts': 800
            },
            'localization_status': 'LOCALIZED',
            'control_analysis': {
                'status': 'LOCALIZED',
                'message': 'Control segments remain healthy',
                'control_segments': {
                    'Other banks (same device=ANDROID, upi_app=PAYTM)': {
                        'attempts': 200,
                        'successes': 190,
                        'success_rate': 0.95,
                        'status': 'HEALTHY'
                    }
                }
            }
        },
        'impact_evidence': {
            'revenue_at_risk': {
                'paise': 75000,
                'currency': 'INR',
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            'affected_users': 75,
            'affected_transactions': 50
        },
        'investigation_checklist': [
            {
                'check': 'primarily_customer_caused',
                'result': 'PASS',
                'details': 'Technical error rate increased significantly while customer error rate unchanged'
            },
            {
                'check': 'control_analysis_healthy',
                'result': 'PASS',
                'details': 'All control segments are healthy'
            }
        ],
        'temporal_evidence': {},
        'volume_evidence': {},
        'latency_evidence': {},
        'sample_payments': [
            {
                'payment_id': 'pay_sample_003',
                'timestamp': '2026-08-22T11:45:00Z',
                'amount': {'paise': 15000, 'currency': 'INR'},
                'status': 'FAILED',
                'failure_reason': 'GATEWAY_TIMEOUT'
            }
        ],
        'hypothesis_evidence': {}
    }
    return evidence_package

def create_scenario_h_llm_report(evidence_package):
    '''Create a realistic LLM report for Scenario H with low confidence'''
    return {
        'incident_id': evidence_package['incident_metadata']['incident_id'],
        'severity': evidence_package['incident_metadata']['severity'],
        'status': 'ACTION_REQUIRED',
        'summary': {
            'title': 'UPI Payment Gateway Timeout - Localized Issue (Human Review Required)',
            'what_happened': 'Payment success rate dropped from 95% to 80% for UPI transactions with BANK_H on Android Paytm due to gateway timeouts',
            'where': {
                'payment_method': 'UPI',
                'bank': 'BANK_H',
                'device': 'ANDROID',
                'upi_app': 'PAYTM'
            },
            'confidence': 0.75,  # BELOW 0.85 THRESHOLD - This will trigger LOW_CONFIDENCE
            'confidence_level': 'MEDIUM',
            'confidence_explanation': 'Medium confidence based on technical error pattern, but requires human review due to conflicting indicators in error patterns',
            'evidence_summary': [
                'Success rate dropped 15 percentage points (95% → 80%)',
                'Technical error rate increased from 3% to 17.5%',
                'Error analysis shows GATEWAY_TIMEOUT as primary failure reason',
                'Issue is localized to UPI|BANK_H|ANDROID|PAYTM segment',
                'Control segments show normal behavior'
            ]
        },
        'likely_cause': {
            'primary': 'Payment gateway timeout issue with BANK_H UPI integration',
            'confidence': 0.72,
            'evidence_refs': [
                'error_evidence.error_code_distribution.GATEWAY_TIMEOUT',
                'error_evidence.changes.technical_error_rate_change'
            ]
        },
        'alternative_hypotheses': [
            {
                'hypothesis': 'Customer network connectivity issues',
                'evidence_refs': ['error_evidence.changes.customer_error_rate_change'],
                'assessment': 'CONTRADICTED'
            },
            {
                'hypothesis': 'Bank server overload',
                'evidence_refs': ['error_evidence.error_code_distribution.NETWORK_ERROR'],
                'assessment': 'CONTRADICTED'
            }
        ],
        'recommended_next_steps': [
            'Monitor payment success rate for the next 15 minutes',
            'Check BANK_H gateway status and logs',
            'Prepare customer communication if issue persists',
            'Have fallback routing options ready',
            'Escalate to senior payments team for manual review'
        ],
        'recovery': {
            'eligible': True,
            'recommendation': 'PAYMENT_LINK',
            'amount': {'paise': 15000, 'currency': 'INR'},
            'reason': 'To compensate affected users for failed transactions due to gateway timeout'
        },
        'timeline': [
            {
                'time': evidence_package['incident_metadata']['detection_timestamp'],
                'event': 'Incident detected by automated monitoring'
            },
            {
                'time': datetime.now(timezone.utc).isoformat(),
                'event': 'Forensic analysis completed'
            }
        ]
    }

def main():
    # Create the scenario data
    evidence_h = create_scenario_h_evidence()
    llm_report_h = create_scenario_h_llm_report(evidence_h)
    
    # Create policy engine and make decision
    policy_engine = PolicyEngine()
    decision = policy_engine.make_decision(evidence_h, llm_report_h)
    
    print("Scenario H Verification")
    print("======================")
    print(f"Incident ID: {evidence_h['incident_metadata']['incident_id']}")
    print(f"Detector Classification: {evidence_h['incident_metadata']['detector_classification']}")
    print(f"Baseline Attempts: {evidence_h['affected_segment']['baseline_attempts']}")
    print(f"LLM Confidence: {llm_report_h['summary']['confidence']}")
    print(f"Revenue at Risk (paise): {evidence_h['impact_evidence']['revenue_at_risk']['paise']}")
    print(f"Localization Status: {evidence_h['localization_evidence']['localization_status']}")
    print(f"Investigation Checklist Results: {[check['result'] for check in evidence_h['investigation_checklist']]}")
    print(f"Requested Recovery Action: {llm_report_h['recovery']['recommendation']}")
    print(f"Statistical Significance: {evidence_h['success_rate_evidence']['statistical_significance']['statistically_significant']}")
    print()
    print("Policy Decision:")
    print(f"  Decision: {decision['decision']}")
    print(f"  Reason Codes: {decision['reason_codes']}")
    print(f"  Human Readable Reason: {decision['human_readable_reason']}")
    print()
    
    # Verify this meets our requirements
    assert decision['decision'] == 'HUMAN_APPROVAL', f"Expected HUMAN_APPROVAL, got {decision['decision']}"
    assert 'LOW_CONFIDENCE' in decision['reason_codes'], "LOW_CONFIDENCE should be in reason codes"
    print("✓ Scenario correctly results in HUMAN_APPROVAL due to LOW_CONFIDENCE")
    print("✓ This scenario can be used for the human approval path in the demo")

if __name__ == '__main__':
    main()
