import apiClient from './client';

export const merchantAPI = {
  getOverview: () => apiClient.get('/api/merchant/overview'),
  getIncidents: () => apiClient.get('/api/merchant/incidents'),
  getIncidentDetail: (incidentId: string) => apiClient.get(`/api/merchant/incidents/${incidentId}`),
  getRecoveries: () => apiClient.get('/api/merchant/recoveries'),
};

export type MerchantOverview = {
  total_incidents: number;
  active_incidents: number;
  overall_success_rate_change: number;
  total_revenue_at_risk_paise: number;
  recent_incidents: Array<any>;
};

export type MerchantIncident = {
  incident_id: string;
  merchant_id: string;
  detection_timestamp: string;
  severity: string;
  classification: string;
  affected_segment: any;
  impact_evidence: any;
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
};

export type MerchantRecovery = {
  recovery_id: string;
  incident_id: string;
  action_type: string;
  state: string;
  amount_paise: number;
  currency: string;
  created_at: string;
  completed_at?: string;
  error?: string;
  audit_events?: Array<any>;
};