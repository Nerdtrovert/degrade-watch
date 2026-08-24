import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { approvalsAPI, ApprovalDetail } from '../../api/approvals';

const ApprovalDetail: React.FC = () => {
  const { approvalId } = useParams<{ approvalId: string }>();
  const [approval, setApproval] = useState<ApprovalDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchApproval = async () => {
      try {
        setLoading(true);
        const response = await approvalsAPI.getApprovalDetail(approvalId!);
        setApproval(response.data.approval);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch approval detail:', err);
        if (err.response?.status === 404) {
          setError('Approval not found');
        } else {
          setError('Failed to load approval details');
        }
      } finally {
        setLoading(false);
      }
    };

    if (approvalId) {
      fetchApproval();
    }
  }, [approvalId]);

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  if (error) {
    return <div className="text-center py-12 text-red-500">{error}</div>;
  }

  if (!approval) {
    return <div className="text-center py-12">No approval data available</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-4">
        <h1 className="text-2xl font-bold">Approval Detail</h1>
        <Link to="/approvals" className="text-sm text-blue-600 hover:text-blue-800">
          ← Back to Queue
        </Link>
      </div>

      {/* We'll split the detail into sections */}
      <div className="space-y-6">
        {/* Approval Information */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Approval Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p><strong>Approval ID:</strong> {approval.approval_id}</p>
              <p><strong>Incident ID:</strong> {approval.incident_id}</p>
              <p><strong>Merchant ID:</strong> {approval.merchant_id}</p>
              <p><strong>Severity:</strong>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  approval.severity === 'HIGH' ? 'bg-red-100 text-red-800' :
                  approval.severity === 'MEDIUM' ? 'bg-orange-100 text-orange-800' :
                  approval.severity === 'LOW' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-green-100 text-green-800'
                }`}>
                  {approval.severity}
                </span>
              </p>
              <p><strong>Revenue at Risk:</strong> {(approval.revenue_at_risk_paise || 0) / 100} INR</p>
              <p><strong>Proposed Action:</strong> {approval.proposed_action}</p>
              <p><strong>Policy Reason Codes:</strong> {approval.policy_reason_codes.join(', ')}</p>
              <p><strong>Confidence:</strong> {((approval.confidence || 0) * 100).toFixed(1)}%</p>
              <p><strong>Status:</strong>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  approval.status === 'PENDING' ? 'bg-yellow-100 text-yellow-800' :
                  approval.status === 'APPROVED' ? 'bg-green-100 text-green-800' :
                  approval.status === 'REJECTED' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {approval.status}
                </span>
              </p>
              <p><strong>Created At:</strong> {new Date(approval.created_at).toLocaleString()}</p>
              {approval.updated_at && (
                <p><strong>Updated At:</strong> {new Date(approval.updated_at).toLocaleString()}</p>
              )}
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Related Incident</h3>
              {approval.incident ? (
                <div className="space-y-2">
                  <p><strong>Detection Time:</strong> {new Date(approval.incident.detection_timestamp).toLocaleString()}</p>
                  <p><strong>Classification:</strong> {approval.incident.classification}</p>
                  <p><strong>Affected Segment:</strong> {approval.incident.affected_segment.payment_method} | {approval.incident.affected_segment.bank} | {approval.incident.affected_segment.device}</p>
                  <p><strong>Success Rate Change:</strong> {(((approval.incident.success_rate_evidence?.current_success_rate || 0) - (approval.incident.success_rate_evidence?.baseline_success_rate || 0)) * 100).toFixed(1)} pp</p>
                  <p><strong>Revenue at Risk:</strong> {(approval.incident.impact_evidence?.revenue_at_risk.paise || 0) / 100} INR</p>
                </div>
              ) : (
                <p>No incident data available</p>
              )}
            </div>
          </div>
        </div>

        {/* Evidence */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Evidence Package</h2>
          {approval.evidence ? (
            <div className="space-y-3">
              <div>
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Localization</h3>
                <p><strong>Localization Status:</strong> {approval.evidence.localization_evidence.localization_status || 'N/A'}</p>
                <p><strong>Control Analysis:</strong> {approval.evidence.localization_evidence.control_analysis.message || 'N/A'}</p>
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Impact</h3>
                <p><strong>Revenue at Risk:</strong> {(approval.evidence.impact_evidence.revenue_at_risk.paise || 0) / 100} INR</p>
                <p><strong>Affected Users:</strong> {approval.evidence.impact_evidence.affected_users || 0}</p>
                <p><strong>Affected Transactions:</strong> {approval.evidence.impact_evidence.affected_transactions || 0}</p>
              </div>
              <div className="mt-4">
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Investigation Checklist</h3>
                <ul className="space-y-2">
                  {approval.evidence.investigation_checklist.map((check: any, index: number) => (
                    <li key={index} className="p-2 bg-gray-50 rounded">
                      <div className="flex justify-between">
                        <span><strong>{check.check}:</strong> {check.result}</span>
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${ check.result === 'PASS' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-700 border-red-200'}`}>{check.result}</span>
                      </div>
                      <p className="mt-1 text-sm text-gray-600">{check.details}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <p>No evidence data available</p>
          )}
        </div>

        {/* LLM Report */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">LLM Forensic Report</h2>
          {approval.llm_report ? (
            <div className="space-y-3">
              <div>
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Summary</h3>
                <p><strong>Title:</strong> {approval.llm_report.summary.title}</p>
                <p><strong>What Happened:</strong> {approval.llm_report.summary.what_happened}</p>
                <p><strong>Where:</strong></p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Payment Method: {approval.llm_report.summary.where.payment_method}</li>
                  <li>Bank: {approval.llm_report.summary.where.bank}</li>
                  <li>Device: {approval.llm_report.summary.where.device}</li>
                  <li>UPI App: {approval.llm_report.summary.where.upi_app}</li>
                </ul>
                <p><strong>Confidence:</strong> {((approval.llm_report.summary.confidence || 0) * 100).toFixed(1)}% ({approval.llm_report.summary.confidence_level})</p>
                <p><strong>Confidence Explanation:</strong> {approval.llm_report.summary.confidence_explanation}</p>
              </div>
              <div className="mt-4">
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Evidence Summary</h3>
                <ul className="list-disc list-inside space-y-1">
                  {approval.llm_report.summary.evidence_summary.map((point: string, index: number) => (
                    <li key={index}>{point}</li>
                  ))}
                </ul>
              </div>
              <div className="mt-4">
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Likely Cause</h3>
                <p><strong>Primary:</strong> {approval.llm_report.likely_cause.primary}</p>
                <p><strong>Confidence:</strong> {((approval.llm_report.likely_cause.confidence || 0) * 100).toFixed(1)}%</p>
              </div>
              <div className="mt-4">
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Alternative Hypotheses</h3>
                {approval.llm_report.alternative_hypotheses.map((hypothesis: any, index: number) => (
                  <div key={index} className="p-3 bg-gray-50 rounded">
                    <p><strong>Hypothesis:</strong> {hypothesis.hypothesis}</p>
                    <p><strong>Assessment:</strong> {hypothesis.assessment}</p>
                    <p><strong>Evidence Refs:</strong> {hypothesis.evidence_refs.join(', ')}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Recommended Next Steps</h3>
                <ol className="list-decimal list-inside space-y-1">
                  {approval.llm_report.recommended_next_steps.map((step: string, index: number) => (
                    <li key={index}>{step}</li>
                  ))}
                </ol>
              </div>
              <div className="mt-4">
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Recovery Recommendation</h3>
                <p><strong>Eligible:</strong> {approval.llm_report.recovery.eligible ? 'Yes' : 'No'}</p>
                <p><strong>Recommendation:</strong> {approval.llm_report.recovery.recommendation}</p>
                <p><strong>Amount:</strong> {(approval.llm_report.recovery.amount.paise || 0) / 100} INR</p>
                <p><strong>Reason:</strong> {approval.llm_report.recovery.reason}</p>
              </div>
            </div>
          ) : (
            <p>No LLM report data available</p>
          )}
        </div>

        {/* Policy Decision */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Policy Decision</h2>
          {approval.policy_decision ? (
            <div className="space-y-3">
              <p><strong>Decision:</strong>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  approval.policy_decision.decision === 'AUTO_APPROVED' ? 'bg-green-100 text-green-800' :
                  approval.policy_decision.decision === 'HUMAN_APPROVAL' ? 'bg-yellow-100 text-yellow-800' :
                  approval.policy_decision.decision === 'BLOCKED' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {approval.policy_decision.decision}
                </span>
              </p>
              <p><strong>Action Type:</strong> {approval.policy_decision.action_type}</p>
              <p><strong>Reason Codes:</strong> {approval.policy_decision.reason_codes.join(', ')}</p>
              <p><strong>Human Readable Reason:</strong> {approval.policy_decision.human_readable_reason}</p>
              <p><strong>Metadata:</strong> {JSON.stringify(approval.policy_decision.metadata || {}, null, 2)}</p>
            </div>
          ) : (
            <p>No policy decision data available</p>
          )}
        </div>
      </div>

      {/* Action Buttons (only show for pending approvals) */}
      {approval.status === 'PENDING' && (
        <div className="mt-6 flex justify-end space-x-3">
          <button
            onClick={() => handleApprove(approval.approval_id)}
            className="px-4 py-2 bg-green-500 text-white font-medium rounded hover:bg-green-600"
          >
            Approve Recovery
          </button>
          <button
            onClick={() => handleReject(approval.approval_id)}
            className="px-4 py-2 bg-red-500 text-white font-medium rounded hover:bg-red-600"
          >
            Reject Recovery
          </button>
        </div>
      )}
    </div>
  );

  // Handler functions
  async function handleApprove(approvalId: string) {
    try {
      await approvalsAPI.approveApproval(approvalId);
      alert('Recovery approved successfully');
      // In a real app, we would redirect to the approvals queue or show a success message
      window.location.href = '/approvals';
    } catch (err: any) {
      console.error('Failed to approve:', err);
      alert('Failed to approve recovery');
    }
  }

  async function handleReject(approvalId: string) {
    try {
      await approvalsAPI.rejectApproval(approvalId);
      alert('Recovery rejected successfully');
      // In a real app, we would redirect to the approvals queue or show a success message
      window.location.href = '/approvals';
    } catch (err: any) {
      console.error('Failed to reject:', err);
      alert('Failed to reject recovery');
    }
  }
};

export default ApprovalDetail;