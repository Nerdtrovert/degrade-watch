import apiClient from './client';

export const supportAPI = {
  getIncidents: () => apiClient.get('/api/support/incidents'),
  getIncidentDetail: (incidentId: string) => apiClient.get(`/api/support/incidents/${incidentId}`),
  getEvidence: (incidentId: string) => apiClient.get(`/api/support/evidence/${incidentId}`),
  getAudit: (incidentId: string) => apiClient.get(`/api/support/audit/${incidentId}`),
};

export type SupportIncident = {
  incident_id: string;
  merchant_id: string;
  detection_timestamp: string;
  severity: string;
  classification: string;
  affected_segment: any;
  impact_evidence: any;
  policy_status: string; // From the API: policy_decision.decision
  recovery_status: string; // From the API: recovery.state
  // Additional fields for detail view
  success_rate_evidence?: any;
  error_evidence?: any;
  localization_evidence?: any;
  temporal_evidence?: any;
  volume_evidence?: any;
  latency_evidence?: any;
  investigation_checklist?: any[];
  sample_payments?: any[];
  hypothesis_evidence?: any;
  llm_report?: any;
  policy_decision?: any;
  recovery?: any;
  audit_trail?: Array<any>;
};

export type SupportEvidence = any; // We'll use the same as evidence package

export type SupportAudit = {
  audit_trail: Array<any>;
};