import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { supportAPI, SupportIncident } from '../../api/support';

const SupportIncidentDetail: React.FC = () => {
  const { incidentId } = useParams<{ incidentId: string }>();
  const [incident, setIncident] = useState<SupportIncident | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchIncident = async () => {
      try {
        setLoading(true);
        const response = await supportAPI.getIncidentDetail(incidentId!);
        setIncident(response.data.incident);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch support incident detail:', err);
        if (err.response?.status === 404) {
          setError('Incident not found');
        } else {
          setError('Failed to load incident details');
        }
      } finally {
        setLoading(false);
      }
    };

    if (incidentId) {
      fetchIncident();
    }
  }, [incidentId]);

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  if (error) {
    return <div className="text-center py-12 text-red-500">{error}</div>;
  }

  if (!incident) {
    return <div className="text-center py-12">No incident data available</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-4">
        <h1 className="text-2xl font-bold">Incident Detail (Forensic View)</h1>
        <Link to="/support" className="text-sm text-blue-600 hover:text-blue-800">
          ← Back to Console
        </Link>
      </div>

      {/* We'll split the detail into sections */}
      <div className="space-y-6">
        {/* Incident Metadata */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Incident Metadata</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p><strong>Incident ID:</strong> {incident.incident_id}</p>
              <p><strong>Merchant ID:</strong> {incident.merchant_id}</p>
              <p><strong>Detection Time:</strong> {new Date(incident.detection_timestamp).toLocaleString()}</p>
              <p><strong>Analysis Window:</strong> {/* This would come from the evidence package, but we don't have it in the support incident object */}
                {/* We'll need to get the evidence to show the full analysis window, but for now we'll skip or get from evidence endpoint */}
                To be loaded from evidence
              </p>
              <p><strong>Severity:</strong>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  incident.severity === 'HIGH' ? 'bg-red-100 text-red-800' :
                  incident.severity === 'MEDIUM' ? 'bg-orange-100 text-orange-800' :
                  incident.severity === 'LOW' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-green-100 text-green-800'
                }`}>
                  {incident.severity}
                </span>
              </p>
              <p><strong>Classification:</strong>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  incident.classification === 'INCIDENT' ? 'bg-red-100 text-red-800' :
                  incident.classification === 'NORMAL' ? 'bg-green-100 text-green-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {incident.classification}
                </span>
              </p>
              <p><strong>Policy Status:</strong>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  incident.policy_status === 'AUTO_APPROVED' ? 'bg-green-100 text-green-800' :
                  incident.policy_status === 'HUMAN_APPROVAL' ? 'bg-yellow-100 text-yellow-800' :
                  incident.policy_status === 'BLOCKED' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {incident.policy_status}
                </span>
              </p>
              <p><strong>Recovery Status:</strong>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  incident.recovery_status === 'COMPLETED' ? 'bg-green-100 text-green-800' :
                  incident.recovery_status === 'PROCESSING' ? 'bg-blue-100 text-blue-800' :
                  incident.recovery_status === 'PENDING' ? 'bg-yellow-100 text-yellow-800' :
                  incident.recovery_status === 'FAILED' ? 'bg-red-100 text-red-800' :
                  incident.recovery_status === 'CANCELLED' ? 'bg-gray-100 text-gray-800' :
                  incident.recovery_status === 'NOT_AUTHORIZED' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {incident.recovery_status}
                </span>
              </p>
            </div>
            <div>
              <p><strong>Affected Segment:</strong></p>
              <ul className="list-disc list-inside space-y-1">
                <li>Payment Method: {incident.affected_segment.payment_method}</li>
                <li>Bank: {incident.affected_segment.bank}</li>
                <li>Device: {incident.affected_segment.device}</li>
                <li>UPI App: {incident.affected_segment.upi_app || 'N/A'}</li>
                <li>Hierarchy Level: {incident.affected_segment.hierarchy_level || 'N/A'}</li>
                <li>Segment Key: {incident.affected_segment.segment_key || 'N/A'}</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Success Rate Evidence */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Success Rate Evidence</h2>
          {incident.success_rate_evidence ? (
            <div className="space-y-3">
              <p><strong>Baseline Success Rate:</strong> {(incident.success_rate_evidence.baseline_success_rate * 100).toFixed(1)}%</p>
              <p><strong>Current Success Rate:</strong> {(incident.success_rate_evidence.current_success_rate * 100).toFixed(1)}%</p>
              <p><strong>Absolute Change:</strong> {(incident.success_rate_evidence.absolute_change * 100).toFixed(1)} pp</p>
              <p><strong>Relative Change:</strong> {(incident.success_rate_evidence.relative_change * 100).toFixed(1)}%</p>
              <p><strong>Baseline Attempts:</strong> {incident.success_rate_evidence.baseline_attempts || 0}</p>
              <p><strong>Current Attempts:</strong> {incident.success_rate_evidence.current_attempts || 0}</p>
              {incident.success_rate_evidence.statistical_significance ? (
                <div className="bg-gray-50 p-3 rounded">
                  <p><strong>Statistical Significance:</strong></p>
                  <p>Statistically Significant: {incident.success_rate_evidence.statistical_significance.statistically_significant ? 'Yes' : 'No'}</p>
                  <p>p-value: {incident.success_rate_evidence.statistical_significance.p_value}</p>
                  <p>Z-score: {incident.success_rate_evidence.statistical_significance.z_score}</p>
                  <p>Confidence Level: {(incident.success_rate_evidence.statistical_significance.confidence_level * 100).toFixed(1)}%</p>
                  <p><strong>Interpretation:</strong> {incident.success_rate_evidence.interpretation || 'N/A'}</p>
                </div>
              ) : null}
            </div>
          ) : (
            <p>No success rate evidence available</p>
          )}
        </div>

        {/* Error Evidence */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Error Evidence</h2>
          {incident.error_evidence ? (
            <div className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Baseline</h3>
                  <p><strong>Customer Error Rate:</strong> {(incident.error_evidence.baseline.customer_error_rate * 100).toFixed(1)}%</p>
                  <p><strong>Technical Error Rate:</strong> {(incident.error_evidence.baseline.technical_error_rate * 100).toFixed(1)}%</p>
                  <p><strong>Other Error Rate:</strong> {(incident.error_evidence.baseline.other_error_rate * 100).toFixed(1)}%</p>
                  <p><strong>Failure Rate:</strong> {(incident.error_evidence.baseline.failure_rate * 100).toFixed(1)}%</p>
                  <p><strong>Failure Breakdown:</strong></p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Customer Caused: {incident.error_evidence.baseline.failure_breakdown?.customer_caused || 0}</li>
                    <li>Technical: {incident.error_evidence.baseline.failure_breakdown?.technical || 0}</li>
                    <li>Other: {incident.error_evidence.baseline.failure_breakdown?.other || 0}</li>
                  </ul>
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Current</h3>
                  <p><strong>Customer Error Rate:</strong> {(incident.error_evidence.current.customer_error_rate * 100).toFixed(1)}%</p>
                  <p><strong>Technical Error Rate:</strong> {(incident.error_evidence.current.technical_error_rate * 100).toFixed(1)}%</p>
                  <p><strong>Other Error Rate:</strong> {(incident.error_evidence.current.other_error_rate * 100).toFixed(1)}%</p>
                  <p><strong>Failure Rate:</strong> {(incident.error_evidence.current.failure_rate * 100).toFixed(1)}%</p>
                  <p><strong>Failure Breakdown:</strong></p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Customer Caused: {incident.error_evidence.current.failure_breakdown?.customer_caused || 0}</li>
                    <li>Technical: {incident.error_evidence.current.failure_breakdown?.technical || 0}</li>
                    <li>Other: {incident.error_evidence.current.failure_breakdown?.other || 0}</li>
                  </ul>
                </div>
              </div>
              <div className="mt-4">
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Changes</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p><strong>Customer Error Rate Change:</strong> {(incident.error_evidence.changes.customer_error_rate_change * 100).toFixed(1)} pp</p>
                    <p><strong>Technical Error Rate Change:</strong> {(incident.error_evidence.changes.technical_error_rate_change * 100).toFixed(1)} pp</p>
                    <p><strong>Other Error Rate Change:</strong> {(incident.error_evidence.changes.other_error_rate_change * 100).toFixed(1)} pp</p>
                    <p><strong>Customer Error Relative Change:</strong> {(incident.error_evidence.changes.customer_error_relative_change * 100).toFixed(1)}%</p>
                    <p><strong>Technical Error Relative Change:</strong> {(incident.error_evidence.changes.technical_error_relative_change * 100).toFixed(1)}%</p>
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Error Code Distribution</h3>
                    {incident.error_evidence.error_code_distribution ? (
                        <ul className="list-disc list-inside space-y-1">
                          {Object.entries(incident.error_evidence.error_code_distribution).map(([code, count]: [string, number]) => (
                            <li key={code}>
                              {code}: {count}
                            </li>
                          ))}
                        </ul>
                    ) : (
                        <p>No error code distribution data</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <p>No error evidence available</p>
          )}
        </div>

        {/* Localization Evidence */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Localization Evidence</h2>
          {incident.localization_evidence ? (
            <div className="space-y-3">
              <div>
                <p><strong>Affected Segment:</strong></p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Payment Method: {incident.localization_evidence.affected_segment.payment_method}</li>
                  <li>Bank: {incident.localization_evidence.affected_segment.bank}</li>
                  <li>Device: {incident.localization_evidence.affected_segment.device}</li>
                  <li>UPI App: {incident.localization_evidence.affected_segment.upi_app || 'N/A'}</li>
                  <li>Success Rate: {(incident.localization_evidence.affected_segment.success_rate * 100).toFixed(1)}%</li>
                  <li>Attempts: {incident.localization_evidence.affected_segment.attempts || 0}</li>
                </ul>
              </div>
              <p><strong>Localization Status:</strong> {incident.localization_evidence.localization_status || 'N/A'}</p>
              {incident.localization_evidence.control_analysis ? (
                <div className="mt-3">
                  <p><strong>Control Analysis:</strong></p>
                  <p>{incident.localization_evidence.control_analysis.message || 'N/A'}</p>
                  <p><strong>Control Segments:</strong></p>
                  <ul className="list-disc list-inside space-y-1">
                    {Object.entries(incident.localization_evidence.control_analysis.control_segments || {}).map(([segmentName, segmentData]: [string, any]) => (
                      <li key={segmentName} className="mb-2">
                        <strong>{segmentName}</strong>
                        <ul className="list-disc list-inside pl-4 space-y-1">
                          <li>Attempts: {segmentData.attempts || 0}</li>
                          <li>Successes: {segmentData.successes || 0}</li>
                          <li>Success Rate: {(segmentData.success_rate * 100).toFixed(1)}%</li>
                          <li>Status: {segmentData.status || 'N/A'}</li>
                        </ul>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : (
            <p>No localization evidence available</p>
          )}
        </div>

        {/* Impact Evidence */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Impact Evidence</h2>
          {incident.impact_evidence ? (
            <div className="space-y-3">
              <p><strong>Revenue at Risk:</strong> {(incident.impact_evidence.revenue_at_risk.paise || 0) / 100} INR</p>
              <p><strong>Timestamp:</strong> {new Date(incident.impact_evidence.revenue_at_risk.timestamp || 0).toLocaleString()}</p>
              <p><strong>Affected Users:</strong> {incident.impact_evidence.affected_users || 0}</p>
              <p><strong>Affected Transactions:</strong> {incident.impact_evidence.affected_transactions || 0}</p>
            </div>
          ) : (
            <p>No impact evidence available</p>
          )}
        </div>

        {/* Investigation Checklist */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Investigation Checklist</h2>
          {incident.investigation_checklist && incident.investigation_checklist.length > 0 ? (
            <ul className="space-y-2">
              {incident.investigation_checklist.map((check: any, index: number) => (
                <li key={index} className="p-3 bg-gray-50 rounded">
                  <div className="flex justify-between">
                    <span><strong>{check.check}:</strong> {check.result}</span>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${ check.result === 'PASS' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-700 border-red-200'}`}>{check.result}</span>
                  </div>
                  <p className="mt-1 text-sm text-gray-600">{check.details}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p>No investigation checklist available</p>
          )}
        </div>

        {/* Sample Payments */}
        <div className="card overflow-hidden border-slate-300 shadow-sm">
          <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Sample Payment Evidence</h2>
          {incident.sample_payments && incident.sample_payments.length > 0 ? (
            <div className="space-y-3">
              {incident.sample_payments.map((payment: any, index: number) => (
                <div key={index} className="p-3 bg-gray-50 rounded">
                  <p><strong>Payment ID:</strong> {payment.payment_id}</p>
                  <p><strong>Timestamp:</strong> {new Date(payment.timestamp).toLocaleString()}</p>
                  <p><strong>Amount:</strong> {payment.amount.paise / 100} INR ({payment.amount.currency})</p>
                  <p><strong>Status:</strong> {payment.status}</p>
                  <p><strong>Failure Reason:</strong> {payment.failure_reason}</p>
                </div>
              ))}
            </div>
          ) : (
            <p>No sample payment evidence available</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default SupportIncidentDetail;