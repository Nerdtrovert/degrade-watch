import apiClient from './client';

export const approvalsAPI = {
  getApprovals: () => apiClient.get('/api/approvals'),
  getApprovalDetail: (approvalId: string) => apiClient.get(`/api/approvals/${approvalId}`),
  approveApproval: (approvalId: string) => apiClient.post(`/api/approvals/${approvalId}/approve`),
  rejectApproval: (approvalId: string) => apiClient.post(`/api/approvals/${approvalId}/reject`),
};

export type Approval = {
  approval_id: string;
  incident_id: string;
  merchant_id: string;
  severity: string;
  revenue_at_risk_paise: number;
  proposed_action: string;
  policy_reason_codes: string[];
  confidence: number;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  created_at: string;
  updated_at?: string;
};

export type ApprovalDetail = Approval & {
  incident: any;
  evidence: any;
  llm_report: any;
  policy_decision: any;
};