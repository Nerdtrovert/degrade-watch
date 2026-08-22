import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { merchantAPI, MerchantIncident } from '../api/merchant';

const MerchantIncidentDetail: React.FC = () => {
  const { incidentId } = useParams<{ incidentId: string }>();
  const [incident, setIncident] = useState<MerchantIncident | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchIncident = async () => {
      try {
        setLoading(true);
        const response = await merchantAPI.getIncidentDetail(incidentId!);
        setIncident(response.data);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch incident detail:', err);
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
        <h1 className="text-2xl font-bold">Incident Detail</h1>
        <Link to="/merchant" className="text-sm text-blue-600 hover:text-blue-800">
          ← Back to Dashboard
        </Link>
      </div>

      {/* Incident Metadata */}
      <div className="bg-white p-4 rounded-lg shadow mb-4">
        <h2 className="text-xl font-bold mb-2">Incident Metadata</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <p><strong>Incident ID:</strong> {incident.incident_id}</p>
            <p><strong>Merchant ID:</strong> {incident.merchant_id}</p>
            <p><strong>Detection Time:</strong> {new Date(incident.detection_timestamp).toLocaleString()}</p>
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

      {/* Payment Impact */}
      <div className="bg-white p-4 rounded-lg shadow mb-4">
        <h2 className="text-xl font-bold mb-2">Payment Impact</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <p><strong>Baseline Success Rate:</strong> {(incident.success_rate_evidence?.baseline_success_rate || 0) * 100}%</p>
            <p><strong>Current Success Rate:</strong> {(incident.success_rate_evidence?.current_success_rate || 0) * 100}%</p>
            <p><strong>Change:</strong>
              <span className={`${((incident.success_rate_evidence?.current_success_rate || 0) - (incident.success_rate_evidence?.baseline_success_rate || 0)) >= 0 ? 'text-green-500' : 'text-red-500'} font-medium`}>
                {((incident.success_rate_evidence?.current_success_rate || 0) - (incident.success_rate_evidence?.baseline_success_rate || 0)) * 100}% points
              </span>
            </p>
          </div>
          <div>
            <p><strong>Baseline Technical Error Rate:</strong> {(incident.error_evidence?.baseline.technical_error_rate || 0) * 100}%</p>
            <p><strong>Current Technical Error Rate:</strong> {(incident.error_evidence?.current.technical_error_rate || 0) * 100}%</p>
            <p><strong>Technical Error Change:</strong>
              <span className={`${((incident.error_evidence?.current.technical_error_rate || 0) - (incident.error_evidence?.baseline.technical_error_rate || 0)) >= 0 ? 'text-red-500' : 'text-green-500'} font-medium`}>
                {((incident.error_evidence?.current.technical_error_rate || 0) - (incident.error_evidence?.baseline.technical_error_rate || 0)) * 100}% points
              </span>
            </p>
          </div>
          <div>
            <p><strong>Affected Users:</strong> {incident.impact_evidence?.affected_users || 0}</p>
            <p><strong>Affected Transactions:</strong> {incident.impact_evidence?.affected_transactions || 0}</p>
            <p><strong>Revenue at Risk:</strong> {(incident.impact_evidence?.revenue_at_risk.paise || 0) / 100} INR</p>
          </div>
        </div>
      </div>

      {/* Forensic Summary */}
      <div className="bg-white p-4 rounded-lg shadow mb-4">
        <h2 className="text-xl font-bold mb-2">Forensic Summary</h2>
        {/* This would normally come from the LLM report, but for now we'll use a placeholder or from the investigation checklist */}
        <div className="space-y-3">
          <div className="bg-gray-50 p-3 rounded">
            <p><strong>Investigation Checklist:</strong></p>
            <ul className="list-disc list-inse mt-1 space-y-1">
              {(incident.investigation_checklist || []).map((check: any, index: number) => (
                <li key={index}>
                  <strong>{check.check}:</strong> {check.result} - {check.details}
                </li>
              ))}
            </ul>
          </div>
          {(incident.sample_payments || []).length > 0 && (
            <div className="mt-4">
              <h3 className="text-lg font-bold mb-2">Sample Failed Payments</h3>
              <div className="space-y-2">
                {(incident.sample_payments || []).map((payment: any, index: number) => (
                  <div key={index} className="p-2 bg-red-50 rounded">
                    <p><strong>Payment ID:</strong> {payment.payment_id}</p>
                    <p><strong>Timestamp:</strong> {new Date(payment.timestamp).toLocaleString()}</p>
                    <p><strong>Amount:</strong> {payment.amount.paise / 100} INR</p>
                    <p><strong>Status:</strong> {payment.status}</p>
                    <p><strong>Failure Reason:</strong> {payment.failure_reason}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recovery Information */}
      <div className="bg-white p-4 rounded-lg shadow mb-4">
        <h2 className="text-xl font-bold mb-2">Recovery Status</h2>
        {/* In a real app, we would fetch the recovery status from the recovery engine or approvals */}
        {/* For now, we'll show a placeholder based on the incident */}
        <div className="space-y-3">
          <p><strong>Recovery Action:</strong> PAYMENT_LINK (proposed)</p>
          <p><strong>Recovery Amount:</strong> 150 INR (example)</p>
          <p><strong>Status:</strong>
            <span className="px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
              PENDING_APPROVAL
            </span>
          </p>
          <p className="text-sm text-gray-500">
            Note: This is a placeholder. In the full system, this would show the actual recovery status from the backend.
          </p>
        </div>
      </div>
    </div>
  );
};

export default MerchantIncidentDetail;